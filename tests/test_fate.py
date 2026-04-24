import flnr
from tests._support.moirai import (
    fate_external_request_terminate,
    fate_internal_failure_kill,
    fate_no_intervention,
    fate_timeout_kill,
    fate_timeout_terminate,
)


def test_process_termination_decision_str() -> None:
    assert (
        f"{flnr.ProcessTerminationDecision.NO_INTERVENTION}"
        == "no_intervention"
    )
    assert f"{flnr.ProcessTerminationDecision.TIMEOUT}" == "timeout"
    assert (
        f"{flnr.ProcessTerminationDecision.EXTERNAL_REQUEST}"
        == "external_request"
    )
    assert (
        f"{flnr.ProcessTerminationDecision.INTERNAL_FAILURE}"
        == "internal_failure"
    )


def test_process_termination_method_str() -> None:
    assert f"{flnr.ProcessTerminationMethod.NONE}" == "none"
    assert f"{flnr.ProcessTerminationMethod.TERMINATE}" == "terminate"
    assert f"{flnr.ProcessTerminationMethod.KILL}" == "kill"


def test_string_representation_simple_fate() -> None:
    fate = flnr.ProcessFate(
        termination_decision=flnr.ProcessTerminationDecision.NO_INTERVENTION,
        termination_method=flnr.ProcessTerminationMethod.NONE,
        returncode=2,
    )
    assert str(fate) == "returncode=2, decision=no_intervention, method=none"


def test_string_representation_timeout_terminate() -> None:
    fate = flnr.ProcessFate(
        termination_decision=flnr.ProcessTerminationDecision.TIMEOUT,
        termination_method=flnr.ProcessTerminationMethod.TERMINATE,
        returncode=1,
    )
    assert str(fate) == "returncode=1, decision=timeout, method=terminate"


def test_string_representation_external_request_terminate() -> None:
    fate = flnr.ProcessFate(
        termination_decision=flnr.ProcessTerminationDecision.EXTERNAL_REQUEST,
        termination_method=flnr.ProcessTerminationMethod.TERMINATE,
        returncode=1,
    )
    assert (
        str(fate) == "returncode=1, decision=external_request, method=terminate"
    )


def test_string_representation_internal_failure_kill() -> None:
    fate = flnr.ProcessFate(
        termination_decision=flnr.ProcessTerminationDecision.INTERNAL_FAILURE,
        termination_method=flnr.ProcessTerminationMethod.KILL,
        returncode=0,
    )
    assert str(fate) == "returncode=0, decision=internal_failure, method=kill"


def test_string_representation_internal_failure_kill_nocode() -> None:
    fate = flnr.ProcessFate(
        termination_decision=flnr.ProcessTerminationDecision.INTERNAL_FAILURE,
        termination_method=flnr.ProcessTerminationMethod.KILL,
        returncode=None,
    )
    assert (
        str(fate) == "returncode=None, decision=internal_failure, method=kill"
    )


def test_omen_simple() -> None:
    assert fate_no_intervention(2) == flnr.ProcessFate(
        termination_decision=flnr.ProcessTerminationDecision.NO_INTERVENTION,
        termination_method=flnr.ProcessTerminationMethod.NONE,
        returncode=2,
    )


def test_omen_timeout_terminate() -> None:
    assert fate_timeout_terminate(42) == flnr.ProcessFate(
        termination_decision=flnr.ProcessTerminationDecision.TIMEOUT,
        termination_method=flnr.ProcessTerminationMethod.TERMINATE,
        returncode=42,
    )


def test_omen_external_request_terminate() -> None:
    assert fate_external_request_terminate(42) == flnr.ProcessFate(
        termination_decision=flnr.ProcessTerminationDecision.EXTERNAL_REQUEST,
        termination_method=flnr.ProcessTerminationMethod.TERMINATE,
        returncode=42,
    )


def test_omen_timeout_kill() -> None:
    assert fate_timeout_kill(42) == flnr.ProcessFate(
        termination_decision=flnr.ProcessTerminationDecision.TIMEOUT,
        termination_method=flnr.ProcessTerminationMethod.KILL,
        returncode=42,
    )
    assert fate_timeout_kill(None) == flnr.ProcessFate(
        termination_decision=flnr.ProcessTerminationDecision.TIMEOUT,
        termination_method=flnr.ProcessTerminationMethod.KILL,
        returncode=None,
    )


def test_omen_internal_failure() -> None:
    assert fate_internal_failure_kill(777) == flnr.ProcessFate(
        termination_decision=flnr.ProcessTerminationDecision.INTERNAL_FAILURE,
        termination_method=flnr.ProcessTerminationMethod.KILL,
        returncode=777,
    )
    assert fate_internal_failure_kill(None) == flnr.ProcessFate(
        termination_decision=flnr.ProcessTerminationDecision.INTERNAL_FAILURE,
        termination_method=flnr.ProcessTerminationMethod.KILL,
        returncode=None,
    )
