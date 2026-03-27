# `flnr`

<!-- markdownlint-disable link-fragments -->

<!-- mdformat-toc start --slug=gitlab --no-anchors --maxlevel=6 --minlevel=1 -->

- [`flnr`](#flnr)
  - [About](#about)
  - [Examples](#examples)
    - [Output monitoring](#output-monitoring)
    - [System monitoring](#system-monitoring)
  - [Raison d'être](#raison-d%C3%AAtre)
  - [Alternatives](#alternatives)
  - [Development](#development)
    - [Using uv](#using-uv)
      - [Common Commands](#common-commands)

<!-- mdformat-toc end -->

<!-- markdownlint-enable link-fragments -->

## About

**flnr** is a lightweight wrapper around Python subprocesses that routes output
to your logging system with callback hooks for monitoring - no complex
observability stack required.

*Note: The library uses asyncio under the hood. User-supplied callbacks are
expected to be synchronous (this limitation may be relaxed in the future).*

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


class SystemMonitorForDemo(flnr.ProcessMonitor):
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
        system_monitors=[SystemMonitorForDemo(sink=sys.stdout, period=1.0)],
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
behavior without wrestling with enterprise-grade solutions.

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

```bash
uv run pytest
uv run ./repo.py format
uv run ./repo.py format --check
uv run ./repo.py lint
uv sync
```

**Note:** The uv workflow provides full testing support and includes formatting
and linting tools available on PyPI.
