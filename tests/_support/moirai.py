import flnr


def _weave_fate(
    *,
    returncode: int | None,
    decision: flnr.ProcessTerminationDecision,
    method: flnr.ProcessTerminationMethod,
) -> flnr.ProcessFate:
    return flnr.ProcessFate(
        termination_decision=decision,
        termination_method=method,
        returncode=returncode,
    )


def fate_no_intervention(returncode: int = 0) -> flnr.ProcessFate:
    return _weave_fate(
        returncode=returncode,
        decision=flnr.ProcessTerminationDecision.NO_INTERVENTION,
        method=flnr.ProcessTerminationMethod.NONE,
    )


def fate_timeout_terminate(returncode: int | None) -> flnr.ProcessFate:
    return _weave_fate(
        returncode=returncode,
        decision=flnr.ProcessTerminationDecision.TIMEOUT,
        method=flnr.ProcessTerminationMethod.TERMINATE,
    )


def fate_external_request_terminate(returncode: int | None) -> flnr.ProcessFate:
    return _weave_fate(
        returncode=returncode,
        decision=flnr.ProcessTerminationDecision.EXTERNAL_REQUEST,
        method=flnr.ProcessTerminationMethod.TERMINATE,
    )


def fate_timeout_kill(returncode: int | None) -> flnr.ProcessFate:
    return _weave_fate(
        returncode=returncode,
        decision=flnr.ProcessTerminationDecision.TIMEOUT,
        method=flnr.ProcessTerminationMethod.KILL,
    )


def fate_internal_failure_kill(returncode: int | None) -> flnr.ProcessFate:
    return _weave_fate(
        returncode=returncode,
        decision=flnr.ProcessTerminationDecision.INTERNAL_FAILURE,
        method=flnr.ProcessTerminationMethod.KILL,
    )
