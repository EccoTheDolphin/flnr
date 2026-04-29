import flnr
from tests._support.exception_report import (
    normalize_traceback_report,
)
from tests._support.utils import ExceptionMutator

from ._render_utils import (
    _make_failure_sequence,
    _render_structured_exc,
)

TRACEBACK_PATTERN = """Traceback (most recent call last):
  File "<file>", line <n>, in <func>
    raise_it()
  File "<file>", line <n>, in <func>
    raise exc"""


def test_all_monitor_report(
    captured_exc: ExceptionMutator,
) -> None:
    rendered_report = _render_structured_exc(
        monitor_failures=_make_failure_sequence(
            captured_exc(RuntimeError("out1")),
            hook=flnr.MonitorHook.OBSERVE,
            stream=flnr.OutputStream.STDOUT,
            monitor_indices=[3],
        )
        + _make_failure_sequence(
            captured_exc(ValueError("sys1")),
            hook=flnr.MonitorHook.ON_START,
            stream=None,
            monitor_indices=[0],
        )
        + _make_failure_sequence(
            captured_exc(RuntimeError("err1")),
            hook=flnr.MonitorHook.ON_END,
            stream=flnr.OutputStream.STDERR,
            monitor_indices=[42],
        ),
    )
    expected_report = f"""process execution failure
fate: returncode=0, decision=no_intervention, method=none
3 monitor failure(s) recorded:

[1] stdout monitor #3 (_DummyMonitor) failed in observe: RuntimeError: out1
[2] environment monitor #0 (_DummyMonitor) failed in on_start: ValueError: sys1
[3] stderr monitor #42 (_DummyMonitor) failed in on_end: RuntimeError: err1

Monitor failure details:

[1] stdout monitor #3 (_DummyMonitor) failed in observe
{TRACEBACK_PATTERN}
RuntimeError: out1

[2] environment monitor #0 (_DummyMonitor) failed in on_start
{TRACEBACK_PATTERN}
ValueError: sys1

[3] stderr monitor #42 (_DummyMonitor) failed in on_end
{TRACEBACK_PATTERN}
RuntimeError: err1"""
    normalized_report = normalize_traceback_report(rendered_report)
    assert normalized_report == expected_report


def test_monitor_errs_with_internal_errors(
    captured_exc: ExceptionMutator,
) -> None:
    rendered_report = _render_structured_exc(
        monitor_failures=_make_failure_sequence(
            captured_exc(RuntimeError("err1")),
            hook=flnr.MonitorHook.ON_END,
            stream=flnr.OutputStream.STDERR,
            monitor_indices=[42],
        ),
        internal_exceptions=[
            captured_exc(RuntimeError("oops1")),
            captured_exc(ImportError("oops2")),
        ],
    )
    expected_report = f"""process execution failure
fate: returncode=0, decision=no_intervention, method=none
1 monitor failure(s) recorded:

[1] stderr monitor #42 (_DummyMonitor) failed in on_end: RuntimeError: err1

Monitor failure details:

[1] stderr monitor #42 (_DummyMonitor) failed in on_end
{TRACEBACK_PATTERN}
RuntimeError: err1

Internal failures:

[1] RuntimeError: oops1
{TRACEBACK_PATTERN}
RuntimeError: oops1

[2] ImportError: oops2
{TRACEBACK_PATTERN}
ImportError: oops2"""
    normalized_report = normalize_traceback_report(rendered_report)
    assert normalized_report == expected_report
