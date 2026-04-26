import sys

import pytest

import flnr


@pytest.mark.skipif(
    not flnr.supports_host_termination_request(),
    reason="HostTerminationRequest implementation does not work on platform",
)
def test_multitrigger() -> None:
    trigger_object = flnr.HostTerminationRequest()
    for _ in range(1024 * 1024):
        trigger_object.trigger()
    trigger_object.close()


@pytest.mark.skipif(
    not flnr.supports_host_termination_request(),
    reason="HostTerminationRequest implementation does not work on platform",
)
def test_trigger_on_close() -> None:
    trigger_object = flnr.HostTerminationRequest()
    trigger_object.close()
    trigger_object.trigger()


def test_hostsignals_sentinel_serialization() -> None:
    assert (
        f"{flnr.HostTerminationRequest.HOST_SIGNALS}" == "_HostSignalsSentinel"
    )


@pytest.mark.skipif(
    not flnr.supports_host_termination_request(),
    reason="HostTerminationRequest implementation does not work on platform",
)
def test_host_termination_request_windows_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    terminator = flnr.HostTerminationRequest()
    monkeypatch.setattr(sys, "platform", "win32")
    try:
        with pytest.raises(RuntimeError, match="not supported on Windows"):
            flnr.run_ex(
                ["this-command-must-not-run"], host_termination=terminator
            )
    finally:
        terminator.close()


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

    def _true() -> bool:
        return True

    monkeypatch.setattr(
        flnr.host_control.os,  # type: ignore[attr-defined]
        "set_blocking",
        _fail,
        raising=False,
    )
    monkeypatch.setattr(
        flnr.host_control, "supports_host_termination_request", _true
    )

    with pytest.raises(OSError, match="simulated failure"):
        flnr.HostTerminationRequest()


def test_platform_termination_platform_not_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _false() -> bool:
        return False

    monkeypatch.setattr(
        flnr.host_control, "supports_host_termination_request", _false
    )
    expected_err = "HostTerminationRequest is not supported on this platform"
    with pytest.raises(
        flnr.HostTerminationNotSupportedError, match=expected_err
    ):
        flnr.HostTerminationRequest()


def test_os_pipe_failure(monkeypatch: pytest.MonkeyPatch) -> None:

    def _pipe_fail() -> None:
        error_msg = "simulated pipe failure"
        raise OSError(error_msg)

    def _set_blocking_passed(_: int, __: bool) -> None:
        pass

    def _true() -> bool:
        return True

    monkeypatch.setattr(
        flnr.host_control.os,  # type: ignore[attr-defined]
        "set_blocking",
        _set_blocking_passed,
        raising=False,
    )
    monkeypatch.setattr(
        flnr.host_control, "supports_host_termination_request", _true
    )
    monkeypatch.setattr(
        flnr.host_control.os,  # type: ignore[attr-defined]
        "pipe",
        _pipe_fail,
    )
    with pytest.raises(OSError, match="simulated pipe failure"):
        flnr.HostTerminationRequest()
