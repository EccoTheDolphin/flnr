import io
import subprocess
from pathlib import Path

import pytest

import flnr
from tests._support.probes import OutputMonitorProbe
from tests._support.utils import PythonCmdBuilder


def test_stdout_file_capture(
    py_exec: PythonCmdBuilder, test_resources: Path
) -> None:
    output = io.BytesIO()
    input_file = test_resources / "data" / "default.txt"
    flnr.run_ex(
        py_exec("print_file.py", input_file),
        stdout_monitors=[OutputMonitorProbe(sink=output)],
    )
    assert input_file.read_bytes() == output.getvalue()


def test_stdout_only(py_exec: PythonCmdBuilder) -> None:
    stdout_bin = io.BytesIO()
    flnr.run_ex(
        py_exec("stderrstdout_output.py"),
        stdout_monitors=[OutputMonitorProbe(sink=stdout_bin)],
        merge_std_streams=False,
    )
    assert stdout_bin.getvalue() == b"stdout output"


def test_stderr_only(py_exec: PythonCmdBuilder) -> None:
    stderr_bin = io.BytesIO()
    flnr.run_ex(
        py_exec("stderrstdout_output.py"),
        stderr_monitors=[OutputMonitorProbe(sink=stderr_bin)],
        merge_std_streams=False,
    )
    assert stderr_bin.getvalue() == b"stderr output"


def test_explicit_merge(py_exec: PythonCmdBuilder) -> None:
    output_bin = io.BytesIO()
    flnr.run_ex(
        py_exec("stderrstdout_output.py"),
        stdout_monitors=[OutputMonitorProbe(sink=output_bin)],
        merge_std_streams=True,
    )
    assert output_bin.getvalue() == b"stderr outputstdout output"


def test_default_merge(py_exec: PythonCmdBuilder) -> None:
    output_bin = io.BytesIO()
    flnr.run_ex(
        py_exec("stderrstdout_output.py"),
        stdout_monitors=[OutputMonitorProbe(sink=output_bin)],
    )
    assert output_bin.getvalue() == b"stderr outputstdout output"


def test_default_split(py_exec: PythonCmdBuilder) -> None:
    output_stdout_bin = io.BytesIO()
    output_stderr_bin = io.BytesIO()
    flnr.run_ex(
        py_exec("stderrstdout_output.py"),
        stdout_monitors=[OutputMonitorProbe(sink=output_stdout_bin)],
        stderr_monitors=[OutputMonitorProbe(sink=output_stderr_bin)],
    )
    assert output_stdout_bin.getvalue() == b"stdout output"
    assert output_stderr_bin.getvalue() == b"stderr output"


def test_default_stderr_only(py_exec: PythonCmdBuilder) -> None:
    output_stderr_bin = io.BytesIO()
    flnr.run_ex(
        py_exec("stderrstdout_output.py"),
        stderr_monitors=[OutputMonitorProbe(sink=output_stderr_bin)],
    )
    assert output_stderr_bin.getvalue() == b"stderr output"


def test_stdout_bind_to_parent(
    py_exec: PythonCmdBuilder, capfdbinary: pytest.CaptureFixture[bytes]
) -> None:
    flnr.run_ex(
        py_exec("stderrstdout_output.py"),
        stdout_monitors=flnr.BIND_TO_PARENT,
        merge_std_streams=False,
    )

    captured = capfdbinary.readouterr()
    assert captured.out == b"stdout output"
    assert captured.err == b""


def test_stderr_bind_to_parent(
    py_exec: PythonCmdBuilder, capfdbinary: pytest.CaptureFixture[bytes]
) -> None:
    flnr.run_ex(
        py_exec("stderrstdout_output.py"),
        stderr_monitors=flnr.BIND_TO_PARENT,
        merge_std_streams=False,
    )

    captured = capfdbinary.readouterr()
    assert captured.out == b""
    assert captured.err == b"stderr output"


def test_stdout_bind_to_parent_default_merge(
    py_exec: PythonCmdBuilder, capfdbinary: pytest.CaptureFixture[bytes]
) -> None:
    flnr.run_ex(
        py_exec("stderrstdout_output.py"),
        stdout_monitors=flnr.BIND_TO_PARENT,
    )

    captured = capfdbinary.readouterr()
    assert (captured.out, captured.err) == (
        b"stderr outputstdout output",
        b"",
    )


def test_stdout_bind_to_parent_with_monitored_stderr(
    py_exec: PythonCmdBuilder, capfdbinary: pytest.CaptureFixture[bytes]
) -> None:
    output_stderr_bin = io.BytesIO()
    flnr.run_ex(
        py_exec("stderrstdout_output.py"),
        stdout_monitors=flnr.BIND_TO_PARENT,
        stderr_monitors=[OutputMonitorProbe(sink=output_stderr_bin)],
    )

    captured = capfdbinary.readouterr()
    assert captured.out == b"stdout output"
    assert captured.err == b""
    assert output_stderr_bin.getvalue() == b"stderr output"


def test_explicit_merge_rejects_stderr_bind_to_parent(
    py_exec: PythonCmdBuilder,
) -> None:
    with pytest.raises(
        ValueError,
        match="stderr_monitors must be None when merge_std_streams=True",
    ):
        flnr.run_ex(
            py_exec("py_true.py"),
            stdout_monitors=flnr.BIND_TO_PARENT,
            stderr_monitors=flnr.BIND_TO_PARENT,
            merge_std_streams=True,
        )


def test_stdin_inherit_from_parent(py_exec: PythonCmdBuilder) -> None:
    result = subprocess.run(
        py_exec("stdin_binding_driver.py", "inherit_stdin"),
        input=b"input payload",
        capture_output=True,
        check=True,
    )

    assert result.stdout == b"input payload"
    assert result.stderr == b""


def test_stdin_defaults_to_devnull(py_exec: PythonCmdBuilder) -> None:
    result = subprocess.run(
        py_exec("stdin_binding_driver.py", "default_stdin"),
        input=b"input payload",
        capture_output=True,
        check=True,
    )

    assert result.stdout == b"<empty>"
    assert result.stderr == b""
