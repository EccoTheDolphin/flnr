import time

import pytest

import flnr
from tests.lib.utils import PythonCmdBuilder


class _SleepyObserverImpl(flnr.OutputMonitor):
    def __init__(self, *, sleep_duration: float) -> None:
        self.sleep_duration = sleep_duration

    def process(self, _: bytes, __: float) -> None:
        time.sleep(self.sleep_duration)


@pytest.mark.slow
@pytest.mark.parametrize("sleep_duration", [0.5, 1.0])
def test_sleepy_observer_1mb_sleepy(
    py_exec: PythonCmdBuilder, sleep_duration: float
) -> None:
    flnr.run_shell_ex(
        py_exec("drain_stressor.py", str(1024 * 1024), "num", "flush"),
        stdout_observers=[_SleepyObserverImpl(sleep_duration=sleep_duration)],
    )
