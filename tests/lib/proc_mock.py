import asyncio
import io
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeAlias
from unittest.mock import AsyncMock, patch

import flnr

StreamDataType: TypeAlias = Exception | bytes | Callable[[int, int], bytes]


class ProcMonImpl(flnr.ProcessMonitor):
    def __init__(self, *, sink: io.IOBase, period: float) -> None:
        super().__init__(period=period)
        self.sink = sink

    def on_start(self, pid: int, cmd: Sequence[str]) -> None:
        self.sink.write(f"on_start called. pid = {pid}, command = {cmd}\n")

    def observe(self, pid: int) -> None:
        self.sink.write(f"observe called. pid = {pid}\n")

    def on_end(self, status: int, term: flnr.ProcessTerminationReason) -> None:
        self.sink.write(f"on_end called. status = {status}, reason = {term}\n")


class MockProcessState:
    def __init__(self, *, returncode: int, pid: int) -> None:
        self.returncode = returncode
        self.pid = pid
        self.exit_event = asyncio.Event()


@dataclass
class MockReadStreamEvent:
    data: StreamDataType
    arrival_delay: float | None
    proc_exit_event: bool = False


class MockReaderNoDataError(Exception):
    pass


class MockReaderStream:
    def __init__(
        self,
        input_stream_chunks: Sequence[MockReadStreamEvent],
        stop_event: asyncio.Event,
    ) -> None:
        self._read_count = 0
        self._input_stream_chunks = input_stream_chunks

        self._proc_stop_event = stop_event

    async def read(self, n: int = -1) -> bytes:
        self._read_count += 1

        if not self._input_stream_chunks:
            err_msg = "MockReaderStream was created, but event stream is empty"
            raise MockReaderNoDataError(err_msg)

        element_index = min(
            len(self._input_stream_chunks) - 1, self._read_count - 1
        )
        current_chunk = self._input_stream_chunks[element_index]

        if (
            current_chunk.arrival_delay is not None
            and current_chunk.arrival_delay > 0
        ):
            await asyncio.sleep(current_chunk.arrival_delay)

        if current_chunk.proc_exit_event:
            self._proc_stop_event.set()

        if isinstance(current_chunk.data, bytes):
            return current_chunk.data
        if isinstance(current_chunk.data, Exception):
            raise current_chunk.data
        if callable(current_chunk.data):
            return current_chunk.data(self._read_count - 1, n)

        err_msg = "unknown data type"
        raise ValueError(err_msg)

    def close(self) -> None:
        pass

    async def drain(self) -> None:
        pass


class MockStreamingProcess:
    def __init__(
        self,
        *,
        proc_state: MockProcessState,
        stdout_sr: MockReaderStream | None,
        stderr_sr: MockReaderStream | None,
    ) -> None:

        self._proc_state = proc_state
        self.pid = proc_state.pid
        self.returncode: int | None = None
        self.stdout = stdout_sr
        self.stderr = stderr_sr

    async def wait(self) -> int:
        await self._proc_state.exit_event.wait()
        self.returncode = self._proc_state.returncode
        return self.returncode

    def terminate(self) -> None:
        self.returncode = self._proc_state.returncode
        self._proc_state.exit_event.set()


class StreamControl:
    def __init__(self, *, returncode: int | None, pid: int) -> None:
        self.pid = pid
        self.returncode = returncode
        self.events: list[MockReadStreamEvent] = []
        self.stdout_mon: list[flnr.OutputMonitor] = []
        self.stderr_mon: list[flnr.OutputMonitor] = []
        self.proc_mon: list[flnr.ProcessMonitor] = []

    @staticmethod
    def _set_delays(
        events: Sequence[MockReadStreamEvent], delay: float | Sequence[float]
    ) -> None:
        if isinstance(delay, float):
            for event in events:
                event.arrival_delay = delay
        else:
            if len(events) != len(delay):
                err_msg = "invalid number of delays specified"
                raise ValueError(err_msg)
            for index, event in enumerate(events):
                event.arrival_delay = delay[index]

    def set_stderr_delays(
        self, delay: float | Sequence[float]
    ) -> "StreamControl":
        StreamControl._set_delays([], delay)
        return self

    def set_stdout_delays(
        self, delay: float | Sequence[float]
    ) -> "StreamControl":
        StreamControl._set_delays(self.events, delay)
        return self

    def add_events(self, events: Sequence[StreamDataType]) -> "StreamControl":
        self.events += [
            MockReadStreamEvent(
                data=event, arrival_delay=0, proc_exit_event=False
            )
            for event in events
        ]
        return self

    def add_output_observers(
        self, mon: Sequence[flnr.OutputMonitor]
    ) -> "StreamControl":
        self.stdout_mon += mon
        return self

    def add_stderr_observers(
        self, mon: Sequence[flnr.OutputMonitor]
    ) -> "StreamControl":
        self.stderr_mon += mon
        return self

    def add_process_monitors(
        self, mon: Sequence[flnr.ProcessMonitor]
    ) -> "StreamControl":
        self.proc_mon += mon
        return self

    def build_process(self) -> MockStreamingProcess:
        procstatuscode = -1
        if self.returncode is not None:
            procstatuscode = self.returncode
            self.events[-1].proc_exit_event = True

        exit_state = MockProcessState(returncode=procstatuscode, pid=self.pid)
        stdout_sr = MockReaderStream(self.events, exit_state.exit_event)

        return MockStreamingProcess(
            proc_state=exit_state, stdout_sr=stdout_sr, stderr_sr=None
        )

    def run(
        self,
        process: MockStreamingProcess,
        timeouts: flnr.ExecutionTimeouts | None = None,
    ) -> None:
        with patch(
            "asyncio.create_subprocess_exec", AsyncMock(return_value=process)
        ):
            flnr.run_shell_ex(
                ["dummy.command"],
                merge_std_streams=True,
                stdout_observers=self.stdout_mon,
                stderr_observers=self.stderr_mon,
                process_monitors=self.proc_mon,
                timeouts=timeouts,
            )
