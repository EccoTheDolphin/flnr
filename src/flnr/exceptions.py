"""Exceptions defined by the library."""

import traceback
from collections.abc import Sequence


class FlnrExceptionBaseError(Exception):
    """Base class for all exceptions raised by flnr."""


class CommandFailedError(FlnrExceptionBaseError):
    """Raised if command fails when user asked to ensure that it succeeds."""


class MonitorFailedError(FlnrExceptionBaseError):
    """Raised when one or more monitors (output or process) fail.

    This exception aggregates all monitor failures and includes the process
    return code. Users are expected to inspect the contained exceptions.
    """

    def __init__(
        self, returncode: int, exc_list: Sequence[BaseException], message: str
    ) -> None:
        """Provide information about monitoring error and process status."""
        super().__init__(message)
        self.proc_returncode = returncode
        self.monitor_exceptions = exc_list

    def __str__(self) -> str:
        """Serialize information about encountered abnormal situations."""
        err_msgs: list[str] = []
        err_msgs.append(f"{self.args[0]}")
        err_msgs.append(f"process returncode: {self.proc_returncode}")
        for i, cause in enumerate(self.monitor_exceptions):
            tr = "  ".join(
                traceback.format_exception(
                    type(cause), cause, cause.__traceback__
                )
            )
            err_msgs.append(f"{i}: {cause}; {tr}")
        return "\n".join(err_msgs)
