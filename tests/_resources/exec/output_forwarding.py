import os
import subprocess
import sys
import time
from pathlib import Path
from typing import TextIO

from tests._support.events.child_drain import EventSystem
from tests._support.tracing import TraceEmitter

trace = TraceEmitter(EventSystem)

env = os.environ
MAIN_TERMINATION_DELAY = float(env["MAIN_TERMINATION_DELAY"])
CHILD_TICK_DELAY = float(env["CHILD_TICK_DELAY"])
CHILD_TICK_COUNT = int(env["CHILD_TICK_COUNT"])
CHILD_TERMINATION_DELAY = float(env["CHILD_TERMINATION_DELAY"])
FIFTH_TICK_INDEX = 4


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
    trace.emit(EventSystem.DESCENDANT_GREETED)

    for i in range(CHILD_TICK_COUNT):
        flushout_line(sys.stdout, f"stdout - tick count: {i}")
        flushout_line(sys.stderr, f"stderr - tick count: {i}")
        if i == 0:
            trace.emit(EventSystem.DESCENDANT_TICKED_FIRST)
        elif i == FIFTH_TICK_INDEX:
            trace.emit(EventSystem.DESCENDANT_TICKED_5)
        delay_execution(CHILD_TICK_DELAY)
    trace.emit(EventSystem.DESCENDANT_TICKED_ALL)

    flushout(sys.stdout, "stdout data end")
    flushout(sys.stderr, "stderr data end")
    trace.emit(EventSystem.DESCENDANT_DATA_END)

    delay_execution(CHILD_TERMINATION_DELAY)

    flushout_line(sys.stdout, "\nbye")
    flushout_line(sys.stderr, "bye")
    trace.emit(EventSystem.DESCENDANT_SAID_BYE)

    sys.stdout.close()
    os.close(1)
    sys.stderr.close()
    os.close(2)
    trace.emit(EventSystem.DESCENDANT_RELEASED_STDO)

    sys.exit(0)

script_path = Path(__file__).resolve()
print(f"first process started: pid={os.getpid()}")
sys.stdout.flush()
trace.emit(EventSystem.SUPERVISED_GREETED)

subprocess.Popen(
    [sys.executable, script_path, "child"],
    stdout=sys.stdout,
    stderr=sys.stderr,
    start_new_session=True,
)
trace.emit(EventSystem.SUPERVISED_SPAWNED_DESCENDANT)

sys.stdout.close()
os.close(1)
sys.stderr.close()
os.close(2)
trace.emit(EventSystem.SUPERVISED_RELEASED_STDO)

delay_execution(MAIN_TERMINATION_DELAY)
trace.emit(EventSystem.SUPERVISED_CLOSING)
