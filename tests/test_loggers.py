import io
import re
import signal
from collections.abc import Sequence
from pathlib import Path
from unittest.mock import patch

import pytest

import flnr


class UnsupportedOutputImpl(flnr.OutputMonitor):
    def __init__(self) -> None:
        super().__init__(line_proc=False)

    def process(self, data: bytes) -> None:
        pass


class BinaryOutputImpl(flnr.OutputMonitor):
    def __init__(self, sink: io.IOBase) -> None:
        super().__init__(line_proc=True)
        self.sink = sink

    def process(self, data: bytes) -> None:
        self.sink.write(data)


class ProcessMonitorTestImplementation(flnr.ProcessMonitor):
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
        msg = ProcessMonitorTestImplementation.called_pattern(pid, self.counter)
        print(msg, file=self.sink)

    def on_end(
        self, return_code: int, stop_info: flnr.ProcessTerminationReason
    ) -> None:
        print(
            f"stopped, code = {return_code}, info = {stop_info}",
            file=self.sink,
        )

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


def test_logger_basic_text(test_resources: Path) -> None:
    output = io.StringIO()
    input_file = test_resources / "data" / "miami_nights.txt"
    flnr.run_shell_ex(
        ["cat", input_file],
        timeout=5.0,
        stdout_observers=[
            flnr.LoggingOutputMonitor(
                sink=output, encoding="utf-8", auto_flush=True
            )
        ],
    )
    assert input_file.read_text() == output.getvalue()


def test_logger_basic_bin(test_resources: Path) -> None:
    output = io.BytesIO()
    input_file = test_resources / "data" / "miami_nights.txt"
    flnr.run_shell_ex(
        ["cat", input_file],
        timeout=5.0,
        stdout_observers=[BinaryOutputImpl(sink=output)],
    )
    assert input_file.read_bytes() == output.getvalue()


def test_logger_byte_proc_unsupported() -> None:
    with pytest.raises(NotImplementedError):
        UnsupportedOutputImpl()


def test_logger_stderr_capture(test_resources: Path) -> None:
    stderr_output = io.StringIO()
    flnr.run_shell_ex(
        [test_resources / "exec" / "stderr_output.py"],
        timeout=5.0,
        stderr_observers=[
            flnr.LoggingOutputMonitor(sink=stderr_output, encoding="utf-8")
        ],
        merge_std_streams=False,
    )
    assert stderr_output.getvalue() == "stderr output"


def test_logger_stderr_capture_with_merge(test_resources: Path) -> None:
    stderr_output = io.StringIO()
    with pytest.raises(
        ValueError,
        match="stderr observers provided, while stdout/stderr merged",
    ):
        flnr.run_shell_ex(
            [test_resources / "exec" / "stderr_output.py"],
            timeout=5.0,
            stderr_observers=[
                flnr.LoggingOutputMonitor(sink=stderr_output, encoding="utf-8")
            ],
            merge_std_streams=True,
        )


def test_logger_encoding(test_resources: Path) -> None:
    output_utf8 = io.StringIO()
    output_latin1 = io.StringIO()
    binary_stream1 = io.BytesIO()
    binary_stream2 = io.BytesIO()
    input_file = test_resources / "data" / "invalid_utf8.txt"
    flnr.run_shell_ex(
        ["cat", input_file],
        timeout=5.0,
        stdout_observers=[
            flnr.LoggingOutputMonitor(sink=output_utf8, encoding="utf-8"),
            flnr.LoggingOutputMonitor(sink=output_latin1, encoding="latin-1"),
            flnr.LoggingOutputMonitor(sink=binary_stream1, encoding=None),
            flnr.LoggingOutputMonitor(sink=binary_stream2),
        ],
    )

    binary_content = input_file.read_bytes()

    assert binary_content == binary_stream1.getvalue()
    assert binary_content == binary_stream2.getvalue()
    assert (
        binary_content.decode("utf-8", errors="replace")
        == output_utf8.getvalue()
    )
    assert (
        binary_content.decode("latin-1", errors="replace")
        == output_latin1.getvalue()
    )


def test_logger_incompatible_sink(test_resources: Path) -> None:
    string_output = io.StringIO()
    input_file = test_resources / "data" / "invalid_utf8.txt"
    with pytest.raises(
        flnr.MonitorFailedError, match=r"monitor failures were detected"
    ) as excinfo:
        flnr.run_shell_ex(
            ["cat", input_file],
            timeout=5.0,
            stdout_observers=[
                flnr.LoggingOutputMonitor(sink=string_output, encoding=None),
            ],
        )
    assert excinfo.value.proc_returncode == 0
    assert excinfo.value.monitor_exceptions
    assert len(excinfo.value.monitor_exceptions) == 1
    assert isinstance(excinfo.value.monitor_exceptions[0], TypeError)


