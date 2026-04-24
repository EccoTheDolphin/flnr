"""Scripted process helpers used by the test suite."""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeAlias
from unittest.mock import AsyncMock, patch

import flnr

StreamEventPayload: TypeAlias = Exception | bytes | Callable[[int, int], bytes]


@dataclass
class StreamEvent:
    payload: StreamEventPayload
    delay: float | None
    signals_process_exit: bool = False


class StreamReaderNoDataError(Exception):
    pass


class _StreamEventReader:
    def __init__(
        self,
        events: Sequence[StreamEvent],
        process_exit_event: asyncio.Event,
    ) -> None:
        self._read_count = 0
        self._events = events
        self._process_exit_event = process_exit_event

    async def read(self, n: int = -1) -> bytes:
        self._read_count += 1

        if not self._events:
            err_msg = "stream reader was created, but event stream is empty"
            raise StreamReaderNoDataError(err_msg)

        element_index = min(len(self._events) - 1, self._read_count - 1)
        current_event = self._events[element_index]

        if current_event.delay is not None and current_event.delay > 0:
            await asyncio.sleep(current_event.delay)

        if current_event.signals_process_exit:
            self._process_exit_event.set()

        if isinstance(current_event.payload, bytes):
            return current_event.payload
        if isinstance(current_event.payload, Exception):
            raise current_event.payload
        if callable(current_event.payload):
            return current_event.payload(self._read_count - 1, n)

        err_msg = "unknown data type"
        raise ValueError(err_msg)


class ScriptedProcess:
    """Process-shaped test double driven by an execution descriptor."""

    def __init__(
        self,
        *,
        pid: int,
        process_exit_event: asyncio.Event,
        on_descriptor_exit: int | None,
        on_terminate: int | None,
        on_kill: int | None,
    ) -> None:
        self.pid = pid
        self.stdout: _StreamEventReader | None = None
        self.stderr: _StreamEventReader | None = None

        self._on_descriptor_exit = on_descriptor_exit
        self._on_terminate = on_terminate
        self._on_kill = on_kill

        self._process_exit_event = process_exit_event
        self._exit_code: int | None = None

    def attach_stdout(self, reader: _StreamEventReader) -> None:
        self.stdout = reader

    def attach_stderr(self, reader: _StreamEventReader) -> None:
        self.stderr = reader

    async def wait(self) -> int:
        await self._process_exit_event.wait()

        async def get_code() -> int:
            while True:
                returncode = self.returncode
                if returncode is not None:
                    break
                await asyncio.sleep(0.01)
            return returncode

        return await get_code()

    @property
    def returncode(self) -> int | None:
        if self._process_exit_event.is_set() and self._exit_code is None:
            self._exit_code = self._on_descriptor_exit
        return self._exit_code

    def terminate(self) -> None:
        if self.returncode is not None:
            return
        self._process_exit_event.set()
        self._exit_code = self._on_terminate

    def kill(self) -> None:
        if self.returncode is not None:
            return
        self._process_exit_event.set()
        self._exit_code = self._on_kill


