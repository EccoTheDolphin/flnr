"""POSIX command rendering."""

import os
import shlex
from collections.abc import Mapping

from flnr.command_tracing.env_listing import EnvListing

# Private and not documented hooks to change rendering style. These may be gone
# in future without notice.
_FLNR_INTERNAL_COMMAND_TRACE_STYLE = "FLNR_INTERNAL_COMMAND_TRACE_STYLE"
_COMMAND_TRACE_STYLE_MULTILINE = "multiline"


def _quote(value: object) -> str:
    return shlex.quote(str(value))


def _render_path_assignment(
    key: str,
    value: str,
    *,
    host_env: Mapping[str, str],
) -> str | None:
    if key != "PATH":
        return None

    host_path = host_env.get("PATH")
    if not host_path:
        return None

    if value == host_path:
        return f"{_quote(key)}=$PATH"

    suffix = ":" + host_path
    if value.endswith(suffix):
        prefix = value[: -len(suffix)]
        return f"{_quote(key)}={_quote(prefix)}:$PATH"

    return None


def _render_assignment(
    key: str,
    value: str,
    *,
    host_env: Mapping[str, str],
) -> str:
    path_assignment = _render_path_assignment(key, value, host_env=host_env)
    if path_assignment is not None:
        return path_assignment

    return f"{_quote(key)}={_quote(value)}"


def _render_multiline_recipe(
    *, env_parts: tuple[str, ...], cmd_parts: tuple[str, ...]
) -> str:
    result: list[str] = []
    base_indent = " " * 2
    arg_indent = " " * 4

    if env_parts:
        result.append(base_indent + env_parts[0])
        result.extend(arg_indent + env_item for env_item in env_parts[1:])
    assert cmd_parts
    result.append(base_indent + cmd_parts[0])
    result.extend(arg_indent + arg_item for arg_item in cmd_parts[1:])
    result[0] = ">\n" + result[0]
    return " \\\n".join(result)


def _render_compact_recipe(
    *, env_parts: tuple[str, ...], cmd_parts: tuple[str, ...]
) -> str:
    assert cmd_parts
    return " ".join(env_parts + cmd_parts)


def render_recipe(
    *,
    cmd: tuple[str, ...],
    env_listing: EnvListing,
    host_env: Mapping[str, str],
) -> str:
    """Render a POSIX-shell command recipe."""
    env_parts: list[str] = []
    cmd_parts: list[str] = []

    if (
        env_listing.variables
        or env_listing.removed_variables
        or env_listing.clear_environment
    ):
        env_parts.append("env")
        if env_listing.clear_environment:
            env_parts.append("-i")
        else:
            env_parts.extend(
                f"-u {_quote(variable)}"
                for variable in env_listing.removed_variables
            )
        env_parts.extend(
            _render_assignment(key, value, host_env=host_env)
            for key, value in env_listing.variables
        )

    cmd_parts.extend(_quote(arg) for arg in cmd)

    if (
        os.environ.get(_FLNR_INTERNAL_COMMAND_TRACE_STYLE)
        == _COMMAND_TRACE_STYLE_MULTILINE
    ):
        return _render_multiline_recipe(
            cmd_parts=tuple(cmd_parts), env_parts=tuple(env_parts)
        )
    return _render_compact_recipe(
        cmd_parts=tuple(cmd_parts), env_parts=tuple(env_parts)
    )
