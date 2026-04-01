# `flnr`

<!-- markdownlint-disable link-fragments -->

<!-- mdformat-toc start --slug=gitlab --no-anchors --maxlevel=6 --minlevel=1 -->

- [`flnr`](#flnr)
  - [About](#about)
  - [Raison d'être](#raison-d%C3%AAtre)
  - [Examples](#examples)
    - [Output monitoring](#output-monitoring)
    - [System monitoring](#system-monitoring)
  - [Usage Notes](#usage-notes)
  - [Alternatives](#alternatives)
  - [Development](#development)
    - [Using uv](#using-uv)
      - [Common Commands](#common-commands)

<!-- mdformat-toc end -->

<!-- markdownlint-enable link-fragments -->

## About

**flnr** is a lightweight wrapper around Python subprocesses that routes output
to your logging system with callback hooks for monitoring, without requiring
a full observability stack.

> [!NOTE]
> The library uses asyncio under the hood. User-supplied callbacks are
> expected to be synchronous. Usage of asyncio is an implementation detail and
> users should not rely on its usage in future versions of the library.

> [!WARNING]
> The library is not designed to be used from within an existing async context.
> Calling `run_shell_ex` creates its own event loop and blocks the caller.
> Attempting to use the library from an async context raises `RuntimeError`.

## Raison d'être

If you have a test suite that:

- Runs in CI
- Spawns subprocesses (databases, servers, batch jobs)
- Fails sporadically with no clear reason
- Has no observability infrastructure

**Then read on.**

This library lets you wrap your subprocess call, capture all output with
timestamps, monitor system stats, and get the evidence you need to figure out
why the test failed.

When testing a complex software stack, a common pattern emerges:

- A testsuite ships with its own testing infrastructure
- You integrate it into your automation pipelines. This typically results in a
  subprocess being spawned by your automation harness.
- Some tests fail sporadically - either due to software bugs or infrastructure
  issues.

Debugging infrastructure problems is difficult, especially in complex
environments where **Dark And Evil** monsters like the Dreaded Kubernetes roam
the field.

While a proper telemetry system would help, setting one up requires dedicated
observability expertise - a luxury not every team has.

This library fills the gap. It gives you a simple way to monitor subprocess
behavior without wrestling with enterprise-grade solutions. It can greatly
simplify debugging cases where you automate running of scripts that you don't
fully control.

## Examples

### Output monitoring

The following example demonstrates running a shell command with custom output
logging:

```python
import io
import os
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
        timeouts=flnr.ExecutionTimeouts(run=5.0),
        process_monitors=[ProcessMonitorForDemo(sink=sys.stdout, period=1.0)],
    )
except flnr.CommandFailedError as e:
    print(f"{e}")
```

## Usage Notes

- **Always set a run timeout**. If a monitor crashes, we disable it and keep
  the subprocess running. You get a `MonitorFailedError` after the process
  exits. Without one, a stuck subprocess will hide monitor errors indefinitely.
  The timeout guarantees you eventually see what failed.

- **Output monitors must be lightweight and fast**. Output monitors run in
  the same thread as the reading loop. If a monitor blocks, it stalls the
  subprocess. The intended usage model is just to write data to a log file,
  possibly adding a timestamp. That's it. Process monitors should not run too
  frequently and should generally limit themselves to lightweight checks (e.g.,
  calling `ps` or `sar` every few minutes). If you need something more
  complex, then this library is likely not the solution you need.

- **Set `output_drain` high enough**. After the process exits, we wait this
  many seconds for remaining output, then close the pipes. This can result
  in data loss. For example, in cases where orphaned processes still hold the
  respective file descriptors and continue writing data, that data will be
  gone.

- Output buffering on the subprocess side is highly environment-dependent and
  not always predictable. For example, programs may switch between
  line-buffered, block-buffered, or unbuffered modes depending on whether
  stdout is connected to a TTY or a pipe. This directly affects how quickly
  data reaches output monitors.
  At the moment, users of the library have no real control over this behavior.
  See [issue #5](https://github.com/EccoTheDolphin/flnr/issues/5) for details.

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
