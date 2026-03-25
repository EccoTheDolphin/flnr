import io
from pathlib import Path

import flnr
from tests.lib.utils import BinaryCapture, PythonCmdBuilder, TextOutputMonitor


def test_logger_basic_text(
    py_exec: PythonCmdBuilder, test_resources: Path
) -> None:
    output = io.StringIO()
    input_file = test_resources / "data" / "miami_nights.txt"
    flnr.run_shell_ex(
        py_exec("print_file.py", input_file),
        stdout_observers=[TextOutputMonitor(sink=output)],
    )
    assert input_file.read_text(encoding="utf-8") == output.getvalue()


def test_logger_basic_bin(
    py_exec: PythonCmdBuilder, test_resources: Path
) -> None:
    output = io.BytesIO()
    input_file = test_resources / "data" / "miami_nights.txt"
    flnr.run_shell_ex(
        py_exec("print_file.py", input_file),
        stdout_observers=[BinaryCapture(sink=output)],
    )
    assert input_file.read_bytes() == output.getvalue()


def test_logger_stdout_capture(py_exec: PythonCmdBuilder) -> None:
    stderr_output = io.StringIO()
    flnr.run_shell_ex(
        py_exec("stderrstdout_output.py"),
        stdout_observers=[TextOutputMonitor(sink=stderr_output)],
        merge_std_streams=False,
    )
    assert stderr_output.getvalue() == "stdout output"


def test_logger_stderr_capture(py_exec: PythonCmdBuilder) -> None:
    stderr_output = io.StringIO()
    flnr.run_shell_ex(
        py_exec("stderrstdout_output.py"),
        stderr_observers=[
            TextOutputMonitor(sink=stderr_output, encoding="utf-8")
        ],
        merge_std_streams=False,
    )
    assert stderr_output.getvalue() == "stderr output"


def test_logger_stderr_to_stdout(py_exec: PythonCmdBuilder) -> None:
    stderr_output = io.StringIO()
    flnr.run_shell_ex(
        py_exec("stderrstdout_output.py"),
        stdout_observers=[TextOutputMonitor(sink=stderr_output)],
        merge_std_streams=True,
    )
    assert stderr_output.getvalue() == "stderr outputstdout output"


def test_logger_stderr_to_stdout_default(py_exec: PythonCmdBuilder) -> None:
    stderr_output = io.StringIO()
    flnr.run_shell_ex(
        py_exec("stderrstdout_output.py"),
        stdout_observers=[TextOutputMonitor(sink=stderr_output)],
    )
    assert stderr_output.getvalue() == "stderr outputstdout output"
