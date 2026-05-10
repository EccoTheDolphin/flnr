import time

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
        self.last_process_ts: float | None = None
        self.disabled_ts: float | None = None

    def process(self, _: bytes, ts: float) -> None:
        self.process_calls += 1
        self.last_process_ts = ts
        err_msg = "err"
        raise RuntimeError(err_msg)

    def on_disable(
        self, reason: flnr.OutputMonitorDisableReason, ts: float
    ) -> None:
        self.disable_reason = reason
        self.disabled_ts = ts


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
    assert monitor.last_process_ts is not None
    assert monitor.disabled_ts is not None
    assert monitor.disabled_ts >= monitor.last_process_ts


def test_stream_failure_disables_active_output_monitors_with_error_reason() -> (
    None
):
    descriptor = ExecutionDescriptor(returncode=0, pid=1)
    descriptor.add_stdout_events([_ReaderError("err")])

    probe = OutputMonitorProbe(sink=None)

    ts_then = time.monotonic()
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
    assert probe.ts_stop is not None
    assert probe.ts_stop >= ts_then
