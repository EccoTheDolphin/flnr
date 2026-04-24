from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from .fate import ProcessFate
from .monitor_failure import MonitorFailure, MonitorHook, OutputStream
from .monitors import (
    EnvironmentMonitor,
    OutputMonitor,
    OutputMonitorDisableReason,
)

TMonitor = TypeVar("TMonitor")


@dataclass(slots=True)
class _MonitorHandleBase(Generic[TMonitor]):
    monitor: TMonitor
    monitor_index: int
    monitor_failures: list[MonitorFailure]
    is_active: bool = field(default=True, init=False)

    def _record_failure(
        self,
        *,
        hook: MonitorHook,
        exception: Exception,
        stream: OutputStream | None = None,
    ) -> None:
        self.monitor_failures.append(
            MonitorFailure(
                monitor=self.monitor,
                monitor_index=self.monitor_index,
                hook=hook,
                exception=exception,
                stream=stream,
            )
        )
        self.is_active = False


@dataclass(slots=True)
class _OutputMonitorHandle(_MonitorHandleBase[OutputMonitor]):
    stream: OutputStream

    def _disable(self, reason: OutputMonitorDisableReason, ts: float) -> None:
        self.is_active = False
        try:
            self.monitor.on_disable(reason, ts)
        except Exception as exc:  # noqa: BLE001
            self._record_failure(
                hook=MonitorHook.ON_DISABLE,
                exception=exc,
                stream=self.stream,
            )

    def process(self, data: bytes, ts: float) -> None:
        assert self.is_active

        try:
            self.monitor.process(data, ts)
        except Exception as exc:  # noqa: BLE001
            self._record_failure(
                hook=MonitorHook.PROCESS,
                exception=exc,
                stream=self.stream,
            )
            self._disable(OutputMonitorDisableReason.ERROR, ts)

    def on_disable(self, reason: OutputMonitorDisableReason, ts: float) -> None:
        assert self.is_active
        self._disable(reason, ts)


@dataclass(slots=True)
class _EnvironmentMonitorHandle(_MonitorHandleBase[EnvironmentMonitor]):
    def on_start(self, pid: int, cmd: Sequence[str]) -> None:
        assert self.is_active

        try:
            self.monitor.on_start(pid, cmd)
        except Exception as exc:  # noqa: BLE001
            self._record_failure(
                hook=MonitorHook.ON_START,
                exception=exc,
            )

    def observe(self, pid: int) -> None:
        assert self.is_active

        try:
            self.monitor.observe(pid)
        except Exception as exc:  # noqa: BLE001
            self._record_failure(
                hook=MonitorHook.OBSERVE,
                exception=exc,
            )

    def on_end(self, fate: ProcessFate) -> None:
        assert self.is_active

        try:
            self.monitor.on_end(fate)
        except Exception as exc:  # noqa: BLE001
            self._record_failure(
                hook=MonitorHook.ON_END,
                exception=exc,
            )
