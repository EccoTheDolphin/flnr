import io
import pathlib
import sys
from collections.abc import Sequence
from typing import TextIO

import pytest

import flnr


class CustomLoggerForDemo(flnr.OutputMonitor):
    """Custom implementation of output monitoring."""

    def __init__(self, *, sink: io.IOBase) -> None:
        super().__init__(line_proc=True)
        self.sink = sink

    def process(self, data: bytes) -> None:
        self.sink.write(f"captured data length: {len(data)}\n")


def _run_logger_example() -> None:
    try:
        with (
            pathlib.Path("/dev/null").open("w") as null_file,
            pathlib.Path("data_length.log").open("w") as length_file,
        ):
            flnr.run_shell_ex(
                ["cat", "/dev/random"],
                stdout_observers=[
                    flnr.LoggingOutputMonitor(
                        sink=sys.stdout, encoding="latin-1"
                    ),
                    flnr.LoggingOutputMonitor(
                        sink=null_file, encoding="utf-8", auto_flush=True
                    ),
                    CustomLoggerForDemo(sink=length_file),
                ],
                timeout=5.0,
                merge_std_streams=True,
            )
    except flnr.CommandFailedError as e:
        print(f"{e}")


def test_custom_logger_example(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _run_logger_example()
    content = pathlib.Path("data_length.log").read_text(encoding="utf-8")
    assert "captured data length: " in content
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
            timeout=5.0,
            process_monitors=[
                ProcessMonitorForDemo(sink=sys.stdout, period=1.0)
            ],
        )
    except flnr.CommandFailedError as e:
        print(f"{e}")


def test_sysmon_example(capsys: pytest.CaptureFixture[str]) -> None:
    _run_sysmon_example()
    out = capsys.readouterr().out
    assert "on_start" in out
    assert "observe, pid" in out
    assert "on_end, return_code = -15, info=terminate" in out
