from __future__ import annotations

import statistics
import subprocess
import sys
import time
from collections.abc import Callable, Sequence

import flnr


class PMon(flnr.EnvironmentMonitor):
    def __init__(self, *, period: float) -> None:
        super().__init__(period=period)

    def on_start(self, _: int, __: Sequence[str]) -> None:
        pass

    def observe(self, _: int) -> None:
        pass

    def on_end(self, _: flnr.ProcessFate) -> None:
        pass


class DummyMonitor(flnr.OutputMonitor):
    def process(self, _: bytes, __: float) -> None:
        pass

    def on_disable(self, _: flnr.OutputMonitorDisableReason, __: float) -> None:
        pass


REPEATS: int = 100
WARMUP: int = 5
INNER: int = 1

CommandFn = Callable[[], None]


def measure(
    fn: CommandFn,
    repeats: int = REPEATS,
    warmup: int = WARMUP,
    inner: int = INNER,
) -> list[float]:
    for _ in range(warmup):
        for _ in range(inner):
            fn()

    samples: list[float] = []
    for _ in range(repeats):
        t0: float = time.monotonic()
        for _ in range(inner):
            fn()
        t1: float = time.monotonic()
        samples.append((t1 - t0) / inner)

    return samples


def trimmed_mean(values: list[float], trim: int = 2) -> float:
    if len(values) <= 2 * trim:
        return statistics.mean(values)
    sorted_values: list[float] = sorted(values)
    return statistics.mean(sorted_values[trim:-trim])


def print_stats(name: str, samples: list[float]) -> None:
    avg: float = statistics.mean(samples)
    med: float = statistics.median(samples)
    tavg: float = trimmed_mean(samples)

    print(f"{name}:")
    print(f"  avg:     {avg * 1000:.3f} ms")
    print(f"  median:  {med * 1000:.3f} ms")
    print(f"  trimmed: {tavg * 1000:.3f} ms")
    print(
        f"  min/max: {min(samples) * 1000:.3f} / {max(samples) * 1000:.3f} ms"
    )
    print()


def cmd_run(cmd: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(cmd, capture_output=True, check=True)


PROGRAM_TO_RUN = "tests/_resources/exec/py_true.py"


def run_subprocess() -> None:
    cmd_run([sys.executable, PROGRAM_TO_RUN])


def run_flnr() -> None:
    flnr.run_ex(
        [sys.executable, PROGRAM_TO_RUN],
        stdout_monitors=[DummyMonitor()],
        environment_monitors=[PMon(period=1.0)],
    )


def main() -> None:
    sp: list[float] = measure(run_subprocess)
    ff: list[float] = measure(run_flnr)

    print_stats("subprocess", sp)
    print_stats("flnr", ff)

    sp_avg: float = trimmed_mean(sp)
    ff_avg: float = trimmed_mean(ff)

    print("comparison:")
    print(f"  ratio: {(ff_avg / sp_avg):.3f}x")
    print(f"  delta: {(ff_avg - sp_avg) * 1000:.3f} ms")


if __name__ == "__main__":
    main()
