"""Flnr a library for non-invasive monitoring of subprocesses."""

import asyncio
import contextlib
import io
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path
from typing import Any


class CommandFailedError(Exception):
    """Exception that when user asked to ensure that command succeeds."""


class OutputMonitor(ABC):  # pylint: disable=too-few-public-methods
    """Interface that subprocess output monitors must implement."""

    def __init__(self, *, line_proc: bool) -> None:
        """Select between lines/bytes processing mode."""
        self.line_proc = line_proc

    @abstractmethod
    def process(self, data: bytes) -> None:
        """Process subprocess output."""


class LoggingOutputMonitor(OutputMonitor):  # pylint: disable=too-few-public-methods
    """Standard implementation of output monitoring."""

    def __init__(
        self,
        *,
        file: io.IOBase,
        encoding: str | None = None,
        auto_flush: bool = True,
    ) -> None:
        """Define how data is processed by the monitor.

        :param file: output stream to send processed result
        :param encoding: encoding of data to process. Use *None* for binary
        :param auto_flush: flush output stream after each write to file
        """
        super().__init__(line_proc=True)
        self.file = file
        self.encoding = encoding
        self.auto_flush = auto_flush

    def process(self, data: bytes) -> None:
        """Process subprocess output.

        If encoding is specified, the data is decoded to python string
        before writing to output file
        """
        if self.encoding is not None:
            decoded = data.decode(self.encoding, errors="replace")
            self.file.write(decoded)
        else:
            self.file.write(data)
        if self.auto_flush:
            self.file.flush()


TERMINATE_NORMAL = "finished"
TERMINATE_TIMEOUT = "terminate"
TERMINATE_KILL = "kill"


class ProcessMonitor(ABC):
    """Interface that global monitors must implement."""

    def __init__(self, *, period: float) -> None:
        """Define how often the monitor is called."""
        self.period = period

    @abstractmethod
    def on_start(self, pid: int, cmd: list[str]) -> None:
        """Notification when subprocess corresponding to command is created."""

    @abstractmethod
    def observe(self, pid: int) -> None:
        """Periodic notification while subprocess is guaranteed to exist."""

    @abstractmethod
    def on_end(self, return_code: int, stop_info: str) -> None:
        """Notify when subprocess is finished."""


async def _stream_line_reader(
    sr: asyncio.StreamReader, onservers_in: list[OutputMonitor] | None
) -> None:
    if onservers_in is None:
        observers: list[OutputMonitor] = []
    else:
        observers = onservers_in
    assert observers is not None

    while True:
        line = await sr.readline()
        if line:
            for observer in observers:
                observer.process(line)
        else:
            break


async def _periodic_monitor_call(
    period_seconds: float,
    proc: asyncio.subprocess.Process,  # pylint: disable=no-member
    monitor: ProcessMonitor,
) -> None:
    while True:
        if proc.returncode is not None:
            break
        monitor.observe(proc.pid)
        await asyncio.sleep(period_seconds)


def _adjusted_monitors(
    monitors: list[ProcessMonitor] | None = None,
) -> list[ProcessMonitor]:
    if monitors is not None:
        return monitors
    empty_mon: list[ProcessMonitor] = []
    return empty_mon


async def _cancel_tasks(tasks: list[asyncio.Task[Any]]) -> None:
    for task in tasks:
        if task.cancel():
            with contextlib.suppress(asyncio.CancelledError):
                await task


async def _run_shell_ex_async(
    cmd: list[str],
    *,
    env: dict[str, str],
    cwd: Path | None = None,
    merge_std_streams: bool = True,
    timeout: float | None = None,
    stdout_observers: list[OutputMonitor] | None = None,
    stderr_observers: list[OutputMonitor] | None = None,
    monitors_in: list[ProcessMonitor] | None = None,
    check: bool = True,
) -> int:
    if merge_std_streams:
        stderr = asyncio.subprocess.STDOUT
    else:
        stderr = asyncio.subprocess.PIPE

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=stderr,
        cwd=cwd,
        env=env,
    )

    background_taskset: list[asyncio.Task[Any]] = []
    monitors = _adjusted_monitors(monitors_in)

    for monitor in monitors:
        monitor.on_start(process.pid, cmd)

    assert process.stdout is not None
    background_taskset.append(
        asyncio.create_task(
            _stream_line_reader(process.stdout, stdout_observers)
        )
    )
    if not merge_std_streams:
        assert process.stderr is not None
        background_taskset.append(
            asyncio.create_task(
                _stream_line_reader(process.stderr, stderr_observers)
            )
        )
    background_taskset.extend(
        asyncio.create_task(
            _periodic_monitor_call(monitor.period, process, monitor)
        )
        for monitor in monitors
    )

    try:
        await asyncio.wait_for(process.wait(), timeout=timeout)
        termination_reason = TERMINATE_NORMAL
    except TimeoutError:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
            termination_reason = TERMINATE_TIMEOUT
        except TimeoutError:
            process.kill()
            await process.wait()
            termination_reason = TERMINATE_KILL

    # wait for pending tasks to complete
    await asyncio.wait(background_taskset, timeout=1.0)
    # cancel all pending tasks
    await _cancel_tasks(background_taskset)

    assert process.returncode is not None
    for monitor in monitors:
        monitor.on_end(process.returncode, termination_reason)

    if check and process.returncode != 0:
        msg = f"unexpected return code {process.returncode}"
        raise CommandFailedError(msg)
    return process.returncode


def run_shell_ex(
    cmd: Sequence[str | Path],
    *,
    env: dict[str, str],
    cwd: Path | None = None,
    merge_std_streams: bool = True,
    timeout: float | None = None,
    stdout_observers: list[OutputMonitor] | None = None,
    stderr_observers: list[OutputMonitor] | None = None,
    system_monitors: list[ProcessMonitor] | None = None,
    check: bool = True,
) -> int:
    """Run shell command in background, allowing subprocess observation."""
    stringified_cmd = [str(item) for item in cmd]

    return asyncio.run(
        _run_shell_ex_async(
            stringified_cmd,
            env=env,
            cwd=cwd,
            merge_std_streams=merge_std_streams,
            timeout=timeout,
            stdout_observers=stdout_observers,
            stderr_observers=stderr_observers,
            monitors_in=system_monitors,
            check=check,
        )
    )
