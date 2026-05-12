import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

import flnr
from tests._support.utils import PythonCmdBuilder


@dataclass(frozen=True)
class _TraceCall:
    cmd: tuple[str, ...]
    cwd: Path | None
    env: Mapping[str, str]
    host_env: Mapping[str, str]


class _RecordingTracerImpl:
    def __init__(self) -> None:
        self.calls: list[_TraceCall] = []

    def trace_command(
        self,
        *,
        cmd: tuple[str, ...],
        cwd: Path | None,
        env: Mapping[str, str],
        host_env: Mapping[str, str],
    ) -> None:
        self.calls.append(
            _TraceCall(
                cmd=cmd,
                cwd=cwd,
                env=env,
                host_env=host_env,
            )
        )


def test_run_ex_invokes_tracer_with_execution_context(
    py_exec: PythonCmdBuilder,
) -> None:
    tracer = _RecordingTracerImpl()
    cmd = py_exec("py_true.py")
    path_cmd: list[str | Path] = [Path(cmd[0]), *cmd[1:]]
    cwd = Path("tests") / ".."
    env = {**os.environ, "FLNR_TRACE_TEST": "visible"}

    fate = flnr.run_ex(path_cmd, cwd=cwd, env=env, tracer=tracer)

    assert fate.returncode == 0
    assert len(tracer.calls) == 1

    call = tracer.calls[0]
    assert call.cmd == tuple(str(item) for item in path_cmd)
    assert call.cwd == cwd
    assert set(call.env) == set(env)
    assert dict(call.env) == dict(env)
    assert call.host_env == os.environ
    assert call.host_env is not os.environ


def test_run_ex_invokes_tracer_before_process_creation() -> None:
    tracer = _RecordingTracerImpl()

    with pytest.raises(FileNotFoundError):
        flnr.run_ex(["/does/not/exist"], tracer=tracer)

    assert len(tracer.calls) == 1
    assert tracer.calls[0].cmd == ("/does/not/exist",)


def test_invalid_stream_routing_is_not_traced(
    py_exec: PythonCmdBuilder,
) -> None:
    tracer = _RecordingTracerImpl()

    with pytest.raises(
        ValueError,
        match="stderr_monitors must be None when merge_std_streams=True",
    ):
        flnr.run_ex(
            py_exec("py_true.py"),
            stdout_monitors=flnr.BIND_TO_PARENT,
            stderr_monitors=flnr.BIND_TO_PARENT,
            merge_std_streams=True,
            tracer=tracer,
        )

    assert tracer.calls == []
