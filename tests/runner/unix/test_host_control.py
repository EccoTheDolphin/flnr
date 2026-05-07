import re
import signal
import subprocess
import sys
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

import flnr
from tests._support.utils import (
    TEST_DIR_ROOT,
    PythonCmdBuilder,
    return_code_for_sigterm,
)


class _FailingTracerImpl:
    def trace_command(
        self,
        *,
        cmd: tuple[str, ...],
        cwd: Path | None,
        env: Mapping[str, str],
        host_env: Mapping[str, str],
    ) -> None:
        del cmd, cwd, env, host_env
        error_msg = "logger failed"
        raise RuntimeError(error_msg)


def test_runner_host_signal_no_trigger(py_exec: PythonCmdBuilder) -> None:
    request = flnr.HostTerminationRequest()
    try:
        flnr.run_ex(
            py_exec("py_true.py"),
            host_termination=flnr.HostTerminationRequest.HOST_SIGNALS,
        )
    finally:
        request.close()


def test_runner_host_signals_unchanged_when_tracer_fails(
    py_exec: PythonCmdBuilder,
) -> None:
    old_sigint = signal.getsignal(signal.SIGINT)
    old_sigterm = signal.getsignal(signal.SIGTERM)

    with pytest.raises(RuntimeError, match="logger failed"):
        flnr.run_ex(
            py_exec("py_true.py"),
            host_termination=flnr.HostTerminationRequest.HOST_SIGNALS,
            tracer=_FailingTracerImpl(),
        )

    assert signal.getsignal(signal.SIGINT) == old_sigint
    assert signal.getsignal(signal.SIGTERM) == old_sigterm


@dataclass
class _HostControlTriple:
    proc: subprocess.Popen[str]
    parent_pid: int
    child_pid: int


def _hostcontrol_triple(
    control_type: str, args: Sequence[str]
) -> _HostControlTriple:
    proc = subprocess.Popen(
        [
            sys.executable,
            str(TEST_DIR_ROOT / "_resources" / "exec" / "flnr_signal.py"),
            control_type,
            *args,
        ],
        stdout=subprocess.PIPE,
        encoding="latin-1",
    )
    assert proc.stdout is not None
    parent_match = re.match(
        r"process is started, pid = (\d+)", proc.stdout.readline()
    )

    pulse1 = proc.stdout.readline().rstrip()
    pulse2 = proc.stdout.readline().rstrip()

    child_pid_string = pulse2 if pulse1 == "child is ready" else pulse1
    child_match = re.match(r"child pid = (\d+)", child_pid_string)

    assert parent_match is not None
    parent_pid_group = parent_match.group(1)
    assert parent_pid_group is not None

    assert child_match is not None
    child_pid_group = child_match.group(1)
    assert child_pid_group is not None

    return _HostControlTriple(
        proc=proc,
        parent_pid=int(parent_pid_group),
        child_pid=int(child_pid_group),
    )


@pytest.mark.parametrize("termination_type", ["host_signals", "extrq"])
def test_runner_host_exceptions_sigint(termination_type: str) -> None:
    hostcontrol = _hostcontrol_triple(
        termination_type,
        [str(TEST_DIR_ROOT / "_resources" / "exec" / "cat_dev_random.py")],
    )
    hostcontrol.proc.send_signal(signal.SIGINT)
    sigterm_code = return_code_for_sigterm()
    child_fate = (
        f"returncode={sigterm_code}, decision=external_request, "
        "method=terminate"
    )
    assert hostcontrol.proc.stdout is not None
    assert child_fate == hostcontrol.proc.stdout.readline().rstrip()
    assert hostcontrol.proc.stdout.readline().rstrip() == "done"
    hostcontrol.proc.wait()


@pytest.mark.parametrize("termination_type", ["host_signals", "extrq"])
def test_runner_host_exceptions_sigterm_ignored(termination_type: str) -> None:
    hostcontrol = _hostcontrol_triple(
        termination_type,
        [str(TEST_DIR_ROOT / "_resources" / "exec" / "sigterm_ignore.py")],
    )
    assert hostcontrol.proc.stdout is not None
    hostcontrol.proc.send_signal(signal.SIGTERM)
    sigkill_code = -signal.SIGKILL
    child_fate = (
        f"returncode={sigkill_code}, decision=external_request, method=kill"
    )
    assert child_fate == hostcontrol.proc.stdout.readline().rstrip()
    assert hostcontrol.proc.stdout.readline().rstrip() == "done"
    hostcontrol.proc.wait()


def _run_flnr_with_hostsignals() -> None:
    expected_err = (
        "automatic termination on host signals is supported only for main "
        "Python thread"
    )
    with pytest.raises(RuntimeError, match=expected_err):
        flnr.run_ex(
            [sys.executable],
            host_termination=flnr.HostTerminationRequest.HOST_SIGNALS,
        )


def test_runner_host_signals_not_main() -> None:
    t = threading.Thread(target=_run_flnr_with_hostsignals)
    t.start()
    t.join()