def test_basic_process_monitor_sigterm() -> None:
    string_output = io.StringIO()
    with pytest.raises(flnr.CommandFailedError):
        flnr.run_shell_ex(
            ["cat", "/dev/random"],
            timeout=5.0,
            process_monitors=[
                ProcessMonitorTestImplementation(sink=string_output, period=1.0)
            ],
        )

    outlines = string_output.getvalue().splitlines()
    assert len(outlines) > 0
    pid = ProcessMonitorTestImplementation.pid_from_log_record(outlines[0])
    assert outlines[1] == "cat"
    assert outlines[2] == "/dev/random"
    for i in range(1, 5):
        msg = ProcessMonitorTestImplementation.called_pattern(pid, i)
        assert msg == outlines[i + 2]
    timeout_reason = flnr.ProcessTerminationReason.TIMEOUT
    assert (
        outlines[-1]
        == f"stopped, code = -{signal.SIGTERM}, info = {timeout_reason}"
    )


def test_basic_process_monitor_sigkill(test_resources: Path) -> None:
    string_output = io.StringIO()
    with pytest.raises(flnr.CommandFailedError):
        flnr.run_shell_ex(
            [test_resources / "exec" / "sigterm_ignore.py"],
            timeout=5.0,
            process_monitors=[
                ProcessMonitorTestImplementation(sink=string_output, period=1.0)
            ],
        )

    outlines = string_output.getvalue().splitlines()
    assert len(outlines) > 0
    pid = ProcessMonitorTestImplementation.pid_from_log_record(outlines[0])
    assert outlines[1] == str(test_resources / "exec" / "sigterm_ignore.py")
    for i in range(1, 5):
        msg = ProcessMonitorTestImplementation.called_pattern(pid, i)
        assert msg == outlines[i + 1]
    process_killed_reason = flnr.ProcessTerminationReason.KILL
    assert (
        outlines[-1]
        == f"stopped, code = -{signal.SIGKILL}, info = {process_killed_reason}"
    )


def test_basic_process_monitor_success() -> None:
    string_output = io.StringIO()
    # NOTE: test can fail under VERY heavy load
    flnr.run_shell_ex(
        ["sleep", "5"],
        timeout=10,
        process_monitors=[
            ProcessMonitorTestImplementation(sink=string_output, period=1.0)
        ],
    )

    outlines = string_output.getvalue().splitlines()
    assert len(outlines) > 0
    pid = ProcessMonitorTestImplementation.pid_from_log_record(outlines[0])
    assert outlines[1] == "sleep"
    assert outlines[2] == "5"
    for i in range(1, 5):
        msg = ProcessMonitorTestImplementation.called_pattern(pid, i)
        assert msg == outlines[i + 2]
    normal_termination = flnr.ProcessTerminationReason.NORMAL
    assert outlines[-1] == f"stopped, code = 0, info = {normal_termination}"


def test_reader_cancelation(test_resources: Path) -> None:
    string_output = io.StringIO()
    flnr.run_shell_ex(
        [test_resources / "exec" / "stdout_forwarding.py"],
        timeout=15,
        stdout_observers=[
            flnr.LoggingOutputMonitor(sink=string_output, encoding="latin-1")
        ],
    )
    outlines = string_output.getvalue().splitlines()
    assert len(outlines) > 0
    assert "first process started: pid=" in outlines[0]
    assert "second process started: pid=" in outlines[1]
    for i in range(5):
        assert f"tick count: {i}" == outlines[i + 2]


def _run_autoflush_test(
    log_mon: flnr.LoggingOutputMonitor, input_file: Path, expected_flushes: int
) -> None:
    sink = log_mon.sink
    with patch.object(sink, "flush", wraps=sink.flush) as spy:
        flnr.run_shell_ex(["cat", input_file], stdout_observers=[log_mon])
        assert spy.call_count == expected_flushes


def test_autoflush(test_resources: Path) -> None:
    input_file = test_resources / "data" / "miami_nights.txt"
    lines_count = len(input_file.read_text().splitlines())
    with Path("/dev/null").open("w") as null_file:
        log_mon = flnr.LoggingOutputMonitor(
            sink=null_file, encoding="latin-1", auto_flush=True
        )
        _run_autoflush_test(log_mon, input_file, lines_count)
    with Path("/dev/null").open("wb") as null_file:
        log_mon = flnr.LoggingOutputMonitor(sink=null_file)
        _run_autoflush_test(log_mon, input_file, lines_count)

    with Path("/dev/null").open("w") as null_file:
        log_mon = flnr.LoggingOutputMonitor(
            sink=null_file, encoding="latin-1", auto_flush=False
        )
        _run_autoflush_test(log_mon, input_file, 0)


# Since theh underlying process ends quickly, the expectation is that the first
# callback may not be called since the process is finished. We don't have
# relevant asserts because such test would be unreliable and subject to
# sporadic failures.
def test_sysmon_quick_process() -> None:
    string_output = io.StringIO()
    flnr.run_shell_ex(
        ["true"],
        timeout=5,
        process_monitors=[
            ProcessMonitorTestImplementation(sink=string_output, period=1.0)
        ],
    )
    outlines = string_output.getvalue().splitlines()
    assert len(outlines) > 0
    assert outlines[0].startswith("pid = ")
    assert outlines[-1] == "stopped, code = 0, info = finished"
