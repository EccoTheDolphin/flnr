import asyncio
import re
import socket
import sys
from collections.abc import Callable
from typing import NoReturn

import pytest

import flnr
from tests._support import moirai
from tests._support.utils import (
    PythonCmdBuilder,
    return_code_for_sigterm,
)


def _run_with_rejected_async_loop_reader_attachment(
    monkeypatch: pytest.MonkeyPatch,
    run: Callable[[], object],
) -> None:
    rejected: list[bool] = []

    class RejectingAddReaderAttachment:
        def __init__(
            self,
            reader: socket.socket,
            loop: asyncio.AbstractEventLoop,
            ext_termination_request: asyncio.Event,
        ) -> None:
            del reader, loop, ext_termination_request
            error_msg = "simulated add_reader failure"
            rejected.append(True)
            raise OSError(error_msg)

    monkeypatch.setattr(
        "flnr._host_control.waker._AsyncLoopReaderAttachment",
        RejectingAddReaderAttachment,
    )

    try:
        run()
    finally:
        assert len(rejected) == 1


def test_multitrigger() -> None:
    trigger_object = flnr.HostTerminationRequest()
    for _ in range(1024 * 1024):
        trigger_object.trigger()
    trigger_object.close()


def test_trigger_on_close() -> None:
    trigger_object = flnr.HostTerminationRequest()
    trigger_object.close()
    trigger_object.trigger()


def test_trigger_ignores_send_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    def _fail_send(_: socket.socket, __: bytes) -> int:
        error_msg = "simulated send failure"
        raise OSError(error_msg)

    monkeypatch.setattr(socket.socket, "send", _fail_send)

    trigger_object = flnr.HostTerminationRequest()
    try:
        trigger_object.trigger()
    finally:
        trigger_object.close()


def test_trigger_double_close() -> None:
    trigger_object = flnr.HostTerminationRequest()
    trigger_object.close()
    with pytest.raises(
        OSError, match="HostTerminationRequest is already closed"
    ) as excinfo:
        trigger_object.close()
    exc = excinfo.value
    assert str(exc.__cause__) == "calling close on a closed wakeup source"


def test_hostsignals_sentinel_serialization() -> None:
    assert (
        f"{flnr.HostTerminationRequest.HOST_SIGNALS}" == "_HostSignalsSentinel"
    )


def test_runner_host_control_closed(py_exec: PythonCmdBuilder) -> None:
    request = flnr.HostTerminationRequest()
    request.close()
    with pytest.raises(
        OSError, match="attempting to use closed HostTerminationRequest"
    ) as excinfo:
        flnr.run_ex(py_exec("py_true.py"), host_termination=request)

    exc = excinfo.value
    assert str(exc.__cause__) == "attempting to use closed wakeup source"


def test_runner_host_control_no_trigger(py_exec: PythonCmdBuilder) -> None:
    request = flnr.HostTerminationRequest()
    try:
        flnr.run_ex(py_exec("py_true.py"), host_termination=request)
    finally:
        request.close()


