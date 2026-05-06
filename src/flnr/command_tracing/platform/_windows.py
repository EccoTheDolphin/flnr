"""PowerShell command rendering."""

from collections.abc import Mapping
from pathlib import Path

from flnr.command_tracing.env_listing import EnvListing


def _quote(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _render_path_assignment(
    key: str,
    value: str,
    *,
    host_env: Mapping[str, str],
) -> str | None:
    if key.upper() != "PATH":
        return None

    host_path = (
        host_env.get(key) or host_env.get("PATH") or host_env.get("Path")
    )
    if not host_path:
        return None

    target = f"$psi.Environment[{_quote(key)}]"
    if value == host_path:
        return f"{target} = $env:{key}"

    suffix = ";" + host_path
    if value.endswith(suffix):
        prefix = value[: -len(suffix)]
        return f"{target} = {_quote(prefix)} + ';' + $env:{key}"

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

    return f"$psi.Environment[{_quote(key)}] = {_quote(value)}"


def render_recipe(
    *,
    cmd: tuple[str, ...],
    cwd: Path | None,
    env_listing: EnvListing,
    host_env: Mapping[str, str],
) -> str:
    """Render a PowerShell command recipe."""
    command = " ".join(["&", *(_quote(arg) for arg in cmd)])
    if (
        cwd is None
        and not env_listing.variables
        and not env_listing.removed_variables
        and not env_listing.clear_environment
    ):
        return command

    lines = [
        ">",
        "$psi = [System.Diagnostics.ProcessStartInfo]::new()",
        f"$psi.FileName = {_quote(cmd[0])}",
        "$psi.UseShellExecute = $false",
    ]
    if cwd is None:
        lines.append("$psi.WorkingDirectory = (Get-Location).Path")
    else:
        lines.append(f"$psi.WorkingDirectory = {_quote(cwd)}")
    if env_listing.clear_environment:
        lines.append("$psi.Environment.Clear()")
    else:
        lines.extend(
            f"[void]$psi.Environment.Remove({_quote(variable)})"
            for variable in env_listing.removed_variables
        )
    lines.extend(
        _render_assignment(key, value, host_env=host_env)
        for key, value in env_listing.variables
    )
    lines.extend(f"$psi.ArgumentList.Add({_quote(arg)})" for arg in cmd[1:])
    lines.extend(
        [
            "$p = [System.Diagnostics.Process]::Start($psi)",
            "$p.WaitForExit()",
            "$p.ExitCode",
        ]
    )
    return "\n  ".join(lines)
