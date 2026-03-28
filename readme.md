# `flnr`

<!-- markdownlint-disable link-fragments -->

<!-- mdformat-toc start --slug=gitlab --no-anchors --maxlevel=6 --minlevel=1 -->

- [`flnr`](#flnr)
  - [About](#about)
  - [Examples](#examples)
    - [Output monitoring](#output-monitoring)
    - [System monitoring](#system-monitoring)
  - [Raison d'être](#raison-d%C3%AAtre)
  - [Limitations and Controversial Design Choices](#limitations-and-controversial-design-choices)
  - [Alternatives](#alternatives)
  - [Development](#development)
    - [Using uv](#using-uv)
      - [Common Commands](#common-commands)

<!-- mdformat-toc end -->

<!-- markdownlint-enable link-fragments -->

## About

**flnr** is a lightweight wrapper around Python subprocesses that routes output
to your logging system with callback hooks for monitoring, without requiring
a full observability stack

> [!NOTE]
> *Note: The library uses asyncio under the hood. User-supplied callbacks are
> expected to be synchronous (this limitation may be relaxed in the future).*

> [!WARNING]
> The library is not designed to be used in an async context. Attempting to do
> so will result in a `RuntimeError` being thrown from the main entry point.

## Examples

### Output monitoring

The following example demonstrates running a shell command with custom output
logging:

```python
import io
import os
import sys
import pathlib

import flnr


class CustomLoggerForDemo(flnr.OutputMonitor):
    """Custom implementation of output monitoring."""

    def __init__(self, *, sink: io.IOBase) -> None:
        super().__init__(line_proc=True)
        self.sink = sink

    def process(self, data: bytes) -> None:
        self.sink.write(f"captured data length: {len(data)}\n")


try:
    with (
        pathlib.Path("/dev/null").open("w") as null_file,
        pathlib.Path("data_length.log").open("w") as length_file,
    ):
        flnr.run_shell_ex(
            ["cat", "/dev/random"],
            stdout_observers=[
                flnr.LoggingOutputMonitor(sink=sys.stdout, encoding="latin-1"),
                flnr.LoggingOutputMonitor(
                    sink=null_file, encoding="utf-8", auto_flush=True
                ),
                CustomLoggerForDemo(sink=length_file),
            ],
            timeout=5.0,
            merge_std_streams=True,
        )
except flnr.CommandFailedError as e:
    print(f"{e}")
```

### System monitoring

This example demonstrates how to set up a system monitor:

```python
import io
import os
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
        timeout=5.0,
        process_monitors=[ProcessMonitorForDemo(sink=sys.stdout, period=1.0)],
    )
except flnr.CommandFailedError as e:
    print(f"{e}")
```

## Raison d'être

When testing complex programs like GDB, a common pattern emerges:

- A testsuite ships with its own testing infrastructure
- You integrate it into your automation pipelines. Typical integration results
  in a subprocess being spawned by your automation harness.
- Some tests fail sporadically - either due to software bugs or infrastructure
  issues.

Debugging infrastructure problems is difficult, especially in complex
environments where **Dark And Evil** monsters like the Dreaded Kubernetes roam
the field.

While a proper telemetry system would help, setting one up requires dedicated
observability expertise - a luxury not every team has.

This library fills the gap. It gives you a simple way to monitor subprocess
behavior without wrestling with enterprise-grade solutions. It can greatly
simplify cases where you need to automate running of scripts that you don't
fully control.

## Limitations and Controversial Design Choices

- At the moment stdout/stderr are drained using `asyncio.StreamReader.readline`.
  Bytes-based processing is not implemented. This implies that if your process
  outputs lots of data without ever putting '\\n' in its output, output
  monitoring facilities won't get invoked until EOF is encountered. Note that
  if the file descriptor is propagated to a child, EOF may never be observed
  and the associated reader task can be simply cancelled, resulting in a loss of
  data. Also not that if the subprocess produces large amounts of data without
  newline characters, memory usage may grow unbounded because data is buffered
  internally until a newline or EOF is encountered.

- Output observers are intended to be lightweight and fast. The intended usage model
  is just to write data to a log file, possibly adding a timestamp. That's
  it. Process monitors should not be called too often and generally should limit
  themselves to something like calling `ps` or `sar` once every few minutes. If
  you need something more complex, then this library is likely not the solution you need.

- The library assumes that the exit code of the launched process is the main
  result the user is interested in. It means that if some user-supplied monitor
  fails, it will be simply disabled, allowing the process to run until the end.
  When such failures are detected, they will be reported in a dedicated exception
  `MonitorFailedError` along with the application exit code.

- When the underlying process is terminated, the library assumes that all the
  data that may be available on the respective stdout/stderr can be discarded
  after a certain amount of time. This means that if there are orphaned processes
  that still hold the respective file descriptors and write some data - this data
  will be silently discarded.

## Alternatives

The closest thing I could find is the [con-duct](https://github.com/con/duct)
project. However, it seems tailored to specific usage scenarios, offering
something closer to a complete monitoring solution. Still, it may be a viable
alternative if you're comfortable with something less lightweight.

## Development

Development infrastructure is shamelessly borrowed from
[python_experiments](https://github.com/rudenkornk/python_experiments)
(by [rudenkornk](https://github.com/rudenkornk)).
It facilitates a **uv**-based development workflow (I ditched the nix part,
since it was overkill).

### Using uv

[uv](https://docs.astral.sh/uv/) is the only prerequisite for this workflow.

#### Common Commands

```
uv run pytest
uv run ./repo.py format
uv run ./repo.py format --check
uv run ./repo.py lint
uv sync
```

**Note:** The uv workflow provides full testing support and includes formatting
and linting tools available on PyPI.
