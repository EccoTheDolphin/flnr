import io
from pathlib import Path

import flnr
from tests._support.probes import OutputMonitorProbe
from tests._support.utils import PythonCmdBuilder


def test_logger_basic_bin(
    py_exec: PythonCmdBuilder, test_resources: Path
) -> None:
    output = io.BytesIO()
    input_file = test_resources / "data" / "default.txt"
    flnr.run_ex(
        py_exec("print_file.py", input_file),
        stdout_monitors=[OutputMonitorProbe(sink=output)],
    )
    assert input_file.read_bytes() == output.getvalue()


def test_logger_stdout_capture(py_exec: PythonCmdBuilder) -> None:
    stdout_bin = io.BytesIO()
    flnr.run_ex(
        py_exec("stderrstdout_output.py"),
        stdout_monitors=[OutputMonitorProbe(sink=stdout_bin)],
        merge_std_streams=False,
    )
    assert stdout_bin.getvalue() == b"stdout output"


def test_logger_stderr_capture(py_exec: PythonCmdBuilder) -> None:
    stderr_bin = io.BytesIO()
    flnr.run_ex(
        py_exec("stderrstdout_output.py"),
        stderr_monitors=[OutputMonitorProbe(sink=stderr_bin)],
        merge_std_streams=False,
    )
    assert stderr_bin.getvalue() == b"stderr output"


def test_logger_stderr_to_stdout(py_exec: PythonCmdBuilder) -> None:
    output_bin = io.BytesIO()
    flnr.run_ex(
        py_exec("stderrstdout_output.py"),
        stdout_monitors=[OutputMonitorProbe(sink=output_bin)],
        merge_std_streams=True,
    )
    assert output_bin.getvalue() == b"stderr outputstdout output"


def test_logger_stderr_to_stdout_default(py_exec: PythonCmdBuilder) -> None:
    output_bin = io.BytesIO()
    flnr.run_ex(
        py_exec("stderrstdout_output.py"),
        stdout_monitors=[OutputMonitorProbe(sink=output_bin)],
    )
    assert output_bin.getvalue() == b"stderr outputstdout output"


def test_logger_stderr_and_stdout_default(py_exec: PythonCmdBuilder) -> None:
    output_stdout_bin = io.BytesIO()
    output_stderr_bin = io.BytesIO()
    flnr.run_ex(
        py_exec("stderrstdout_output.py"),
        stdout_monitors=[OutputMonitorProbe(sink=output_stdout_bin)],
        stderr_monitors=[OutputMonitorProbe(sink=output_stderr_bin)],
    )
    assert output_stdout_bin.getvalue() == b"stdout output"
    assert output_stderr_bin.getvalue() == b"stderr output"


def test_logger_stderr_only_default(py_exec: PythonCmdBuilder) -> None:
    output_stderr_bin = io.BytesIO()
    flnr.run_ex(
        py_exec("stderrstdout_output.py"),
        stderr_monitors=[OutputMonitorProbe(sink=output_stderr_bin)],
    )
    assert output_stderr_bin.getvalue() == b"stderr output"
