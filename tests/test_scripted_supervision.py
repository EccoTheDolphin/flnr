import io

import pytest

import flnr
from tests._support import moirai
from tests._support.probes import EnvMonitorProbe, OutputMonitorProbe
from tests._support.proc_mock import (
    ExecutionDescriptor,
    run_descriptor,
    run_scripted_process,
)
from tests._support.utils import return_code_for_sigkill


class _MyCustomReaderError(Exception):
    pass


def test_output_from_mock_streamer() -> None:
    output = io.BytesIO()
    descriptor = ExecutionDescriptor(returncode=0, pid=42)
    descriptor.add_stdout_events([b"data", b""])
    run_descriptor(
        descriptor,
        stdout_monitors=[OutputMonitorProbe(sink=output)],
    )
    assert output.getvalue() == b"data"


def test_env_monitor_from_dead_streamer() -> None:
    env_monitor_sink = io.StringIO()
    descriptor = ExecutionDescriptor(returncode=0, pid=42)
    descriptor.add_stdout_events(
        [b"data\n", b"", RuntimeError("should not happen")]
    )
    descriptor.set_stdout_delays(1.0)
    process = descriptor.build_process()
    process.terminate()
    run_scripted_process(
        process,
        environment_monitors=[
            EnvMonitorProbe(sink=env_monitor_sink, period=0.5)
        ],
        timeouts=flnr.ExecutionTimeouts(run=1.0, output_drain=5.0),
    )
    env_monitor_lines = env_monitor_sink.getvalue().splitlines()
    assert (
        env_monitor_lines[0]
        == "on_start called. pid = 42, command = ['dummy.command']"
    )
    expected_fate = moirai.fate_no_intervention(0)
    assert env_monitor_lines[1] == f"on_end called. {expected_fate}"


def test_env_monitor_output() -> None:
    env_monitor_sink = io.StringIO()
    descriptor = ExecutionDescriptor(returncode=0, pid=41)
    descriptor.add_stdout_events([b"data\n", b""])
    descriptor.set_stdout_delays(1.0)
    run_descriptor(
        descriptor,
        environment_monitors=[
            EnvMonitorProbe(sink=env_monitor_sink, period=0.5)
        ],
    )
    env_monitor_lines = env_monitor_sink.getvalue().splitlines()
    assert (
        env_monitor_lines[0]
        == "on_start called. pid = 41, command = ['dummy.command']"
    )
    assert env_monitor_lines[1] == "observe called. pid = 41"
    assert env_monitor_lines[2] == "observe called. pid = 41"
    expected_fate = moirai.fate_no_intervention(0)
    assert env_monitor_lines[-1] == f"on_end called. {expected_fate}"


def test_stream_error_once() -> None:
    output = io.BytesIO()
    descriptor = ExecutionDescriptor(returncode=0, pid=42)
    descriptor.add_stdout_events(
        [b"data1\n", _MyCustomReaderError("err"), b"data2", b""]
    )
    with pytest.raises(
        flnr.SupervisionFailedError,
        match="supervision failed due to unrecoverable errors",
    ) as excinfo:
        run_descriptor(
            descriptor,
            stdout_monitors=[OutputMonitorProbe(sink=output)],
        )
    assert output.getvalue() == b"data1\n"
    expected_fate = moirai.fate_internal_failure_kill(0)
    assert excinfo.value.fate == expected_fate
    assert len(excinfo.value.monitor_failures) == 0
    assert len(excinfo.value.internal_exceptions) == 1
    assert isinstance(
        excinfo.value.internal_exceptions[0], _MyCustomReaderError
    )


def test_stream_error_without_run_timeout() -> None:
    output = io.BytesIO()
    descriptor = ExecutionDescriptor(
        returncode=None, pid=777, on_kill=return_code_for_sigkill()
    )
    descriptor.add_stdout_events(
        [b"data1", b"data2", _MyCustomReaderError("err")]
    )
    expected_code = return_code_for_sigkill()
    with pytest.raises(
        flnr.SupervisionFailedError,
        match="supervision failed due to unrecoverable errors",
    ) as excinfo:
        run_descriptor(
            descriptor,
            stdout_monitors=[OutputMonitorProbe(sink=output)],
            timeouts=flnr.ExecutionTimeouts(run=None),
        )
    expected_fate = moirai.fate_internal_failure_kill(expected_code)
    assert excinfo.value.fate == expected_fate
    assert output.getvalue() == b"data1data2"
    assert len(excinfo.value.monitor_failures) == 0
    assert len(excinfo.value.internal_exceptions) == 1
    assert isinstance(
        excinfo.value.internal_exceptions[0], _MyCustomReaderError
    )


def test_unkillable_process() -> None:
    descriptor = ExecutionDescriptor(returncode=None, pid=777)
    descriptor.add_stdout_events([b"x"])
    with pytest.raises(
        flnr.ProcessKillFailedError,
        match=r"process exit was not observed",
    ) as excinfo:
        run_descriptor(
            descriptor,
            timeouts=flnr.ExecutionTimeouts(run=1, terminate=1),
        )
    assert excinfo.value.fate == moirai.fate_timeout_kill(None)
