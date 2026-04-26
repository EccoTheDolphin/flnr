import io
from pathlib import Path

import flnr
from tests._support.utils import PythonCmdBuilder


def test_merged_streams(py_exec: PythonCmdBuilder) -> None:
    string_output = io.StringIO()
    flnr.run_ex(
        py_exec("stderrstdout_output.py"),
        stdout_monitors=[
            flnr.TextOutputMonitor(sink=string_output, encoding="utf-8")
        ],
        merge_std_streams=True,
    )
    assert string_output.getvalue() == "stderr outputstdout output"


def test_stdout_text(test_resources: Path, py_exec: PythonCmdBuilder) -> None:
    output = io.StringIO()
    input_file = test_resources / "data" / "default.txt"
    flnr.run_ex(
        py_exec("print_file.py", input_file),
        stdout_monitors=[flnr.TextOutputMonitor(sink=output, encoding="utf-8")],
    )
    assert input_file.read_text(encoding="utf-8") == output.getvalue()
