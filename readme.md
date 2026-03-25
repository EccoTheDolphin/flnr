# `flnr`

<!-- markdownlint-disable link-fragments -->

<!-- mdformat-toc start --slug=gitlab --no-anchors --maxlevel=6 --minlevel=1 -->

- [`flnr`](#flnr)
  - [About](#about)
  - [Examples](#examples)
    - [Output monitoring](#output-monitoring)
    - [System monitoring](#system-monitoring)
  - [Raison d'être](#raison-d%C3%AAtre)
  - [Development](#development)
    - [Using uv](#using-uv)
      - [Common Commands](#common-commands)

<!-- mdformat-toc end -->

<!-- markdownlint-enable link-fragments -->

## About

A lightweight wrapper around Python subprocesses that routes output to your
logging system with callback hooks for monitoring - no complex observability
stack required.

*Note: The library uses asyncio under the hood. User-supplied callbacks are
expected to be synchronous (this limitation may be relaxed in the future).*

## Examples

### Output monitoring

The following example demonstrates running a shell command with custom output
logging:

```python
import flnr
import io
import os
import sys


class CustomLogger(flnr.OutputMonitor):
    """Custom implementation of output monitoring."""

    def __init__(self, *, file: io.IOBase) -> None:
        super().__init__(line_proc=True)
        self.file = file

    def process(self, data: bytes) -> None:
        self.file.write(f"{len(data)}\n")


try:
    with (
        open("/dev/null", "w") as null_file,
        open("length.log", "w") as length_file,
    ):
        flnr.run_shell_ex(
            ["cat", "/dev/random"],
            env=os.environ.copy(),
            stdout_observers=[
                flnr.LoggingOutputMonitor(file=sys.stdout, encoding="latin-1"),
                flnr.LoggingOutputMonitor(
                    file=null_file, encoding="utf-8", auto_flush=True
                ),
                flnr.CustomLogger(file=length_file),
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
import flnr
import io
import os


class SystemMonitor(flnr.ProcessMonitor):
    def __init__(self, *, file: io.IOBase) -> None:
        super().__init__(period=1.0)
        self.file = file

    def on_start(self, pid: int, cmd: list[str]) -> None:
        pass

    def observe(self, pid: int) -> None:
        # Here you can call your system monitoring scripts
        pass

    def on_end(self, return_code: int, stop_info: str) -> None:
        pass


try:
    with open("sysmon.log", "w") as sysmon_file:
        flnr.run_shell_ex(
            ["cat", "/dev/random"],
            env=os.environ.copy(),
            timeout=5.0,
            system_monitors=[SystemMonitor(file=sysmon_file)],
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

## Development

Development infrastructure is shamelessly borrowed
from https://github.com/rudenkornk/python_experiments (by @rudenkornk).
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
