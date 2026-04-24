"""Exceptions defined by the library."""

from collections.abc import Sequence

from ._monitor_failure_rendering import (
    format_internal_exceptions,
    format_monitor_failures,
)
from .fate import ProcessFate
from .monitor_failure import MonitorFailure


class ProcessExecutionError(Exception):
    """Base exception for failures raised during supervised process execution.

    These exceptions carry the resolved ``ProcessFate`` together with any
    monitor exceptions collected during execution. Users are expected to
    inspect both pieces of information.
    """

    def __init__(
        self,
        *,
        fate: ProcessFate,
        monitor_failures: Sequence[MonitorFailure],
        internal_exceptions: Sequence[BaseException] = (),
        message: str,
    ) -> None:
        """Store the resolved ``ProcessFate`` and recorded failures.

        This object contains the execution result (``ProcessFate``), recorded
        monitor failures, and any captured internal failures.

        Internal failures are expected to be absent during normal operation.
        They are mainly present in cases that result in
        ``SupervisionFailedError`` or ``ProcessKillFailedError``.
        """
        super().__init__(message)
        self.fate = fate
        self.monitor_failures = tuple(monitor_failures)
        self.internal_exceptions = tuple(internal_exceptions)

    def __str__(self) -> str:
        """Serialize information about encountered abnormal situations."""
        err_msgs: list[str] = []
        err_msgs.append(f"{self.args[0]}")
        err_msgs.append(f"fate: {self.fate}")

        monitor_failures = format_monitor_failures(tuple(self.monitor_failures))
        if monitor_failures:
            err_msgs.append(monitor_failures)

        internal_text = format_internal_exceptions(
            tuple(self.internal_exceptions)
        )
        if internal_text:
            err_msgs.append(internal_text)

        return "\n".join(err_msgs)


class CommandFailedError(ProcessExecutionError):
    """Raised when ``check=True`` and the observed return code is non-zero.

    This also covers subprocesses terminated by **flnr** after a run timeout or
    host-requested termination if the resulting return code is non-zero.
    Inspect the ``fate`` field to distinguish the cause and final outcome.
    """


class MonitorFailedError(ProcessExecutionError):
    """Raised when one or more monitor callbacks fail during execution."""


class SupervisionFailedError(ProcessExecutionError):
    """Raised when flnr cannot continue supervising the process correctly.

    In this situation flnr attempts to force-stop the process and report any
    failures it managed to record.

    Reported output, process state, and collected diagnostics may be incomplete
    or unreliable.

    This exception may indicate a serious failure in the execution environment
    itself, as opposed to an ordinary failure of the supervised process
    """


class ProcessKillFailedError(ProcessExecutionError):
    """Raised when **flnr** cannot confirm process exit after intervention.

    This means **flnr** completed its supervisory actions but could not observe
    a final process exit state within the allowed time window.

    In such cases ``fate.returncode`` is expected to be ``None``.

    Like tears in the rain, this moment will be lost in time.
    Your process, however, will not.
    """
