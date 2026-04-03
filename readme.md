# `flnr`

<!-- markdownlint-disable link-fragments -->

<!-- mdformat-toc start --slug=gitlab --no-anchors --maxlevel=6 --minlevel=1 -->

- [`flnr`](#flnr)
  - [About](#about)
  - [Raison d'être](#raison-d%C3%AAtre)
  - [Examples](#examples)
    - [Minimal usage](#minimal-usage)
    - [Output monitoring](#output-monitoring)
    - [System monitoring](#system-monitoring)
  - [Usage Notes](#usage-notes)
  - [Requirements](#requirements)
  - [Alternatives](#alternatives)
  - [Development](#development)
    - [Using uv](#using-uv)
      - [Common Commands](#common-commands)

<!-- mdformat-toc end -->

<!-- markdownlint-enable link-fragments -->

## About

**flnr** is a minimal framework that takes control of process execution and
calls your code while streaming its output.

> [!NOTE]
> The library uses asyncio under the hood. User-supplied callbacks are
> expected to be synchronous. Usage of asyncio is an implementation detail and
> users should not rely on its usage in future versions of the library.

> [!WARNING]
> `flnr` is **not** designed for use inside an existing async context.
> Calling `run_shell_ex` creates its own event loop and blocks the caller. Using
> it from an async context raises `RuntimeError`.

`flnr` provides the provides scaffolding for wrapping external process
execution, while handling output flow and error propagation.

Design principles:

- Single‑threaded, blocking
- monitoring logic executes synchronously in the same execution context as output
  processing. **no isolation** is provided.

Monitors are invoked as data is read from the child process. If you need
concurrency or isolation, this tool is not a good fit.

## Raison d'être

If you have a test suite that:

- Runs in CI
- Launches external programs as child processes
- Fails sporadically and provides little insight into why

…and observability is a luxury you don't have, **read on**.

The pattern above is a typical situation when integrating third‑party tools or
test suites into your automation pipeline.

Debugging sporadic failures is difficult, especially in complex environments
where failures can originate from tests, the product under test, or the
surrounding infrastructure—where Dark And Evil monsters like the Dreaded
Kubernetes roam the field. `flnr` gives you just enough visibility to
understand what happened - without building or adopting a full observability
stack.

> [!NOTE]
> The implementation is a single‑threaded, synchronous, cooperative subprocess
> runner where user code runs inline and can stall the entire system by design.
> This is what it is. Take it or leave it.

## Examples

### Minimal usage

```python
import flnr

flnr.run_shell_ex(
    ["echo", "hello"],
    timeouts=flnr.ExecutionTimeouts(run=5.0),
)
```

### Output monitoring

Runs an external command with two output monitors: one tracks throughput,
another adds timestamps to each line.

```python
import io
import sys
import pathlib

from datetime import datetime
import flnr


class ThroughputMonitor(flnr.OutputMonitor):
    def __init__(self, *, sink: io.IOBase) -> None:
        self.sink = sink
        self.bytes_received = 0

    def process(self, data: bytes) -> None:
        self.bytes_received += len(data)
        self.sink.write(f"{self.bytes_received} bytes\n".encode("latin-1"))


class TimestampingMonitor(flnr.OutputMonitor):
    def __init__(self, *, sink: io.IOBase) -> None:
        self.sink = sink
        self.ils = flnr.IncrementalLineSplitter()

    def process(self, data: bytes) -> None:
        for line in self.ils.feed(data):
            timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
            self.sink.write(timestamp.encode("latin-1"))
            self.sink.write(b" ")
            self.sink.write(line)


try:
    with (
        pathlib.Path("throughput.log").open("wb") as throughput_log,
        pathlib.Path("timestamped.bin").open("wb") as timestamped_output,
    ):
        flnr.run_shell_ex(
            ["cat", "/dev/random"],
            stdout_observers=[
                ThroughputMonitor(sink=throughput_log),
                TimestampingMonitor(sink=timestamped_output),
            ],
            timeouts=flnr.ExecutionTimeouts(run=5.0),
            merge_std_streams=True,
        )
except flnr.CommandFailedError as e:
    print(f"{e}")
```

### System monitoring

A process monitor that hooks into the child process lifecycle. Extend
`observe()` to collect system stats (e.g., via ps, /proc, or psutil).

```python
import sys

import flnr

from typing import TextIO, Sequence


class ProcessMonitorForDemo(flnr.ProcessMonitor):
    def __init__(self, *, sink: TextIO, period: float) -> None:
        super().__init__(period=period)
        self.sink = sink

    def on_start(self, pid: int, cmd: Sequence[str]) -> None:
        self.sink.write(f"on_start {pid} {cmd}\n")

    def observe(self, pid: int) -> None:
        self.sink.write(f"observe, pid={pid}\n")

    def on_end(
        self, return_code: int, stop_info: flnr.ProcessTerminationReason
    ) -> None:
        self.sink.write(
            f"on_end, return_code = {return_code}, info={stop_info}\n"
        )


try:
    flnr.run_shell_ex(
        ["cat", "/dev/random"],
        timeouts=flnr.ExecutionTimeouts(run=5.0),
        process_monitors=[ProcessMonitorForDemo(sink=sys.stdout, period=1.0)],
    )
except flnr.CommandFailedError as e:
    print(f"{e}")
```

## Usage Notes

- **Always set a run timeout**. If a monitor crashes, we disable it and keep
  the child process running. You get a `MonitorFailedError` after the process
  exits. Without one, a stuck child process can hide monitor errors
  indefinitely. The timeout guarantees you eventually see what failed.

- **If a monitor blocks, the entire system stops**. Monitors run in the same
  execution context as output processing. It may and will stall the child
  process. The intended usage model is just to write data to a log file,
  possibly adding a timestamp. That's it. Process monitors should not run too
  frequently and should generally limit themselves to lightweight checks
  (e.g., calling `ps` or `sar` every few minutes). If you need something more
  complex, then this library is likely not the solution you need.

- **Set `output_drain` high enough**. After the process exits, we wait this
  many seconds for remaining output, then close the pipes. This can result
  in data loss. For example, in cases where orphaned processes still hold the
  respective file descriptors and continue writing data, that data will be
  gone.

- Output buffering is environment-dependent and unpredictable, and users
  currently have no control over this behavior. For example, programs may
  switch between line-buffered, block-buffered, or unbuffered modes depending
  on whether stdout is connected to a TTY or a pipe. This directly affects how
  quickly data reaches output monitors.
  See [issue #5](https://github.com/EccoTheDolphin/flnr/issues/5) for details.

## Requirements

- Python 3.10 and above

## Alternatives

The closest thing I could find is the [con-duct](https://github.com/con/duct)
project. It is closer to a full monitoring solution, while `flnr` focuses on
being minimal and embedding directly into existing workflows.

## Development

Development infrastructure is shamelessly borrowed from
[python_experiments](https://github.com/rudenkornk/python_experiments)
(by [rudenkornk](https://github.com/rudenkornk)).
It facilitates a **uv**-based development workflow (I ditched the nix part,
since it was overkill).

### Using uv

[uv](https://docs.astral.sh/uv/) is the only prerequisite for this workflow.

#### Common Commands

```bash
uv run pytest
uv run ./repo.py format
uv run ./repo.py format --check
uv run ./repo.py lint
uv sync
```

**Note:** The uv workflow provides full testing support and includes formatting
and linting tools available on PyPI.
