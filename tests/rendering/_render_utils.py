from collections.abc import Iterable, Sequence
from itertools import count

import flnr
from tests._support import moirai


class _DummyMonitor:
    pass


def _make_monitor_failure(
    base: Exception,
    hook: flnr.MonitorHook,
    stream: flnr.OutputStream | None,
    index: int,
) -> flnr.MonitorFailure:
    return flnr.MonitorFailure(
        exception=base,
        monitor=_DummyMonitor(),
        hook=hook,
        monitor_index=index,
        stream=stream,
    )


def _make_failure_sequence(
    *ex_base: Exception,
    hook: flnr.MonitorHook,
    stream: flnr.OutputStream | None,
    monitor_indices: Iterable[int] | None = None,
) -> list[flnr.MonitorFailure]:

    index_iter = iter(count() if monitor_indices is None else monitor_indices)

    failures: list[flnr.MonitorFailure] = []

    for base in ex_base:
        monitor_index = next(index_iter)
        failures.append(
            _make_monitor_failure(
                base=base, hook=hook, stream=stream, index=monitor_index
            )
        )
    return failures


def _render_structured_exc(
    *,
    monitor_failures: Sequence[flnr.MonitorFailure] = (),
    internal_exceptions: Sequence[BaseException] = (),
    fate: flnr.ProcessFate | None = None,
    err_msg: str | None = None,
) -> str:
    actual_fate = moirai.fate_no_intervention(0) if fate is None else fate
    actual_error = "process execution failure" if err_msg is None else err_msg
    return str(
        flnr.ProcessExecutionError(
            fate=actual_fate,
            monitor_failures=list(monitor_failures),
            internal_exceptions=list(internal_exceptions),
            message=actual_error,
        )
    )
