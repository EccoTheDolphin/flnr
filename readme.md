# `flnr`

<!-- markdownlint-disable link-fragments -->

<!-- mdformat-toc start --slug=gitlab --no-anchors --maxlevel=6 --minlevel=1 -->

- [`flnr`](#flnr)
  - [About](#about)
  - [Raison d'être](#raison-d%C3%AAtre)
  - [Examples](#examples)
    - [Minimal usage](#minimal-usage)
    - [Host termination](#host-termination)
    - [Output monitoring](#output-monitoring)
    - [Environment monitoring](#environment-monitoring)
  - [Usage Notes](#usage-notes)
  - [Requirements](#requirements)
  - [Alternatives](#alternatives)
  - [Development](#development)
    - [Using uv](#using-uv)
      - [Common Commands](#common-commands)

<!-- mdformat-toc end -->

<!-- markdownlint-enable link-fragments -->

## About

**flnr** is a minimal framework for executing external programs as child
processes. It streams output to user-supplied monitors, provides hooks for
observing the execution environment, and manages process lifecycle and error
propagation.

The library has **zero runtime dependencies** and wraps asynchronous stream
handling in a synchronous API, keeping adoption cost low for existing
synchronous scripts.

Standard tools often force a choice between treating a process as an opaque box
or navigating the intricate mechanics of stream buffers. `flnr` bridges this
gap by acting as a managed relay for process data. It exposes a high-level
interface for process execution, output routing, and structured final-state
reporting.

Monitoring is organized around two core interfaces:

- `flnr.OutputMonitor`: For real-time processing of output. The library includes
  built-in implementations like `flnr.TextOutputMonitor` and
  `flnr.BinaryOutputMonitor`.
- `flnr.EnvironmentMonitor`: For periodic callbacks while the process is
  active.

> [!NOTE]
> The library uses asyncio under the hood, but exposes a synchronous API.
> User-supplied callbacks are expected to be synchronous. Usage of asyncio is
> an implementation detail and users should not rely on its usage in future
> versions of the library.

> [!WARNING]
> `flnr` is **not** designed for use inside an existing async context.
> `run_ex` blocks and owns the event loop. It cannot be safely composed
> with other async code. Using it from an async context raises
> `RuntimeError`.

Design principles:

- Single‑threaded, blocking
- monitoring logic executes synchronously in the same execution context as
  output processing. **No isolation** is provided.

Monitors are invoked as data is read from the child process. If you need
concurrency or isolation, this tool is not a good fit.

Monitors are intended to be observational only. This is a usage convention, not
a constraint enforced by the library, and users are expected to follow it.

**Result-Priority Error Handling:** To ensure subprocess results are never
discarded due to an observer crash, monitor failures are captured and deferred.
The supervisor prioritizes completing the process and draining its pipes over
immediate error propagation.

## Raison d'être

If you have a test suite that:

- Runs in CI
- Launches external programs as child processes
- Fails sporadically and provides little insight into why

… and observability is a luxury you don't have, **read on**.

The pattern above is a typical situation when integrating third‑party tools or
test suites into your automation pipeline.

Debugging sporadic failures is difficult, especially in complex environments
where failures can originate from tests, the product under test, or the
surrounding infrastructure—where Dark and Evil monsters like the Dreaded
Kubernetes roam the field. `flnr` gives you just enough visibility to
understand what happened - without building or adopting a full observability
stack.

> [!NOTE]
> The implementation is a blocking subprocess runner with synchronous
> callbacks and built-in lifecycle/timeout management. Because monitors run on
> the same thread as the output relay, slow or blocking user code will stall
> process execution. This is a deliberate design trade-off to prioritize zero
> dependencies and execution predictability over isolation.

## Examples

### Minimal usage

```python
import flnr

fate = flnr.run_ex(["echo", "hello"], timeouts=flnr.ExecutionTimeouts(run=5.0))

print(f"returncode: {fate.returncode}")
print(f"termination_decision: {fate.termination_decision}")
print(f"termination_method: {fate.termination_method}")
# or just:
print(fate)
```

### Host termination

`flnr` can stop a running command in response to a host-side termination
request. The convenience path is `HostTerminationRequest.HOST_SIGNALS`, which
lets `run_ex()` temporarily install SIGINT and SIGTERM handlers for the
current call.

```python
import flnr

fate = flnr.run_ex(
    ["make", "integration-tests"],
    host_termination=flnr.HostTerminationRequest.HOST_SIGNALS,
)
```

For applications that want to own signal handling themselves, `flnr` also
provides `HostTerminationRequest()`. It is a stable, sticky trigger source:
once triggered, it stays triggered, and later runs attached to the same object
observe termination immediately.

```python
import signal
import flnr

terminator = flnr.HostTerminationRequest()
signal.signal(signal.SIGINT, lambda s, f: terminator.trigger())

fate = flnr.run_ex(
    ["make", "integration-tests"],
    host_termination=terminator,
)
```

### Output monitoring

Runs an external command with three output monitors: a custom throughput
monitor, `flnr.BinaryOutputMonitor` for writing raw byte output, and
`flnr.TextOutputMonitor` for writing text output, optionally prefixed with
timestamps. The monitors operate independently, each handling the same process
output and writing to a different destination.

```python
import io
import pathlib
import sys
import time

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


# Noise generator as a single expression. We consume a non-terminating iterator
# into a zero-length deque.
noisy_stream = (
    "import os; from collections import deque; "
    "deque((os.write(1, os.urandom(1024)) for _ in iter(int, 1)), maxlen=0)"
)

# Simulating a long-running process by generating infinite random noise.
# We decode as latin-1 to ensure the text monitor remains resilient
# to high-entropy garbage while the binary monitor captures the raw state.
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
                flnr.TextOutputMonitor(sink=txt, encoding="latin-1"),
            ],
            # stop the process after 3 seconds of execution.
            timeouts=flnr.ExecutionTimeouts(run=3.0, output_drain=1.0),
        )
except flnr.CommandFailedError as e:
    # The run timeout expired; the process was successfully terminated.
    print(e)
```

`TextOutputMonitor` can prefix emitted text lines with timestamps. With
`timestamp_base`, the prefixes are relative to a chosen starting point.

### Environment monitoring

An environment monitor that hooks into the child process lifecycle. Extend
`observe()` to collect system stats (e.g., via ps, /proc, or psutil).

```python
import sys

import flnr

from typing import TextIO, Sequence


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
        ["cat", "/dev/random"],
        timeouts=flnr.ExecutionTimeouts(run=5.0),
        environment_monitors=[EnvMonitorForDemo(sink=sys.stdout, period=1.0)],
    )
except flnr.CommandFailedError as e:
    print(f"{e}")
```

## Usage Notes

- **Monitor failure reporting is deferred until process exit.** Crashes in
  monitors are captured internally but are only raised after the child process
  finishes. A stuck process will therefore delay or hide these errors. **Always
  set a `run` timeout** for critical tasks to guarantee process termination and
  timely reporting.

- **Set `output_drain` to a sufficiently high value.** After the process exits,
  we wait this many seconds for remaining output, then close the pipes. This
  can result in data loss. For example, in cases where orphaned processes
  still hold the respective file descriptors and continue writing data, that
  data will be lost.

- **If a monitor blocks, internal processing stops.** Monitors run in the same
  execution context as output processing. It can and will stall the child
  process. The intended usage model is just to write data to a log file,
  possibly adding a timestamp. That's it. Execution environment monitors should
  not run too frequently and should generally limit themselves to quick,
  low-cost checks (e.g., calling `ps` or `sar` every few minutes). If you need
  more complex processing, this library is probably not the solution you need.

- **Timeout escalation happens in stages.** If the `run` timeout expires, the
  process is terminated and given `terminate` seconds to exit. If it does not,
  it is killed and the library waits another `kill` seconds (defaulting to the
  `terminate` value) for confirmation that the process has exited. Monitors are
  paused during this final wait to avoid prolonging the teardown. If no such
  confirmation arrives, `ProcessKillFailedError` is raised.

- **`flnr` provides built-in shutdown-aware modes.** By default, `run_ex()`
  leaves the host application's signal handling unchanged. When shutdown-aware
  execution is needed, pass
  `host_termination=HostTerminationRequest.HOST_SIGNALS` to let `flnr`
  temporarily watch common shutdown signals during the call, or pass a
  `HostTerminationRequest()` instance when the application manages signal
  handling itself and needs a stable termination trigger.

- **Output buffering is environment-dependent and unpredictable.** Users
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
