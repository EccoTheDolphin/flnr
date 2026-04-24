import flnr
from tests._support import moirai
from tests._support.utils import ExceptionMutator

from ._render_utils import (
    _make_failure_sequence,
)


def _assert_same_rendering_as_base(
    exc: flnr.ProcessExecutionError,
) -> None:
    reference = flnr.ProcessExecutionError(
        fate=exc.fate,
        monitor_failures=exc.monitor_failures,
        internal_exceptions=exc.internal_exceptions,
        message=exc.args[0],
    )
    assert str(exc) == str(reference)


def test_command_failed_report() -> None:
    exc = flnr.CommandFailedError(
        fate=moirai.fate_timeout_terminate(0),
        message="command failed",
        monitor_failures=(),
    )
    _assert_same_rendering_as_base(exc)


def test_monitor_failed_report(
    captured_exc: ExceptionMutator,
) -> None:
    monitor_failures = tuple(
        _make_failure_sequence(
            captured_exc(RuntimeError("out1")),
            hook=flnr.MonitorHook.OBSERVE,
            stream=flnr.OutputStream.STDERR,
            monitor_indices=[0],
        )
    )

    exc = flnr.MonitorFailedError(
        fate=moirai.fate_no_intervention(0),
        message="monitor failed",
        monitor_failures=monitor_failures,
    )
    _assert_same_rendering_as_base(exc)


def test_supervision_failed_report(
    captured_exc: ExceptionMutator,
) -> None:
    internal_exceptions = (captured_exc(RuntimeError("ex1")),)

    exc = flnr.SupervisionFailedError(
        fate=moirai.fate_internal_failure_kill(42),
        message="supervision failed",
        monitor_failures=(),
        internal_exceptions=internal_exceptions,
    )
    _assert_same_rendering_as_base(exc)


def test_process_kill_failed_report(
    captured_exc: ExceptionMutator,
) -> None:
    monitor_failures = tuple(
        _make_failure_sequence(
            captured_exc(RuntimeError("out1")),
            hook=flnr.MonitorHook.OBSERVE,
            stream=flnr.OutputStream.STDOUT,
            monitor_indices=[3],
        )
    )

    exc = flnr.ProcessKillFailedError(
        fate=moirai.fate_timeout_kill(None),
        message="kill failure",
        monitor_failures=monitor_failures,
    )
    _assert_same_rendering_as_base(exc)
