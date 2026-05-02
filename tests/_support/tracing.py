import os
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

TRACE_DIR_ENV = "FLNR_TEST_TRACE_DIR"


def _get_event_dir(moniker: str, *, should_exist: bool) -> Path:
    event_dir = Path(moniker)
    if should_exist:
        if not event_dir.is_dir():
            error_msg = f"could not find event directory: {event_dir}"
            raise FileNotFoundError(error_msg)
    else:
        event_dir.mkdir()
    return event_dir


EventGroup: TypeAlias = type[object]


class InvalidTraceProfileWarning(UserWarning):
    pass


class EventTracingError(Exception):
    pass


class EventNotFoundError(EventTracingError):
    pass


class EventFoundError(EventTracingError):
    pass


class TraceEvent:
    pass


@dataclass(frozen=True)
class TraceEventId:
    event_id: str


def _collect_trace_events(group: EventGroup) -> dict[TraceEvent, TraceEventId]:
    result: dict[TraceEvent, TraceEventId] = {}

    for name, value in vars(group).items():
        if isinstance(value, TraceEvent):
            result[value] = TraceEventId(name)

    return result


class TraceEmitter:
    def __init__(self, event_group: EventGroup) -> None:
        self.event_dir = _get_event_dir(
            os.environ[TRACE_DIR_ENV], should_exist=True
        )
        self.supported_events = _collect_trace_events(event_group)

    def emit(self, ev: TraceEvent) -> None:
        event = self.supported_events[ev]
        (self.event_dir / event.event_id).touch(exist_ok=False)


class TraceObserver:
    def __init__(self, event_group: EventGroup, trace_location: Path) -> None:
        self.event_dir = _get_event_dir(str(trace_location), should_exist=False)
        self.supported_events = _collect_trace_events(event_group)

    def assert_absent(self, ev: TraceEvent) -> None:
        event = self.supported_events[ev]
        if not (self.event_dir / event.event_id).exists():
            return
        error_msg = f"event: {event.event_id} is present"
        raise EventFoundError(error_msg)

    def assert_present(self, ev: TraceEvent) -> None:
        event = self.supported_events[ev]
        if (self.event_dir / event.event_id).exists():
            return
        error_msg = f"event: {event.event_id} is not found"
        raise EventNotFoundError(error_msg)

    def observed_events(self) -> tuple[str, ...]:
        observed: list[str] = [
            event.event_id
            for event in self.supported_events.values()
            if (self.event_dir / event.event_id).exists()
        ]
        return tuple(sorted(observed))

    def expect_state(
        self,
        must_present: tuple[TraceEvent, ...],
        must_absent: tuple[TraceEvent, ...],
    ) -> None:
        for ev in must_present:
            self.assert_present(ev)
        for ev in must_absent:
            self.assert_absent(ev)
