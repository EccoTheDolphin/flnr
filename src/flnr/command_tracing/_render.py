"""Platform dispatch for command rendering."""

from collections.abc import Mapping
from pathlib import Path

from .env_listing import EnvListing
from .platform import _posix, _windows


def _render_command_recipe(
    *,
    cmd: tuple[str, ...],
    cwd: Path | None,
    env_listing: EnvListing,
    host_env: Mapping[str, str],
    platform: str,
) -> str:
    """Render a command recipe for the selected platform."""
    if platform.startswith("win"):
        return _windows.render_recipe(
            cmd=cmd,
            cwd=cwd,
            env_listing=env_listing,
            host_env=host_env,
        )
    return _posix.render_recipe(
        cmd=cmd,
        env_listing=env_listing,
        host_env=host_env,
    )