class ExecutionDescriptor:
    def __init__(
        self,
        *,
        pid: int,
        returncode: int | None,
        on_terminate: None | int = None,
        on_kill: None | int = None,
    ) -> None:
        self.pid = pid
        self.returncode = returncode
        self.stdout_events: list[StreamEvent] = []
        self.stderr_events: list[StreamEvent] = []
        self.on_terminate = on_terminate
        self.on_kill = on_kill

    @staticmethod
    def _append_events(
        target: list[StreamEvent],
        payloads: Sequence[StreamEventPayload],
    ) -> None:
        target.extend(
            StreamEvent(payload=payload, delay=0, signals_process_exit=False)
            for payload in payloads
        )

    @staticmethod
    def _set_delays(
        events: Sequence[StreamEvent], delay: float | Sequence[float]
    ) -> None:
        if isinstance(delay, float):
            for event in events:
                event.delay = delay
        else:
            if len(events) != len(delay):
                err_msg = "invalid number of delays specified"
                raise ValueError(err_msg)
            for index, event in enumerate(events):
                event.delay = delay[index]

    def set_stderr_delays(
        self, delay: float | Sequence[float]
    ) -> "ExecutionDescriptor":
        ExecutionDescriptor._set_delays(self.stderr_events, delay)
        return self

    def set_stdout_delays(
        self, delay: float | Sequence[float]
    ) -> "ExecutionDescriptor":
        ExecutionDescriptor._set_delays(self.stdout_events, delay)
        return self

    def add_stdout_events(
        self, events: Sequence[StreamEventPayload]
    ) -> "ExecutionDescriptor":
        self._append_events(self.stdout_events, events)
        return self

    def add_stderr_events(
        self, events: Sequence[StreamEventPayload]
    ) -> "ExecutionDescriptor":
        self._append_events(self.stderr_events, events)
        return self

    @staticmethod
    def _clone_events(events: Sequence[StreamEvent]) -> list[StreamEvent]:
        return [
            StreamEvent(
                payload=event.payload,
                delay=event.delay,
                signals_process_exit=event.signals_process_exit,
            )
            for event in events
        ]

    def build_process(self) -> ScriptedProcess:
        process_exit_event = asyncio.Event()
        process = ScriptedProcess(
            pid=self.pid,
            process_exit_event=process_exit_event,
            on_descriptor_exit=self.returncode,
            on_terminate=self.on_terminate,
            on_kill=self.on_kill,
        )

        stdout_events = self._clone_events(self.stdout_events)
        stderr_events = self._clone_events(self.stderr_events)

        if self.returncode is not None:
            if stdout_events:
                stdout_events[-1].signals_process_exit = True
            elif stderr_events:
                stderr_events[-1].signals_process_exit = True

        if stdout_events:
            process.attach_stdout(
                _StreamEventReader(stdout_events, process_exit_event)
            )
        if stderr_events:
            process.attach_stderr(
                _StreamEventReader(stderr_events, process_exit_event)
            )
        return process


def run_scripted_process(
    process: ScriptedProcess,
    *,
    stdout_monitors: Sequence[flnr.OutputMonitor] | None = None,
    stderr_monitors: Sequence[flnr.OutputMonitor] | None = None,
    environment_monitors: Sequence[flnr.EnvironmentMonitor] | None = None,
    timeouts: flnr.ExecutionTimeouts | None = None,
    check: bool = True,
) -> flnr.ProcessFate:
    stderr_monitors = stderr_monitors or []
    if stderr_monitors and process.stderr is None:
        err_msg = "stderr monitors provided, but scripted process has no stderr"
        raise ValueError(err_msg)

    with patch(
        "asyncio.create_subprocess_exec", AsyncMock(return_value=process)
    ):
        return flnr.run_ex(
            ["dummy.command"],
            merge_std_streams=process.stderr is None,
            stdout_monitors=stdout_monitors or [],
            stderr_monitors=stderr_monitors,
            environment_monitors=environment_monitors or [],
            timeouts=timeouts,
            check=check,
        )


def run_descriptor(
    descriptor: ExecutionDescriptor,
    *,
    stdout_monitors: Sequence[flnr.OutputMonitor] | None = None,
    stderr_monitors: Sequence[flnr.OutputMonitor] | None = None,
    environment_monitors: Sequence[flnr.EnvironmentMonitor] | None = None,
    timeouts: flnr.ExecutionTimeouts | None = None,
    check: bool = True,
) -> flnr.ProcessFate:
    return run_scripted_process(
        descriptor.build_process(),
        stdout_monitors=stdout_monitors,
        stderr_monitors=stderr_monitors,
        environment_monitors=environment_monitors,
        timeouts=timeouts,
        check=check,
    )
