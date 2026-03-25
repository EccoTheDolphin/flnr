import asyncio
import io
import os
import re
import signal
import time
from collections.abc import Mapping
from pathlib import Path

import pytest

import flnr


def test_runner_success() -> None:
    return_code = flnr.run_shell_ex(["true"])
    assert return_code == 0


def test_runner_failure_exc() -> None:
    with pytest.raises(flnr.CommandFailedError):
        flnr.run_shell_ex(["false"])
    with pytest.raises(flnr.CommandFailedError):
        flnr.run_shell_ex(["false"], check=True)


def test_runner_could_not_find_file() -> None:
    with pytest.raises(FileNotFoundError):
        flnr.run_shell_ex(["/lalallalalala/kambala"])


def test_runner_failure_noexc() -> None:
    return_code = flnr.run_shell_ex(["false"], check=False)
    assert return_code != 0


def test_runner_timeout_sigterm() -> None:
    with pytest.raises(
        flnr.CommandFailedError,
        match=f"unexpected return code -{signal.SIGTERM}$",
    ):
        flnr.run_shell_ex(["cat", "/dev/random"], timeout=1.0)


def test_runner_timeout_sigterm_noexc() -> None:
    return_code = flnr.run_shell_ex(
        ["cat", "/dev/random"], timeout=1.0, check=False
    )
    assert return_code == -signal.SIGTERM


def test_runner_timeout_sigkill(test_resources: Path) -> None:
    # NOTE: this can fail under VERY heavy load if the process won't be
    # able mask SIGTERM
    with pytest.raises(
        flnr.CommandFailedError,
        match=f"unexpected return code -{signal.SIGKILL}$",
    ):
        flnr.run_shell_ex(
            [test_resources / "exec" / "sigterm_ignore.py"],
            timeout=1.0,
        )


def test_runner_timeout_sigkill_noexc(test_resources: Path) -> None:
    # NOTE: this can fail under VERY heavy load if the process won't be
    # able mask SIGTERM
    return_code = flnr.run_shell_ex(
        [test_resources / "exec" / "sigterm_ignore.py"],
        timeout=1.0,
        check=False,
    )
    assert return_code == -signal.SIGKILL


def _run_timeout_duration_test(timeout: float) -> None:
    time_start = time.monotonic()
    # NOTE: this is potentially a brittle test
    return_code = flnr.run_shell_ex(
        ["cat", "/dev/random"],
        timeout=timeout,
        check=False,
    )
    assert return_code == -signal.SIGTERM
    time_end = time.monotonic()
    assert time_end - time_start > timeout


def test_runner_timeout_2seconds() -> None:
    _run_timeout_duration_test(2)


def test_runner_timeout_10seconds() -> None:
    _run_timeout_duration_test(10)


async def _run_inside_async_context() -> None:
    flnr.run_shell_ex(["true"])


def test_runner_no_async_context() -> None:
    with pytest.raises(
        RuntimeError,
        match=re.escape(
            "run_shell_ex() cannot be called from an async context"
        ),
    ):
        asyncio.run(_run_inside_async_context())


def _dump_dict_like_env(env: Mapping[str, str]) -> str:
    output: list[str] = []
    output.append("--- environment dump start ---")
    for name, value in sorted(env.items()):
        output.append(f"{name}: {value}")
    output.append("--- environment dump end---\n")
    return "\n".join(output)


def _run_environment_printout_check(
    test_resources: Path,
    env_in: Mapping[str, str] | None,
    env_expected: Mapping[str, str],
) -> None:
    env_dump_stream = io.StringIO()
    flnr.run_shell_ex(
        [test_resources / "exec" / "env_printout.py"],
        stdout_observers=[
            flnr.LoggingOutputMonitor(sink=env_dump_stream, encoding="utf-8"),
        ],
        env=env_in,
    )
    env_dump = env_dump_stream.getvalue()
    assert env_dump == _dump_dict_like_env(env_expected)


def test_env_context_copy(test_resources: Path) -> None:
    _run_environment_printout_check(
        test_resources, os.environ.copy(), os.environ.copy()
    )


def test_env_context_default(test_resources: Path) -> None:
    _run_environment_printout_check(
        test_resources,
        None,
        os.environ.copy(),
    )


def test_env_context_empty(test_resources: Path) -> None:
    # Apparently python interpreter always sets LC_CTYPE
    _run_environment_printout_check(test_resources, {}, {"LC_CTYPE": "C.UTF-8"})


def test_env_context_custom(test_resources: Path) -> None:
    _run_environment_printout_check(
        test_resources,
        {"lalala": "kambala", "a": "b"},
        {"LC_CTYPE": "C.UTF-8", "a": "b", "lalala": "kambala"},
    )
