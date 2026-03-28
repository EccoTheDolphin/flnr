import io
import signal
from collections.abc import Sequence
from pathlib import Path

import pytest

import flnr


class _OutputMonitorErrorForTestError(Exception):
    def __init__(self, data: bytes, err_msg: str) -> None:
        super().__init__(err_msg)
        self.data = data


class _ProcessMonitorErrorForTestError(Exception):
    pass


class RoqueOutputMonitor(flnr.OutputMonitor):
    def __init__(self, *, error_at_line: int) -> None:
        self.error_at_line = error_at_line
        self.call_count = 0

    def process(self, data: bytes) -> None:
        if self.call_count >= self.error_at_line:
            err_msg = "output monitor collapse"
            raise _OutputMonitorErrorForTestError(data, err_msg)
        self.call_count += 1


class ProcessMonitorRogueOnStart(flnr.ProcessMonitor):
    def __init__(self, *, sink: io.IOBase, period: float) -> None:
        super().__init__(period=period)
        self.sink = sink
        self.sink.write("init called\n")

    def on_start(self, pid: int, cmd: Sequence[str]) -> None:
        self.sink.write(f"on start called, cmd = {cmd}, pid = {pid}\n")
        err_msg = "on start error"
        raise _ProcessMonitorErrorForTestError(err_msg)

    def observe(self, pid: int) -> None:
        self.sink.write(f"observe called, pid = {pid}\n")

    def on_end(
        self, return_code: int, stop_info: flnr.ProcessTerminationReason
    ) -> None:
        self.sink.write(
            f"on end called, returncode={return_code}, stop_info={stop_info}\n"
        )


class ProcessMonitorRogueObserve(flnr.ProcessMonitor):
    def __init__(self, *, sink: io.IOBase, period: float) -> None:
        super().__init__(period=period)
        self.sink = sink
        self.sink.write("init called\n")

    def on_start(self, _: int, __: Sequence[str]) -> None:
        self.sink.write("on start called\n")

    def observe(self, _: int) -> None:
        err_msg = "on observe error"
        raise _ProcessMonitorErrorForTestError(err_msg)

    def on_end(self, _: int, __: flnr.ProcessTerminationReason) -> None:
        self.sink.write("on end called")


class ProcessMonitorRogueOnEnd(flnr.ProcessMonitor):
    def __init__(self, *, sink: io.IOBase, period: float) -> None:
        super().__init__(period=period)
        self.sink = sink
        self.sink.write("init called\n")

    def on_start(self, _: int, __: Sequence[str]) -> None:
        self.sink.write("on start called\n")

    def observe(self, _: int) -> None:
        self.sink.write("observe called\n")

    def on_end(self, _: int, __: flnr.ProcessTerminationReason) -> None:
        err_msg = "on end error"
        raise _ProcessMonitorErrorForTestError(err_msg)


def test_logger_output_rogue(test_resources: Path) -> None:
    output = io.StringIO()
    input_file = test_resources / "data" / "miami_nights.txt"
    with pytest.raises(
        flnr.MonitorFailedError, match="2 monitor failures were detected"
    ) as excinfo:
        flnr.run_shell_ex(
            ["cat", input_file],
            timeout=5.0,
            stdout_observers=[
                RoqueOutputMonitor(error_at_line=2),
                flnr.LoggingOutputMonitor(
                    sink=output, encoding="utf-8", auto_flush=True
                ),
                RoqueOutputMonitor(error_at_line=0),
            ],
        )
    assert input_file.read_text() == output.getvalue()
    excval = excinfo.value
    assert excval.proc_returncode == 0
    expected_failures_count = 2
    assert len(excval.monitor_exceptions) == expected_failures_count
    assert isinstance(
        excval.monitor_exceptions[0], _OutputMonitorErrorForTestError
    )
    assert excval.monitor_exceptions[0].data == b"It's the cars and the clubs\n"
    assert isinstance(
        excval.monitor_exceptions[1], _OutputMonitorErrorForTestError
    )
    assert excval.monitor_exceptions[1].data == b"I get lost in the life\n"

    assert "0: output monitor collapse" in str(excval)
    assert "1: output monitor collapse" in str(excval)


def test_system_monitor_rogue_startup() -> None:
    output = io.StringIO()
    with pytest.raises(
        flnr.MonitorFailedError, match="1 monitor failures were detected"
    ) as excinfo:
        flnr.run_shell_ex(
            ["cat", "/dev/random"],
            timeout=5.0,
            process_monitors=[
                ProcessMonitorRogueOnStart(sink=output, period=1.0)
            ],
        )
    excval = excinfo.value
    assert excval.proc_returncode == -signal.SIGTERM
    expected_failures_count = 1
    assert len(excval.monitor_exceptions) == expected_failures_count

    outstrings = output.getvalue().splitlines()
    assert outstrings[0] == "init called"
    assert outstrings[1].startswith("on start called")
    expected_message_count = 2
    assert len(outstrings) == expected_message_count


def test_system_monitor_rogue_observe() -> None:
    output = io.StringIO()
    with pytest.raises(
        flnr.MonitorFailedError, match="1 monitor failures were detected"
    ) as excinfo:
        flnr.run_shell_ex(
            ["sleep", "3"],
            timeout=5.0,
            process_monitors=[
                ProcessMonitorRogueObserve(sink=output, period=1.0)
            ],
        )
    excval = excinfo.value
    assert excval.proc_returncode == 0

    outstrings = output.getvalue().splitlines()
    assert outstrings[0] == "init called"
    assert outstrings[1].startswith("on start called")
    expected_message_count = 2
    assert len(outstrings) == expected_message_count


def test_system_monitor_rogue_on_end() -> None:
    output = io.StringIO()
    with pytest.raises(
        flnr.MonitorFailedError, match="1 monitor failures were detected"
    ) as excinfo:
        flnr.run_shell_ex(
            ["sleep", "3"],
            timeout=5.0,
            process_monitors=[
                ProcessMonitorRogueOnEnd(sink=output, period=1.0)
            ],
        )
    excval = excinfo.value
    assert excval.proc_returncode == 0

    outstrings = output.getvalue().splitlines()
    expected_message_count = 3
    assert len(outstrings) >= expected_message_count
    assert outstrings[0] == "init called"
    assert outstrings[1].startswith("on start called")
    assert outstrings[2].startswith("observe called")
    assert outstrings[-1].startswith("observe called")
