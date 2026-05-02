from collections.abc import Sequence
from pathlib import Path

import flnr
from tests._support.events import child_drain
from tests._support.output_forwarding import (
    OutputForwardingRunner,
    OutputForwardingTimings,
)
from tests._support.tracing import TraceEvent
from tests._support.utils import PythonCmdBuilder

MARKER_BYE = "bye"
MARKER_STDOUT_END = "stdout data end"
MARKER_STDERR_END = "stderr data end"


def _run_output_forwarding(
    py_exec: PythonCmdBuilder,
    tmp_path: Path,
    *,
    expected_disable_reason: flnr.OutputMonitorDisableReason,
    stderr_merged: bool,
    timings: Sequence[OutputForwardingTimings],
    present_events: Sequence[TraceEvent],
    absent_events: Sequence[TraceEvent],
) -> tuple[str, ...]:
    runner = OutputForwardingRunner(py_exec, tmp_path)
    _, outlines = runner.run_until_trace_shape(
        expected_disable_reason=expected_disable_reason,
        timings=timings,
        stderr_merged=stderr_merged,
        present_events=present_events,
        absent_events=absent_events,
    )
    return outlines


# child process: can be terminated (run timeout could be exceeded)
# grandchild: child still runs
# output contents: at least 5 ticks observed, not data end marker present
# output monitor: timeouts on-drain
def test_drain_timeout_ticks(py_exec: PythonCmdBuilder, tmp_path: Path) -> None:
    outlines = _run_output_forwarding(
        py_exec,
        tmp_path,
        expected_disable_reason=flnr.OutputMonitorDisableReason.DRAIN_TIMEOUT,
        stderr_merged=True,
        timings=[
            OutputForwardingTimings(
                timeouts=flnr.ExecutionTimeouts(run=10, output_drain=2),
                parent_process_delay=10.0,
                child_tick_delay=1.5,
                child_tick_count=10,
                child_termination_delay=5,
            )
        ],
        present_events=[
            child_drain.EventSystem.SUPERVISED_RELEASED_STDO,
            child_drain.EventSystem.DESCENDANT_TICKED_FIRST,
            child_drain.EventSystem.DESCENDANT_TICKED_5,
        ],
        absent_events=[child_drain.EventSystem.DESCENDANT_DATA_END],
    )
    # we ensure that at least 5 ticks are present
    for i in range(5):
        assert f"stdout - tick count: {i}" == outlines[i * 2]
        assert f"stderr - tick count: {i}" == outlines[i * 2 + 1]
    # the last line does not have "data end markers"
    for end_marker in [MARKER_BYE, MARKER_STDOUT_END, MARKER_STDERR_END]:
        assert end_marker not in outlines[-1]


# child process: killed by terminate (run timeout exceeded)
# grandchild: child still runs
# output contents: ticks emitted, data end markers present, no bye msg present
# output monitor: timeouts on-drain
def test_run_timeout_drain_timeout(
    py_exec: PythonCmdBuilder, tmp_path: Path
) -> None:
    total_ticks_count = 10
    outlines = _run_output_forwarding(
        py_exec,
        tmp_path,
        expected_disable_reason=flnr.OutputMonitorDisableReason.DRAIN_TIMEOUT,
        stderr_merged=True,
        timings=[
            OutputForwardingTimings(
                timeouts=flnr.ExecutionTimeouts(run=5, output_drain=2),
                parent_process_delay=10.0,
                child_tick_delay=0.2,
                child_tick_count=total_ticks_count,
                child_termination_delay=10,
            )
        ],
        present_events=[
            child_drain.EventSystem.SUPERVISED_RELEASED_STDO,
            child_drain.EventSystem.DESCENDANT_DATA_END,
        ],
        absent_events=[child_drain.EventSystem.DESCENDANT_SAID_BYE],
    )
    for i in range(total_ticks_count):
        assert f"stdout - tick count: {i}" == outlines[i * 2]
        assert f"stderr - tick count: {i}" == outlines[i * 2 + 1]
    assert outlines[-1] == f"{MARKER_STDOUT_END}{MARKER_STDERR_END}"


# child process: finished before terminate timeout (could be terminated)
# grandchild: child still runs
# output contents: ticks emitted, data end markers present, no bye msg present
# output monitor: timeouts on-drain
def _timings_descendant_pipe_open() -> Sequence[OutputForwardingTimings]:
    return [
        OutputForwardingTimings(
            timeouts=flnr.ExecutionTimeouts(run=run, output_drain=drain),
            parent_process_delay=run,
            child_tick_delay=1.0,
            child_tick_count=5,
            child_termination_delay=40,
        )
        for run, drain in [(1, 7), (2, 8), (4, 10)]
    ]


