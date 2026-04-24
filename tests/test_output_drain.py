import io
import os
from collections.abc import Sequence

import flnr
from tests._support.probes import OutputMonitorProbe
from tests._support.utils import PythonCmdBuilder

MARKER_BYE = "bye"
MARKER_STDOUT_END = "stdout data end"
MARKER_STDERR_END = "stderr data end"


def _run_output_draining(
    py_exec: PythonCmdBuilder,
    *,
    timeouts: flnr.ExecutionTimeouts,
    stderr_merged: bool,
    parent_process_delay: float,
    child_tick_delay: float,
    child_tick_count: int,
    child_termination_delay: float,
    expected_disable_reason: flnr.OutputMonitorDisableReason,
) -> Sequence[str]:
    bin_output = io.BytesIO()
    output_probe = OutputMonitorProbe(sink=bin_output)
    flnr.run_ex(
        py_exec("output_forwarding.py"),
        timeouts=timeouts,
        stdout_monitors=[output_probe],
        env=os.environ
        | {
            "MAIN_TERMINATION_DELAY": str(parent_process_delay),
            "CHILD_TICK_DELAY": str(child_tick_delay),
            "CHILD_TICK_COUNT": str(child_tick_count),
            "CHILD_TERMINATION_DELAY": str(child_termination_delay),
        },
        merge_std_streams=stderr_merged,
        check=False,
    )
    outlines = bin_output.getvalue().decode(encoding="utf-8").splitlines()
    assert len(outlines) > 0, "output probe should observe some data"
    assert "first process started: pid=" in outlines[0]
    assert "second process started: pid=" in outlines[1]
    assert output_probe.stop_reason == expected_disable_reason
    return outlines[2:]


# child process: can be terminated (run timeout could be exceeded)
# grandchild: child still runs
# output contents: at least 4 ticks observed, not data end marker present
# output monitor: timeouts on-drain
def test_reader_cancellation_tick_cycle(py_exec: PythonCmdBuilder) -> None:
    outlines = _run_output_draining(
        py_exec,
        timeouts=flnr.ExecutionTimeouts(run=10, output_drain=2),
        stderr_merged=True,
        parent_process_delay=10.0,
        child_tick_delay=2,
        child_tick_count=10,
        child_termination_delay=5,
        expected_disable_reason=flnr.OutputMonitorDisableReason.DRAIN_TIMEOUT,
    )
    # we ensure that at least 4 ticks are present
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
def test_reader_run_timeouts_when_child_hang(py_exec: PythonCmdBuilder) -> None:
    total_ticks_count = 10
    outlines = _run_output_draining(
        py_exec,
        timeouts=flnr.ExecutionTimeouts(run=5, output_drain=2),
        stderr_merged=True,
        parent_process_delay=10.0,
        child_tick_delay=0.2,
        child_tick_count=total_ticks_count,
        child_termination_delay=10,
        expected_disable_reason=flnr.OutputMonitorDisableReason.DRAIN_TIMEOUT,
    )
    for i in range(total_ticks_count):
        assert f"stdout - tick count: {i}" == outlines[i * 2]
        assert f"stderr - tick count: {i}" == outlines[i * 2 + 1]
    assert outlines[-1] == f"{MARKER_STDOUT_END}{MARKER_STDERR_END}"


# child process: finished before terminate timeout (could be terminated)
# grandchild: child still runs
# output contents: ticks emitted, data end markers present, no bye msg present
# output monitor: timeouts on-drain
def test_reader_drain_child_never_stops(py_exec: PythonCmdBuilder) -> None:
    outlines = _run_output_draining(
        py_exec,
        timeouts=flnr.ExecutionTimeouts(run=1, output_drain=7),
        stderr_merged=True,
        parent_process_delay=1,
        child_tick_delay=1.0,
        child_tick_count=5,
        child_termination_delay=120,
        expected_disable_reason=flnr.OutputMonitorDisableReason.DRAIN_TIMEOUT,
    )
    assert outlines[-1] == f"{MARKER_STDOUT_END}{MARKER_STDERR_END}"


# child: finishes before run timeout
# grandchild: dead before its parent
# output contents: ticks emitted, data end markers present, bye msg present
# output monitor: eof
def test_reader_drain_child_eofs_before_parent(
    py_exec: PythonCmdBuilder,
) -> None:
    outlines = _run_output_draining(
        py_exec,
        timeouts=flnr.ExecutionTimeouts(run=4, output_drain=1),
        stderr_merged=True,
        parent_process_delay=2,
        # no ticks for child
        child_tick_delay=1.0,
        child_tick_count=0,
        child_termination_delay=0,
        expected_disable_reason=flnr.OutputMonitorDisableReason.EOF,
    )
    assert outlines[-3] == f"{MARKER_STDOUT_END}{MARKER_STDERR_END}"
    assert outlines[-2] == MARKER_BYE
    assert outlines[-1] == MARKER_BYE


# child process: finishes before run timeout
# grandchild: dies after run timeout, but before drain timeout triggers
# output contents: ticks emitted, data end markers present, bye msg present
# output monitor: eof
def test_reader_cancellation_when_child_said_bye(
    py_exec: PythonCmdBuilder,
) -> None:
    outlines = _run_output_draining(
        py_exec,
        timeouts=flnr.ExecutionTimeouts(run=15, output_drain=10),
        stderr_merged=True,
        parent_process_delay=1,
        child_tick_delay=0.2,
        child_tick_count=5,
        child_termination_delay=2,
        expected_disable_reason=flnr.OutputMonitorDisableReason.EOF,
    )

    assert outlines[-3] == f"{MARKER_STDOUT_END}{MARKER_STDERR_END}"
    assert outlines[-2] == MARKER_BYE
    assert outlines[-1] == MARKER_BYE


# child: finishes before run timeout
# grandchild: finishes after it's parent, before drain timeout triggers
# output contents: ticks emitted, data end markers present, bye msg present
# output monitor: no stderr contents, eof
def test_reader_cancellation_when_child_said_bye_nostderr(
    py_exec: PythonCmdBuilder,
) -> None:
    outlines = _run_output_draining(
        py_exec,
        timeouts=flnr.ExecutionTimeouts(run=15, output_drain=15),
        stderr_merged=False,
        parent_process_delay=1,
        child_tick_delay=1.0,
        child_tick_count=5,
        child_termination_delay=2,
        expected_disable_reason=flnr.OutputMonitorDisableReason.EOF,
    )
    for i in range(5):
        assert f"stdout - tick count: {i}" == outlines[i]
    assert outlines[-2] == MARKER_STDOUT_END
    assert outlines[-1] == MARKER_BYE
