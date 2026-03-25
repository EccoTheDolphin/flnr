"""Internal orchestration utilities."""

import asyncio
import time
from collections.abc import Sequence
from typing import Any

from .exceptions import MonitorFailedError
from .monitors import OutputMonitor, ProcessMonitor, ProcessTerminationReason

# Delay in seconds before retrying a failed read operation.  The intention for
# this delay is to ensure that the underlying pipe is left alone for a while in
# a hope that blocking problem resolves itself (if the error is recoverable).
# The exact value is just an arbitrary small number and has no subtle meaning.
# If you encounter scenarios where this delay is insufficient or excessive,
# please report them.
_DELAY_FOR_RETRY_ON_UNEXPECTED_READER_EXCEPTION = 0.01
# Internal chunk size used by process output reader
_READER_TASK_CHUNK_SIZE = 64 * 1024
# Maximum number of consecutive abnormal situations for reader to bail out.
# Currently, it is not clear if we need this at all, as we have no real-world
# evidence that such situations are observed in the wild. If you encounter
# scenarios where this delay is insufficient or excessive, please report them.
_MAX_CONSECUTIVE_FAILURES_FOR_READER = 3


def _feed_data_to_output_monitors(
    monitor_errors: list[BaseException],
    monitors: Sequence[OutputMonitor],
    data: bytes,
    ts: float,
) -> Sequence[OutputMonitor]:

    active_monitors = []
    for monitor in monitors:
        try:
            monitor.process(data, ts)
            active_monitors.append(monitor)
        except Exception as e:  # noqa: PERF203, BLE001
            # annotate with timestamp
            monitor_errors.append(e)
            continue
    return active_monitors


async def _reader_task(
    logging_errors: list[BaseException],
    sr: asyncio.StreamReader,
    observers: Sequence[OutputMonitor],
) -> None:
    active_observers = observers
    consecutive_failures_count = 0
    while True:
        try:
            data = await sr.read(_READER_TASK_CHUNK_SIZE)
            # data can be empty here, this is fine
            consecutive_failures_count = 0
            active_observers = _feed_data_to_output_monitors(
                logging_errors, active_observers, data, time.monotonic()
            )
            if not data:
                # this is EOF. Stop the reader
                break
        except asyncio.CancelledError:
            # since task is going to be cancelled, we indicate that the data
            # is ended
            _feed_data_to_output_monitors(
                logging_errors, active_observers, b"", time.monotonic()
            )
            raise
        # Here comes the tricky part. python does not really document the
        # set of exceptions it can raise here. we have no way of knowing which
        # ones are recoverable and which ones are not. Our strategy here is:
        # - we assume that all exceptions are recoverable: the next read
        # will either succeed or it will throw once again.
        # - if this is a temporary hick-up, we allow system to do something
        # else and then retry
        # - if we have several consecutive exceptions without forward progress
        # we bail-out and report failure
        except Exception as e:  # noqa: BLE001
            consecutive_failures_count += 1
            if (
                consecutive_failures_count
                > _MAX_CONSECUTIVE_FAILURES_FOR_READER
            ):
                # reader task is effectively dead, no more data is expected
                _feed_data_to_output_monitors(
                    logging_errors, active_observers, b"", time.monotonic()
                )
                break
            logging_errors.append(e)
            # let the system do something else
            await asyncio.sleep(_DELAY_FOR_RETRY_ON_UNEXPECTED_READER_EXCEPTION)


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

        assert proc.stdout is not None

        self.output_reader_tasks.append(
            asyncio.create_task(
                _reader_task(self.monitor_errors, proc.stdout, stdout_observers)
            )
        )
        if proc.stderr is not None:
            self.output_reader_tasks.append(
                asyncio.create_task(
                    _reader_task(
                        self.monitor_errors, proc.stderr, stderr_observers
                    )
                )
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
