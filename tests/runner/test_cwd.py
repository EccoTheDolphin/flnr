import io
import shutil
from pathlib import Path

import pytest

import flnr
from tests._support.probes import OutputMonitorProbe
from tests._support.utils import (
    PythonCmdBuilder,
)


def test_child_observes_cwd(
    py_exec: PythonCmdBuilder, tmp_path: Path, test_resources: Path
) -> None:
    bin_output = io.BytesIO()

    default_data_source = test_resources / "data" / "default.txt"
    input_file_name = "contents.data"
    shutil.copyfile(default_data_source, tmp_path / input_file_name)
    flnr.run_ex(
        py_exec("print_file.py", input_file_name),
        stdout_monitors=[OutputMonitorProbe(sink=bin_output)],
        cwd=tmp_path,
    )

    assert bin_output.getvalue() == default_data_source.read_bytes()


def test_missing_cwd_fails(py_exec: PythonCmdBuilder, tmp_path: Path) -> None:
    with pytest.raises((FileNotFoundError, NotADirectoryError)) as exc_info:
        flnr.run_ex(py_exec("py_true.py"), cwd=tmp_path / "kambala")

    # windows is obnoxious and does not name the directory
    msg = str(exc_info.value)
    assert "kambala" in msg or "The directory name is invalid" in msg
