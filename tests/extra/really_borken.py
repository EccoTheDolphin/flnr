import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence

import pytest

import flnr

# NOTE: this test program targets low-level implementation details of asynio
# itself It is heavily linux-specific and rely on undocumented details of
# asynio itself. The purpose is to distrurb asyncio transport layer operation
# and see how the system works. After such tests is run the driver state
# becomes irrecoverably broken. We use the term "borken" for that.  Given that
# these test delve into undocumented territory of the python interpreter
# itself, they are organized into self-contained self-checking program.


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


class _ChildPipeBreaker(flnr.ProcessMonitor):
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

    def on_end(self, __: int, _: flnr.ProcessTerminationReason) -> None:
        pass


class _AsyncioTransportBreaker(flnr.ProcessMonitor):
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

    def on_end(self, __: int, _: flnr.ProcessTerminationReason) -> None:
        pass


def test_borken_transport_state() -> None:
    with pytest.raises(OSError, match="Bad file descriptor") as excinfo:
        flnr.run_shell_ex(
            ["sleep", "10"],
            timeouts=flnr.ExecutionTimeouts(run=5.0),
            process_monitors=[_AsyncioTransportBreaker(period=1.0)],
        )
    print(f"===\n{excinfo}\n===")
    assert isinstance(excinfo.value.__context__, flnr.CommandFailedError)
    print("test passed")


def test_borken_closed_output_pipe() -> None:
    with pytest.raises(
        (flnr.MonitorFailedError, flnr.CommandFailedError)
    ) as excinfo:
        flnr.run_shell_ex(
            ["cat", "/dev/random"],
            timeouts=flnr.ExecutionTimeouts(run=5.0),
            process_monitors=[_ChildPipeBreaker(period=1.0)],
        )
    e = excinfo.value
    # there is a race between our reader and child. both results are possible
    if isinstance(e, flnr.MonitorFailedError):
        expected_mon_exc = 3
        assert e.proc_returncode != 0
        assert len(e.monitor_exceptions) == expected_mon_exc
        for ex in e.monitor_exceptions:
            assert isinstance(ex, OSError)
        print(f"got monitor failed error\n==={e}\n===\n")
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
