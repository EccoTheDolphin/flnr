"""Flnr a library for non-invasive monitoring of subprocesses."""

import asyncio
import io
import os
import traceback
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from enum import Enum
from pathlib import Path
from typing import Any, TextIO
from typing import cast as typing_cast


class FlnrExceptionBaseError(Exception):
    """Base class for all exceptions raised by flnr."""


class CommandFailedError(FlnrExceptionBaseError):
    """Raised if command fails when user asked to ensure that it succeeds."""


class MonitorFailedError(FlnrExceptionBaseError):
    """Raised when one or more monitors (output or process) fail.

    This exception aggregates all monitor failures and includes the process
    return code. Users are expected to inspect the contained exceptions.
    """

    def __init__(
        self, returncode: int, exc_list: Sequence[BaseException], message: str
    ) -> None:
        """Provide information about monitoring error and process status."""
        super().__init__(message)
        self.proc_returncode = returncode
        self.monitor_exceptions = exc_list

    def __str__(self) -> str:
        """Serialize information about encountered abnormal situations."""
        err_msgs: list[str] = []
        err_msgs.append(f"{self.args[0]}")
        err_msgs.append(f"process returncode: {self.proc_returncode}")
        for i, cause in enumerate(self.monitor_exceptions):
            tr = "  ".join(
                traceback.format_exception(
                    type(cause), cause, cause.__traceback__
                )
            )
            err_msgs.append(f"{i}: {cause}; {tr}")
        return "\n".join(err_msgs)


class OutputMonitor(ABC):  # pylint: disable=too-few-public-methods
    """Interface that subprocess output monitors must implement."""

    def __init__(self, *, line_proc: bool) -> None:
        """Select between lines/bytes processing mode.

        :param line_proc: request line processing mode

        At the moment line_proc = True is the only supported mode
        """
        self.line_proc = line_proc

        if not line_proc:
            err_msg = "line_proc=False is not yet supported."
            raise NotImplementedError(err_msg)

    @abstractmethod
    def process(self, data: bytes) -> None:
        """Process subprocess output."""


class LoggingOutputMonitor(OutputMonitor):  # pylint: disable=too-few-public-methods
    """Standard implementation of output monitoring."""

    def __init__(
        self,
        *,
        sink: io.IOBase | TextIO,
        encoding: str | None = None,
        auto_flush: bool = True,
    ) -> None:
        """Define how data is processed by the monitor.

        :param sink: output stream to send processed result
        :param encoding: encoding of data to process. Use *None* for binary
        :param auto_flush: flush output stream after each write to sink
        """
        super().__init__(line_proc=True)
        self.sink = sink
        self.encoding = encoding
        self.auto_flush = auto_flush

    def process(self, data: bytes) -> None:
        """Process subprocess output.

        If encoding is specified, the data is decoded to python string
        before writing to output
        """
        if self.encoding is not None:
            decoded = data.decode(self.encoding, errors="replace")
            self.sink.write(decoded)
        else:
            typing_cast("io.IOBase", self.sink).write(data)
        if self.auto_flush:
            self.sink.flush()


class ProcessTerminationReason(Enum):
    """Identify reason for process termination."""

    NORMAL = "finished"
    TIMEOUT = "terminate"
    KILL = "kill"

    def __str__(self) -> str:
        """Provide string representation of ProcessTerminationReason."""
        return self.value


class ProcessMonitor(ABC):
    """Interface that global monitors must implement."""

    def __init__(self, *, period: float) -> None:
        """Define how often the monitor is called."""
        self.period = period

    @abstractmethod
    def on_start(self, pid: int, cmd: Sequence[str]) -> None:
        """Notification when subprocess corresponding to command is created."""

    @abstractmethod
    def observe(self, pid: int) -> None:
        """Periodic notification while the subprocess is being monitored.

        At the time `observe(pid)` is called:

        - The PID is guaranteed to still refer to the original process
        - The PID has not been reused by the OS
        - The process may have already exited but has not yet been reaped

        Callbacks must not assume that the process is still running, only that
        the PID is still valid and owned by the original process.
        """

    @abstractmethod
    def on_end(
        self, return_code: int, stop_info: ProcessTerminationReason
    ) -> None:
        """Best-effort notification callback that is called when process exits.

        It is NOT guaranteed to be called if the monitor fails during execution.
        It must not be relied upon for cleanup or critical logic.
        """


async def _stream_line_reader(
    logging_errors: list[BaseException],
    sr: asyncio.StreamReader,
    observers_in: Sequence[OutputMonitor] | None,
) -> None:
    active_observers = list(observers_in or [])
    while True:
        line = await sr.readline()
        if line:
            to_preserve = []
            for observer in active_observers:
                try:
                    observer.process(line)
                    to_preserve.append(observer)
                except Exception as e:  # noqa: PERF203, BLE001
                    logging_errors.append(e)
                    continue
            active_observers = to_preserve
        else:
            break


async def _periodic_monitor_call(
    proc: asyncio.subprocess.Process,  # pylint: disable=no-member
    monitor: ProcessMonitor,
) -> None:
    while proc.returncode is None:
        monitor.observe(proc.pid)
        await asyncio.sleep(monitor.period)


async def _cancel_tasks(tasks: list[asyncio.Task[Any]]) -> None:
    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)


def _create_output_readers(
    logging_errors: list[BaseException],
    stdout: asyncio.StreamReader,
    stderr: asyncio.StreamReader | None,
    stdout_observers: Sequence[OutputMonitor] | None,
    stderr_observers: Sequence[OutputMonitor] | None,
) -> list[asyncio.Task[Any]]:
    background_taskset: list[asyncio.Task[Any]] = []
    background_taskset.append(
        asyncio.create_task(
            _stream_line_reader(logging_errors, stdout, stdout_observers)
        )
    )
    if stderr is not None:
        background_taskset.append(
            asyncio.create_task(
                _stream_line_reader(logging_errors, stderr, stderr_observers)
            )
        )
    return background_taskset


