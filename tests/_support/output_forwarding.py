import io
import os
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import flnr
from tests._support.events import child_drain
from tests._support.probes import OutputMonitorProbe
from tests._support.tracing import (
    TRACE_DIR_ENV,
    EventTracingError,
    InvalidTraceProfileWarning,
    TraceEvent,
    TraceObserver,
)
from tests._support.utils import (
    TEST_DIR_ROOT,
    PythonCmdBuilder,
    pythonpath_env,
)


@dataclass
class OutputForwardingTimings:
    timeouts: flnr.ExecutionTimeouts
    parent_process_delay: float
    child_tick_count: int
    child_tick_delay: float
    child_termination_delay: float


@dataclass
class _OutputForwardingAttempt:
    fate: flnr.ProcessFate
    output_probe: OutputMonitorProbe
    trace: TraceObserver
    output: str
    command_error: flnr.CommandFailedError | None = None


class OutputForwardingRunner:
    def __init__(self, py_exec: PythonCmdBuilder, tmp_path: Path) -> None:
        self.py_exec = py_exec
        self.tmp_path = tmp_path

    @staticmethod
    def _timing_env(timing: OutputForwardingTimings) -> dict[str, str]:
        return {
            "MAIN_TERMINATION_DELAY": str(timing.parent_process_delay),
            "CHILD_TICK_DELAY": str(timing.child_tick_delay),
            "CHILD_TICK_COUNT": str(timing.child_tick_count),
            "CHILD_TERMINATION_DELAY": str(timing.child_termination_delay),
        }

    def _run_attempt(
        self,
        *,
        index: int,
        timing: OutputForwardingTimings,
        stderr_merged: bool,
        check: bool,
    ) -> _OutputForwardingAttempt:
        bin_output = io.BytesIO()
        output_probe = OutputMonitorProbe(sink=bin_output)
        trace_root = self.tmp_path / f"trace-{index}"
        trace = TraceObserver(child_drain.EventSystem, trace_root)

        command_error: flnr.CommandFailedError | None = None
        try:
            fate = flnr.run_ex(
                self.py_exec("output_forwarding.py"),
                timeouts=timing.timeouts,
                stdout_monitors=[output_probe],
                env=os.environ
                | pythonpath_env(TEST_DIR_ROOT.parent, os.environ)
                | {TRACE_DIR_ENV: str(trace_root)}
                | self._timing_env(timing),
                merge_std_streams=stderr_merged,
                check=check,
            )
        except flnr.CommandFailedError as exc:
            command_error = exc
            fate = exc.fate
        output = bin_output.getvalue().decode(encoding="utf-8")
        return _OutputForwardingAttempt(
            fate=fate,
            output_probe=output_probe,
            trace=trace,
            output=output,
            command_error=command_error,
        )

    @staticmethod
    def _assert_mandatory_output(
        attempt: _OutputForwardingAttempt,
        expected_disable_reason: flnr.OutputMonitorDisableReason,
    ) -> None:
        assert attempt.output_probe.stop_reason == expected_disable_reason
        outlines = attempt.output.splitlines()
        assert len(outlines) > 0, "output probe should observe some data"
        assert "first process started: pid=" in outlines[0]
        assert len(outlines) > 1, "output probe should observe child greeting"
        assert "second process started: pid=" in outlines[1]

    def run_until_trace_shape(
        self,
        *,
        expected_disable_reason: flnr.OutputMonitorDisableReason,
        stderr_merged: bool,
        timings: Sequence[OutputForwardingTimings],
        present_events: Sequence[TraceEvent],
        absent_events: Sequence[TraceEvent],
        check: bool = False,
    ) -> tuple[flnr.ProcessFate, tuple[str, ...]]:
        for i, timing in enumerate(timings):
            attempt = self._run_attempt(
                index=i,
                timing=timing,
                stderr_merged=stderr_merged,
                check=check,
            )
            try:
                attempt.trace.expect_state(
                    must_present=tuple(present_events),
                    must_absent=tuple(absent_events),
                )
            except EventTracingError:
                warnings.warn(
                    (
                        f"timing profile {i} did not produce expected "
                        "trace shape\n"
                        f"timing: {timing!r}\n"
                        f"process_fate: {attempt.fate}\n"
                        f"command_error: {attempt.command_error!r}\n"
                        f"observed_events: "
                        f"{attempt.trace.observed_events()!r}\n"
                        f"output: {attempt.output}\n"
                    ),
                    InvalidTraceProfileWarning,
                    stacklevel=2,
                )
                continue

            self._assert_mandatory_output(attempt, expected_disable_reason)
            if attempt.command_error is not None:
                raise attempt.command_error
            return attempt.fate, tuple(attempt.output.splitlines()[2:])

        error_msg = "could not obtain expected execution profile"
        raise RuntimeError(error_msg)
