import io
import os
import time
from collections.abc import Sequence
from pathlib import Path

import pytest

import flnr
from tests._support import moirai
from tests._support.probes import OutputMonitorProbe
from tests._support.utils import (
    PythonCmdBuilder,
    return_code_for_sigterm,
)


class _OutputMonitorErrorForTestError(Exception):
    def __init__(self, data: bytes, err_msg: str) -> None:
        super().__init__(err_msg)
        self.data = data


class _EnvMonitorErrorForTestError(Exception):
    pass


class _RogueOutputMonitor(flnr.OutputMonitor):
    def __init__(self, *, error_at_line: int) -> None:
        self.error_at_line = error_at_line
        self.lines_count = 0
        self.ils = flnr.IncrementalLineSplitter()
        self.disable_reason: None | flnr.OutputMonitorDisableReason = None
        self.error_at: float | None = None
        self.disabled_at: float = 0

    def process(self, data: bytes, _: float) -> None:
        for line in self.ils.feed(data):
            if self.lines_count >= self.error_at_line:
                err_msg = "output monitor collapse"
                self.error_at = time.monotonic()
                raise _OutputMonitorErrorForTestError(line, err_msg)
            self.lines_count += 1

    def on_disable(
        self, reason: flnr.OutputMonitorDisableReason, ts: float
    ) -> None:
        self.disable_reason = reason
        self.disabled_at = ts


class _RogueOutputMonitorOnDisable(flnr.OutputMonitor):
    def __init__(self) -> None:
        self.reason: flnr.OutputMonitorDisableReason | None = None
        self.data_ts: float = 0
        self.disable_ts: float = -1

    def process(self, _: bytes, ts: float) -> None:
        self.data_ts = ts

    def on_disable(
        self, reason: flnr.OutputMonitorDisableReason, ts: float
    ) -> None:
        self.reason = reason
        self.disable_ts = ts
        err_data = b""
        err_msg = f"{reason}"
        raise _OutputMonitorErrorForTestError(err_data, err_msg)


class _EnvMonitorRogueOnStart(flnr.EnvironmentMonitor):
    def __init__(self, *, sink: io.IOBase, period: float) -> None:
        super().__init__(period=period)
        self.sink = sink
        self.sink.write("init called\n")

    def on_start(self, pid: int, cmd: Sequence[str]) -> None:
        self.sink.write(f"on start called, cmd = {cmd}, pid = {pid}\n")
        err_msg = "on start error"
        raise _EnvMonitorErrorForTestError(err_msg)

    def observe(self, pid: int) -> None:
        self.sink.write(f"observe called, pid = {pid}\n")

    def on_end(self, fate: flnr.ProcessFate) -> None:
        self.sink.write(f"on end called, {fate}\n")


class _EnvMonitorRogueObserve(flnr.EnvironmentMonitor):
    def __init__(self, *, sink: io.IOBase, period: float) -> None:
        super().__init__(period=period)
        self.sink = sink
        self.sink.write("init called\n")

    def on_start(self, _: int, __: Sequence[str]) -> None:
        self.sink.write("on start called\n")

    def observe(self, _: int) -> None:
        err_msg = "on observe error"
        raise _EnvMonitorErrorForTestError(err_msg)

    def on_end(self, _: flnr.ProcessFate) -> None:
        self.sink.write("on end called")


class _EnvMonitorRogueOnEnd(flnr.EnvironmentMonitor):
    def __init__(self, *, sink: io.IOBase, period: float) -> None:
        super().__init__(period=period)
        self.sink = sink
        self.sink.write("init called\n")

    def on_start(self, _: int, __: Sequence[str]) -> None:
        self.sink.write("on start called\n")

    def observe(self, _: int) -> None:
        self.sink.write("observe called\n")

    def on_end(self, _: flnr.ProcessFate) -> None:
        err_msg = "on end error"
        raise _EnvMonitorErrorForTestError(err_msg)


def test_output_monitor_rogue_on_data(
    test_resources: Path, py_exec: PythonCmdBuilder
) -> None:
    bin_output = io.BytesIO()
    input_file = test_resources / "data" / "default.txt"
    with pytest.raises(
        flnr.MonitorFailedError, match="2 monitor failure\\(s\\) recorded"
    ) as excinfo:
        flnr.run_ex(
            py_exec("ln_print.py", input_file, "utf-8", "0.2"),
            stdout_monitors=[
                _RogueOutputMonitor(error_at_line=2),
                OutputMonitorProbe(sink=bin_output),
                _RogueOutputMonitor(error_at_line=0),
            ],
        )
    assert input_file.read_bytes() == bin_output.getvalue()
    excval = excinfo.value
    assert excval.fate.returncode == 0
    expected_failures_count = 2

    err_msgs = [
        "[1] stdout monitor #2 (_RogueOutputMonitor) failed in process",
        "[2] stdout monitor #0 (_RogueOutputMonitor) failed in process",
    ]
    for err_msg in err_msgs:
        assert err_msg in str(excinfo.value)

    assert len(excval.monitor_failures) == expected_failures_count
    assert isinstance(
        excval.monitor_failures[0].exception, _OutputMonitorErrorForTestError
    )

    input_lines = input_file.read_text(encoding="utf-8").splitlines()
    eol = os.linesep.encode("utf-8")
    assert (
        excval.monitor_failures[0].exception.data
        == input_lines[0].encode(encoding="utf-8") + eol
    )
    assert isinstance(
        excval.monitor_failures[1].exception, _OutputMonitorErrorForTestError
    )
    assert (
        excval.monitor_failures[1].exception.data
        == input_lines[2].encode(encoding="utf-8") + eol
    )

    assert "output monitor collapse" in str(
        excval.monitor_failures[0].exception
    )
    assert "output monitor collapse" in str(
        excval.monitor_failures[1].exception
    )


