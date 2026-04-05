import math
import platform
import signal
from pathlib import Path
from typing import Protocol

from .binmon import BinaryCapture as BinaryCapture
from .proc_mock import ProcMonImpl as ProcMonImpl
from .proc_mock import StreamControl as StreamControl
from .text_output_mon import TextOutputMonitor as TextOutputMonitor


class PythonCmdBuilder(Protocol):
    def __call__(self, name: str | Path, *args: str | Path) -> list[str]: ...


def return_code_for_sigterm() -> int:
    if platform.system() == "Windows":
        return 1
    return -signal.SIGTERM


def time_duration_exceeds_value(
    time_end: float, time_start: float, value: float, jitter: float = 0.1
) -> int:
    duration = math.fabs(time_end - time_start)
    return duration > (value - (value * jitter))
