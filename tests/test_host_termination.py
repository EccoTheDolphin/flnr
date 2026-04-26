import socket
import sys

import pytest

import flnr

from tests._support import moirai
from tests._support.utils import (
    TEST_DIR_ROOT,
    PythonCmdBuilder,
    return_code_for_sigterm,
)



def test_multitrigger() -> None:
    trigger_object = flnr.HostTerminationRequest()
    for _ in range(1024 * 1024):
        trigger_object.trigger()
    trigger_object.close()


def test_trigger_on_close() -> None:
    trigger_object = flnr.HostTerminationRequest()
    trigger_object.close()
    trigger_object.trigger()


def test_hostsignals_sentinel_serialization() -> None:
    assert (
        f"{flnr.HostTerminationRequest.HOST_SIGNALS}" == "_HostSignalsSentinel"
    )


def test_runner_host_control_closed(py_exec: PythonCmdBuilder) -> None:
    request = flnr.HostTerminationRequest()
    request.close()
    with pytest.raises(
        OSError, match="attempting to use closed HostTerminationRequest"
    ):
        flnr.run_ex(py_exec("py_true.py"), host_termination=request)


def test_runner_host_control_no_trigger(py_exec: PythonCmdBuilder) -> None:
    request = flnr.HostTerminationRequest()
    try:
        flnr.run_ex(py_exec("py_true.py"), host_termination=request)
    finally:
        request.close()


def test_runner_host_control_sticky(py_exec: PythonCmdBuilder) -> None:
    request = flnr.HostTerminationRequest()
    try:
        request.trigger()
        with pytest.raises(flnr.CommandFailedError) as excinfo:
            flnr.run_ex(py_exec("cat_dev_random.py"), host_termination=request)
        exc = excinfo.value
        assert exc.fate == moirai.fate_external_request_terminate(
            return_code_for_sigterm()
        )
    finally:
        request.close()


def test_host_signals_windows_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not sys.platform.startswith("win"):
        monkeypatch.setattr(sys, "platform", "win32")
    with pytest.raises(RuntimeError, match="not supported on Windows"):
        flnr.run_ex(
            ["this-command-must-not-run"],
            host_termination=flnr.HostTerminationRequest.HOST_SIGNALS,
        )


def test_host_termination_invalid_object() -> None:
    with pytest.raises(
        TypeError, match="unexpected type for host_termination object"
    ):
        flnr.run_ex(
            ["this-command-must-not-run"],
            host_termination=object(),  # type: ignore[arg-type]
        )


# this is unit tests targeting internal error resulting from potential failures
# on set_blocking call
def test_set_blocking_failure(monkeypatch: pytest.MonkeyPatch) -> None:

    def _fail(_: int, __: bool) -> None:
        error_msg = "simulated failure"
        raise OSError(error_msg)

    monkeypatch.setattr(
        socket.socket,
        "setblocking",
        _fail,
        raising=False,
    )

    with pytest.raises(OSError, match="simulated failure"):
        flnr.HostTerminationRequest()


def test_socket_socketpair_failure(monkeypatch: pytest.MonkeyPatch) -> None:

    def _socketpair_fail() -> None:
        error_msg = "simulated pipe failure"
        raise OSError(error_msg)

    monkeypatch.setattr(socket, "socketpair", _socketpair_fail)
    with pytest.raises(OSError, match="simulated pipe failure"):
        flnr.HostTerminationRequest()