def test_output_monitor_rogue_on_end(
    test_resources: Path, py_exec: PythonCmdBuilder
) -> None:
    input_file = test_resources / "data" / "default.txt"
    out_mon = _RogueOutputMonitorOnDisable()
    with pytest.raises(
        flnr.MonitorFailedError, match="1 monitor failure\\(s\\) recorded"
    ):
        flnr.run_ex(
            py_exec("ln_print.py", input_file, "utf-8", "0.2"),
            stdout_monitors=[out_mon],
        )
    assert out_mon.data_ts >= 0
    assert out_mon.disable_ts >= out_mon.data_ts
    assert out_mon.reason == flnr.OutputMonitorDisableReason.EOF


def test_env_monitor_rogue_startup(py_exec: PythonCmdBuilder) -> None:
    output = io.StringIO()
    expected_code = return_code_for_sigterm()
    with pytest.raises(
        flnr.CommandFailedError,
        match=rf"unexpected return code {expected_code}\n",
    ) as excinfo:
        flnr.run_ex(
            py_exec("cat_dev_random.py"),
            timeouts=flnr.ExecutionTimeouts(run=5.0),
            environment_monitors=[
                _EnvMonitorRogueOnStart(sink=output, period=1.0)
            ],
        )
    excval = excinfo.value
    assert excval.fate == moirai.fate_timeout_terminate(expected_code)

    expected_failures_count = 1
    assert len(excval.monitor_failures) == expected_failures_count

    outstrings = output.getvalue().splitlines()
    assert outstrings[0] == "init called"
    assert outstrings[1].startswith("on start called")
    expected_message_count = 2
    assert len(outstrings) == expected_message_count

    err_msgs = [
        (
            "[1] environment monitor #0 (_EnvMonitorRogueOnStart) "
            "failed in on_start"
        )
    ]
    for err_msg in err_msgs:
        assert err_msg in str(excinfo.value)


def test_env_monitor_rogue_observe(py_exec: PythonCmdBuilder) -> None:
    output = io.StringIO()
    with pytest.raises(
        flnr.MonitorFailedError, match="1 monitor failure\\(s\\) recorded"
    ) as excinfo:
        flnr.run_ex(
            py_exec("py_sleep.py", "3"),
            environment_monitors=[
                _EnvMonitorRogueObserve(sink=output, period=1.0)
            ],
        )
    excval = excinfo.value
    assert excval.fate.returncode == 0

    outstrings = output.getvalue().splitlines()
    assert outstrings[0] == "init called"
    assert outstrings[1].startswith("on start called")
    expected_message_count = 2
    assert len(outstrings) == expected_message_count

    err_msgs = [
        (
            "[1] environment monitor #0 (_EnvMonitorRogueObserve) "
            "failed in observe"
        )
    ]
    for err_msg in err_msgs:
        assert err_msg in str(excinfo.value)


def test_env_monitor_rogue_on_end(py_exec: PythonCmdBuilder) -> None:
    output = io.StringIO()
    with pytest.raises(
        flnr.MonitorFailedError, match="1 monitor failure\\(s\\) recorded"
    ) as excinfo:
        flnr.run_ex(
            py_exec("py_sleep.py", "3"),
            environment_monitors=[
                _EnvMonitorRogueOnEnd(sink=output, period=1.0)
            ],
        )
    excval = excinfo.value
    assert excval.fate.returncode == 0

    outstrings = output.getvalue().splitlines()
    expected_message_count = 3
    assert len(outstrings) >= expected_message_count
    assert outstrings[0] == "init called"
    assert outstrings[1].startswith("on start called")
    assert outstrings[2].startswith("observe called")
    assert outstrings[-1].startswith("observe called")

    err_msgs = [
        "[1] environment monitor #0 (_EnvMonitorRogueOnEnd) failed in on_end",
    ]
    for err_msg in err_msgs:
        assert err_msg in str(excinfo.value)


def test_merge_rejects_stderr_monitor(py_exec: PythonCmdBuilder) -> None:
    with pytest.raises(
        ValueError,
        match="stderr_monitors must be None when merge_std_streams=True",
    ):
        flnr.run_ex(
            py_exec("py_true.py"),
            stderr_monitors=[OutputMonitorProbe(sink=None)],
            merge_std_streams=True,
        )
