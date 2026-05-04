import asyncio
import io

import flnr
from tests._support.probes import OutputMonitorProbe
from tests._support.utils import PythonCmdBuilder

# Wires and chains.
# These names are intentionally stable enough to make asyncio task dumps useful
# during lifecycle debugging.
FLNR_TASK_NAMES = [
    "echafaud.ext_termination_request",
    "echafaud.fatal_reader_error",
    "echafaud.process_exit",
    "env_monitor.0",
    "process_fate",
    "reader.stderr",
    "reader.stderr.drain_controller",
    "reader.stderr.relay",
    "reader.stdout",
    "reader.stdout.drain_controller",
    "reader.stdout.relay",
]


class _InternalTaskObserver(flnr.EnvironmentMonitor):
    def __init__(self, *, period: float) -> None:
        super().__init__(period=period)
        self.task_names: list[str] | None = None
        self.term_trigger = flnr.HostTerminationRequest()

    def observe(self, _: int) -> None:
        self.task_names = sorted(
            [
                task.get_name()
                for task in asyncio.all_tasks()
                if task.get_name() in FLNR_TASK_NAMES
            ]
        )
        if len(self.task_names) == len(FLNR_TASK_NAMES):
            self.term_trigger.trigger()


def test_internal_task_debug_names(py_exec: PythonCmdBuilder) -> None:
    observer = _InternalTaskObserver(period=0.1)
    try:
        flnr.run_ex(
            # expectation for the job to be terminated much sooner (due to
            # observer triggering the host_termination)
            py_exec("py_sleep.py", "100"),
            environment_monitors=[observer],
            stdout_monitors=[OutputMonitorProbe(sink=io.BytesIO())],
            stderr_monitors=[OutputMonitorProbe(sink=io.BytesIO())],
            host_termination=observer.term_trigger,
            check=False,
        )
        assert observer.task_names is not None
        assert all(
            observer.task_names.count(item) == 1 for item in FLNR_TASK_NAMES
        )
    finally:
        observer.term_trigger.close()
