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
