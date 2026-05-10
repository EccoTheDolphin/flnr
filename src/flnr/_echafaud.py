"""internal lifecycle/termination machinery."""

import asyncio
from dataclasses import dataclass

from ._process_utils import (
    _effective_death_confirmation_timeout,
    _wait_for_process_exit,
)
from ._task_ledger import _TaskLedger
from .fate import (
    ProcessFate,
    ProcessTerminationDecision,
    ProcessTerminationMethod,
)
from .timeouts import ExecutionTimeouts


def _attempt_to_kill(process: asyncio.subprocess.Process) -> None:
    if process.returncode is None:
        process.kill()


@dataclass(frozen=True, slots=True)
class _ProcessLifecycleScope:
    fatal_reader_error: asyncio.Event
    monitor_callbacks_allowed: asyncio.Event
    ext_termination_request: asyncio.Event
    timeouts: ExecutionTimeouts


async def _resolve_process_fate(
    process: asyncio.subprocess.Process, scope: _ProcessLifecycleScope
) -> ProcessFate:

    task_ledger = _TaskLedger()
    try:
        # note for python 3.11 transition: tasks should be created via task
        # group
        process_exit_task = task_ledger.create_task(
            _wait_for_process_exit(process),
            name="flnr.echafaud.process_exit",
        )
        fatal_reader_error_task = task_ledger.create_task(
            scope.fatal_reader_error.wait(),
            name="flnr.echafaud.fatal_reader_error",
        )
        ext_termination_request_task = task_ledger.create_task(
            scope.ext_termination_request.wait(),
            name="flnr.echafaud.ext_termination_request",
        )

        done_tasks, _ = await asyncio.wait(
            {
                process_exit_task,
                fatal_reader_error_task,
                ext_termination_request_task,
            },
            timeout=scope.timeouts.run,
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Resolve the supervisory decision in priority order:
        # 1. a fatal reader failure forces immediate termination
        # 2. a run-timeout breach forces termination
        # 3. otherwise the process completed without intervention
        if fatal_reader_error_task in done_tasks:
            termination_decision = ProcessTerminationDecision.INTERNAL_FAILURE
            termination_method = ProcessTerminationMethod.KILL
            # just kill
            _attempt_to_kill(process)
        elif process_exit_task not in done_tasks:
            if ext_termination_request_task in done_tasks:
                termination_decision = (
                    ProcessTerminationDecision.EXTERNAL_REQUEST
                )
            else:
                termination_decision = ProcessTerminationDecision.TIMEOUT
            termination_method = ProcessTerminationMethod.TERMINATE
            # terminate, escalate to kill
            process.terminate()
            try:
                await asyncio.wait_for(
                    asyncio.shield(process_exit_task),
                    timeout=scope.timeouts.terminate,
                )
            except asyncio.exceptions.TimeoutError:
                termination_method = ProcessTerminationMethod.KILL
                _attempt_to_kill(process)
        else:
            termination_decision = ProcessTerminationDecision.NO_INTERVENTION
            termination_method = ProcessTerminationMethod.NONE
            # process already finished, nothing to do here

        # After the decision has been resolved, pause monitor callbacks and
        # wait for final exit observation. If exit is already known, this is
        # effectively a no-op.
        assert scope.monitor_callbacks_allowed.is_set()
        scope.monitor_callbacks_allowed.clear()
        kill_timeout = _effective_death_confirmation_timeout(
            scope.timeouts.terminate, scope.timeouts.kill
        )
        try:
            await asyncio.wait_for(
                asyncio.shield(process_exit_task), timeout=kill_timeout
            )
        except asyncio.exceptions.TimeoutError:
            return ProcessFate(
                termination_decision=termination_decision,
                termination_method=termination_method,
                returncode=None,
            )
        finally:
            assert not scope.monitor_callbacks_allowed.is_set()
            scope.monitor_callbacks_allowed.set()
    finally:
        await task_ledger.cancel_all()

    return ProcessFate(
        termination_decision=termination_decision,
        termination_method=termination_method,
        returncode=process.returncode,
    )
