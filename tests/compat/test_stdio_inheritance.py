"""Compatibility checks for subprocess stdio behavior relied on by flnr.

These tests document stdlib/platform behavior rather than flnr's public
runner contract.
"""

import asyncio
import subprocess
import sys

import pytest

from tests._support.utils import PythonCmdBuilder


def test_raw_subprocess_bound_to_stdout(
    py_exec: PythonCmdBuilder, capfdbinary: pytest.CaptureFixture[bytes]
) -> None:
    proc = subprocess.run(
        py_exec("stderrstdout_output.py"),
        stdout=None,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        check=True,
    )

    assert proc.returncode == 0

    captured = capfdbinary.readouterr()
    assert (captured.out, captured.err) == (
        b"stderr outputstdout output",
        b"",
    )


@pytest.mark.xfail(
    sys.platform.startswith("win"),
    reason=(
        "Windows asyncio does not merge stderr=STDOUT into inherited stdout."
    ),
    strict=True,
)
def test_raw_asyncio_stdout_inherit_stderr_stdout(
    py_exec: PythonCmdBuilder, capfdbinary: pytest.CaptureFixture[bytes]
) -> None:
    async def run() -> int:
        proc = await asyncio.create_subprocess_exec(
            *py_exec("stderrstdout_output.py"),
            stdout=None,
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.DEVNULL,
        )
        return await proc.wait()

    assert asyncio.run(run()) == 0

    captured = capfdbinary.readouterr()
    assert (captured.out, captured.err) == (
        b"stderr outputstdout output",
        b"",
    )


def test_raw_asyncio_stderr_to_fd1(
    py_exec: PythonCmdBuilder,
    capfdbinary: pytest.CaptureFixture[bytes],
) -> None:
    async def run() -> int:
        proc = await asyncio.create_subprocess_exec(
            *py_exec("stderrstdout_output.py"),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=None,
            # it looks like asyncio accepts explicit file descriptors here,
            # matching subprocess-style stdio routing even though the asyncio
            # docs do not spell this out clearly.
            # https://github.com/python/cpython/pull/107986
            stderr=1,
        )
        return await proc.wait()

    assert asyncio.run(run()) == 0

    captured = capfdbinary.readouterr()
    assert (captured.out, captured.err) == (
        b"stderr outputstdout output",
        b"",
    )
