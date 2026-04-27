"""Small subprocess supervision harness for CI and automation code."""

import asyncio
import os
import sys
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any

from ._async_utils import _cancel_tasks
from ._echafaud import (
    _attempt_to_kill,
    _ProcessLifecycleScope,
    _resolve_process_fate,
)
from ._observatory import (
    _env_monitor_task,
    _EnvironmentMonitorScope,
    _reader_task,
    _ReaderTaskSignals,
)
from ._stream_routing import _resolve_std_stream_plan
from .exceptions import (
    CommandFailedError,
    MonitorFailedError,
    ProcessKillFailedError,
    SupervisionFailedError,
)
from .fate import ProcessFate
from .host_control import HostTerminationAttachment as HostTerminationAttachment
from .host_control import (
    HostTerminationControlType as HostTerminationControlType,
)
from .host_control import HostTerminationRequest as HostTerminationRequest
from .host_control import (
    _attach_host_termination,
    _is_host_termination_object,
    _validate_host_termination_support,
)
from .monitor_failure import MonitorFailure, OutputStream
from .monitors import (
    EnvironmentMonitor,
    OutputMonitor,
)
from .timeouts import (
    ExecutionTimeouts,
)


@dataclass(frozen=True)
class _RunnerArgs:
    cmd: Sequence[str]
    cwd: Path | None
    env: Mapping[str, str]
    merge_std_streams: bool | None
    stdout_monitors: Sequence[OutputMonitor]
    stderr_monitors: Sequence[OutputMonitor]
    environment_monitors: Sequence[EnvironmentMonitor]
    check: bool
    timeouts: ExecutionTimeouts
    host_termination: HostTerminationControlType = None


