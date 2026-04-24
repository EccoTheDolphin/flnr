"""Identification of monitor failure reasons."""

from dataclasses import dataclass
from enum import Enum


class _StrEnum(str, Enum):
    """Home-brewed version of a modern string enum."""

    def __str__(self) -> str:
        """Provide string representation of enumerated string value."""
        return str(self.value)


class MonitorHook(_StrEnum):
    """Identification of the method that caused failure."""

    PROCESS = "process"
    ON_DISABLE = "on_disable"
    ON_START = "on_start"
    OBSERVE = "observe"
    ON_END = "on_end"


class OutputStream(_StrEnum):
    """Identification of output stream for error reporting."""

    STDOUT = "stdout"
    STDERR = "stderr"


@dataclass(frozen=True, slots=True)
class MonitorFailure:
    """Information about a monitor failure instance."""

    monitor: object
    hook: MonitorHook
    exception: Exception
    monitor_index: int
    stream: OutputStream | None = None

    @property
    def monitor_name(self) -> str:
        """Human-readable monitor type."""
        return type(self.monitor).__name__

    @property
    def monitor_kind(self) -> str:
        """Human-readable monitor kind."""
        return (
            "environment monitor"
            if self.stream is None
            else f"{self.stream} monitor"
        )

    @property
    def location(self) -> str:
        """Identification of what method was called at the moment of failure."""
        return self.hook

    def __str__(self) -> str:
        """Human-readable renderer."""
        return (
            f"{self.monitor_kind} #{self.monitor_index} ({self.monitor_name}) "
            f"failed in {self.hook}: {self.exception!r}"
        )
