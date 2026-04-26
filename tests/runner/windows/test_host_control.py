import sys

import pytest

import flnr


def test_host_signals_not_supported() -> None:
    expected_err = (
        "HostTerminationRequest.HOST_SIGNALS is not supported on Windows"
    )
    with pytest.raises(RuntimeError, match=expected_err):
        flnr.run_ex(
            [sys.executable],
            host_termination=flnr.HostTerminationRequest.HOST_SIGNALS,
        )
