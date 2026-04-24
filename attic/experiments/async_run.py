from __future__ import annotations

import asyncio
import io  # noqa: TC003
import pathlib
import sys
import time
from collections.abc import Sequence  # noqa: TC003
from contextlib import ExitStack
from dataclasses import dataclass
from typing import TextIO

import flnr

PROGRAM_TO_RUN = "tests/_resources/exec/cat_dev_random.py"


@dataclass(frozen=True)
class RunArtifacts:
    bin_path: pathlib.Path
    text_path: pathlib.Path


async def _run_in_threads(
    *,
    timeout: float,
    sink_pairs: Sequence[tuple[io.IOBase, TextIO]],
) -> Sequence[flnr.ProcessFate | flnr.CommandFailedError | BaseException]:
    tasks = [
        asyncio.to_thread(
            flnr.run_ex,
            [sys.executable, PROGRAM_TO_RUN],
            stdout_monitors=[
                flnr.BinaryOutputMonitor(sink=bin_sink),
                flnr.TextOutputMonitor(sink=text_sink, encoding="latin-1"),
            ],
            timeouts=flnr.ExecutionTimeouts(run=timeout),
        )
        for bin_sink, text_sink in sink_pairs
    ]

    return await asyncio.gather(*tasks, return_exceptions=True)


def main() -> None:
    n_runs = 4
    timeout = 5.0

    artifacts = [
        RunArtifacts(
            bin_path=pathlib.Path(f"_tmp-bin-{i}.bin"),
            text_path=pathlib.Path(f"_tmp-text-{i}.log"),
        )
        for i in range(1, n_runs + 1)
    ]

    with ExitStack() as stack:
        sink_pairs = [
            (
                stack.enter_context(art.bin_path.open("wb")),
                stack.enter_context(art.text_path.open("w", encoding="utf-8")),
            )
            for art in artifacts
        ]

        time_start = time.monotonic()
        results = asyncio.run(
            _run_in_threads(timeout=timeout, sink_pairs=sink_pairs)
        )
        time_end = time.monotonic()

    for i, result in enumerate(results, start=1):
        assert isinstance(result, flnr.CommandFailedError)
        print(f"run #{i}: {result.fate}")

    for i, art in enumerate(artifacts, start=1):
        print(
            f"run #{i} sizes: "
            f"{art.bin_path.name}={art.bin_path.stat().st_size} bytes, "
            f"{art.text_path.name}={art.text_path.stat().st_size} bytes"
        )

    duration = time_end - time_start
    print(f"the whole run took {duration} seconds")


if __name__ == "__main__":
    main()
