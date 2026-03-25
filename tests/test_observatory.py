import io

import pytest

import flnr
from tests.lib.utils import BinaryCapture, ProcMonImpl, StreamControl


class _MyCustomReaderError(Exception):
    pass


def test_output_from_mock_streamer() -> None:
    output = io.BytesIO()
    ctl = StreamControl(returncode=0, pid=42)
    ctl.add_events([b"data", b""])
    ctl.add_output_observers([BinaryCapture(sink=output)])
    ctl.run(ctl.build_process())
    assert output.getvalue() == b"data"


def test_sysmon_output_from_dead_streamer() -> None:
    sysmon_sink = io.StringIO()
    ctl = StreamControl(returncode=0, pid=42)
    ctl.add_events([b"data\n", b"", RuntimeError("should not happen")])
    ctl.set_stdout_delays(1.0)
    ctl.add_process_monitors([ProcMonImpl(sink=sysmon_sink, period=0.5)])
    proc = ctl.build_process()
    proc.terminate()
    ctl.run(proc, timeouts=flnr.ExecutionTimeouts(run=1.0, output_drain=5.0))
    sysmon_lines = sysmon_sink.getvalue().splitlines()
    assert (
        sysmon_lines[0]
        == "on_start called. pid = 42, command = ['dummy.command']"
    )
    assert sysmon_lines[1] == "on_end called. status = 0, reason = finished"


def test_sysmon_output() -> None:
    sysmon_sink = io.StringIO()
    ctl = StreamControl(returncode=0, pid=41)
    ctl.add_events([b"data\n", b""])
    ctl.set_stdout_delays(1.0)
    ctl.add_process_monitors([ProcMonImpl(sink=sysmon_sink, period=0.5)])
    ctl.run(ctl.build_process())
    sysmon_lines = sysmon_sink.getvalue().splitlines()
    assert (
        sysmon_lines[0]
        == "on_start called. pid = 41, command = ['dummy.command']"
    )
    assert sysmon_lines[1] == "observe called. pid = 41"
    assert sysmon_lines[2] == "observe called. pid = 41"
    assert sysmon_lines[-1] == "on_end called. status = 0, reason = finished"


def test_reader_error_once() -> None:
    output = io.BytesIO()
    ctl = StreamControl(returncode=0, pid=42)
    ctl.add_events([b"data1\n", _MyCustomReaderError("err"), b"data2", b""])
    ctl.add_output_observers([BinaryCapture(sink=output)])
    with pytest.raises(
        flnr.exceptions.MonitorFailedError,
        match=r"^1 monitor failures were detected",
    ) as excinfo:
        ctl.run(ctl.build_process())
    assert output.getvalue() == b"data1\ndata2"
    assert excinfo.value.proc_returncode == 0
    assert len(excinfo.value.monitor_exceptions) == 1
    assert isinstance(excinfo.value.monitor_exceptions[0], _MyCustomReaderError)


def test_reader_stream_of_errors() -> None:
    output = io.BytesIO()
    ctl = StreamControl(returncode=None, pid=777)
    ctl.add_events([b"data1", b"data2", _MyCustomReaderError("err")])
    ctl.add_output_observers([BinaryCapture(sink=output)])
    with pytest.raises(
        flnr.exceptions.MonitorFailedError,
        match=r"^3 monitor failures were detected",
    ) as excinfo:
        # NOTE: this deadlocks without timeout because the reader dies while
        # subprocess never terminates
        ctl.run(ctl.build_process(), timeouts=flnr.ExecutionTimeouts(run=5.0))
    assert output.getvalue() == b"data1data2"
    assert isinstance(excinfo.value.monitor_exceptions[0], _MyCustomReaderError)