class _RunnerScope:
    async def _start_process(self) -> asyncio.subprocess.Process:
        stream_routing = _resolve_std_stream_plan(
            merge_std_streams=self.args.merge_std_streams,
            has_stdout_monitors=len(self.args.stdout_monitors) > 0,
            has_stderr_monitors=len(self.args.stderr_monitors) > 0,
        )

        return await asyncio.create_subprocess_exec(
            *self.args.cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=stream_routing.stdout,
            stderr=stream_routing.stderr,
            cwd=self.args.cwd,
            env=self.args.env,
        )

    def __init__(self, args: _RunnerArgs) -> None:
        self.args = args
        self.process: asyncio.subprocess.Process | None = None

        self.reader_stdout_task: asyncio.Task[None] | None = None
        self.reader_stderr_task: asyncio.Task[None] | None = None
        self.process_fate_task: asyncio.Task[ProcessFate] | None = None

        self.env_monitor_tasks: list[asyncio.Task[None]] = []

        # "feu_vert" for monitoring system
        self.monitor_callbacks_allowed: asyncio.Event = asyncio.Event()
        self.monitor_callbacks_allowed.set()

        self.ext_termination_request: asyncio.Event = asyncio.Event()

        self.host_termination_binding: HostTerminationAttachment | None = None

        self.reader_ctrl = _ReaderTaskSignals(
            monitor_callbacks_allowed=self.monitor_callbacks_allowed,
            drain_requested=asyncio.Event(),
            fatal_reader_error=asyncio.Event(),
        )

        self.monitor_failures: list[MonitorFailure] = []

    def _create_reader_task(
        self,
        sr: asyncio.StreamReader,
        stream_id: OutputStream,
        monitors: Sequence[OutputMonitor],
        name: str,
    ) -> asyncio.Task[Any]:
        return asyncio.create_task(
            _reader_task(
                sr=sr,
                stream_id=stream_id,
                drain_timeout=self.args.timeouts.output_drain,
                monitors=monitors,
                monitor_failures=self.monitor_failures,
                control=self.reader_ctrl,
            ),
            name=name,
        )

    def _create_environment_monitor_task(
        self,
        monitor: EnvironmentMonitor,
        monitor_index: int,
        scope: _EnvironmentMonitorScope,
    ) -> asyncio.Task[Any]:
        return asyncio.create_task(
            _env_monitor_task(
                monitor=monitor,
                monitor_index=monitor_index,
                scope=scope,
            ),
            name=f"env_monitor.{monitor_index}",
        )

    async def _ainit(self) -> None:
        self.host_termination_binding = _attach_host_termination(
            self.args.host_termination,
            asyncio.get_running_loop(),
            self.ext_termination_request,
        )
        self.process = await self._start_process()
        if self.process.stdout is not None:
            self.reader_stdout_task = self._create_reader_task(
                self.process.stdout,
                OutputStream.STDOUT,
                self.args.stdout_monitors,
                "reader.stdout",
            )

        if self.process.stderr is not None:
            self.reader_stderr_task = self._create_reader_task(
                self.process.stderr,
                OutputStream.STDERR,
                self.args.stderr_monitors,
                "reader.stderr",
            )

        self.process_fate_task = asyncio.create_task(
            _resolve_process_fate(
                self.process,
                _ProcessLifecycleScope(
                    fatal_reader_error=self.reader_ctrl.fatal_reader_error,
                    monitor_callbacks_allowed=self.monitor_callbacks_allowed,
                    ext_termination_request=self.ext_termination_request,
                    timeouts=self.args.timeouts,
                ),
            ),
            name="process_fate",
        )

        env_mon_scope = _EnvironmentMonitorScope(
            pid=self.process.pid,
            cmd=self.args.cmd,
            monitor_failures=self.monitor_failures,
            process_fate_task=self.process_fate_task,
            monitor_callbacks_allowed=self.monitor_callbacks_allowed,
        )
        self.env_monitor_tasks = [
            self._create_environment_monitor_task(
                monitor, i, scope=env_mon_scope
            )
            for i, monitor in enumerate(self.args.environment_monitors)
        ]

    async def _acleanup(self) -> None:
        try:
            # this may affect global state, so deactivate sooner
            if self.host_termination_binding is not None:
                await self.host_termination_binding.deactivate()
        finally:
            # next, we kill subprocess since it is the most expensive object
            if self.process is not None:
                _attempt_to_kill(self.process)
            await _cancel_tasks(
                self.process_fate_task,
                *self.env_monitor_tasks,
                self.reader_stderr_task,
                self.reader_stdout_task,
            )

    async def __aenter__(self) -> "_RunnerScope":
        try:
            await self._ainit()
        except Exception:
            await self._acleanup()
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        await self._acleanup()
        return False

    def reader_tasks(self) -> Sequence[asyncio.Task[Any]]:
        result: list[asyncio.Task[Any]] = []
        if self.reader_stdout_task is not None:
            result.append(self.reader_stdout_task)
        if self.reader_stderr_task is not None:
            result.append(self.reader_stderr_task)
        return result

    async def close_monitoring(self) -> None:
        self.reader_ctrl.drain_requested.set()
        await asyncio.gather(
            *self.reader_tasks(),
            *self.env_monitor_tasks,
            return_exceptions=True,
        )

    def report_result(self, process_fate: ProcessFate) -> ProcessFate:
        assert self.process is not None

        internal_failures: list[BaseException] = []
        for task in list(self.reader_tasks()) + self.env_monitor_tasks:
            if task.cancelled():
                continue
            exc = task.exception()
            if exc:
                internal_failures.append(exc)

        if process_fate.returncode is None:
            error_msg = "process exit was not observed"
            raise ProcessKillFailedError(
                fate=process_fate,
                monitor_failures=tuple(self.monitor_failures),
                internal_exceptions=tuple(internal_failures),
                message=error_msg,
            )

        if internal_failures:
            error_msg = "supervision failed due to unrecoverable errors"
            raise SupervisionFailedError(
                fate=process_fate,
                monitor_failures=tuple(self.monitor_failures),
                internal_exceptions=tuple(internal_failures),
                message=error_msg,
            )

        assert self.process.returncode is not None
        # inspect subprocess state
        if self.args.check and self.process.returncode != 0:
            error_msg = f"unexpected return code {self.process.returncode}"
            raise CommandFailedError(
                fate=process_fate,
                monitor_failures=tuple(self.monitor_failures),
                message=error_msg,
            )

        # report monitoring errors
        if self.monitor_failures:
            error_msg = "monitor failures were detected during the run"
            raise MonitorFailedError(
                fate=process_fate,
                monitor_failures=tuple(self.monitor_failures),
                message=error_msg,
            )

        return process_fate


