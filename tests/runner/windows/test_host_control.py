import sys

import pytest

import flnr


def test_host_signals_not_supported() -> None:
    expected_err = (
        "HostTerminationRequest.HOST_SIGNALS is not supported on Windows "
        "in the current implementation"
    )
    with pytest.raises(RuntimeError, match=expected_err):
        flnr.run_ex(
            [sys.executable],
            host_termination=flnr.HostTerminationRequest.HOST_SIGNALS,
        )


def test_host_termination_request_not_supported() -> None:
    expected_err = "HostTerminationRequest is not supported on this platform"
    with pytest.raises(
        flnr.HostTerminationNotSupportedError, match=expected_err
    ):
        flnr.HostTerminationRequest()
