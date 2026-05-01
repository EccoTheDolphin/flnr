import asyncio
import sys
from collections.abc import Sequence
from dataclasses import dataclass

from .monitors import OutputMonitor
from .stdio import BindToParent


@dataclass(frozen=True)
class _OutputRoute:
    monitors: Sequence[OutputMonitor] = ()
    tie_to_parent: bool = False

    @property
    def has_monitors(self) -> bool:
        return bool(self.monitors)

    @property
    def active(self) -> bool:
        return self.tie_to_parent or self.has_monitors


def _resolve_output_stream_route(
    value: Sequence[OutputMonitor] | BindToParent | None,
) -> _OutputRoute:
    if value is None:
        return _OutputRoute(monitors=(), tie_to_parent=False)
    if isinstance(value, BindToParent):
        return _OutputRoute(monitors=(), tie_to_parent=True)
    return _OutputRoute(monitors=value, tie_to_parent=False)


@dataclass(frozen=True)
class _StdStreamPlan:
    stdout: int | None
    stderr: int | None


def _target_for(route: _OutputRoute) -> int | None:
    if route.tie_to_parent:
        return None
    if route.has_monitors:
        return asyncio.subprocess.PIPE
    return asyncio.subprocess.DEVNULL


def _target_for_merged_stderr(stdout: int | None) -> int:
    windows_parent_stdout_fd = 1
    if stdout is None and sys.platform.startswith("win"):
        return windows_parent_stdout_fd
    return asyncio.subprocess.STDOUT


def _resolve_std_stream_plan(
    *,
    merge_std_streams: bool | None,
    stdout_route: _OutputRoute,
    stderr_route: _OutputRoute,
) -> _StdStreamPlan:
    if merge_std_streams is True and stderr_route.active:
        error_msg = "stderr_monitors must be None when merge_std_streams=True"
        raise ValueError(error_msg)

    should_merge = (
        merge_std_streams
        if merge_std_streams is not None
        else stdout_route.active and not stderr_route.active
    )

    stdout = _target_for(stdout_route)
    stderr = (
        _target_for_merged_stderr(stdout)
        if should_merge
        else _target_for(stderr_route)
    )

    return _StdStreamPlan(stdout=stdout, stderr=stderr)
