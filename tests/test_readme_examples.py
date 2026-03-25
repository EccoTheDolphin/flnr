import io
import pathlib
import re
import sys
from collections.abc import Sequence
from typing import TextIO

import pytest

import flnr


class ThroughputMonitor(flnr.OutputMonitor):
    def __init__(self, *, sink: io.IOBase) -> None:
        self.sink = sink
        self.bytes_received = 0

    def process(self, data: bytes, ts: float) -> None:
        self.bytes_received += len(data)
        msg = f"{ts:.3f}s total {self.bytes_received} bytes\n"
        self.sink.write(msg.encode("latin-1"))


class TimestampingMonitor(flnr.OutputMonitor):
    def __init__(self, *, sink: io.IOBase) -> None:
        self.sink = sink
        self.ils = flnr.IncrementalLineSplitter()

    def process(self, data: bytes, ts: float) -> None:
        for line in self.ils.feed(data):
            self.sink.write(f"{ts:.3f}s ".encode("latin-1"))
            self.sink.write(line)


def _run_logger_example() -> None:
    try:
        with (
            pathlib.Path("throughput.log").open("wb") as throughput_log,
            pathlib.Path("timestamped.bin").open("wb") as timestamped_output,
        ):
            flnr.run_shell_ex(
                ["cat", "/dev/random"],
                stdout_observers=[
                    ThroughputMonitor(sink=throughput_log),
                    TimestampingMonitor(sink=timestamped_output),
                ],
                timeouts=flnr.ExecutionTimeouts(run=3.0, output_drain=1.0),
                merge_std_streams=True,
            )
    except flnr.CommandFailedError as e:
        print(f"{e}")


@pytest.mark.skipif(
    sys.platform != "linux", reason="This test is for Linux only"
)
def test_custom_logger_example(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _run_logger_example()
    with pathlib.Path("throughput.log").open("r") as file:
        line1 = file.readline()
        line2 = file.readline()
        fmt = r"(\d+)\.(\d+)s total (\d+) bytes"
        match1 = re.match(fmt, line1)
        assert match1 is not None
        match2 = re.match(fmt, line2)
        assert match2 is not None

        assert int(match2.group(3)) > int(match1.group(3))
        assert float(f"{match2.group(1)}.{match2.group(2)}") > float(
            f"{match1.group(1)}.{match1.group(2)}"
        )

    assert "unexpected return code -15" in capsys.readouterr().out


class ProcessMonitorForDemo(flnr.ProcessMonitor):
    def __init__(self, *, sink: TextIO, period: float) -> None:
        super().__init__(period=period)
        self.sink = sink

    def on_start(self, pid: int, cmd: Sequence[str]) -> None:
        self.sink.write(f"on_start {pid} {cmd}\n")

    def observe(self, pid: int) -> None:
        self.sink.write(f"observe, pid={pid}\n")

    def on_end(
        self, return_code: int, stop_info: flnr.ProcessTerminationReason
    ) -> None:
        self.sink.write(
            f"on_end, return_code = {return_code}, info={stop_info}\n"
        )


def _run_sysmon_example() -> None:
    try:
        flnr.run_shell_ex(
            ["cat", "/dev/random"],
            timeouts=flnr.ExecutionTimeouts(run=5.0),
            process_monitors=[
                ProcessMonitorForDemo(sink=sys.stdout, period=1.0)
            ],
        )
    except flnr.CommandFailedError as e:
        print(f"{e}")


@pytest.mark.skipif(
    sys.platform != "linux", reason="This test is for Linux only"
)
def test_sysmon_example(capsys: pytest.CaptureFixture[str]) -> None:
    _run_sysmon_example()
    out = capsys.readouterr().out
    assert "on_start" in out
    assert "observe, pid" in out
    assert "on_end, return_code = -15, info=terminate" in out
