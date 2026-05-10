# `flnr`

[![CI](https://github.com/EccoTheDolphin/flnr/actions/workflows/workflow.yml/badge.svg?branch=main)](https://github.com/EccoTheDolphin/flnr/actions/workflows/workflow.yml)
[![Docs](https://app.readthedocs.org/projects/flnr/badge/?version=latest)](https://flnr.readthedocs.io/en/latest/)
[![PyPI](https://img.shields.io/pypi/v/flnr.svg)](https://pypi.org/project/flnr/)
[![Python](https://img.shields.io/pypi/pyversions/flnr.svg)](https://pypi.org/project/flnr/)
[![License](https://img.shields.io/pypi/l/flnr.svg)](https://pypi.org/project/flnr/)

[API Reference](https://flnr.readthedocs.io/en/latest/) ·
[PyPI](https://pypi.org/project/flnr/) ·
[Source](https://github.com/EccoTheDolphin/flnr/)

<!-- markdownlint-disable link-fragments -->

<!-- mdformat-toc start --slug=gitlab --no-anchors --maxlevel=6 --minlevel=1 -->

- [`flnr`](#flnr)
  - [About](#about)
  - [Installation](#installation)
  - [Raison d'être](#raison-d%C3%AAtre)
  - [Core Concepts](#core-concepts)
  - [Design Constraints](#design-constraints)
  - [Important Operational Behaviors](#important-operational-behaviors)
  - [Error Handling](#error-handling)
  - [Examples](#examples)
    - [Minimal usage](#minimal-usage)
    - [Host termination](#host-termination)
    - [Output monitoring](#output-monitoring)
    - [Environment monitoring](#environment-monitoring)
    - [Failure diagnostics](#failure-diagnostics)
  - [Requirements](#requirements)
  - [Alternatives](#alternatives)
  - [Development](#development)
    - [Using uv](#using-uv)
      - [Common Commands](#common-commands)

<!-- mdformat-toc end -->

<!-- markdownlint-enable link-fragments -->

## About

**flnr** is a small library for supervising subprocesses in CI and automation code.
It runs a direct child process, routes output through user-supplied monitors,
escalates timeouts, records final process state, and preserves monitor
failures as part of the final execution result.

It is designed for situations where a failed external command must still leave
usable diagnostic state: observed output, termination path, return code, monitor
errors, and host-requested shutdown.

The library has **zero runtime dependencies** and exposes a synchronous API.

It can replace direct `subprocess.run()` / `Popen` use when command execution
needs observable output handling, explicit lifecycle control, and structured
final-state reporting.

## Installation

```bash
pip install flnr
```

Requires Python 3.10+.

## Raison d'être

If you have a test suite that:

- Runs in CI
- Launches external programs as child processes
- Fails sporadically and provides little insight into why

… and observability is a luxury you don't have, **read on**.

Integrating third‑party tools or test suites into your automation pipeline is
messy. Debugging sporadic failures is difficult, especially in complex
environments where failures can originate from tests, the product under test,
or the surrounding infrastructure—where Dark and Evil monsters like the Dreaded
Kubernetes roam the field.

Standard tools often force a choice between treating a process as an opaque box
or manually dealing with pipes, buffering, and teardown details. `flnr` gives
you just enough visibility to understand what happened without demanding you
build or adopt a massive observability stack.

## Core Concepts

The library revolves around a small set of core types and interfaces:

- `flnr.run_ex()`: Executes an external program as a child process, supervises
  its lifecycle, routes output to monitors, and returns a `flnr.ProcessFate`.

- `flnr.ProcessFate`: A structured final-state object that records the
  subprocess return code and the termination path.

- `flnr.OutputMonitor`: Receives stdout/stderr chunks as they arrive. The
  library ships with built-in implementations such as `flnr.TextOutputMonitor`
  and `flnr.BinaryOutputMonitor`.

- `flnr.EnvironmentMonitor`: Receives lifecycle callbacks (`on_start`,
  `observe`, `on_end`) intended for low-cost observation; heavy work blocks the
  output relay.

- **State-Preserving Exceptions:** Execution failures raise subclasses of
  `flnr.ProcessExecutionError` that retain the resolved `flnr.ProcessFate`.

- **Host Termination Requests:** Let caller code request flnr-controlled child
  termination explicitly via `flnr.HostTerminationRequest`. On Unix/POSIX,
  `flnr.HostTerminationRequest.HOST_SIGNALS` provides an opt-in shortcut that
  temporarily maps host SIGINT/SIGTERM to that request for one `run_ex()` call.

- `flnr.CommandTracerProtocol`: Contract for command recipe tracers.
  `flnr.CommandTracer` logs shell-oriented command recipes.

## Design Constraints

`flnr` gets its simplicity from a deliberately narrow execution model. These
constraints are part of the design, not accidental omissions.

- **Single-threaded & Blocking:** `flnr.run_ex()` blocks the caller until the
  direct child reaches a resolved final state and output monitoring has
  finished or timed out.

- **Not Composable with an Existing Asyncio Event Loop:** `flnr` uses `asyncio`
  internally but **must not** be used inside an existing async context. It owns
  the event loop. Calling it directly from async code raises `RuntimeError`. If
  you must use it in an asyncio app, dispatch it via `asyncio.to_thread()`.

- **No Isolation:** Monitors run synchronously on the same thread as the output
  relay. If your monitor code is slow or blocks, output processing stalls and
  the child process may stall through pipe backpressure.

- **Direct Children Only:** `flnr` supervises the direct child process. It does
  not track or kill descendant process trees. However, it *does* drain the
  standard pipes. If an orphaned descendant keeps inherited stdout/stderr file
  descriptors open, `flnr` will wait for them until the `output_drain` timeout.

- **Deferred Monitor Failures:** Monitor failures are reported *after*
  subprocess execution completes. A stuck process will delay or hide these
  errors. **Always set a `run` timeout** for critical tasks to guarantee
  process termination and timely reporting.

## Important Operational Behaviors

- **Exceptions Carry State:** Execution failures retain the resolved
  `flnr.ProcessFate` and any associated `flnr.MonitorFailure` objects, so
  failure does not discard final execution state.

- **Timeout escalation happens in stages:** If the run timeout expires, the
  process is asked to terminate and given `terminate` seconds. If it ignores
  this, it is killed, followed by a kill confirmation wait period. If no such
  confirmation arrives, `flnr.ProcessKillFailedError` is raised. Monitors are
  temporarily paused during the final wait to avoid prolonging teardown.

- **Output buffering is environment-dependent:** Currently, users have no
  control over this behavior. Programs may switch between line-buffered,
  block-buffered, or unbuffered modes depending on whether stdout is
  connected to a TTY or a pipe. This directly affects how quickly data
  reaches output monitors.
  See [issue #5](https://github.com/EccoTheDolphin/flnr/issues/5) for details.

- **Text Monitor Fragmentation:** To prevent memory exhaustion from
  pathological output, `flnr.TextOutputMonitor` caps internal carry-over
  buffers. If a process emits a continuous stream without a newline long enough
  to exceed the configured limit, the monitor forcefully fragments it and emits
  the tail early.

- **Unhandled Output Is Discarded:** Child output is discarded unless it is
  routed to output monitors or bound to the parent stream with
  `flnr.BIND_TO_PARENT`. Configure `stdout_monitors` to observe stdout and, by
  default, stderr too; configure `stderr_monitors` when stderr should be handled
  separately. Parent-bound output is not observed by output monitors.

- **Stdin Defaults to DEVNULL:** Child stdin is connected to `DEVNULL` by
  default. Use `stdin=flnr.INHERIT_STDIN` for interactive commands that should
  read from the parent stdin.

## Error Handling

All execution failures derive from `flnr.ProcessExecutionError`. Every concrete
subclass retains the resolved `flnr.ProcessFate`, so even failed runs still
carry structured final execution state.

Concrete subclasses include, in the order they take precedence during error
resolution:

- `flnr.ProcessKillFailedError`: Forced termination was requested, but process
  exit could not be confirmed within the configured timeout.
- `flnr.SupervisionFailedError`: `flnr` encountered an unrecoverable
  supervision error.
- `flnr.CommandFailedError`: The child process finished with a non-zero exit
  status and `check=True`.
- `flnr.MonitorFailedError`: One or more monitors failed during execution.

When multiple failure conditions occur during a run, the highest-precedence
class is raised.

Monitor-related failures are aggregated and recorded as `flnr.MonitorFailure`
instances and reported as a `monitor_failures` attribute on the exception.

## Examples

### Minimal usage

<!-- readme-sync path="intro_simple.py" lang="python" -->

```python
import sys

import flnr

# No output monitors are configured in this minimal example,
# so the child's stdout is intentionally discarded.
fate = flnr.run_ex(
    [sys.executable, "-c", "print('hello')"],
    timeouts=flnr.ExecutionTimeouts(run=5.0),
)

print(f"returncode: {fate.returncode}")
print(f"termination_decision: {fate.termination_decision}")
print(f"termination_method: {fate.termination_method}")
# This will print something like:
# returncode=0, decision=no_intervention, method=none
print(fate)
```

<!-- /readme-sync -->

### Host termination

`flnr` provides a stable, sticky trigger source called
`flnr.HostTerminationRequest` to let the host process request termination of a
running command.

Once triggered, the request remains active. Any run attached to an
already-triggered request will observe termination immediately upon startup.
This is ideal for applications that manage their own signal handling or need to
trigger shutdowns coming from external sources.

<!-- readme-sync path="intro_host_term.py" lang="python" -->

```python
import signal

import flnr

terminator = flnr.HostTerminationRequest()
# SIGINT causes the trigger to fire, which causes the subprocess to enter
# the terminate stage defined by `flnr`.
signal.signal(signal.SIGINT, lambda _, __: terminator.trigger())

fate = flnr.run_ex(
    ["make", "integration-tests"],
    host_termination=terminator,
)

# Note that the terminator object is kept alive for the duration of the script.
# Although `terminator` has a `.close()` method for releasing resources,
# calling it while signals may still arrive races with `.trigger()`.
```

<!-- /readme-sync -->

> [!WARNING]
> Attaching to an already-triggered request does not prevent process creation
> ahead of time. The run observes termination as soon as supervision starts.

For simple CLI scripts that want signal-triggered child termination without
explicit signal management, `flnr` offers
`flnr.HostTerminationRequest.HOST_SIGNALS` as a convenience shortcut:

<!-- readme-sync path="intro_host_signals.py" lang="python" -->

```python
import flnr

# Unix-only example.
# Once the subprocess starts, SIGTERM or SIGINT sent to the host process will
# cause the child to enter the terminate stage defined by `flnr`.
fate = flnr.run_ex(
    ["make", "integration-tests"],
    host_termination=flnr.HostTerminationRequest.HOST_SIGNALS,
)
```

<!-- /readme-sync -->

> [!NOTE]
> `flnr.HostTerminationRequest.HOST_SIGNALS` convenience mode is
> **Unix/POSIX-only** and requires `flnr.run_ex()` to be called from the **main
> Python thread**.

This temporarily installs SIGINT and SIGTERM handlers for the duration of the
call. While this mode is active, SIGINT/SIGTERM make the host process request
child termination. For example, Ctrl+C will not
immediately raise `KeyboardInterrupt` in the caller. `flnr` owns those handlers
while the process runs and restores the previous ones as soon as
`flnr.run_ex()` returns.

### Output monitoring

Runs an external command with three output monitors: a custom throughput
monitor, `flnr.BinaryOutputMonitor` for writing raw byte output, and
`flnr.TextOutputMonitor` for writing decoded text, optionally prefixed with
timestamps. The monitors are attached to stdout. They receive the same output
chunks, but each keeps its own state and writes to its own destination.

<!-- readme-sync path="mon_output.py" lang="python" -->

```python
import io
import pathlib
import sys

import flnr


class ThroughputMonitor(flnr.OutputMonitor):
    def __init__(self, *, sink: io.IOBase) -> None:
        self.sink = sink
        self.bytes_received = 0

    def process(self, data: bytes, ts: float) -> None:
        self.bytes_received += len(data)
        msg = f"{ts:.3f}s total {self.bytes_received} bytes\n"
        self.sink.write(msg.encode("latin-1"))

    def on_disable(self, _: flnr.OutputMonitorDisableReason, __: float) -> None:
        pass


# Noise generator as a single expression
noisy_stream = "import os\nwhile True:\n    os.write(1, os.urandom(1024))"

# Simulating a long-running process by generating infinite random noise.
# We decode as latin-1 so arbitrary bytes always become text at the monitor
# boundary. The sink still writes UTF-8 on purpose: decoding policy belongs
# to the monitor, not to the destination file.
try:
    with (
        pathlib.Path("throughput.id-11e1a300.log").open("wb") as throughput_log,
        pathlib.Path("binary.id-243f6a88.bin").open("wb") as binary_log,
        pathlib.Path("text.id-5f3759df.txt").open("w", encoding="utf-8") as txt,
    ):
        flnr.run_ex(
            [sys.executable, "-c", noisy_stream],
            stdout_monitors=[
                ThroughputMonitor(sink=throughput_log),
                flnr.BinaryOutputMonitor(sink=binary_log),
                flnr.TextOutputMonitor(
                    sink=txt, encoding="latin-1", timestamp_precision=3
                ),
            ],
            # stop the process after 3 seconds of execution.
            timeouts=flnr.ExecutionTimeouts(run=3.0, output_drain=1.0),
        )
except flnr.CommandFailedError as e:
    # The run timeout expired; the process was successfully terminated.
    print(e)
# After the process is terminated due to timeout, the resulting files contain:
# throughput records (as defined by the custom monitor), raw output with random
# noise produced by the script, and the same output transcoded from
# latin-1 to UTF-8 with timestamps at line boundaries.
```

<!-- /readme-sync -->

`flnr.TextOutputMonitor` can prefix emitted text lines with timestamps. With
`timestamp_base`, the prefixes are relative to a chosen starting point.

### Environment monitoring

An environment monitor that hooks into the child process lifecycle. Extend
`observe()` to collect system stats (e.g., via ps, /proc, or psutil).

<!-- readme-sync path="mon_env.py" lang="python" -->

```python
import sys
from collections.abc import Sequence
from typing import TextIO

import flnr


class EnvMonitorForDemo(flnr.EnvironmentMonitor):
    def __init__(self, *, sink: TextIO, period: float) -> None:
        super().__init__(period=period)
        self.sink = sink

    def on_start(self, pid: int, cmd: Sequence[str]) -> None:
        self.sink.write(f"on_start {pid} {cmd}\n")

    def observe(self, pid: int) -> None:
        self.sink.write(f"observe, pid={pid}\n")

    def on_end(self, fate: flnr.ProcessFate) -> None:
        self.sink.write(f"on_end, {fate}\n")


try:
    flnr.run_ex(
        [sys.executable, "-c", "import time; time.sleep(100)"],
        timeouts=flnr.ExecutionTimeouts(run=5.0),
        environment_monitors=[EnvMonitorForDemo(sink=sys.stdout, period=1.0)],
    )
except flnr.CommandFailedError as e:
    # The serialized representation of the exception looks like this:
    # unexpected return code -15
    # fate: returncode=-15, decision=timeout, method=terminate
    print(f"{e}")
```

<!-- /readme-sync -->

### Failure diagnostics

Execution exceptions preserve the resolved process state and any monitor
failures recorded during the run. This example shows a command failure reported
together with two output monitor failures.

<!-- readme-sync path="failure_diagnostics.py" lang="python" -->

```python
import sys

import flnr


class FailsOnMarker(flnr.OutputMonitor):
    def __init__(self, marker: bytes) -> None:
        self.marker = marker
        # Output monitors receive data in chunks, so split lines incrementally.
        self.lines = flnr.IncrementalLineSplitter()

    def process(self, data: bytes, ts: float) -> None:
        del ts
        for line in self.lines.feed(data):
            if self.marker in line:
                msg = f"monitor failed on {self.marker.decode()}"
                raise RuntimeError(msg)


cmd = [
    sys.executable,
    "-c",
    "print('alpha'); print('beta'); raise SystemExit(42)",
]

try:
    flnr.run_ex(
        cmd,
        stdout_monitors=[
            FailsOnMarker(b"alpha"),
            FailsOnMarker(b"beta"),
        ],
    )
except flnr.CommandFailedError as exc:
    print(exc)
```

<!-- /readme-sync -->

The rendered exception report includes both the process result and per-monitor
failure details:

<!-- readme-sync path="failure_diagnostics.expected.txt" lang="text" -->

```text
unexpected return code 42
fate: returncode=42, decision=no_intervention, method=none
2 monitor failure(s) recorded:

[1] stdout monitor #0 (FailsOnMarker) failed in process: RuntimeError: monitor failed on alpha
[2] stdout monitor #1 (FailsOnMarker) failed in process: RuntimeError: monitor failed on beta

Monitor failure details:

[1] stdout monitor #0 (FailsOnMarker) failed in process
Traceback (most recent call last):
  File "<file>", line <n>, in <func>
    self.monitor.process(data, ts)
  File "<file>", line <n>, in <func>
    raise RuntimeError(msg)
RuntimeError: monitor failed on alpha

[2] stdout monitor #1 (FailsOnMarker) failed in process
Traceback (most recent call last):
  File "<file>", line <n>, in <func>
    self.monitor.process(data, ts)
  File "<file>", line <n>, in <func>
    raise RuntimeError(msg)
RuntimeError: monitor failed on beta
```

<!-- /readme-sync -->

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
uv run ./attic/repo.py format
uv run ./attic/repo.py format --check
uv run ./attic/repo.py lint
uv sync
```

**Note:** The uv workflow provides full testing support and includes formatting
and linting tools available on PyPI.

Mutation testing, local profile:

```
cd "${PROJECT_DIR}"
rm -rf mutants
env COVERAGE_PROCESS_START="${PWD}/pyproject.toml" \
    uv run --group mutation mutmut run --max-children 16
```
