import sys
from pathlib import Path
from typing import NoReturn, cast

import pytest

from tests._support.utils import ExceptionMutator, ExcKindType, PythonCmdBuilder


@pytest.fixture(scope="session")
def test_resources() -> Path:
    """Return path to the resources directory."""
    return Path(__file__).parent / "_resources"


@pytest.fixture(scope="session")
def py_exec(test_resources: Path) -> PythonCmdBuilder:
    def _cmd(name: str | Path, *args: str | Path) -> list[str]:
        str_args = [str(arg) for arg in args]
        if isinstance(name, Path):
            script_path = name
        else:
            script_path = test_resources / "exec" / name
        assert script_path.is_file()
        return [
            str(sys.executable),
            str(script_path.resolve()),
            *str_args,
        ]

    return _cmd


@pytest.fixture(scope="session")
def captured_exc() -> ExceptionMutator:
    def _capture(exc: ExcKindType) -> ExcKindType:
        def raise_it() -> NoReturn:
            raise exc

        try:
            raise_it()
        except BaseException as caught:  # noqa: BLE001
            return cast("ExcKindType", caught)

    return _capture
