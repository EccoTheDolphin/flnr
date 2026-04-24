import io
import os
import signal
import sys
import time

import pytest

import flnr
from tests._support import moirai
from tests._support.probes import OutputMonitorProbe
from tests._support.utils import (
    PythonCmdBuilder,
    return_code_for_sigterm,
    time_duration_exceeds_value,
)


def _run_timeout_duration_test(
    py_exec: PythonCmdBuilder, timeout: float
) -> None:
    time_start = time.monotonic()
    # NOTE: this is potentially a brittle test
    fate = flnr.run_ex(
        py_exec("cat_dev_random.py"),
        timeouts=flnr.ExecutionTimeouts(run=timeout, output_drain=0.01),
        check=False,
    )
    time_end = time.monotonic()
    assert fate == moirai.fate_timeout_terminate(return_code_for_sigterm())
    assert time_duration_exceeds_value(time_end, time_start, timeout)
    assert time_end - time_start < 3 * timeout


def _run_timeout_when_child_activated(
    py_exec: PythonCmdBuilder, *, check: bool
) -> flnr.ProcessFate:
    bin_output = io.BytesIO()
    run_timeout = 5
    tick_count = 10
    run_duration = run_timeout * 4
    try:
        return flnr.run_ex(
            py_exec("output_forwarding.py"),
            timeouts=flnr.ExecutionTimeouts(
                run=5.0, output_drain=1, terminate=1
            ),
            env=os.environ
            | {
                "MAIN_TERMINATION_DELAY": str(run_duration),
                "CHILD_TICK_DELAY": str(0.1),
                "CHILD_TICK_COUNT": str(tick_count),
                "CHILD_TERMINATION_DELAY": str(run_duration),
            },
            stdout_monitors=[OutputMonitorProbe(sink=bin_output)],
            check=check,
        )
    finally:
        assert len(bin_output.getvalue().splitlines()) > tick_count


def test_runner_success(py_exec: PythonCmdBuilder) -> None:
    fate = flnr.run_ex(py_exec("py_true.py"))
    assert fate == moirai.fate_no_intervention(0)


def test_runner_success_run_timeout_none_explicit(
    py_exec: PythonCmdBuilder,
) -> None:
    fate = flnr.run_ex(
        py_exec("py_true.py"), timeouts=flnr.ExecutionTimeouts(run=None)
    )
    assert fate == moirai.fate_no_intervention(0)


def test_runner_success_checked(py_exec: PythonCmdBuilder) -> None:
    fate = flnr.run_ex(py_exec("py_true.py"), check=True)
    assert fate == moirai.fate_no_intervention(0)


def test_runner_failure_noexc(py_exec: PythonCmdBuilder) -> None:
    fate = flnr.run_ex(py_exec("py_false.py"), check=False)
    assert fate == moirai.fate_no_intervention(1)


def test_runner_failure_noexc_run_timeout_none_explicit(
    py_exec: PythonCmdBuilder,
) -> None:
    fate = flnr.run_ex(
        py_exec("py_false.py"),
        check=False,
        timeouts=flnr.ExecutionTimeouts(run=None),
    )
    assert fate == moirai.fate_no_intervention(1)


def test_runner_failure_exc(py_exec: PythonCmdBuilder) -> None:
    with pytest.raises(flnr.CommandFailedError) as excinfo:
        flnr.run_ex(py_exec("py_false.py"))
    assert excinfo.value.fate == moirai.fate_no_intervention(1)

    with pytest.raises(flnr.CommandFailedError) as excinfo:
        flnr.run_ex(py_exec("py_false.py"), check=True)
    assert excinfo.value.fate == moirai.fate_no_intervention(1)


def test_runner_timeout_sigterm(py_exec: PythonCmdBuilder) -> None:
    with pytest.raises(
        flnr.CommandFailedError,
        match=f"unexpected return code {return_code_for_sigterm()}\n",
    ) as excinfo:
        flnr.run_ex(
            py_exec("cat_dev_random.py"),
            timeouts=flnr.ExecutionTimeouts(run=5.0),
        )
    assert excinfo.value.fate == moirai.fate_timeout_terminate(
        return_code_for_sigterm()
    )


def test_runner_timeout_sigterm_noexc(py_exec: PythonCmdBuilder) -> None:
    fate = flnr.run_ex(
        py_exec("cat_dev_random.py"),
        timeouts=flnr.ExecutionTimeouts(run=5.0),
        check=False,
    )
    assert fate == moirai.fate_timeout_terminate(return_code_for_sigterm())


def test_runner_timeout_2seconds(py_exec: PythonCmdBuilder) -> None:
    _run_timeout_duration_test(py_exec, 2)


def test_runner_timeout_10seconds(py_exec: PythonCmdBuilder) -> None:
    _run_timeout_duration_test(py_exec, 10)


def test_runner_timeout_sigterm_live_child(py_exec: PythonCmdBuilder) -> None:
    with pytest.raises(
        flnr.CommandFailedError,
        match=f"unexpected return code {return_code_for_sigterm()}\n",
    ) as excinfo:
        _run_timeout_when_child_activated(py_exec, check=True)
    assert excinfo.value.fate == moirai.fate_timeout_terminate(
        return_code_for_sigterm()
    )


def test_runner_timeout_sigterm_noexc_live_child(
    py_exec: PythonCmdBuilder,
) -> None:
    fate = _run_timeout_when_child_activated(py_exec, check=False)
    assert fate == moirai.fate_timeout_terminate(return_code_for_sigterm())


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="we are unable to get SIGKILL on windows",
)
def test_runner_timeout_sigkill(py_exec: PythonCmdBuilder) -> None:
    # NOTE: this can fail under VERY heavy load if the process won't be able to
    # mask SIGTERM
    with pytest.raises(
        flnr.CommandFailedError,
        match=f"unexpected return code -{signal.SIGKILL}\n",
    ) as excinfo:
        flnr.run_ex(
            py_exec("sigterm_ignore.py"),
            timeouts=flnr.ExecutionTimeouts(run=1.0),
        )
    assert excinfo.value.fate == moirai.fate_timeout_kill(-signal.SIGKILL)


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="we are unable to get SIGKILL on windows",
)
def test_runner_timeout_sigkill_noexc(py_exec: PythonCmdBuilder) -> None:
    # NOTE: this can fail under VERY heavy load if the process won't be able to
    # mask SIGTERM
    fate = flnr.run_ex(
        py_exec("sigterm_ignore.py"),
        timeouts=flnr.ExecutionTimeouts(run=1.0),
        check=False,
    )
    assert fate == moirai.fate_timeout_kill(-signal.SIGKILL)


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="we are unable to get SIGKILL on windows",
)
def test_runner_timeout_sigkill_duration(py_exec: PythonCmdBuilder) -> None:
    # NOTE: this can fail under VERY heavy load if the process won't be able to
    # mask SIGTERM
    time_start = time.monotonic()
    timeouts = flnr.ExecutionTimeouts(run=1.0, terminate=2.0)
    fate = flnr.run_ex(
        py_exec("sigterm_ignore.py"),
        timeouts=timeouts,
        check=False,
    )
    time_end = time.monotonic()
    assert fate.returncode == -signal.SIGKILL
    assert timeouts.run is not None
    # note: we don't take drain into account, since we expect that pipes
    # are closed cleanly
    expected_duration = timeouts.run + timeouts.terminate
    assert time_duration_exceeds_value(time_end, time_start, expected_duration)
    assert time_end - time_start < 3 * expected_duration
