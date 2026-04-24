import pytest

import flnr

from ._render_utils import _DummyMonitor


@pytest.mark.parametrize(
    "stream",
    [None, flnr.OutputStream.STDOUT, flnr.OutputStream.STDERR],
    ids=["no_stream", "stdout", "stderr"],
)
@pytest.mark.parametrize(
    "method",
    [
        flnr.MonitorHook.PROCESS,
        flnr.MonitorHook.ON_DISABLE,
        flnr.MonitorHook.ON_START,
        flnr.MonitorHook.OBSERVE,
        flnr.MonitorHook.ON_END,
    ],
)
def test_monitor_failure_renderer(
    stream: flnr.OutputStream | None, method: flnr.MonitorHook
) -> None:
    render_target = flnr.MonitorFailure(
        monitor=_DummyMonitor(),
        hook=method,
        exception=RuntimeError("exc"),
        monitor_index=3,
        stream=stream,
    )
    stream_prefix = "environment" if stream is None else f"{stream}"
    rendered = str(render_target)
    assert (
        f"{stream_prefix} monitor #3 (_DummyMonitor) "
        f"failed in {method}: RuntimeError('exc')"
    ) == rendered