async def _run_ex_async(
    args: _RunnerArgs,
) -> ProcessFate:
    async with _RunnerScope(args) as scope:
        assert scope.process_fate_task is not None
        fate = await scope.process_fate_task
        await scope.close_monitoring()
        return scope.report_result(fate)


def run_ex(
    cmd: Sequence[str | Path],
    *,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    merge_std_streams: bool | None = None,
    timeouts: ExecutionTimeouts | None = None,
    stdout_monitors: Sequence[OutputMonitor] | None = None,
    stderr_monitors: Sequence[OutputMonitor] | None = None,
    environment_monitors: Sequence[EnvironmentMonitor] | None = None,
    check: bool = True,
    host_termination: HostTerminationControlType = None,
) -> ProcessFate:
    """Run an external program as a child process and supervise it.

    This synchronous entry point blocks the caller until the direct child
    reaches a resolved final state and output monitoring has finished or timed
    out, or until supervision fails.  The subprocess is executed directly,
    without invoking a shell. ``run_ex()`` must not be called from an existing
    async context.

    The return value is a ``ProcessFate`` object describing the resolved
    outcome. When ``check=True`` (the default), a non-zero subprocess return
    code is reported as ``CommandFailedError``.  This includes subprocesses
    terminated by **flnr** after a run timeout or host-requested termination;
    inspect the exception's ``fate`` field to distinguish the cause and final
    outcome.  Monitor failures are reported as ``MonitorFailedError`` after
    process teardown completes.  Unrecoverable supervision failures are
    reported as ``SupervisionFailedError``. If process exit cannot be confirmed
    during teardown, ``ProcessKillFailedError`` is raised.

    ``flnr`` supervises the direct child process only. It does not manage the
    full descendant process tree. Descendants may outlive the direct child,
    keep inherited file descriptors open, and continue producing output until
    ``output_drain`` expires.

    By default, ``merge_std_streams=None`` routes output based on configured
    monitors. ``stdout_monitors`` see stdout and, unless ``stderr_monitors``
    are configured, stderr. Configuring ``stderr_monitors`` routes stderr
    separately. Explicit ``merge_std_streams=True`` always merges stderr into
    stdout and rejects ``stderr_monitors``. Explicit
    ``merge_std_streams=False`` keeps stdout and stderr separate. Streams
    without monitors are connected to ``DEVNULL``.

    - ``None`` leaves host-driven termination handling disabled.
    - ``HostTerminationRequest.HOST_SIGNALS`` installs temporary SIGINT and
      SIGTERM handlers for the duration of the call. While active, ``flnr``
      owns those handlers and restores the previous ones when the call
      returns. **This mode is supported only when called from the main Python
      thread**.
    - ``HostTerminationRequest()`` attaches the run to a caller-managed,
      sticky trigger source that may be reused across runs. Attaching to an
      already-triggered request does not prevent process creation ahead of
      time; the run observes termination as soon as supervision starts.

    :rtype: ProcessFate
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        error_msg = "run_ex() cannot be called from an async context"
        raise RuntimeError(error_msg)

    if not cmd:
        error_msg = "cmd must not be empty"
        raise ValueError(error_msg)

    if isinstance(cmd, (str, bytes, bytearray, memoryview)):
        error_msg = (
            "cmd must be a sequence of argument items, not a string-like object"
        )
        raise TypeError(error_msg)

    if not _is_host_termination_object(host_termination):
        error_msg = (
            f"unexpected type for host_termination object {host_termination}"
        )
        raise TypeError(error_msg)

    _validate_host_termination_support(host_termination, sys.platform)

    if (host_termination is HostTerminationRequest.HOST_SIGNALS) and (
        threading.current_thread() is not threading.main_thread()
    ):
        error_msg = (
            "automatic termination on host signals is supported only for "
            "main Python thread"
        )
        raise RuntimeError(error_msg)

    if env is None:
        env = os.environ.copy()

    args = _RunnerArgs(
        cmd=[str(item) for item in cmd],
        env=env,
        cwd=cwd,
        merge_std_streams=merge_std_streams,
        stdout_monitors=(stdout_monitors or []),
        stderr_monitors=(stderr_monitors or []),
        environment_monitors=(environment_monitors or []),
        check=check,
        timeouts=timeouts or ExecutionTimeouts(),
        host_termination=host_termination,
    )

    return asyncio.run(_run_ex_async(args))
