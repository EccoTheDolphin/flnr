"""Interfaces for output and environment monitors."""

import math
from abc import ABC, abstractmethod
from collections.abc import Sequence
from enum import Enum

from .fate import ProcessFate


class OutputMonitorDisableReason(Enum):
    """Identify the reason for output monitor disable event.

    **flnr** manages the lifecycle of each output monitor. A monitor starts
    active and may be disabled under certain circumstances. Once disabled,
    the transition is final. When disabling a monitor, **flnr** attempts to
    notify it by providing one of the reasons below.

    Attributes:
        EOF: The output stream associated with this monitor has ended. No
            further data will be available. This is the expected reason under
            normal operation.
        ERROR: The monitor raised an unhandled exception when **flnr**
            attempted to interact with it. Monitors should not interrupt
            execution flow; if they throw, they are disabled.
        DRAIN_TIMEOUT: The process finished execution, but **flnr** could not
            drain all remaining data from the output stream within the
            configured ``output_drain`` timeout. This may happen, for
            instance, when a subprocess spawns children that inherit and hold
            open its stdout or stderr descriptors.

    """

    EOF = "eof"
    ERROR = "error"
    DRAIN_TIMEOUT = "drain_timeout"

    def __str__(self) -> str:
        """Provide string representation of ``OutputMonitorDisableReason``."""
        return self.value


class OutputMonitor(ABC):  # pylint: disable=too-few-public-methods
    """Interface that subprocess output monitors must implement.

    Output monitors are treated as disposable, self-contained objects.
    Their purpose is to forward subprocess output to some sink
    (typically a file on disk), optionally applying simple transformations
    such as transcoding or timestamping.

    If an output monitor raises an exception, that exception is saved and
    the monitor is disabled. The error is reported only after the monitored
    process finishes execution.
    """

    @abstractmethod
    def process(self, data: bytes, ts: float) -> None:
        """Process data from subprocess output stream.

        The timestamp identifies when **flnr** read this chunk from the
        stream.
        """

    def on_disable(  # noqa: B027
        self,
        reason: OutputMonitorDisableReason,
        ts: float,
    ) -> None:
        """Notification callback called when output monitor is disabled.

        After this call, `process()` will never be invoked again.
        Override to flush any buffered partial data or write a truncation
        marker.
        Implement as `pass` if you don't need this notification.
        """


def _check_period_value(value: float, *, err_msg: str) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(err_msg)


class EnvironmentMonitor(ABC):
    """Interface for execution-environment monitors.

    Environment monitors are periodic user-supplied callbacks whose purpose is
    to observe the execution environment while the subprocess remains the
    current subject of observation.

    These monitors are not process-control hooks. They are observational
    callbacks. The provided ``pid`` is a convenience handle that helps narrow
    the observation surface when needed.

    If an environment monitor raises an exception, that exception is recorded
    and the monitor is disabled. Execution continues as if that monitor did
    not exist. The error is reported only after monitored execution finishes.
    """

    def __init__(self, *, period: float) -> None:
        """Set the invocation period, in seconds."""
        _check_period_value(
            period, err_msg="EnvironmentMonitor period must be > 0"
        )
        self.period = period

    def on_start(self, pid: int, cmd: Sequence[str]) -> None:  # noqa: B027
        """Notifies when process corresponding to the command is created.

        .. note::
           ``pid`` is provided for logging/notification purposes only. By the
           time ``on_start`` is called, the underlying process may already
           have exited.

        :rtype: :py:obj:`None`
        """

    @abstractmethod
    def observe(self, pid: int) -> None:
        """Periodic callback while the subprocess is being monitored.

        Callbacks must not assume that the process is still running. The only
        guarantee is that **flnr** still treats this process as the current
        subject of monitoring.
        """

    def on_end(  # noqa: B027
        self, process_fate: ProcessFate
    ) -> None:
        """Notifies when environment observation ends.

        The callback receives the final ``ProcessFate`` resolved by **flnr**.

        Usually this happens after process exit has been observed, but
        ``process_fate.returncode`` may be ``None`` if **flnr** could not
        confirm process exit within the allowed observation window.

        This callback is not guaranteed to run if the monitor itself fails
        earlier. It must not be relied upon for cleanup or critical logic.
        """
