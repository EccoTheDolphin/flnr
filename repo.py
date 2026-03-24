#!/usr/bin/env python3

"""Tiny helper to manage this repository."""

# ruff: noqa: D103

import asyncio
import inspect
import logging
import os
import shlex
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import TracebackType
from typing import Annotated, Any, ClassVar

import typer
from rich.logging import RichHandler
from typing_extensions import Self

_logger = logging.getLogger(__name__)


async def cancel_and_wait(
    task: asyncio.Task[Any], msg: str | None = None
) -> None:
    """Cancel the task and wait for it to finish.

    :param task: the asyncio Task to cancel.
    See https://superfastpython.com/asyncio-cancel-task-and-wait/
    """
    task.cancel(msg)
    try:
        await task
    except asyncio.CancelledError as exc:
        # Two options here:
        # 1. We successfully cancelled the task and it raised CancelledError.
        #    In this case we need to suppress the exception and return.
        # 2. Cancellation was sent to this `cancel_and_wait` func.
        #    In this case we need to bubble the exception up.

        if sys.version_info < (3, 11):
            # Unfortunately not supported in python 3.10, so just quietly return
            return

        current_task = asyncio.current_task()
        err = """Fatal bug, cannot acquire asyncio Task object of current
        coroutine."""
        if current_task is None:
            raise AssertionError(err) from exc

        if current_task.cancelling() > 0:  # type: ignore[attr-defined, unused-ignore]
            raise

        return
    # An expected CancelledError was not seen
    msg = f"Cancelled task did not end with an exception: {task}"
    raise RuntimeError(msg)


class ContextLogger:
    """Context manager for logging the start and end of a block of code."""

    def __init__(
        self,
        msg: str,
        *,
        status: bool = False,
        logger: logging.Logger | None = None,
        level: int = logging.INFO,
        ping: float = 60,
    ) -> None:
        """Log message with context manager before and after.

        ... the context is executed, even if exception is raised.

        :param msg: message to log.
        :param status: if `True`, the message is only printed on context exit.
        :param logger: logger to use. If `None`, tries to use logger from
        invoking module.
        :param level: log level to use.
        :param ping: additionally in async context log message every `ping`
        seconds.  Skip if `ping <= 0`
        """
        self._msg = msg
        self._status_mode = status
        self._postfixes: list[str] = []
        self._logger = self._get_logger(logger)
        self._level = level

        # Changing ping on the fly is OK, so leave it public.
        self.ping = ping

        self.__running = False
        self.__start: datetime = datetime.fromtimestamp(0, timezone.utc)
        self.__ping_task: asyncio.Task[Any] | None = None

    @staticmethod
    def _get_logger(logger: logging.Logger | None) -> logging.Logger:
        if logger is not None:
            return logger
        logger_module = inspect.stack()[1].frame.f_globals["__name__"]
        return logging.getLogger(logger_module)

    @staticmethod
    def _prefix(tag: str) -> str:
        return f"[{tag.ljust(11)}]"

    @staticmethod
    def _format_elapsed(elapsed: timedelta | None) -> str:
        if elapsed is None:
            return ""

        jump_sec, sec_in_min = 300, 60
        jump_min, min_in_hour = 60, 60
        jump_hour, hour_in_day = 96, 24

        remaining = int(elapsed.total_seconds())
        if remaining <= jump_sec:  # noqa: SIM108
            seconds = remaining
        else:
            seconds = remaining % sec_in_min
        remaining -= seconds
        remaining //= sec_in_min

        if remaining <= jump_min:
            minutes = remaining
        else:
            minutes = remaining % min_in_hour
        remaining -= minutes
        remaining //= min_in_hour

        if remaining <= jump_hour:  # noqa: SIM108
            hours = remaining
        else:
            hours = remaining % hour_in_day
        remaining -= hours
        remaining //= hour_in_day

        days = remaining

        res = ""
        if days > 0:
            res += f"{days}d "
        if days > 0 or hours > 0:
            res += f"{hours}h "
        if days > 0 or hours > 0 or minutes > 0:
            res += f"{minutes}m "
        res += f"{seconds}s"
        return f" [{res}]"

    @staticmethod
    def _format(
        message: str,
        *,
        tag: str,
        postfixes: Sequence[str] | None,
        elapsed: timedelta | None,
    ) -> str:
        postfixes = postfixes or []
        return (
            f"{ContextLogger._prefix(tag)} {message.lstrip()} "
            + " ".join(postfixes)
            + f" {ContextLogger._format_elapsed(elapsed)}"
        ).strip()

    @staticmethod
    def status(
        message: str,
        *,
        postfixes: Sequence[str] | None = None,
        logger: logging.Logger | None = None,
        level: int = logging.INFO,
    ) -> None:
        """Emit single message between start and end of the block."""
        ContextLogger._get_logger(logger).log(
            level,
            ContextLogger._format(
                message, tag="STATUS", postfixes=postfixes, elapsed=None
            ),
        )

    def add_postfix(self, message: str) -> None:
        """Add postfix message to the last log message.

        Will be printed on context exit.
        """
        self._postfixes.append(message)

    def _log(self, tag: str, elapsed: timedelta | None) -> None:
        self._logger.log(
            self._level,
            ContextLogger._format(
                self._msg, tag=tag, postfixes=self._postfixes, elapsed=elapsed
            ),
        )

    def __enter__(self) -> Self:
        """Enter the context and log the start message."""
        if self.__running:
            msg = """Cannot start the same ContextLogger object if already in
            progress!"""
            raise RuntimeError(msg)
        self.__running = True
        self.__start = datetime.now(timezone.utc)

        if self._status_mode:
            return self
        self._log("STARTED", elapsed=None)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context and log the end message.

        Even if an exception is raised.
        """
        self.__running = False

        tag = "FINISHED"
        elapsed: timedelta | None = datetime.now(timezone.utc) - self.__start
        if self._status_mode:
            tag = "STATUS"
            elapsed = None

        if exc_val is not None:
            tag = "EXCEPTION"
            exc_name = exc_type.__name__ if exc_type is not None else "Unknown"
            self.add_postfix(f"- [{exc_name}]")
        self._log(tag, elapsed=elapsed)

    async def _ping(self) -> None:
        while True:
            await asyncio.sleep(self.ping)
            elapsed = datetime.now(timezone.utc) - self.__start
            self._log("IN PROGRESS", elapsed=elapsed)

    async def __aenter__(self) -> Self:
        """Enter the async context and log the start message.

        Start pinging if needed.
        """
        self.__enter__()
        if self.ping > 0 and not self._status_mode:
            self.__ping_task = asyncio.create_task(self._ping())

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the async context and log the end message.

        Even if an exception is raised. Stop pinging if needed.
        """
        if self.__ping_task is not None:
            await cancel_and_wait(self.__ping_task)

        self.__exit__(exc_type, exc_val, exc_tb)


