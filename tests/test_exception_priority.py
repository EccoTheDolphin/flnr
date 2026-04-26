from collections.abc import Sequence

import pytest

import flnr
from tests._support import moirai
from tests._support.proc_mock import ExecutionDescriptor, run_descriptor


class _ReaderFailureError(Exception):
    pass


class _FailingEnvMonitorOnStart(flnr.EnvironmentMonitor):
    def __init__(self) -> None:
        super().__init__(period=1.0)

    def on_start(self, _: int, __: Sequence[str]) -> None:
        err_msg = "env monitor fail"
        raise RuntimeError(err_msg)

    def observe(self, _: int) -> None:
        pass


class _FailingOutputMonitor(flnr.OutputMonitor):
    def process(self, _: bytes, __: float) -> None:
        err_msg = "output monitor fail"
        raise RuntimeError(err_msg)

    def on_disable(self, _: flnr.OutputMonitorDisableReason, __: float) -> None:
        pass


def test_command_failed_precedes_monitor_failed_when_check_is_true() -> None:
    descriptor = ExecutionDescriptor(returncode=1, pid=42)
    descriptor.add_stdout_events([b""])

    with pytest.raises(flnr.CommandFailedError) as excinfo:
        run_descriptor(
            descriptor,
            environment_monitors=[_FailingEnvMonitorOnStart()],
            check=True,
        )

    exc = excinfo.value
    assert exc.fate == moirai.fate_no_intervention(1)
    assert exc.monitor_failures[0].hook == flnr.MonitorHook.ON_START
    assert isinstance(exc.monitor_failures[0].exception, RuntimeError)
    assert len(exc.monitor_failures) == 1
    assert len(exc.internal_exceptions) == 0


def test_monitor_failed_precedes_command_failed_when_check_is_false() -> None:
    descriptor = ExecutionDescriptor(returncode=1, pid=42)
    descriptor.add_stdout_events([b""])

    with pytest.raises(flnr.MonitorFailedError) as excinfo:
        run_descriptor(
            descriptor,
            environment_monitors=[_FailingEnvMonitorOnStart()],
            check=False,
        )

    exc = excinfo.value
    assert exc.fate == moirai.fate_no_intervention(1)
    assert exc.monitor_failures[0].hook == flnr.MonitorHook.ON_START
    assert isinstance(exc.monitor_failures[0].exception, RuntimeError)
    assert len(exc.monitor_failures) == 1
    assert len(exc.internal_exceptions) == 0


def test_supervision_failed_precedes_command_failed() -> None:
    descriptor = ExecutionDescriptor(returncode=7, pid=42)
    descriptor.add_stdout_events([_ReaderFailureError("err")])

    with pytest.raises(flnr.SupervisionFailedError) as excinfo:
        run_descriptor(descriptor)

    exc = excinfo.value
    assert exc.fate == moirai.fate_internal_failure_kill(7)
    assert len(exc.monitor_failures) == 0
    assert len(exc.internal_exceptions) == 1
    assert isinstance(exc.internal_exceptions[0], _ReaderFailureError)


def test_supervision_failed_precedes_monitor_failed() -> None:
    descriptor = ExecutionDescriptor(returncode=0, pid=42)
    descriptor.add_stdout_events([b"payload", _ReaderFailureError("err")])

    with pytest.raises(flnr.SupervisionFailedError) as excinfo:
        run_descriptor(
            descriptor,
            stdout_monitors=[_FailingOutputMonitor()],
        )

    exc = excinfo.value
    assert exc.fate == moirai.fate_internal_failure_kill(0)
    assert len(exc.monitor_failures) == 1
    assert len(exc.internal_exceptions) == 1
    assert exc.monitor_failures[0].hook == flnr.MonitorHook.PROCESS
    assert isinstance(exc.monitor_failures[0].exception, RuntimeError)
    assert isinstance(exc.internal_exceptions[0], _ReaderFailureError)


def test_process_kill_failed_precedes_supervision_and_monitor_failures() -> (
    None
):
    descriptor = ExecutionDescriptor(
        returncode=None,
        pid=42,
        on_terminate=None,
        on_kill=None,
    )
    descriptor.add_stdout_events([b"payload", _ReaderFailureError("err")])

    with pytest.raises(flnr.ProcessKillFailedError) as excinfo:
        run_descriptor(
            descriptor,
            stdout_monitors=[_FailingOutputMonitor()],
            timeouts=flnr.ExecutionTimeouts(
                run=None,
                terminate=0.1,
                kill=0.1,
                output_drain=0.01,
            ),
        )

    exc = excinfo.value
    assert exc.fate == moirai.fate_internal_failure_kill(None)
    assert len(exc.monitor_failures) == 1
    assert len(exc.internal_exceptions) == 1
    assert exc.monitor_failures[0].hook == flnr.MonitorHook.PROCESS
    assert isinstance(exc.monitor_failures[0].exception, RuntimeError)
    assert isinstance(exc.internal_exceptions[0], _ReaderFailureError)
