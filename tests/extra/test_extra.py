import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.lib.utils import PythonCmdBuilder

pytestmark = [
    pytest.mark.skipif(sys.platform != "linux", reason="Only for Linux"),
    pytest.mark.skipif(shutil.which("lsof") is None, reason="lsof is required"),
]

_parent_dir = Path(__file__).resolve().parent
_extra_tests_driver = _parent_dir / "really_borken.py"


@pytest.mark.extra
def test_child_pipe(py_exec: PythonCmdBuilder) -> None:
    subprocess.run(py_exec(_extra_tests_driver, "child_pipe"), check=True)


@pytest.mark.extra
def test_asyncio_transport(py_exec: PythonCmdBuilder) -> None:
    subprocess.run(
        py_exec(_extra_tests_driver, "asyncio_transport"), check=True
    )
