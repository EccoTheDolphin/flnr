import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence

import pytest

import flnr

# NOTE: this test program targets low-level implementation details of asyncio.
# It is heavily Linux-specific and relies on undocumented details. The purpose
# is to disturb asyncio transport layer operation and see how the system works.
# After such tests are run, the driver state becomes irrecoverably broken. We
# use the term "borken" for that. Given that these tests delve into
# undocumented territory of the Python interpreter itself, they are organized
# into a self-contained, self-checking program.


class DummyOutputMonitor(flnr.OutputMonitor):
    def process(self, _: bytes, __: float) -> None:
        pass

    def on_disable(self, _: flnr.OutputMonitorDisableReason, __: float) -> None:
        pass


def _scan_asyncio_transport() -> dict[str, str]:
    self_pid = os.getpid()
    lsof_binary = shutil.which("lsof")
    assert lsof_binary is not None
    result = subprocess.run(
        [lsof_binary, "-p", str(self_pid)],
        capture_output=True,
        text=True,
        check=True,
    )
    match = re.search(r"eventpoll:(\d+),(\d+)", result.stdout)
    if match:
        fd_transport, fd_child_pipe = int(match.group(1)), int(match.group(2))
        return {
            "transport_socket": str(fd_transport),
            "child_pipe": str(fd_child_pipe),
        }
    err_msg = "could not derive asyncio transport info"
    raise RuntimeError(err_msg)


class _ChildPipeBreaker(flnr.EnvironmentMonitor):
    def __init__(self, *, period: float) -> None:
        super().__init__(period=period)
        self.counter = 0

    def on_start(self, _: int, __: Sequence[str]) -> None:
        pass

    def observe(self, _: int) -> None:
        self.counter += 1
        effect_on_count = 2
        if self.counter == effect_on_count:
            transport_info = _scan_asyncio_transport()
            os.close(int(transport_info["child_pipe"]))

    def on_end(self, fate: flnr.ProcessFate) -> None:
        pass


class _AsyncioTransportBreaker(flnr.EnvironmentMonitor):
    def __init__(self, *, period: float) -> None:
        super().__init__(period=period)
        self.counter = 0

    def on_start(self, _: int, __: Sequence[str]) -> None:
        pass

    def observe(self, _: int) -> None:
        self.counter += 1
        effect_on_count = 2
        if self.counter == effect_on_count:
            transport_info = _scan_asyncio_transport()
            os.close(int(transport_info["transport_socket"]))

    def on_end(self, fate: flnr.ProcessFate) -> None:
        pass


def test_borken_transport_state() -> None:
    # during this test flnr machinery properly detects timeout and as a result
    # CommandFailedError is raised.
    # Then, when the execution loop is destroyed (as part of asyncio.run
    # teardown) the transport layer should emit OSError, overriding the
    # CommandFailedError exception
    with pytest.raises(OSError, match="Bad file descriptor") as excinfo:
        flnr.run_ex(
            ["sleep", "10"],
            timeouts=flnr.ExecutionTimeouts(run=5.0),
            stdout_monitors=[DummyOutputMonitor()],
            environment_monitors=[_AsyncioTransportBreaker(period=1.0)],
        )
    print(f"===\n{excinfo}\n===")
    print(f"===\n{excinfo.value}\n===")
    print(f"===\n{excinfo.value.__context__}\n===")
    assert isinstance(excinfo.value.__context__, flnr.CommandFailedError)
    print("test passed")


def test_borken_closed_output_pipe() -> None:
    with pytest.raises(
        (
            flnr.SupervisionFailedError,
            flnr.CommandFailedError,
            flnr.ProcessKillFailedError,
        )
    ) as excinfo:
        flnr.run_ex(
            ["cat", "/dev/random"],
            timeouts=flnr.ExecutionTimeouts(run=5.0),
            stdout_monitors=[DummyOutputMonitor()],
            environment_monitors=[_ChildPipeBreaker(period=1.0)],
        )
    e = excinfo.value
    # there is a race between our reader and child. both results are possible
    if isinstance(e, flnr.SupervisionFailedError):
        assert (
            e.fate.termination_decision
            == flnr.ProcessTerminationDecision.INTERNAL_FAILURE
        )
        assert e.fate.termination_method == flnr.ProcessTerminationMethod.KILL
        assert e.fate.returncode != 0
        assert len(e.internal_exceptions) == 1
        for ex in e.internal_exceptions:
            assert "Bad file descriptor" in f"{ex}"
            assert isinstance(ex, OSError)
        print(f"got supervisor failed error\n==={e}\n===\n")
    else:
        print(f"got command failed error\n==={e}\n===\n")
    print("test passed")


if __name__ == "__main__":
    if shutil.which("lsof") is None:
        err_msg = "these tests require lsof command to be present"
        raise RuntimeError(err_msg)
    match sys.argv[1]:
        case "child_pipe":
            test_borken_closed_output_pipe()
        case "asyncio_transport":
            test_borken_transport_state()
        case _:
            err_msg = "unknown test type"
            raise ValueError(err_msg)
