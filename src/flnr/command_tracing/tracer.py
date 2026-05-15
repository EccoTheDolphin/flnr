"""Bundled command tracer implementation."""

import logging
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol

from ._render import _render_command_recipe
from .env_listing import (
    EnvListing,
    list_changed_environment,
    list_no_environment,
    list_recreated_environment,
    list_selected_environment,
)

_EnvListingCallable = Callable[
    [Mapping[str, str], Mapping[str, str]],
    EnvListing,
]
_DEFAULT_ENV_LISTING = list_no_environment


class LoggerLike(Protocol):
    """Minimal logger interface consumed by CommandTracer.

    Compatible with ``logging.Logger`` and ``logging.LoggerAdapter`` objects.
    """

    def isEnabledFor(self, level: int) -> bool:  # noqa: N802
        """Return whether records at the given level would be emitted."""
        ...

    def log(self, level: int, msg: object) -> None:
        """Log a record at the given level."""
        ...


class CommandTracer:
    """Log diagnostic command recipes.

    Command recipes are shell-oriented renderings intended for inspection and
    logging. They are informational and are not guaranteed to be exact replay
    scripts.

    By default, command tracing records the working directory and command line
    only. Environment values are not logged unless the caller explicitly
    enables environment tracing.

    Use ``with_selected_environment()`` to trace explicit environment
    variables, ``with_changed_environment()`` to trace values changed from the
    host process environment, or ``with_recreated_environment()`` to trace the
    complete child environment from an empty base. These modes write
    environment variable values to logs, so callers should enable them only for
    values safe to expose in their logging destination.

    The logger object is accepted structurally through ``LoggerLike``.
    """

    def __init__(
        self,
        logger: LoggerLike,
        *,
        env_listing: _EnvListingCallable = _DEFAULT_ENV_LISTING,
        level: int = logging.INFO,
    ) -> None:
        """Create a command tracer.

        The logger is used only through ``isEnabledFor()`` and ``log()``.
        """
        self._logger = logger
        self._env_listing = env_listing
        self._level = level
        self._platform = sys.platform

    @classmethod
    def with_changed_environment(
        cls,
        logger: LoggerLike,
        *,
        level: int = logging.INFO,
    ) -> "CommandTracer":
        """Create a tracer logging the command and modified child environment.

        The log includes the command line and any child environment variables
        that differ from the host process. Host variables missing from the
        child are listed by name only.

        Use this mode only if the changed values are safe for the configured
        log destinations.
        """
        return cls(
            logger,
            env_listing=list_changed_environment,
            level=level,
        )

    @classmethod
    def with_selected_environment(
        cls,
        logger: LoggerLike,
        variables: Sequence[str],
        *,
        level: int = logging.INFO,
    ) -> "CommandTracer":
        """Create a tracer logging the command and selected child variables.

        This tracer restricts environment variable listing to explicitly
        requested keys. Select only variables with values safe for the
        configured log destinations.
        """
        return cls(
            logger,
            env_listing=list_selected_environment(variables),
            level=level,
        )

    @classmethod
    def with_recreated_environment(
        cls,
        logger: LoggerLike,
        *,
        level: int = logging.INFO,
    ) -> "CommandTracer":
        """Create a tracer logging a recreated child environment.

        The log includes the command line and the complete child environment
        as assignments applied after clearing inherited environment values.

        Use this mode only if the full child environment is safe for the
        configured log destinations.
        """
        return cls(
            logger,
            env_listing=list_recreated_environment,
            level=level,
        )

    def trace_command(
        self,
        *,
        cmd: tuple[str, ...],
        cwd: Path | None,
        env: Mapping[str, str],
        host_env: Mapping[str, str],
    ) -> None:
        """Log the command recipe before process creation."""
        if not self._logger.isEnabledFor(self._level):
            return

        env_listing = self._env_listing(env, host_env)
        command = _render_command_recipe(
            cmd=cmd,
            cwd=cwd,
            env_listing=env_listing,
            host_env=host_env,
            platform=self._platform,
        )

        message = [command]
        if cwd is not None:
            message.append(f"@ cwd: {cwd}")
        if env_listing.missing_variables:
            message.append(
                "@ missing env: " + ", ".join(env_listing.missing_variables)
            )
        self._logger.log(self._level, "\n".join(message))
