import logging
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

import flnr
from flnr.command_tracing import (
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


def _logged_record(
    caplog: pytest.LogCaptureFixture,
    logger: logging.Logger,
) -> logging.LogRecord:
    records = [
        record for record in caplog.records if record.name == logger.name
    ]
    assert len(records) == 1
    assert isinstance(records[0].msg, str)
    assert records[0].args == ()
    return records[0]


def _logged_lines(
    caplog: pytest.LogCaptureFixture,
    logger: logging.Logger,
) -> list[str]:
    return _logged_record(caplog, logger).getMessage().splitlines()


def _logged_command_lines(
    *,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    platform: str,
    cmd: tuple[str, ...],
    env_listing: _EnvListingCallable,
    child_env: Mapping[str, str],
    host_env: Mapping[str, str],
    cwd: Path | None = None,
) -> list[str]:
    logger = logging.getLogger(f"tests.flnr.command_rendering.{platform}")
    caplog.set_level(logging.INFO, logger=logger.name)
    monkeypatch.setattr(sys, "platform", platform)
    tracer = flnr.CommandTracer(logger, env_listing=env_listing)

    tracer.trace_command(
        cmd=cmd,
        cwd=cwd,
        env=child_env,
        host_env=host_env,
    )

    return _logged_lines(caplog, logger)


def test_disabled_level_skips_recipe(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("tests.flnr.command_rendering.disabled")
    caplog.set_level(logging.WARNING, logger=logger.name)

    def fail_on_render(
        child_env: Mapping[str, str],
        host_env: Mapping[str, str],
    ) -> EnvListing:
        del child_env, host_env
        error_msg = "disabled logger should not render command"
        raise AssertionError(error_msg)

    tracer = flnr.CommandTracer(
        logger,
        env_listing=fail_on_render,
        level=logging.INFO,
    )
    tracer.trace_command(
        cmd=("tool",),
        cwd=None,
        env={},
        host_env={},
    )

    assert caplog.records == []


def test_default_level_is_info(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("tests.flnr.command_rendering.default_level")
    caplog.set_level(logging.INFO, logger=logger.name)
    monkeypatch.setattr(sys, "platform", "linux")
    tracer = flnr.CommandTracer(logger)

    tracer.trace_command(
        cmd=("tool",),
        cwd=None,
        env={},
        host_env={},
    )

    assert _logged_record(caplog, logger).levelno == logging.INFO


def test_default_env_listing_is_empty(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("tests.flnr.command_rendering.default_env")
    caplog.set_level(logging.INFO, logger=logger.name)
    monkeypatch.setattr(sys, "platform", "linux")
    tracer = flnr.CommandTracer(logger)

    tracer.trace_command(
        cmd=("tool",),
        cwd=None,
        env={"VISIBLE": "visible"},
        host_env={},
    )

    assert _logged_lines(caplog, logger) == [
        "tool",
    ]


def test_changed_env_constructor(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("tests.flnr.command_rendering.changed_ctor")
    caplog.set_level(logging.INFO, logger=logger.name)
    monkeypatch.setattr(sys, "platform", "linux")
    tracer = flnr.CommandTracer.with_changed_environment(logger)

    tracer.trace_command(
        cmd=("tool",),
        cwd=None,
        env={"VISIBLE": "changed", "UNCHANGED": "same"},
        host_env={"VISIBLE": "old", "UNCHANGED": "same"},
    )

    assert _logged_lines(caplog, logger) == [
        "env VISIBLE=changed tool",
    ]


def test_selected_env_constructor(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("tests.flnr.command_rendering.selected_ctor")
    caplog.set_level(logging.INFO, logger=logger.name)
    monkeypatch.setattr(sys, "platform", "linux")
    tracer = flnr.CommandTracer.with_selected_environment(
        logger,
        ["VISIBLE"],
    )

    tracer.trace_command(
        cmd=("tool",),
        cwd=None,
        env={"VISIBLE": "visible", "HIDDEN": "hidden"},
        host_env={},
    )

    assert _logged_lines(caplog, logger) == [
        "env VISIBLE=visible tool",
    ]


def test_recreated_env_constructor(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("tests.flnr.command_rendering.recreated_ctor")
    caplog.set_level(logging.INFO, logger=logger.name)
    monkeypatch.setattr(sys, "platform", "linux")
    tracer = flnr.CommandTracer.with_recreated_environment(logger)

    tracer.trace_command(
        cmd=("tool",),
        cwd=None,
        env={"A": "B", "C": "D"},
        host_env={"A": "old", "REMOVED": "gone"},
    )

    assert _logged_lines(caplog, logger) == [
        "env -i A=B C=D tool",
    ]


def test_constructor_forwards_level(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("tests.flnr.command_rendering.ctor_level")
    caplog.set_level(logging.WARNING, logger=logger.name)
    monkeypatch.setattr(sys, "platform", "linux")
    tracer = flnr.CommandTracer.with_selected_environment(
        logger,
        ["VISIBLE"],
        level=logging.WARNING,
    )

    tracer.trace_command(
        cmd=("tool",),
        cwd=None,
        env={"VISIBLE": "visible"},
        host_env={},
    )

    assert _logged_record(caplog, logger).levelno == logging.WARNING


def test_selected_missing_env(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="linux",
        cmd=("tool",),
        env_listing=list_selected_environment(
            ["FLNR_VISIBLE_ENV", "FLNR_MISSING_ENV"]
        ),
        child_env={"FLNR_VISIBLE_ENV": "visible"},
        host_env={},
    ) == [
        "env FLNR_VISIBLE_ENV=visible tool",
        "@ missing env: FLNR_MISSING_ENV",
    ]


def test_selected_several_missing_env(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="linux",
        cmd=("tool",),
        env_listing=list_selected_environment(
            ["FLNR_VISIBLE_ENV", "FLNR_MISSING_ENV1", "FLNR_MISSING_ENV2"]
        ),
        child_env={"FLNR_VISIBLE_ENV": "visible"},
        host_env={},
    ) == [
        "env FLNR_VISIBLE_ENV=visible tool",
        "@ missing env: FLNR_MISSING_ENV1, FLNR_MISSING_ENV2",
    ]


def test_explicit_cwd(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("tests.flnr.command_rendering.cwd")
    caplog.set_level(logging.INFO, logger=logger.name)
    monkeypatch.setattr(sys, "platform", "linux")
    tracer = flnr.CommandTracer(logger)

    tracer.trace_command(cmd=("tool",), cwd=Path("work"), env={}, host_env={})

    assert _logged_lines(caplog, logger) == [
        "tool",
        "@ cwd: work",
    ]


def test_platform_captured_at_creation(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("tests.flnr.command_rendering.captured_platform")
    caplog.set_level(logging.INFO, logger=logger.name)
    monkeypatch.setattr(sys, "platform", "linux")
    tracer = flnr.CommandTracer(logger, env_listing=list_no_environment)
    monkeypatch.setattr(sys, "platform", "win32")

    tracer.trace_command(
        cmd=("tool", "arg"),
        cwd=None,
        env={},
        host_env={},
    )

    assert _logged_lines(caplog, logger) == [
        "tool arg",
    ]


def test_posix_changed_env(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    child_env = {
        "PATH": "/opt/tool/bin:/usr/bin",
        "SAME": "same",
        "TOOLCHAIN": "/opt/tool",
    }
    host_env = {"PATH": "/usr/bin", "SAME": "same"}

    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="linux",
        cmd=("python", "-m", "build"),
        env_listing=list_changed_environment,
        child_env=child_env,
        host_env=host_env,
    ) == [
        "env PATH=/opt/tool/bin:$PATH TOOLCHAIN=/opt/tool python -m build",
    ]


def test_posix_exact_path(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="linux",
        cmd=("tool",),
        env_listing=list_changed_environment,
        child_env={"PATH": "/custom/bin"},
        host_env={"PATH": "/usr/bin"},
    ) == [
        "env PATH=/custom/bin tool",
    ]


def test_posix_multiline(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv(
        "FLNR_INTERNAL_COMMAND_TRACE_STYLE",
        "multiline",
    )

    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="linux",
        cmd=("tool", "arg1"),
        env_listing=list_selected_environment(["VISIBLE"]),
        child_env={"VISIBLE": "changed"},
        host_env={},
    ) == [">", "  env \\", "    VISIBLE=changed \\", "  tool \\", "    arg1"]


def test_posix_multiline_empty_env(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv(
        "FLNR_INTERNAL_COMMAND_TRACE_STYLE",
        "multiline",
    )
    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="linux",
        cmd=("tool",),
        env_listing=list_changed_environment,
        child_env={},
        host_env={},
    ) == [">", "  tool"]


def test_posix_removed_env(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="linux",
        cmd=("tool",),
        env_listing=list_changed_environment,
        child_env={"PATH": "/usr/bin", "SECRET": "secret"},
        host_env={
            "PATH": "/usr/bin",
            "PYTHONPATH": "removed",
            "SECRET": "secret",
        },
    ) == [
        "env -u PYTHONPATH tool",
    ]


def test_posix_removed_only_env(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="linux",
        cmd=("tool",),
        env_listing=list_changed_environment,
        child_env={},
        host_env={"PATH": "/usr/bin"},
    ) == [
        "env -u PATH tool",
    ]


def test_posix_no_env(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="linux",
        cmd=("tool", "arg"),
        env_listing=list_no_environment,
        child_env={},
        host_env={},
    ) == [
        "tool arg",
    ]


def test_posix_quotes_special_values(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="linux",
        cmd=("tool path", "say it's ok"),
        env_listing=list_selected_environment(["SPECIAL_ENV"]),
        child_env={"SPECIAL_ENV": "two words 'quoted'"},
        host_env={},
    ) == [
        "env SPECIAL_ENV='two words '\"'\"'quoted'\"'\"'' "
        "'tool path' 'say it'\"'\"'s ok'",
    ]


@pytest.mark.parametrize(
    ("child_env", "host_env", "expected"),
    [
        (
            {"PATH": "/usr/bin:/bin"},
            {"PATH": "/usr/bin:/bin"},
            "env PATH=$PATH tool",
        ),
        (
            {"PATH": "/bla:/usr/bin:/bin"},
            {"PATH": "/usr/bin:/bin"},
            "env PATH=/bla:$PATH tool",
        ),
        (
            {"PATH": "/usr/bin:/bin"},
            {},
            "env PATH=/usr/bin:/bin tool",
        ),
        (
            {"PATH": ":/usr/bin:/bin"},
            {"PATH": "/usr/bin:/bin"},
            "env PATH='':$PATH tool",
        ),
    ],
    ids=["same", "prepended", "no-host-path", "empty-prefix"],
)
def test_posix_path_rendering(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    child_env: Mapping[str, str],
    host_env: Mapping[str, str],
    expected: str,
) -> None:
    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="linux",
        cmd=("tool",),
        env_listing=list_selected_environment(["PATH"]),
        child_env=child_env,
        host_env=host_env,
    ) == [
        expected,
    ]


def test_posix_clear_env(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="linux",
        cmd=("tool",),
        env_listing=list_recreated_environment,
        child_env={"A": "B"},
        host_env={},
    ) == [
        "env -i A=B tool",
    ]


def test_windows_selected_env(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="win32",
        cmd=(r".\Program Files\Tool's\tool.exe", "arg with space"),
        env_listing=list_selected_environment(["TOOL_PATH"]),
        child_env={"TOOL_PATH": r"C:\Tool Dir\can't"},
        host_env={},
    ) == [
        ">",
        "  $psi = [System.Diagnostics.ProcessStartInfo]::new()",
        "  $psi.FileName = '.\\Program Files\\Tool''s\\tool.exe'",
        "  $psi.UseShellExecute = $false",
        "  $psi.WorkingDirectory = (Get-Location).Path",
        "  $psi.Environment['TOOL_PATH'] = 'C:\\Tool Dir\\can''t'",
        "  $psi.Arguments = '\"arg with space\"'",
        "  $p = [System.Diagnostics.Process]::Start($psi)",
        "  $p.WaitForExit()",
        "  $p.ExitCode",
    ]


def test_windows_no_env(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="win32",
        cmd=("tool.exe", "arg"),
        env_listing=list_no_environment,
        child_env={},
        host_env={},
    ) == [
        "& 'tool.exe' 'arg'",
    ]


def test_windows_cwd(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="win32",
        cmd=("tool.exe", "arg"),
        env_listing=list_no_environment,
        child_env={},
        host_env={},
        cwd=Path(r"C:\work dir"),
    ) == [
        ">",
        "  $psi = [System.Diagnostics.ProcessStartInfo]::new()",
        "  $psi.FileName = 'tool.exe'",
        "  $psi.UseShellExecute = $false",
        "  $psi.WorkingDirectory = 'C:\\work dir'",
        "  $psi.Arguments = 'arg'",
        "  $p = [System.Diagnostics.Process]::Start($psi)",
        "  $p.WaitForExit()",
        "  $p.ExitCode",
        "@ cwd: C:\\work dir",
    ]


def test_windows_removed_env(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="win32",
        cmd=("python.exe", "-m", "build"),
        env_listing=list_changed_environment,
        child_env={
            "PATH": r"C:\Tool",
            "QUOTE": "can't",
            "SECRET": "secret",
        },
        host_env={
            "PATH": r"C:\Windows",
            "REMOVED": "yes",
            "SECRET": "secret",
        },
    ) == [
        ">",
        "  $psi = [System.Diagnostics.ProcessStartInfo]::new()",
        "  $psi.FileName = 'python.exe'",
        "  $psi.UseShellExecute = $false",
        "  $psi.WorkingDirectory = (Get-Location).Path",
        "  [void]$psi.Environment.Remove('REMOVED')",
        "  $psi.Environment['PATH'] = 'C:\\Tool'",
        "  $psi.Environment['QUOTE'] = 'can''t'",
        "  $psi.Arguments = '-m build'",
        "  $p = [System.Diagnostics.Process]::Start($psi)",
        "  $p.WaitForExit()",
        "  $p.ExitCode",
    ]


@pytest.mark.parametrize(
    ("child_env", "host_env", "expected"),
    [
        (
            {"PATH": r"C:\Windows;C:\Windows\System32"},
            {"PATH": r"C:\Windows;C:\Windows\System32"},
            "  $psi.Environment['PATH'] = $env:PATH",
        ),
        (
            {"PATH": r"C:\Tool;C:\Windows;C:\Windows\System32"},
            {"PATH": r"C:\Windows;C:\Windows\System32"},
            "  $psi.Environment['PATH'] = 'C:\\Tool' + ';' + $env:PATH",
        ),
        (
            {"PATH": r"C:\Tool"},
            {},
            "  $psi.Environment['PATH'] = 'C:\\Tool'",
        ),
    ],
    ids=["same", "prepended", "no-host-path"],
)
def test_windows_path_rendering(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    child_env: Mapping[str, str],
    host_env: Mapping[str, str],
    expected: str,
) -> None:
    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="win32",
        cmd=("tool.exe",),
        env_listing=list_selected_environment(["PATH"]),
        child_env=child_env,
        host_env=host_env,
    ) == [
        ">",
        "  $psi = [System.Diagnostics.ProcessStartInfo]::new()",
        "  $psi.FileName = 'tool.exe'",
        "  $psi.UseShellExecute = $false",
        "  $psi.WorkingDirectory = (Get-Location).Path",
        expected,
        "  $p = [System.Diagnostics.Process]::Start($psi)",
        "  $p.WaitForExit()",
        "  $p.ExitCode",
    ]


def test_windows_removed_only_env(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="win32",
        cmd=("tool.exe",),
        env_listing=list_changed_environment,
        child_env={},
        host_env={"PATH": r"C:\Windows"},
    ) == [
        ">",
        "  $psi = [System.Diagnostics.ProcessStartInfo]::new()",
        "  $psi.FileName = 'tool.exe'",
        "  $psi.UseShellExecute = $false",
        "  $psi.WorkingDirectory = (Get-Location).Path",
        "  [void]$psi.Environment.Remove('PATH')",
        "  $p = [System.Diagnostics.Process]::Start($psi)",
        "  $p.WaitForExit()",
        "  $p.ExitCode",
    ]


def test_windows_clear_env(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="win32",
        cmd=("tool.exe",),
        env_listing=list_recreated_environment,
        child_env={"A": "B"},
        host_env={},
    ) == [
        ">",
        "  $psi = [System.Diagnostics.ProcessStartInfo]::new()",
        "  $psi.FileName = 'tool.exe'",
        "  $psi.UseShellExecute = $false",
        "  $psi.WorkingDirectory = (Get-Location).Path",
        "  $psi.Environment.Clear()",
        "  $psi.Environment['A'] = 'B'",
        "  $p = [System.Diagnostics.Process]::Start($psi)",
        "  $p.WaitForExit()",
        "  $p.ExitCode",
    ]


def test_windows_nontrivial_args(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    expected_arguments = r'"" "arg with space" slash\path\\ quote\"inside'
    assert _logged_command_lines(
        monkeypatch=monkeypatch,
        caplog=caplog,
        platform="win32",
        cmd=(
            "tool.exe",
            "",
            "arg with space",
            r"slash\path\\",
            'quote"inside',
        ),
        env_listing=list_selected_environment(["VISIBLE"]),
        child_env={"VISIBLE": "visible"},
        host_env={},
    ) == [
        ">",
        "  $psi = [System.Diagnostics.ProcessStartInfo]::new()",
        "  $psi.FileName = 'tool.exe'",
        "  $psi.UseShellExecute = $false",
        "  $psi.WorkingDirectory = (Get-Location).Path",
        "  $psi.Environment['VISIBLE'] = 'visible'",
        f"  $psi.Arguments = '{expected_arguments}'",
        "  $p = [System.Diagnostics.Process]::Start($psi)",
        "  $p.WaitForExit()",
        "  $p.ExitCode",
    ]
