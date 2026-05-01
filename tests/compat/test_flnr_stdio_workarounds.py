from types import SimpleNamespace

import pytest

import flnr
from flnr import _stream_routing
from tests._support.utils import PythonCmdBuilder


def test_windows_stdout_binding_merge_workaround(
    py_exec: PythonCmdBuilder,
    capfdbinary: pytest.CaptureFixture[bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        _stream_routing, "sys", SimpleNamespace(platform="win32")
    )

    flnr.run_ex(
        py_exec("stderrstdout_output.py"),
        stdout_monitors=flnr.BIND_TO_PARENT,
    )

    captured = capfdbinary.readouterr()
    assert (captured.out, captured.err) == (
        b"stderr outputstdout output",
        b"",
    )
