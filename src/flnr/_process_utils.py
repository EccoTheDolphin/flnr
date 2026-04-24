import asyncio

from ._async_utils import _cancel_tasks

# Period in seconds for fallback polling of the process return code.
_PROCESS_EXIT_CODE_POLL_PERIOD = 0.05


# As of Python 3.14, CPython documentation suggests that
# asyncio.subprocess.Process.wait() is the standard interface for observing
# process exit. However, implementation details can prevent the returncode
# from being updated immediately upon exit (see:
# https://github.com/python/cpython/issues/119710). To minimize latency while
# ensuring state visibility, we supplement .wait() with periodic polling.
async def _wait_for_process_exit(process: asyncio.subprocess.Process) -> None:
    wait_task = asyncio.create_task(process.wait())
    try:
        while process.returncode is None:
            await asyncio.wait(
                {wait_task}, timeout=_PROCESS_EXIT_CODE_POLL_PERIOD
            )
            if wait_task.done():
                # if for whatever reason the task results in exception,
                # propagate the exception
                await wait_task
    finally:
        await _cancel_tasks(wait_task)


# Ensures the event loop has a sufficient window to observe process state
# changes, even if a user specifies an unreasonably low termination timeout.
def _effective_death_confirmation_timeout(
    requested_terminate_timeout: float, requested_kill_timeout: None | float
) -> float:
    # We use a floor based on the polling period to ensure the state machine
    # has time to cycle before we escalate from SIGTERM to SIGKILL.
    kill_timeout = requested_kill_timeout or requested_terminate_timeout
    return max(kill_timeout, _PROCESS_EXIT_CODE_POLL_PERIOD * 4)
