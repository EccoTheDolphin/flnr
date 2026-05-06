"""Interfaces for command recipe tracing."""

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class CommandTracerProtocol(Protocol):
    """Protocol for command tracing implementations.

    Implementations receive execution details before the child process is
    created.

    Command arguments and environment variable values may be sensitive.
    Implementations should record only values appropriate for their output
    destination.
    """

    def trace_command(
        self,
        *,
        cmd: tuple[str, ...],
        cwd: Path | None,
        env: Mapping[str, str],
        host_env: Mapping[str, str],
    ) -> None:
        """Receive execution details before the child process is created.

        ``cmd`` represents the command to execute: the program path followed by
        its arguments. ``cwd`` is the caller-supplied working directory;
        ``None`` means the child inherits the parent process working directory.
        ``env`` is the environment passed to the child. ``host_env`` is a
        snapshot of the host process environment.
        """
