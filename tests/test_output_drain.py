import io
import os
from collections.abc import Sequence

import flnr
from tests.lib.utils import PythonCmdBuilder, TextOutputMonitor

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
) -> Sequence[str]:
    string_output = io.StringIO()
    flnr.run_shell_ex(
        py_exec("output_forwarding.py"),
        timeouts=timeouts,
        stdout_observers=[
            TextOutputMonitor(sink=string_output, encoding="latin-1")
        ],
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
    outlines = string_output.getvalue().splitlines()
    assert len(outlines) > 0
    assert "first process started: pid=" in outlines[0]
    assert "second process started: pid=" in outlines[1]
    return outlines[2:]


# each line in tick cycle ends in newline - we just that the
# respected data can be properly observed
def test_reader_cancelation_tick_cycle(py_exec: PythonCmdBuilder) -> None:
    outlines = _run_output_draining(
        py_exec,
        # parent will execute for 10 seconds, with 2 seconds for extra output
        # drain slack
        timeouts=flnr.ExecutionTimeouts(run=10, output_drain=2),
        stderr_merged=True,
        parent_process_delay=10.0,
        # child process will emit 10 ticks 2 second each
        child_tick_delay=2,
        child_tick_count=10,
        child_termination_delay=5,
    )
    # we ensure that at least 4 ticks are present
    for i in range(5):
        assert f"stdout - tick count: {i}" == outlines[i * 2]
        assert f"stderr - tick count: {i}" == outlines[i * 2 + 1]
    # the last line does not have "data end markers"
    for end_marker in [MARKER_BYE, MARKER_STDOUT_END, MARKER_STDERR_END]:
        assert end_marker not in outlines[-1]


def test_reader_cancelation_on_child_term_prepare(
    py_exec: PythonCmdBuilder,
) -> None:
    # the main process runs for 10 seconds, while it's child outputs data for
    # 10 seconds in parallel. Then child termination delay kicks in it lasts
    # for 10 seconds that overlaps with 5-second output drain slack
    outlines = _run_output_draining(
        py_exec,
        timeouts=flnr.ExecutionTimeouts(run=15, output_drain=5),
        stderr_merged=True,
        parent_process_delay=10.0,
        # child process will emit 10 ticks 2 second each
        child_tick_delay=1,
        child_tick_count=10,
        child_termination_delay=10,
    )

    assert outlines[-1] == f"{MARKER_STDOUT_END}{MARKER_STDERR_END}"


def test_reader_cancelation_when_child_said_bye(
    py_exec: PythonCmdBuilder,
) -> None:
    # the main process runs for 10 seconds, while it's child outputs data for
    # 10 seconds in parallel. Then child termination delay kicks in it lasts
    # for 10 seconds that overlaps with 5-second output drain slack
    outlines = _run_output_draining(
        py_exec,
        timeouts=flnr.ExecutionTimeouts(run=15, output_drain=10),
        stderr_merged=True,
        parent_process_delay=1,
        # child process will emit 10 ticks 2 second each
        child_tick_delay=0.2,
        child_tick_count=5,
        child_termination_delay=2,
    )

    assert outlines[-3] == f"{MARKER_STDOUT_END}{MARKER_STDERR_END}"
    assert outlines[-2] == MARKER_BYE
    assert outlines[-1] == MARKER_BYE


def test_reader_drain_stdout_not_merged(py_exec: PythonCmdBuilder) -> None:
    # NOTE: in reality the main process runs for 10 seconds, while it's child
    # outputs data for 20 seconds in parallel, so minimal possible drain
    # timeout is around 10 seconds. We add 5 more on top
    outlines = _run_output_draining(
        py_exec,
        timeouts=flnr.ExecutionTimeouts(run=15, output_drain=15),
        stderr_merged=False,
        parent_process_delay=1,
        # child process will emit 10 ticks 2 second each
        child_tick_delay=1.0,
        child_tick_count=5,
        child_termination_delay=2,
    )
    for i in range(5):
        assert f"stdout - tick count: {i}" == outlines[i]
    # we expect data to be truncated
    assert outlines[-2] == MARKER_STDOUT_END
    assert outlines[-1] == MARKER_BYE