class _Observatory:
    """Internal orchestration component.

    Responsible for:
    - starting monitors
    - managing background tasks
    - collecting monitor errors
    - coordinating teardown
    """

    def __init__(
        self,
        *,
        proc: asyncio.subprocess.Process,
        cmd: Sequence[str],
        stdout_observers: Sequence[OutputMonitor],
        stderr_observers: Sequence[OutputMonitor],
        process_monitors: Sequence[ProcessMonitor],
        output_drain_timeout: float,
    ) -> None:

        self.process = proc
        self.monitor_errors: list[BaseException] = []
        self.output_reader_tasks: list[asyncio.Task[Any]] = []

        assert self.process.stdout is not None

        self.output_reader_tasks = _create_output_readers(
            self.monitor_errors,
            self.process.stdout,
            self.process.stderr,
            stdout_observers,
            stderr_observers,
        )

        started_monitors: list[ProcessMonitor] = []
        for process_monitor in process_monitors:
            try:
                process_monitor.on_start(self.process.pid, cmd)
            except Exception as e:  # noqa: BLE001
                self.monitor_errors.append(e)
                continue
            started_monitors.append(process_monitor)

        self.started_monitors = started_monitors
        self.monitor_tasks: list[asyncio.Task[Any]] = [
            asyncio.create_task(_periodic_monitor_call(self.process, monitor))
            for monitor in self.started_monitors
        ]
        self.output_drain_timeout = output_drain_timeout

    def _report_errors(self) -> None:
        for task in self.output_reader_tasks + self.monitor_tasks:
            if task.cancelled():
                continue
            exc = task.exception()
            if exc:
                self.monitor_errors.append(exc)
        if self.monitor_errors:
            failure_count = len(self.monitor_errors)
            logger_task_failed = (
                f"{failure_count} monitor failures were detected"
            )
            assert self.process.returncode is not None
            raise MonitorFailedError(
                self.process.returncode, self.monitor_errors, logger_task_failed
            )

    async def teardown(
        self, termination_reason: ProcessTerminationReason
    ) -> None:
        # wait for pending tasks to complete
        await asyncio.wait(
            self.output_reader_tasks, timeout=self.output_drain_timeout
        )
        # cancel all pending tasks
        await _cancel_tasks(self.output_reader_tasks + self.monitor_tasks)

        assert self.process.returncode is not None

        for i, monitor in enumerate(self.started_monitors):
            monitor_task = self.monitor_tasks[i]
            assert monitor_task.done()
            # if task is done we call on_end callback only if there is no
            # exception
            if monitor_task.cancelled() or not monitor_task.exception():
                try:
                    monitor.on_end(self.process.returncode, termination_reason)
                except Exception as e:  # noqa: BLE001
                    self.monitor_errors.append(e)
                    continue

        self._report_errors()


async def _run_shell_ex_async(
    cmd: Sequence[str],
    *,
    env: Mapping[str, str],
    cwd: Path | None = None,
    merge_std_streams: bool = True,
    timeout: float | None = None,
    stdout_observers: Sequence[OutputMonitor] | None = None,
    stderr_observers: Sequence[OutputMonitor] | None = None,
    process_monitors: Sequence[ProcessMonitor] | None = None,
    check: bool = True,
) -> int:
    if merge_std_streams:
        stderr = asyncio.subprocess.STDOUT
        if stderr_observers is not None and len(stderr_observers) > 0:
            err_msg = "stderr observers provided, while stdout/stderr merged"
            raise ValueError(err_msg)
    else:
        stderr = asyncio.subprocess.PIPE

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=stderr,
        cwd=cwd,
        env=env,
    )

    assert process.stdout is not None
    observatory = _Observatory(
        proc=process,
        cmd=cmd,
        stdout_observers=(stdout_observers or []),
        stderr_observers=(stderr_observers or []),
        process_monitors=(process_monitors or []),
        output_drain_timeout=1.0,
    )

    try:
        await asyncio.wait_for(process.wait(), timeout=timeout)
        termination_reason = ProcessTerminationReason.NORMAL
    except asyncio.exceptions.TimeoutError:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
            termination_reason = ProcessTerminationReason.TIMEOUT
        except asyncio.exceptions.TimeoutError:
            process.kill()
            await process.wait()
            termination_reason = ProcessTerminationReason.KILL

    assert process.returncode is not None
    await observatory.teardown(termination_reason)

    if check and process.returncode != 0:
        msg = f"unexpected return code {process.returncode}"
        raise CommandFailedError(msg)
    return process.returncode


def run_shell_ex(
    cmd: Sequence[str | Path],
    *,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    merge_std_streams: bool = True,
    timeout: float | None = None,
    stdout_observers: Sequence[OutputMonitor] | None = None,
    stderr_observers: Sequence[OutputMonitor] | None = None,
    process_monitors: Sequence[ProcessMonitor] | None = None,
    check: bool = True,
) -> int:
    """Run shell command in background, allowing subprocess observation."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        err_msg = "run_shell_ex() cannot be called from an async context"
        raise RuntimeError(err_msg)
    if env is None:
        env = os.environ.copy()
    return asyncio.run(
        _run_shell_ex_async(
            [str(item) for item in cmd],
            env=env,
            cwd=cwd,
            merge_std_streams=merge_std_streams,
            timeout=timeout,
            stdout_observers=stdout_observers,
            stderr_observers=stderr_observers,
            process_monitors=process_monitors,
            check=check,
        )
    )
