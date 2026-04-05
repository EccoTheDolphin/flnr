import pytest

import flnr


def test_default_timeouts() -> None:
    expected_default_terminate = 5.0
    expected_default_output_drain = 1.0

    default_timeout = flnr.ExecutionTimeouts()
    assert default_timeout.run is None
    assert default_timeout.terminate == expected_default_terminate
    assert default_timeout.output_drain == expected_default_output_drain


def test_custom_timeouts() -> None:
    run_timeout = 1.0
    terminate_timeout = 2.0
    output_drain = 3.0
    timeouts = flnr.ExecutionTimeouts(
        run=run_timeout, terminate=terminate_timeout, output_drain=output_drain
    )
    assert timeouts.run == run_timeout
    assert timeouts.terminate == terminate_timeout
    assert timeouts.output_drain == output_drain


def test_incorrect_run_timeout() -> None:
    for incorrect_value in [0, -1]:
        with pytest.raises(
            ValueError,
            match=r"run timeout must be either None or > 0$",
        ):
            flnr.ExecutionTimeouts(run=incorrect_value)


def test_incorrect_terminate() -> None:
    for incorrect_value in [0, -1]:
        with pytest.raises(
            ValueError,
            match=r"terminate timeout must be > 0$",
        ):
            flnr.ExecutionTimeouts(terminate=incorrect_value)


def test_incorrect_output_drain() -> None:
    for incorrect_value in [0, -1]:
        with pytest.raises(
            ValueError,
            match=r"output_drain timeout must be > 0$",
        ):
            flnr.ExecutionTimeouts(output_drain=incorrect_value)
