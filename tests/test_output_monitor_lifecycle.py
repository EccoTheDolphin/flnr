import pytest

import flnr
from tests._support.probes import OutputMonitorProbe
from tests._support.proc_mock import ExecutionDescriptor, run_descriptor


class _ReaderError(Exception):
    pass


class _FailsOnFirstProcessCall(flnr.OutputMonitor):
    def __init__(self) -> None:
        self.process_calls = 0
        self.disable_reason: flnr.OutputMonitorDisableReason | None = None

    def process(self, _: bytes, __: float) -> None:
        self.process_calls += 1
        err_msg = "err"
        raise RuntimeError(err_msg)

    def on_disable(
        self, reason: flnr.OutputMonitorDisableReason, _: float
    ) -> None:
        self.disable_reason = reason


def test_failure_disables_monitor_with_error_reason() -> None:
    descriptor = ExecutionDescriptor(returncode=0, pid=42)
    descriptor.add_stdout_events([b"first", b"second", b""])

    monitor = _FailsOnFirstProcessCall()

    with pytest.raises(flnr.MonitorFailedError) as excinfo:
        run_descriptor(
            descriptor,
            stdout_monitors=[monitor],
        )

    exc = excinfo.value
    assert len(exc.monitor_failures) == 1
    assert exc.monitor_failures[0].hook == flnr.MonitorHook.PROCESS
    assert monitor.process_calls == 1
    assert monitor.disable_reason == flnr.OutputMonitorDisableReason.ERROR


def test_reader_failure_disables_active_output_monitors_with_error_reason() -> (
    None
):
    descriptor = ExecutionDescriptor(returncode=0, pid=1)
    descriptor.add_stdout_events([_ReaderError("err")])

    probe = OutputMonitorProbe(sink=None)

    with pytest.raises(flnr.SupervisionFailedError) as excinfo:
        run_descriptor(
            descriptor,
            stdout_monitors=[probe],
        )

    exc = excinfo.value
    assert len(exc.monitor_failures) == 0
    assert len(exc.internal_exceptions) == 1
    assert isinstance(exc.internal_exceptions[0], _ReaderError)
    assert probe.n_process_calls == 0
    assert probe.stop_reason == flnr.OutputMonitorDisableReason.ERROR
