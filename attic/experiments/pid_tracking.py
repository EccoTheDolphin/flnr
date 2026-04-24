import os
import subprocess
import sys
from collections.abc import Sequence

import flnr

# This experiment illustrates some asyncio behavior.
# Turns out PIDs are not stable and should not be used for anything aside from
# logging


class PMon(flnr.EnvironmentMonitor):
    def __init__(self) -> None:
        super().__init__(period=1)

    def on_start(self, pid: int, _: Sequence[str]) -> None:
        print("<monitor>::on_start started")
        cmd_run(["ps", "-T", "-p", str(os.getpid())])

        cmd_run(["ps", "-p", str(pid)])
        cmd_run(["kill", str(pid)])
        cmd_run(["sleep", "0.5"])

        cmd_run(["ps", "-p", str(pid)])
        print("<monitor>::on_start ended")

    def observe(self, pid: int) -> None:
        pass

    def on_end(self, fate: flnr.ProcessFate) -> None:
        print(f"<monitor> on_end ({fate})")


def cmd_run(cmd: list[str]) -> None:
    print(f"running command: {cmd}")
    p = subprocess.run(cmd, capture_output=True, check=False)
    print(p.stdout.decode("latin-1"))
    print("--")


cmd_run(["ps", "-T", "-p", str(os.getpid())])

fate = flnr.run_ex(
    [sys.executable, "tests/_resources/exec/cat_dev_random.py"],
    environment_monitors=[PMon()],
    check=False,
)

print(f"process fate: {fate}")
