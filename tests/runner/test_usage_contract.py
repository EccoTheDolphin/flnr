import asyncio
import re
from collections.abc import Sequence

import pytest

import flnr
from tests._support import moirai
from tests._support.utils import (
    PythonCmdBuilder,
    return_code_for_sigterm,
)


def test_runner_could_not_find_file() -> None:
    with pytest.raises(FileNotFoundError):
        flnr.run_ex(["/lalallalalala/kambala"])


def test_runner_empty_cmd() -> None:
    with pytest.raises(ValueError, match="cmd must not be empty"):
        flnr.run_ex([])


def test_runner_not_a_list_args() -> None:
    with pytest.raises(
        TypeError,
        match=(
            "cmd must be a sequence of argument items, not a string-like object"
        ),
    ):
        flnr.run_ex("/usr/bin/env")


def test_runner_stdin_of_incorrect_type() -> None:
    with pytest.raises(
        TypeError,
        match=re.escape("stdin must be None or flnr.INHERIT_STDIN"),
    ):
        flnr.run_ex(["/usr/bin/env"], stdin="lalala")  # type: ignore[arg-type]


async def _run_inside_async_context(py_exec: PythonCmdBuilder) -> None:
    flnr.run_ex(py_exec("py_true.py"))


def test_runner_no_async_context(py_exec: PythonCmdBuilder) -> None:
    with pytest.raises(
        RuntimeError,
        match=re.escape("run_ex() cannot be called from an async context"),
    ):
        asyncio.run(_run_inside_async_context(py_exec))


async def _run_in_threads(
    py_exec: PythonCmdBuilder,
) -> Sequence[flnr.ProcessFate | BaseException]:
    return await asyncio.gather(
        asyncio.to_thread(flnr.run_ex, py_exec("py_true.py")),
        asyncio.to_thread(flnr.run_ex, py_exec("py_false.py"), check=False),
        asyncio.to_thread(
            flnr.run_ex,
            py_exec("cat_dev_random.py"),
            timeouts=flnr.ExecutionTimeouts(run=1),
        ),
        return_exceptions=True,
    )


def test_run_in_threads(py_exec: PythonCmdBuilder) -> None:
    results = asyncio.run(_run_in_threads(py_exec))
    assert results[0] == moirai.fate_no_intervention(0)
    assert results[1] == moirai.fate_no_intervention(1)
    assert isinstance(results[2], flnr.CommandFailedError)
    expected_code = return_code_for_sigterm()
    assert results[2].fate == moirai.fate_timeout_terminate(expected_code)
