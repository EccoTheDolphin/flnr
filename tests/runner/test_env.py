import io
import os
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

import flnr
from tests._support.probes import OutputMonitorProbe
from tests._support.utils import (
    PythonCmdBuilder,
)

TEST_DIR_ROOT = Path(__file__).resolve().parent


def _normalize_environment_dump(env_dump: str) -> str:
    # macOS may inject __CF_USER_TEXT_ENCODING into child environments.
    # It is platform noise, we filter this out
    filtered = [
        line
        for line in env_dump.splitlines()
        if not line.startswith("__CF_USER_TEXT_ENCODING: ")
    ]
    return "\n".join(filtered)


def _dump_dict_like_env(env: Mapping[str, str]) -> str:
    output: list[str] = []
    output.append("--- environment dump start ---")
    for name, value in sorted(env.items()):
        output.append(f"{name}: {value}")
    output.append("--- environment dump end---")
    # this weird double-join handles cases when newlines are inside env
    # variables
    return _normalize_environment_dump("\n".join(output))


def _run_environment_printout_check(
    py_exec: PythonCmdBuilder,
    env_in: Mapping[str, str] | None,
    env_expected: Mapping[str, str],
) -> None:
    bin_output = io.BytesIO()
    flnr.run_ex(
        py_exec("env_printout.py"),
        stdout_monitors=[OutputMonitorProbe(sink=bin_output)],
        env=env_in,
    )
    env_dump_normalized = _normalize_environment_dump(
        bin_output.getvalue().decode(encoding="utf-8")
    )
    env_dump = "\n".join(env_dump_normalized.splitlines())
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