def test_descendant_keeps_pipe_open(
    py_exec: PythonCmdBuilder, tmp_path: Path
) -> None:
    outlines = _run_output_forwarding(
        py_exec,
        tmp_path,
        expected_disable_reason=flnr.OutputMonitorDisableReason.DRAIN_TIMEOUT,
        stderr_merged=True,
        timings=_timings_descendant_pipe_open(),
        present_events=[
            child_drain.EventSystem.SUPERVISED_RELEASED_STDO,
            child_drain.EventSystem.DESCENDANT_DATA_END,
        ],
        absent_events=[child_drain.EventSystem.DESCENDANT_SAID_BYE],
    )
    assert outlines[-1] == f"{MARKER_STDOUT_END}{MARKER_STDERR_END}"


# child: finishes before run timeout
# grandchild: dead before its parent
# output contents: ticks emitted, data end markers present, bye msg present
# output monitor: eof
def test_descendant_eofs_first(
    py_exec: PythonCmdBuilder,
    tmp_path: Path,
) -> None:
    outlines = _run_output_forwarding(
        py_exec,
        tmp_path,
        expected_disable_reason=flnr.OutputMonitorDisableReason.EOF,
        stderr_merged=True,
        timings=[
            OutputForwardingTimings(
                timeouts=flnr.ExecutionTimeouts(run=4, output_drain=1),
                parent_process_delay=2,
                # no ticks for child
                child_tick_delay=1.0,
                child_tick_count=0,
                child_termination_delay=0,
            )
        ],
        present_events=[
            child_drain.EventSystem.SUPERVISED_CLOSING,
            child_drain.EventSystem.DESCENDANT_RELEASED_STDO,
        ],
        absent_events=[],
    )
    assert outlines[-3] == f"{MARKER_STDOUT_END}{MARKER_STDERR_END}"
    assert outlines[-2] == MARKER_BYE
    assert outlines[-1] == MARKER_BYE


# child process: finishes before run timeout
# grandchild: dies after run timeout, but before drain timeout triggers
# output contents: ticks emitted, data end markers present, bye msg present
# output monitor: eof
def test_descendant_exits_during_drain(
    py_exec: PythonCmdBuilder,
    tmp_path: Path,
) -> None:
    outlines = _run_output_forwarding(
        py_exec,
        tmp_path,
        expected_disable_reason=flnr.OutputMonitorDisableReason.EOF,
        stderr_merged=True,
        timings=[
            OutputForwardingTimings(
                timeouts=flnr.ExecutionTimeouts(run=15, output_drain=10),
                parent_process_delay=1,
                child_tick_delay=0.2,
                child_tick_count=5,
                child_termination_delay=2,
            )
        ],
        present_events=[
            child_drain.EventSystem.SUPERVISED_CLOSING,
            child_drain.EventSystem.DESCENDANT_RELEASED_STDO,
        ],
        absent_events=[],
    )

    assert outlines[-3] == f"{MARKER_STDOUT_END}{MARKER_STDERR_END}"
    assert outlines[-2] == MARKER_BYE
    assert outlines[-1] == MARKER_BYE


# child: finishes before run timeout
# grandchild: finishes after it's parent, before drain timeout triggers
# output contents: ticks emitted, data end markers present, bye msg present
# output monitor: no stderr contents, eof
def test_stdout_only_drain(
    py_exec: PythonCmdBuilder,
    tmp_path: Path,
) -> None:
    outlines = _run_output_forwarding(
        py_exec,
        tmp_path,
        expected_disable_reason=flnr.OutputMonitorDisableReason.EOF,
        stderr_merged=False,
        timings=[
            OutputForwardingTimings(
                timeouts=flnr.ExecutionTimeouts(run=15, output_drain=15),
                parent_process_delay=1,
                child_tick_delay=1.0,
                child_tick_count=5,
                child_termination_delay=2,
            )
        ],
        present_events=[
            child_drain.EventSystem.SUPERVISED_CLOSING,
            child_drain.EventSystem.DESCENDANT_RELEASED_STDO,
        ],
        absent_events=[],
    )
    for i in range(5):
        assert f"stdout - tick count: {i}" == outlines[i]
    assert outlines[-2] == MARKER_STDOUT_END
    assert outlines[-1] == MARKER_BYE
