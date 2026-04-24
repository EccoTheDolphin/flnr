import os
import signal
import sys
from collections.abc import Sequence
from typing import Any

import flnr


class SystemMonitorImpl(flnr.EnvironmentMonitor):
    def on_start(self, pid: int, _: Sequence[str]) -> None:
        print(f"child pid = {pid}", flush=True)

    def observe(self, pid: int) -> None:
        pass


class OutputMonImpl(flnr.OutputMonitor):
    def __init__(self) -> None:
        self.process_called = 0

    def process(self, _: bytes, __: float) -> None:
        self.process_called += 1
        if self.process_called == 1:
            print("child is ready", flush=True)


terminator: Any = None
if sys.argv[1] == "extrq":
    terminator = flnr.HostTerminationRequest()
    signal.signal(signal.SIGINT, lambda _, __: terminator.trigger())
    signal.signal(signal.SIGTERM, lambda _, __: terminator.trigger())
elif sys.argv[1] == "host_signals":
    terminator = flnr.HostTerminationRequest.HOST_SIGNALS
else:
    error_msg = f"unsupported mode {sys.argv[1]}"
    raise RuntimeError(error_msg)

print(f"process is started, pid = {os.getpid()}", flush=True)
sys.stdout.flush()
try:
    print(
        flnr.run_ex(
            [sys.executable, *sys.argv[2:]],
            stdout_monitors=[OutputMonImpl()],
            environment_monitors=[SystemMonitorImpl(period=1.0)],
            host_termination=terminator,
        ),
        flush=True,
    )
except flnr.CommandFailedError as ex:
    print(ex.fate, flush=True)

print("done", flush=True)
