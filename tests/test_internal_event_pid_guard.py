import asyncio
import io
from collections.abc import Sequence

import pytest

import flnr
from flnr.flnr import _periodic_monitor_call

# these tests check non-public API, since it is difficult to ensure that
# situation in covered by utilizing only public API


class _ProcessMonitorImplementation(flnr.ProcessMonitor):
    def __init__(self, *, sink: io.IOBase, period: float) -> None:
        super().__init__(period=period)
        self.sink = sink

    def on_start(self, _: int, __: Sequence[str]) -> None:
        pass

    def observe(self, _: int) -> None:
        self.sink.write("observe called")

    def on_end(self, _: int, __: flnr.ProcessTerminationReason) -> None:
        pass


@pytest.mark.asyncio
async def test_internal_pid_guard_trigger() -> None:
    process = await asyncio.create_subprocess_exec(
        "true",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await process.wait()

    output = io.StringIO()
    monitor = _ProcessMonitorImplementation(sink=output, period=0.5)
    task = asyncio.create_task(_periodic_monitor_call(process, monitor))
    await task

    # here we ensure that our monitor is never called, sine process
    # is already dead at the time the task is scheduled
    assert output.getvalue() == ""


@pytest.mark.asyncio
async def test_internal_pid_guard_notrigger() -> None:
    process = await asyncio.create_subprocess_exec(
        "true",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )

    output = io.StringIO()
    monitor = _ProcessMonitorImplementation(sink=output, period=0.5)
    task = asyncio.create_task(_periodic_monitor_call(process, monitor))
    await task

    await process.wait()

    # here we ensure that our monitor is never called, sine process
    # is already dead at the time the task is scheduled
    assert output.getvalue() == "observe called"
