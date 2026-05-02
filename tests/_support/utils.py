import math
import os
import platform
import signal
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, TypeVar

TEST_DIR_ROOT = Path(__file__).resolve().parent.parent

ExcKindType = TypeVar("ExcKindType", bound=BaseException)


def pythonpath_env(repo_root: Path, base: Mapping[str, str]) -> dict[str, str]:
    existing = base.get("PYTHONPATH")
    if existing:
        pythonpath = os.pathsep.join([str(repo_root), existing])
    else:
        pythonpath = str(repo_root)

    return {"PYTHONPATH": pythonpath}


class ExceptionMutator(Protocol):
    def __call__(self, exc: ExcKindType) -> ExcKindType: ...


class PythonCmdBuilder(Protocol):
    def __call__(self, name: str | Path, *args: str | Path) -> list[str]: ...


def return_code_for_sigterm() -> int:
    if platform.system() == "Windows":
        return 1
    return -signal.SIGTERM


def return_code_for_sigkill() -> int:
    return -1


def time_duration_exceeds_value(
    time_end: float, time_start: float, value: float, jitter: float = 0.1
) -> bool:
    duration = math.fabs(time_end - time_start)
    return duration > (value - (value * jitter))