def _paths2shell(paths: Sequence[Path]) -> str:
    # Hopefully no one is that crazy to use colon in the path...
    if any(":" in str(p) for p in paths):
        msg = """Cannot handle colon in paths for extra_paths argument for
        `run_shell`!"""
        raise ValueError(msg)
    return ":".join([str(p) for p in paths])


def shell_command(
    cmd: Sequence[str | Path],
    *,
    extra_env: Mapping[str, str | Path] | None = None,
    extra_paths: Sequence[Path] | None = None,
    capture_output: bool = False,
    cwd: Path | None = None,
) -> str:
    """Return bash equivalent of pure subprocess.run command.

    `subprocess.run` spawns command directly using syscall avoiding any
    shells like bash.
    Sometimes users want to run such commands manually, which requires
    manual parsing of python lists, i.e. `["my", "command", "args"]`
    and then converting them to bash commands.

    This helper function simplifies process and returns str cmd,
    which can be used to supply to bash.

    :param cmd: command to convert.
    :param extra_env: extra environment variables to define.
    :param extra_paths: extra paths to append to PATH variable.
    :param capture_output: whether `subprocess.run` will capture output.
    :param cwd: cwd for spawned command.
    """
    extra_env = extra_env or {}
    extra_paths = extra_paths or []

    if "PATH" in extra_env:
        msg = "Do not pass PATH to extra_env. Use extra_paths instead."
        raise ValueError(msg)

    extra_paths_str = _paths2shell(extra_paths)
    print_cmd = ""

    if cwd is not None and cwd != Path.cwd():
        cwd_str = str(
            os.path.relpath(cwd, Path.cwd())
        )  # Use os.path.relpath since it supports "../"
        cwd_str = shlex.quote(cwd_str)
        print_cmd += f"cd {cwd_str} && "

    for k, val in extra_env.items():
        print_cmd += f"{shlex.quote(str(k))}={shlex.quote(str(val))} "

    if extra_paths:
        print_cmd += f'PATH="{extra_paths_str}:${{PATH}}" '

    print_cmd += " ".join([shlex.quote(str(arg)) for arg in cmd])

    if capture_output:
        print_cmd += " &> CAPTURED"

    return print_cmd.strip()


