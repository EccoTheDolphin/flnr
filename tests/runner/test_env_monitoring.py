import io
import re
import signal
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

import flnr
from tests._support import moirai
from tests._support.utils import PythonCmdBuilder, return_code_for_sigterm


class _EnvMonitorTestImplementation(flnr.EnvironmentMonitor):
    def __init__(self, *, sink: io.IOBase, period: float) -> None:
        super().__init__(period=period)
        self.sink = sink
        self.counter = 0

    def on_start(self, pid: int, cmd: Sequence[str]) -> None:
        print(f"pid = {pid}", file=self.sink)
        for s in cmd:
            print(s, file=self.sink)

    def observe(self, pid: int) -> None:
        self.counter = self.counter + 1
        msg = _EnvMonitorTestImplementation.called_pattern(pid, self.counter)
        print(msg, file=self.sink)

    def on_end(self, fate: flnr.ProcessFate) -> None:
        print(f"stopped. {fate}", file=self.sink)

    @staticmethod
    def pid_from_log_record(record: str) -> int:
        match = re.match(r"pid = (\d+)", record)
        if match:
            return int(match.group(1))
        err_msg = f"pid pattern matching failed for {record}"
        raise ValueError(err_msg)

    @staticmethod
    def called_pattern(pid: int, counter: int) -> str:
        return f"monitor for {pid} called {counter} times"


def test_incorrect_period() -> None:
    for incorrect_value in [0, -1]:
        with pytest.raises(
            ValueError,
            match=r"EnvironmentMonitor period must be > 0$",
        ):
            _EnvMonitorTestImplementation(
                sink=io.StringIO(), period=incorrect_value
            )


def test_success(py_exec: PythonCmdBuilder, test_resources: Path) -> None:
    string_output = io.StringIO()
    # NOTE: test can fail under VERY heavy load
    flnr.run_ex(
        py_exec("py_sleep.py", "5"),
        environment_monitors=[
            _EnvMonitorTestImplementation(sink=string_output, period=1.0)
        ],
    )

    outlines = string_output.getvalue().splitlines()
    assert len(outlines) > 0
    pid = _EnvMonitorTestImplementation.pid_from_log_record(outlines[0])
    assert outlines[1] == sys.executable
    assert outlines[2] == str(test_resources / "exec" / "py_sleep.py")
    assert outlines[3] == "5"
    for i in range(1, 5):
        msg = _EnvMonitorTestImplementation.called_pattern(pid, i)
        assert msg == outlines[i + 3]
    expected_fate = moirai.fate_no_intervention(0)
    assert outlines[-1] == f"stopped. {expected_fate}"


# Since the underlying process ends quickly, the expectation is that the first
# callback may not be called since the process is finished. We don't have
# relevant asserts because such test would be unreliable and subject to
# sporadic failures.
def test_quick_process(py_exec: PythonCmdBuilder) -> None:
    string_output = io.StringIO()
    flnr.run_ex(
        py_exec("py_true.py"),
        environment_monitors=[
            _EnvMonitorTestImplementation(sink=string_output, period=1.0)
        ],
    )
    outlines = string_output.getvalue().splitlines()
    assert len(outlines) > 0
    assert outlines[0].startswith("pid = ")
    expected_fate = moirai.fate_no_intervention(0)
    assert outlines[-1] == f"stopped. {expected_fate}"


def test_timeout_terminate(
    py_exec: PythonCmdBuilder, test_resources: Path
) -> None:
    string_output = io.StringIO()
    with pytest.raises(flnr.CommandFailedError) as excinfo:
        flnr.run_ex(
            py_exec("cat_dev_random.py"),
            timeouts=flnr.ExecutionTimeouts(run=5.0),
            environment_monitors=[
                _EnvMonitorTestImplementation(sink=string_output, period=1.0)
            ],
        )

    expected_fate = moirai.fate_timeout_terminate(return_code_for_sigterm())
    assert excinfo.value.fate == expected_fate

    outlines = string_output.getvalue().splitlines()
    assert len(outlines) > 0
    pid = _EnvMonitorTestImplementation.pid_from_log_record(outlines[0])
    assert outlines[1] == sys.executable
    assert outlines[2] == str(test_resources / "exec" / "cat_dev_random.py")
    # NOTE: this test can fail under heavy load
    for i in range(1, 5):
        msg = _EnvMonitorTestImplementation.called_pattern(pid, i)
        assert msg == outlines[i + 2]

    assert outlines[-1] == f"stopped. {expected_fate}"


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="sigterm ignore is not supported on windows",
)
def test_timeout_kill(py_exec: PythonCmdBuilder) -> None:
    string_output = io.StringIO()
    cmd_line = py_exec("sigterm_ignore.py")
    with pytest.raises(flnr.CommandFailedError) as excinfo:
        flnr.run_ex(
            cmd_line,
            timeouts=flnr.ExecutionTimeouts(run=5.0),
            environment_monitors=[
                _EnvMonitorTestImplementation(sink=string_output, period=1.0)
            ],
        )

    expected_fate = moirai.fate_timeout_kill(-signal.SIGKILL)
    assert excinfo.value.fate == expected_fate

    outlines = string_output.getvalue().splitlines()
    assert len(outlines) > 0
    pid = _EnvMonitorTestImplementation.pid_from_log_record(outlines[0])
    for i, line in enumerate(cmd_line):
        assert outlines[1 + i] == line
    for i in range(1, 5):
        msg = _EnvMonitorTestImplementation.called_pattern(pid, i)
        assert msg == outlines[i + len(cmd_line)]
    assert outlines[-1] == f"stopped. {expected_fate}"