def test_runner_host_control_no_trigger_poll(
    py_exec: PythonCmdBuilder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = flnr.HostTerminationRequest()
    try:
        _run_with_rejected_async_loop_reader_attachment(
            monkeypatch,
            lambda: flnr.run_ex(
                py_exec("py_true.py"), host_termination=request
            ),
        )
    finally:
        request.close()


def test_runner_host_control_triggered_poll(
    py_exec: PythonCmdBuilder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = flnr.HostTerminationRequest()
    try:
        request.trigger()
        with pytest.raises(flnr.CommandFailedError) as excinfo:
            _run_with_rejected_async_loop_reader_attachment(
                monkeypatch,
                lambda: flnr.run_ex(
                    py_exec("cat_dev_random.py"),
                    timeouts=flnr.ExecutionTimeouts(
                        run=10.0, output_drain=0.01, terminate=1
                    ),
                    host_termination=request,
                ),
            )
        exc = excinfo.value
        assert exc.fate == moirai.fate_external_request_terminate(
            return_code_for_sigterm()
        )
    finally:
        request.close()


def test_runner_host_control_poll_select_failure(
    py_exec: PythonCmdBuilder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    select_failed: list[bool] = []

    def _fail_select(
        rlist: object,
        wlist: object,
        xlist: object,
        timeout: float | None = None,
    ) -> NoReturn:
        del rlist, wlist, xlist, timeout
        error_msg = "simulated select failure"
        select_failed.append(True)
        raise OSError(error_msg)

    monkeypatch.setattr("flnr._host_control.waker.select.select", _fail_select)

    request = flnr.HostTerminationRequest()
    try:
        _run_with_rejected_async_loop_reader_attachment(
            monkeypatch,
            lambda: flnr.run_ex(
                py_exec("py_sleep.py", "1"), host_termination=request
            ),
        )
    finally:
        request.close()
    assert len(select_failed) == 1


def test_runner_host_control_poll_creation_failure(
    py_exec: PythonCmdBuilder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    polling_rejected: list[bool] = []

    class RejectingPollingAttachment:
        def __init__(
            self,
            *,
            reader: socket.socket,
            loop: asyncio.AbstractEventLoop,
            event: asyncio.Event,
        ) -> None:
            del reader, loop, event
            error_msg = "simulated polling failure"
            polling_rejected.append(True)
            raise OSError(error_msg)

    monkeypatch.setattr(
        "flnr._host_control.waker._PollingWakeupAttachment",
        RejectingPollingAttachment,
    )

    request = flnr.HostTerminationRequest()
    try:
        with pytest.raises(OSError, match="simulated polling failure"):
            _run_with_rejected_async_loop_reader_attachment(
                monkeypatch,
                lambda: flnr.run_ex(
                    py_exec("py_true.py"), host_termination=request
                ),
            )
    finally:
        request.close()
    assert len(polling_rejected) == 1


def test_runner_host_control_sticky(py_exec: PythonCmdBuilder) -> None:
    request = flnr.HostTerminationRequest()
    try:
        request.trigger()
        with pytest.raises(flnr.CommandFailedError) as excinfo:
            flnr.run_ex(
                py_exec("cat_dev_random.py"),
                timeouts=flnr.ExecutionTimeouts(
                    run=10.0, output_drain=0.01, terminate=1
                ),
                host_termination=request,
            )
        exc = excinfo.value
        assert exc.fate == moirai.fate_external_request_terminate(
            return_code_for_sigterm()
        )
    finally:
        request.close()


async def _run_in_async_thread_with_trigger(
    py_exec: PythonCmdBuilder,
) -> flnr.ProcessFate | flnr.CommandFailedError | BaseException:
    request = flnr.HostTerminationRequest()
    t_run = asyncio.to_thread(
        flnr.run_ex,
        py_exec("cat_dev_random.py"),
        host_termination=request,
    )
    request.trigger()
    try:
        return await asyncio.wait_for(t_run, timeout=10.0)
    finally:
        request.close()


def test_runner_host_termination_trigger_across_threads(
    py_exec: PythonCmdBuilder,
) -> None:
    with pytest.raises(flnr.CommandFailedError) as excinfo:
        asyncio.run(_run_in_async_thread_with_trigger(py_exec))
    assert excinfo.value.fate == moirai.fate_external_request_terminate(
        return_code_for_sigterm()
    )


def test_runner_host_termination_trigger_across_threads_poller(
    py_exec: PythonCmdBuilder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(flnr.CommandFailedError) as excinfo:
        _run_with_rejected_async_loop_reader_attachment(
            monkeypatch,
            lambda: asyncio.run(_run_in_async_thread_with_trigger(py_exec)),
        )
    assert excinfo.value.fate == moirai.fate_external_request_terminate(
        return_code_for_sigterm()
    )


def test_host_signals_windows_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not sys.platform.startswith("win"):
        monkeypatch.setattr(sys, "platform", "win32")
    with pytest.raises(
        RuntimeError,
        match=re.escape(
            "HostTerminationRequest.HOST_SIGNALS is not supported on Windows"
        ),
    ):
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
