import io
import time
from collections.abc import Sequence
from dataclasses import dataclass

import flnr


class EnvMonitorProbe(flnr.EnvironmentMonitor):
    def __init__(self, *, sink: io.IOBase, period: float) -> None:
        super().__init__(period=period)

        self.cmd: None | Sequence[str] = None
        self.pid: None | int = None
        self.ts_start: float | None = None
        self.n_start_called = 0

        self.ts_observed: list[float] = []

        self.ts_end: float | None = None
        self.n_end_called = 0
        self.fate: flnr.ProcessFate | None = None

        self.sink = sink

    def on_start(self, pid: int, cmd: Sequence[str]) -> None:
        ts = time.monotonic()
        assert self.cmd is None, "cmd already set"
        assert self.pid is None, "pid already set"
        assert self.ts_start is None, "ts_start already set"
        assert self.n_start_called == 0, "on_start called more than once"

        self.cmd = list(cmd)
        self.pid = pid
        self.ts_start = ts
        self.n_start_called += 1

        self.sink.write(f"on_start called. pid = {pid}, command = {cmd}\n")

    def observe(self, pid: int) -> None:
        ts = time.monotonic()
        assert self.n_start_called == 1, "observe called before on_start"
        assert self.n_end_called == 0, "observe called after on_end"
        assert self.pid == pid, "pid changed during observation"
        if self.ts_observed:
            assert ts >= self.ts_observed[-1], (
                "observe timestamps went backwards"
            )

        self.ts_observed.append(ts)
        self.sink.write(f"observe called. pid = {pid}\n")

    def on_end(self, fate: flnr.ProcessFate) -> None:
        ts = time.monotonic()
        assert self.n_start_called == 1, "on_end called before on_start"
        assert self.n_end_called == 0, "on_end called more than once"
        assert self.fate is None, "fate already set"

        assert self.ts_start is not None
        assert ts >= self.ts_start, "end timestamp before start"

        if self.ts_observed:
            assert ts >= self.ts_observed[-1], (
                "end timestamp before last observe"
            )

        self.ts_end = ts
        self.fate = fate
        self.n_end_called += 1
        self.sink.write(f"on_end called. {fate}\n")


class OutputMonitorProbe(flnr.OutputMonitor):
    def __init__(self, sink: io.IOBase | None) -> None:
        self.sink = sink

        self.stop_reason: flnr.OutputMonitorDisableReason | None = None
        self.ts_stop: float | None = None

        self.n_processed_bytes = 0
        self.n_process_calls = 0
        self.ts_last_process: float | None = None

    def process(self, data: bytes, ts: float) -> None:
        assert isinstance(data, bytes)
        assert self.stop_reason is None, "process called after on_disable"
        self.n_process_calls += 1
        self.ts_last_process = ts

        self.n_processed_bytes += len(data)
        if self.sink is not None:
            self.sink.write(data)

    def on_disable(
        self, reason: flnr.OutputMonitorDisableReason, ts: float
    ) -> None:
        assert self.stop_reason is None, "on_disable called more than once"
        self.stop_reason = reason
        self.ts_stop = ts


@dataclass(frozen=True)
class WriteCall:
    data: str


@dataclass(frozen=True)
class FlushCall:
    pass


class TextIOProbe(io.StringIO):
    def __init__(
        self,
    ) -> None:
        super().__init__()
        self._closed = False

        self.calls: list[WriteCall | FlushCall] = []

    def writable(self) -> bool:
        return True

    @property
    def closed(self) -> bool:
        return self._closed

    def write(self, s: str) -> int:
        if self._closed:
            err_msg = "I/O operation on closed file."
            raise ValueError(err_msg)

        if not isinstance(s, str):
            err_msg = f"expected str, got {type(s).__name__}"
            raise TypeError(err_msg)

        self.calls.append(WriteCall(s))

        return len(s)

    def flush(self) -> None:
        if self._closed:
            err_msg = "I/O operation on closed file."
            raise ValueError(err_msg)

        self.calls.append(FlushCall())

    def close(self) -> None:
        if not self._closed:
            self._closed = True

    def getvalue(self) -> str:
        write_calls = [w for w in self.calls if isinstance(w, WriteCall)]
        return "".join([w.data for w in write_calls])

    def getevents(self) -> list[WriteCall | FlushCall]:
        return self.calls
