import sys
from pathlib import Path

import pytest

from tests.lib.utils import PythonCmdBuilder


@pytest.fixture(scope="session")
def test_resources() -> Path:
    """Return path to the resources directory."""
    return Path(__file__).parent / "resources"


@pytest.fixture(scope="session")
def py_exec(test_resources: Path) -> PythonCmdBuilder:
    def _cmd(name: str | Path, *args: str | Path) -> list[str]:
        str_args = [str(arg) for arg in args]
        if isinstance(name, Path):
            script_path = name
        else:
            script_path = test_resources / "exec" / name
        return [
            str(sys.executable),
            str(script_path.resolve()),
            *str_args,
        ]

    return _cmd
