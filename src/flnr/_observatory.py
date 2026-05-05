"""internal monitoring and stream-dispatch machinery."""

import asyncio
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ._async_utils import _cancel_tasks
from ._monitor_handles import _EnvironmentMonitorHandle, _OutputMonitorHandle
from ._task_ledger import _TaskLedger
from .fate import ProcessFate
from .monitor_failure import MonitorFailure, OutputStream
from .monitors import (
    EnvironmentMonitor,
    OutputMonitor,
    OutputMonitorDisableReason,
)

# Internal chunk size used by process output reader
_READER_TASK_CHUNK_SIZE = 64 * 1024


class _StreamEventsSink:
    def __init__(
        self,
        monitors: tuple[OutputMonitor, ...],
        monitor_failures: list[MonitorFailure],
        stream_id: OutputStream,
    ) -> None:
        self.monitor_handles = [
            _OutputMonitorHandle(
                monitor=m,
                monitor_index=i,
                stream=stream_id,
                monitor_failures=monitor_failures,
            )
            for i, m in enumerate(monitors)
        ]
        self.monitor_failures = monitor_failures

    def on_data(self, data_chunk: bytes, ts: float) -> None:
        for monitor_handle in self.monitor_handles:
            if monitor_handle.is_active:
                monitor_handle.process(data_chunk, ts)

    def disable(self, reason: OutputMonitorDisableReason, ts: float) -> None:
        for monitor_handle in self.monitor_handles:
            if monitor_handle.is_active:
                monitor_handle.on_disable(reason, ts)
                assert not monitor_handle.is_active


@dataclass
class _ReaderTaskSignals:
    monitor_callbacks_allowed: asyncio.Event
    drain_requested: asyncio.Event
    fatal_reader_error: asyncio.Event


async def _stream_relay(
    sr: asyncio.StreamReader,
    event_sink: _StreamEventsSink,
    monitor_callbacks_allowed: asyncio.Event,
    out_event_fatal_error: asyncio.Event,
) -> None:
    try:
        while data_chunk := await sr.read(_READER_TASK_CHUNK_SIZE):
            ts = time.monotonic()
            await monitor_callbacks_allowed.wait()
            event_sink.on_data(data_chunk, ts=ts)
            await asyncio.sleep(0)
        event_sink.disable(OutputMonitorDisableReason.EOF, time.monotonic())
    except Exception:
        out_event_fatal_error.set()
        raise
    finally:
        # disable() is idempotent for this sink, so calling it on every relay
        # task exit gives a single finalization path.
        # After normal EOF this is effectively a no-op for already-disabled
        # monitors.
        # After an abnormal exit it finalizes any monitors that were left
        # active.
        event_sink.disable(OutputMonitorDisableReason.ERROR, time.monotonic())


async def _drain_controller(
    relay_task: asyncio.Task[Any],
    event_sink: _StreamEventsSink,
    drain_event: asyncio.Event,
    drain_timeout: float,
) -> None:
    await drain_event.wait()
    await asyncio.wait({relay_task}, timeout=drain_timeout)
    event_sink.disable(
        OutputMonitorDisableReason.DRAIN_TIMEOUT, time.monotonic()
    )
    if not relay_task.done():
        await _cancel_tasks(relay_task)


async def _reader_task(
    *,
    sr: asyncio.StreamReader,
    stream_id: OutputStream,
    drain_timeout: float,
    monitors: tuple[OutputMonitor, ...],
    monitor_failures: list[MonitorFailure],
    control: _ReaderTaskSignals,
) -> None:

    self_task = asyncio.current_task()
    assert self_task is not None
    self_name = self_task.get_name()

    event_sink = _StreamEventsSink(monitors, monitor_failures, stream_id)
    task_ledger = _TaskLedger()

    relay_task = task_ledger.create_task(
        _stream_relay(
            sr,
            event_sink,
            control.monitor_callbacks_allowed,
            control.fatal_reader_error,
        ),
        name=f"{self_name}.relay",
    )

    reader_drain_controller_task = task_ledger.create_task(
        _drain_controller(
            relay_task, event_sink, control.drain_requested, drain_timeout
        ),
        name=f"{self_name}.drain_controller",
    )

    try:
        await asyncio.gather(reader_drain_controller_task, relay_task)
    finally:
        await task_ledger.cancel_all()


@dataclass(frozen=True, slots=True)
class _EnvironmentMonitorScope:
    pid: int
    cmd: Sequence[str]
    monitor_failures: list[MonitorFailure]
    process_fate_task: asyncio.Task[ProcessFate]
    monitor_callbacks_allowed: asyncio.Event


async def _env_monitor_task(
    monitor: EnvironmentMonitor,
    monitor_index: int,
    scope: _EnvironmentMonitorScope,
) -> None:
    monitor_handle = _EnvironmentMonitorHandle(
        monitor=monitor,
        monitor_index=monitor_index,
        monitor_failures=scope.monitor_failures,
    )
    await scope.monitor_callbacks_allowed.wait()
    monitor_handle.on_start(scope.pid, scope.cmd)
    if not monitor_handle.is_active:
        return

    while True:
        done, _ = await asyncio.wait(
            {scope.process_fate_task}, timeout=monitor.period
        )

        if scope.process_fate_task in done:
            break
        await scope.monitor_callbacks_allowed.wait()
        monitor_handle.observe(scope.pid)
        if not monitor_handle.is_active:
            return

    resolved_fate = await scope.process_fate_task
    await scope.monitor_callbacks_allowed.wait()
    monitor_handle.on_end(resolved_fate)
