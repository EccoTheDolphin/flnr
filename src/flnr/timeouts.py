"""Command execution timeouts."""

import math
from dataclasses import dataclass


def _check_optional_timeout_value(
    value: float | None,
    *,
    err_msg: str,
) -> None:
    if value is None:
        return

    _check_timeout_value(value, err_msg=err_msg)


def _check_timeout_value(
    value: float,
    *,
    err_msg: str,
) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(err_msg)


@dataclass(frozen=True)
class ExecutionTimeouts:
    """Duration of various time-sensitive aspects of command execution.

    All timeouts are in seconds (fractional values allowed).

    The ``kill`` parameter may be left unspecified: if ``None`` (the default),
    the ``terminate`` value is used for the post-kill wait.

    **Teardown Procedure**

    The library follows a staged escalation when the process must be stopped.
    The exact sequence depends on the supervisory decision that **flnr**
    reaches during execution.

    *If the ``run`` timeout expires:*

    1. **Terminate stage**: The process is asked to terminate and given
       ``terminate`` seconds to exit on its own. Monitors continue to run
       during this phase so final logs and state can be captured.
    2. **Forced kill**: If the process does not exit within the ``terminate``
       grace period, it is forcibly killed.

    *If flnr encounters an unrecoverable internal failure while reading
    process output:*

    - The process is forcibly terminated immediately, without attempting
      the terminate stage.

    *After the forced kill (in either case):*

    3. Monitors are **paused** and the library waits up to the ``kill``
       timeout for confirmation that the process has exited.
    4. If no such confirmation arrives, ``ProcessKillFailedError`` is raised.
    5. Otherwise, monitors are **resumed** to allow any remaining output to be
       drained (subject to the ``output_drain`` timeout).
    """

    run: float | None = None
    terminate: float = 5.0
    output_drain: float = 1.0
    kill: float | None = None

    def __post_init__(self) -> None:
        """Validate parameter values."""
        _check_optional_timeout_value(
            self.run,
            err_msg="run timeout must be either None or > 0",
        )
        _check_timeout_value(
            self.terminate,
            err_msg="terminate timeout must be > 0",
        )
        _check_timeout_value(
            self.output_drain,
            err_msg="output_drain timeout must be > 0",
        )
        _check_optional_timeout_value(
            self.kill,
            err_msg="kill timeout must be either None or > 0",
        )
