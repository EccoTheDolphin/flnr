"""Flnr is a library for non-invasive monitoring of subprocesses."""

import asyncio
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ._observatory import _Observatory
from .exceptions import CommandFailedError
from .monitors import OutputMonitor, ProcessMonitor, ProcessTerminationReason


@dataclass(frozen=True)
class ExecutionTimeouts:
    """Duration of various time-sensitive aspects of command execution.

    All units are in fraction of a second.
    """

    run: float | None = None
    terminate: float = 5.0
    output_drain: float = 1.0

    def __post_init__(self) -> None:
        """Validate parameter values."""
        if self.run is not None and self.run <= 0:
            err_msg = "run timeout must be either None or > 0"
            raise ValueError(err_msg)
        if self.terminate <= 0:
            err_msg = "terminate timeout must be > 0"
            raise ValueError(err_msg)
        if self.output_drain <= 0:
            err_msg = "output_drain timeout must be > 0"
            raise ValueError(err_msg)


async def _run_shell_ex_async(
    cmd: Sequence[str],
    *,
    env: Mapping[str, str],
    cwd: Path | None = None,
    merge_std_streams: bool = True,
    timeouts: ExecutionTimeouts | None = None,
    stdout_observers: Sequence[OutputMonitor] | None = None,
    stderr_observers: Sequence[OutputMonitor] | None = None,
    process_monitors: Sequence[ProcessMonitor] | None = None,
    check: bool = True,
) -> int:
    timeouts = timeouts or ExecutionTimeouts()
    if merge_std_streams:
        stderr = asyncio.subprocess.STDOUT
        if stderr_observers is not None and len(stderr_observers) > 0:
            err_msg = "stderr observers provided, while stdout/stderr merged"
            raise ValueError(err_msg)
    else:
        stderr = asyncio.subprocess.PIPE

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=stderr,
        cwd=cwd,
        env=env,
    )

    assert process.stdout is not None
    observatory = _Observatory(
        proc=process,
        cmd=cmd,
        stdout_observers=(stdout_observers or []),
        stderr_observers=(stderr_observers or []),
        process_monitors=(process_monitors or []),
        output_drain_timeout=timeouts.output_drain,
    )

    try:
        await asyncio.wait_for(process.wait(), timeout=timeouts.run)
        termination_reason = ProcessTerminationReason.NORMAL
    except asyncio.exceptions.TimeoutError:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=timeouts.terminate)
            termination_reason = ProcessTerminationReason.TIMEOUT
        except asyncio.exceptions.TimeoutError:
            process.kill()
            await process.wait()
            termination_reason = ProcessTerminationReason.KILL

    assert process.returncode is not None
    await observatory.teardown(termination_reason)

    if check and process.returncode != 0:
        msg = f"unexpected return code {process.returncode}"
        raise CommandFailedError(msg)
    return process.returncode


def run_shell_ex(
    cmd: Sequence[str | Path],
    *,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    merge_std_streams: bool = True,
    timeouts: ExecutionTimeouts | None = None,
    stdout_observers: Sequence[OutputMonitor] | None = None,
    stderr_observers: Sequence[OutputMonitor] | None = None,
    process_monitors: Sequence[ProcessMonitor] | None = None,
    check: bool = True,
) -> int:
    """Run a subprocess while synchronously observing its output and lifecycle.

    This function blocks the caller until the subprocess exits or is terminated.
    It must not be called from an existing async context.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        err_msg = "run_shell_ex() cannot be called from an async context"
        raise RuntimeError(err_msg)
    if env is None:
        env = os.environ.copy()
    return asyncio.run(
        _run_shell_ex_async(
            [str(item) for item in cmd],
            env=env,
            cwd=cwd,
            merge_std_streams=merge_std_streams,
            timeouts=timeouts,
            stdout_observers=stdout_observers,
            stderr_observers=stderr_observers,
            process_monitors=process_monitors,
            check=check,
        )
    )
