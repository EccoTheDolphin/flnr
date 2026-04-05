import asyncio
import io
import os
import re
import signal
import sys
import time
from collections.abc import Mapping

import pytest

import flnr
from tests.lib.utils import (
    PythonCmdBuilder,
    TextOutputMonitor,
    return_code_for_sigterm,
    time_duration_exceeds_value,
)


def test_runner_success(py_exec: PythonCmdBuilder) -> None:
    return_code = flnr.run_shell_ex(py_exec("py_true.py"))
    assert return_code == 0


def test_runner_failure_exc(py_exec: PythonCmdBuilder) -> None:
    with pytest.raises(flnr.CommandFailedError):
        flnr.run_shell_ex(py_exec("py_false"))
    with pytest.raises(flnr.CommandFailedError):
        flnr.run_shell_ex(py_exec("py_false"), check=True)


def test_runner_could_not_find_file() -> None:
    with pytest.raises(FileNotFoundError):
        flnr.run_shell_ex(["/lalallalalala/kambala"])


def test_runner_failure_noexc(py_exec: PythonCmdBuilder) -> None:
    return_code = flnr.run_shell_ex(py_exec("py_false"), check=False)
    assert return_code != 0


def test_runner_timeout_sigterm(py_exec: PythonCmdBuilder) -> None:
    with pytest.raises(
        flnr.CommandFailedError,
        match=f"unexpected return code {return_code_for_sigterm()}$",
    ):
        flnr.run_shell_ex(
            py_exec("cat_dev_random.py"),
            timeouts=flnr.ExecutionTimeouts(run=5.0),
        )


def test_runner_timeout_sigterm_noexc(py_exec: PythonCmdBuilder) -> None:
    return_code = flnr.run_shell_ex(
        py_exec("cat_dev_random.py"),
        timeouts=flnr.ExecutionTimeouts(run=5.0),
        check=False,
    )
    assert return_code == return_code_for_sigterm()


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="we are unable to get SIGKILL on windows",
)
def test_runner_timeout_sigkill(py_exec: PythonCmdBuilder) -> None:
    # NOTE: this can fail under VERY heavy load if the process won't be
    # able mask SIGTERM
    with pytest.raises(
        flnr.CommandFailedError,
        match=f"unexpected return code -{signal.SIGKILL}$",
    ):
        flnr.run_shell_ex(
            py_exec("sigterm_ignore.py"),
            timeouts=flnr.ExecutionTimeouts(run=1.0),
        )


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="we are unable to get SIGKILL on windows",
)
def test_runner_timeout_sigkill_noexc(py_exec: PythonCmdBuilder) -> None:
    # NOTE: this can fail under VERY heavy load if the process won't be
    # able mask SIGTERM
    return_code = flnr.run_shell_ex(
        py_exec("sigterm_ignore.py"),
        timeouts=flnr.ExecutionTimeouts(run=1.0),
        check=False,
    )
    assert return_code == -signal.SIGKILL


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="we are unable to get SIGKILL on windows",
)
def test_runner_timeout_sigkill_duration(py_exec: PythonCmdBuilder) -> None:
    # NOTE: this can fail under VERY heavy load if the process won't be
    # able mask SIGTERM
    time_start = time.monotonic()
    return_code = flnr.run_shell_ex(
        py_exec("sigterm_ignore.py"),
        timeouts=flnr.ExecutionTimeouts(run=1.0, terminate=2.0),
        check=False,
    )
    assert return_code == -signal.SIGKILL
    time_end = time.monotonic()
    expected_duration = 2.9
    assert time_end - time_start > expected_duration


def _run_timeout_duration_test(
    py_exec: PythonCmdBuilder, timeout: float
) -> None:
    time_start = time.monotonic()
    # NOTE: this is potentially a brittle test
    return_code = flnr.run_shell_ex(
        py_exec("cat_dev_random.py"),
        timeouts=flnr.ExecutionTimeouts(run=timeout),
        check=False,
    )
    assert return_code == return_code_for_sigterm()
    time_end = time.monotonic()
    assert time_duration_exceeds_value(time_end, time_start, timeout)


def test_runner_timeout_2seconds(py_exec: PythonCmdBuilder) -> None:
    _run_timeout_duration_test(py_exec, 2)


def test_runner_timeout_10seconds(py_exec: PythonCmdBuilder) -> None:
    _run_timeout_duration_test(py_exec, 10)


async def _run_inside_async_context(py_exec: PythonCmdBuilder) -> None:
    flnr.run_shell_ex(py_exec("py_true.py"))


def test_runner_no_async_context(py_exec: PythonCmdBuilder) -> None:
    with pytest.raises(
        RuntimeError,
        match=re.escape(
            "run_shell_ex() cannot be called from an async context"
        ),
    ):
        asyncio.run(_run_inside_async_context(py_exec))


def _dump_dict_like_env(env: Mapping[str, str]) -> str:
    output: list[str] = []
    output.append("--- environment dump start ---")
    for name, value in sorted(env.items()):
        output.append(f"{name}: {value}")
    output.append("--- environment dump end---\n")
    return "\n".join(output)


def _run_environment_printout_check(
    py_exec: PythonCmdBuilder,
    env_in: Mapping[str, str] | None,
    env_expected: Mapping[str, str],
) -> None:
    env_dump_stream = io.StringIO()
    flnr.run_shell_ex(
        py_exec("env_printout.py"),
        stdout_observers=[
            TextOutputMonitor(sink=env_dump_stream, encoding="utf-8"),
        ],
        env=env_in,
    )
    env_dump = env_dump_stream.getvalue()
    assert env_dump == _dump_dict_like_env(env_expected)


def test_env_context_copy(py_exec: PythonCmdBuilder) -> None:
    _run_environment_printout_check(
        py_exec, os.environ.copy(), os.environ.copy()
    )


def test_env_context_default(py_exec: PythonCmdBuilder) -> None:
    _run_environment_printout_check(
        py_exec,
        None,
        os.environ.copy(),
    )


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="windows refuses to start process with empty environment",
)
def test_env_context_empty(py_exec: PythonCmdBuilder) -> None:
    # Apparently python interpreter always sets LC_CTYPE
    _run_environment_printout_check(py_exec, {}, {"LC_CTYPE": "C.UTF-8"})


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="windows refuses to start process without some defaults",
)
def test_env_context_custom(py_exec: PythonCmdBuilder) -> None:
    _run_environment_printout_check(
        py_exec,
        {"lalala": "kambala", "a": "b"},
        {"LC_CTYPE": "C.UTF-8", "a": "b", "lalala": "kambala"},
    )
