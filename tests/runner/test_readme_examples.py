import io
import pathlib
import py_compile
import sys

import pytest

import flnr
from tests._support import moirai
from tests._support.utils import (
    return_code_for_sigterm,
)


def test_01_simple(test_resources: pathlib.Path) -> None:
    output = io.StringIO()
    result = flnr.run_ex(
        [sys.executable, test_resources / "readme_examples" / "01_simple.py"],
        stdout_monitors=[flnr.TextOutputMonitor(sink=output)],
    )
    out_lines = output.getvalue().splitlines()
    assert result == moirai.fate_no_intervention(0)
    assert out_lines[-1] == f"{moirai.fate_no_intervention(0)}"


def test_02_host_termination(test_resources: pathlib.Path) -> None:
    py_compile.compile(
        str(test_resources / "readme_examples" / "02_host_termination.py"),
        doraise=True,
    )


def test_03_host_signals(test_resources: pathlib.Path) -> None:
    py_compile.compile(
        str(test_resources / "readme_examples" / "03_host_signals.py"),
        doraise=True,
    )


def test_04_output_mon(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    test_resources: pathlib.Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    output = io.StringIO()
    result = flnr.run_ex(
        [
            sys.executable,
            test_resources / "readme_examples" / "04_output_mon.py",
        ],
        stdout_monitors=[flnr.TextOutputMonitor(sink=output)],
    )

    out_lines = output.getvalue().splitlines()
    expected_fate = moirai.fate_timeout_terminate(return_code_for_sigterm())

    assert result == moirai.fate_no_intervention(0)
    assert out_lines[-1] == f"fate: {expected_fate}"


def test_05_env_mon(test_resources: pathlib.Path) -> None:
    output = io.StringIO()
    result = flnr.run_ex(
        [sys.executable, test_resources / "readme_examples" / "05_env_mon.py"],
        stdout_monitors=[flnr.TextOutputMonitor(sink=output)],
    )

    out_lines = output.getvalue().splitlines()
    expected_fate = moirai.fate_timeout_terminate(return_code_for_sigterm())

    assert result == moirai.fate_no_intervention(0)
    assert out_lines[-1] == f"fate: {expected_fate}"
