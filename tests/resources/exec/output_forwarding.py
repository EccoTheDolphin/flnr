import os
import subprocess
import sys
import time
from pathlib import Path
from typing import TextIO

env = os.environ
MAIN_TERMINATION_DELAY = float(env["MAIN_TERMINATION_DELAY"])
CHILD_TICK_DELAY = float(env["CHILD_TICK_DELAY"])
CHILD_TICK_COUNT = int(env["CHILD_TICK_COUNT"])
CHILD_TERMINATION_DELAY = float(env["CHILD_TERMINATION_DELAY"])


def delay_execution(delay: float) -> None:
    if delay > 0:
        time.sleep(delay)


def flushout_line(stream: TextIO, line: str) -> None:
    print(line, file=stream)
    stream.flush()


def flushout(stream: TextIO, data: str) -> None:
    stream.write(data)
    stream.flush()


if len(sys.argv) > 1:
    flushout_line(sys.stdout, f"second process started: pid={os.getpid()}")
    for i in range(CHILD_TICK_COUNT):
        flushout_line(sys.stdout, f"stdout - tick count: {i}")
        flushout_line(sys.stderr, f"stderr - tick count: {i}")
        delay_execution(CHILD_TICK_DELAY)

    flushout(sys.stdout, "stdout data end")
    flushout(sys.stderr, "stderr data end")

    delay_execution(CHILD_TERMINATION_DELAY)

    flushout_line(sys.stdout, "\nbye")
    flushout_line(sys.stderr, "bye")

    sys.stdout.close()
    os.close(1)
    sys.stderr.close()
    os.close(2)

    sys.exit(0)

script_path = Path(__file__).resolve()
print(f"first process started: pid={os.getpid()}")
sys.stdout.flush()

subprocess.Popen(
    [sys.executable, script_path, "child"],
    stdout=sys.stdout,
    stderr=sys.stderr,
    start_new_session=True,
)
sys.stdout.close()
os.close(1)
sys.stderr.close()
os.close(2)
delay_execution(MAIN_TERMINATION_DELAY)
