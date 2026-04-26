import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class _StdStreamPlan:
    stdout: int
    stderr: int


def _resolve_std_stream_plan(
    *,
    merge_std_streams: bool | None,
    has_stdout_monitors: bool,
    has_stderr_monitors: bool,
) -> _StdStreamPlan:
    if merge_std_streams is True and has_stderr_monitors:
        error_msg = "stderr monitors provided, while stdout/stderr merged"
        raise ValueError(error_msg)

    should_merge = (
        merge_std_streams
        if merge_std_streams is not None
        else has_stdout_monitors and not has_stderr_monitors
    )

    stdout = (
        asyncio.subprocess.PIPE
        if has_stdout_monitors
        else asyncio.subprocess.DEVNULL
    )

    if should_merge:
        stderr = asyncio.subprocess.STDOUT
    else:
        stderr = (
            asyncio.subprocess.PIPE
            if has_stderr_monitors
            else asyncio.subprocess.DEVNULL
        )

    return _StdStreamPlan(stdout=stdout, stderr=stderr)
