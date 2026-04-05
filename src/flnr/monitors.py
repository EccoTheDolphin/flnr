"""Interfaces for output and process monitors."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from enum import Enum


class ProcessTerminationReason(Enum):
    """Identify reason for process termination."""

    NORMAL = "finished"
    TIMEOUT = "terminate"
    KILL = "kill"

    def __str__(self) -> str:
        """Provide string representation of ProcessTerminationReason."""
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

        data comes with an associated timestamp that identifies the moment
        when this was read from the stream.
        """


class ProcessMonitor(ABC):
    """Interface that process monitors must implement.

    Process monitors represent periodic user-supplied callbacks.
    Their goal is to monitor the execution environment while the
    subprocess is running.

    If a process monitor raises an exception, that exception is saved and
    the monitor is disabled. Execution continues as if that monitor did
    not exist. The error is reported only after the monitored process
    finishes execution.
    """

    def __init__(self, *, period: float) -> None:
        """Define how often the monitor is called."""
        self.period = period
        if period <= 0:
            err_msg = "ProcessMonitor period must be > 0"
            raise ValueError(err_msg)

    @abstractmethod
    def on_start(self, pid: int, cmd: Sequence[str]) -> None:
        """Notification when subprocess corresponding to command is created."""

    @abstractmethod
    def observe(self, pid: int) -> None:
        """Periodic notification while the subprocess is being monitored.

        At the time ``observe(pid)`` is called:
        - the PID still refers to the original process,
        - the PID has not been reused by the OS,
        - the process may already have exited but has not yet been reaped.

        Callbacks must not assume that the process is still running, only that
        the PID is still valid and still refers to the original process.
        """

    @abstractmethod
    def on_end(
        self, return_code: int, stop_info: ProcessTerminationReason
    ) -> None:
        """Best-effort notification callback that is called when process exits.

        It is NOT guaranteed to be called if the monitor fails during execution.
        It must not be relied upon for cleanup or critical logic.
        """