def run_shell(
    cmd: Sequence[str | Path],
    *,
    extra_env: Mapping[str, str | Path] | None = None,
    extra_paths: Sequence[Path] | None = None,
    capture_output: bool = False,
    cwd: Path | None = None,
    check: bool = True,
    loglevel: int = logging.INFO,
) -> subprocess.CompletedProcess[str]:
    """Execute `subprocess.run` with different defaults.

    This is a plain wrapper over `subprocess.run`, which
    simplifies common scenario of "just running" a command
    in a bash-like style.

    This util:
    1. Allows to define "extra" environment, instead of replacing it.
    2. Allows to define "extra" PATH, instead of replacing it.
    3. check=True by default.
    4. text=True by default.
    5. Logs supplied command in bash-like form, allowing
       users to run it manually if needed.

    :param cmd: command to run.
    :param extra_env: extra environment variables to define.
    :param extra_paths: extra paths to append to PATH variable.
    :param capture_output: whether to capture output.
    :param cwd: cwd for spawned command.
    :param check: whether to check command exit code.
    :param loglevel: loglevel for dumping bash equivalent of the command.
    """
    extra_env = dict(extra_env) if extra_env is not None else {}
    extra_paths = list(extra_paths) if extra_paths is not None else []

    env = os.environ.copy()
    env.update({k: str(v) for k, v in extra_env.items()})

    extra_paths_str = _paths2shell(extra_paths).strip()
    if extra_paths_str:
        if "PATH" in env and env["PATH"].strip():
            extra_paths_str += ":" + env["PATH"]
        env["PATH"] = extra_paths_str

    print_cmd = shell_command(
        cmd,
        extra_env=extra_env,
        extra_paths=extra_paths,
        capture_output=capture_output,
        cwd=cwd,
    )
    _logger.log(loglevel, f"[RUNNING IN SHELL]: {print_cmd}")
    return subprocess.run(  # noqa: S603
        cmd,
        env=env,
        check=check,
        capture_output=capture_output,
        text=True,
        cwd=cwd,
    )


class _LoggerFormatter(logging.Formatter):
    formats: ClassVar[dict[int, str]] = {
        logging.DEBUG: "[grey]%(message)s[/]",
        logging.INFO: "[green]%(message)s[/]",
        logging.WARNING: "[yellow][WARNING]: %(message)s[/]",
        logging.ERROR: "[red][ERROR]: %(message)s[/]",
    }

    def __init__(self) -> None:
        super().__init__()
        self.formatters = {
            level: logging.Formatter(fmt) for level, fmt in self.formats.items()
        }

    def format(self, record: Any) -> str:  # noqa: ANN401
        formatter = self.formatters[logging.DEBUG]
        for level, fmt in self.formatters.items():
            if record.levelno >= level:
                formatter = fmt

        return formatter.format(record)


def setup_logger(logger: logging.Logger | None = None) -> None:
    """Add formatting to logger with RichHandler and custom formatter."""
    logger = logger or logging.getLogger()
    handler = RichHandler(
        show_time=False, show_path=False, show_level=False, markup=True
    )
    handler.setFormatter(_LoggerFormatter())
    handler.console.stderr = True
    logger.addHandler(handler)


_logger = logging.getLogger(__name__)
_repo_path = Path(__file__).parent


app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Simple script to manage this repository.",
)


@app.callback()
def setup_app() -> None:
    logging.getLogger().setLevel(logging.INFO)
    setup_logger()


def git_files(repo_path: Path, *ext: str) -> list[str]:
    return run_shell(
        ["git", "ls-files", *[f"*{e}" for e in ext]],
        capture_output=True,
        cwd=repo_path,
    ).stdout.splitlines()


def _check_leaked_credentials(repo_path: Path) -> None:
    # In order to properly check for leaked credentials,
    # we have to iterate over all commits in the repo.
    # Pinning first commit ensures, that if the check is run on some shallow
    # cloned repo, it will throw an error.
    first_commit = "42bc948b0d6681eeedf3fe22763096f70760dc23"

    if run_shell(
        ["git", "cat-file", "-e", first_commit], check=False
    ).returncode:
        _logger.error(
            "Looks like git history is shallow and credential check not works."
        )
        raise RuntimeError

    run_shell(["gitleaks", "git"], cwd=repo_path)


@app.command()
def lint() -> None:
    """Lint code."""
    run_shell(["ruff", "check"], cwd=_repo_path)
    run_shell(["mypy", _repo_path])

    run_shell(["yamllint", "--strict", _repo_path / ".github"])
    run_shell(["typos"], cwd=_repo_path)


@app.command(name="format")
def format_code(
    *,
    check: Annotated[
        bool,
        typer.Option("-c", "--check", help="Only check if code is formatted."),
    ] = False,
) -> None:
    """Format codebase."""
    check_arg = ["--check"] if check else []
    diff_arg = ["--diff"] if check else []
    run_shell(["ruff", "format", *check_arg], cwd=_repo_path)
    run_shell(
        ["ruff", "check", "--fix", "--unsafe-fixes", *diff_arg], cwd=_repo_path
    )

    run_shell(
        ["mdformat", *git_files(_repo_path, ".md"), *check_arg], cwd=_repo_path
    )


if __name__ == "__main__":
    app()
