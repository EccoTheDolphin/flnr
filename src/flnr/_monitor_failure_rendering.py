"""String rendering functions for MonitorFailure object."""

import traceback

from .monitor_failure import MonitorFailure


def _format_exc_backtrace(exc: BaseException) -> str:
    return "".join(
        traceback.TracebackException.from_exception(
            exc,
            capture_locals=False,
        ).format(chain=True)
    ).rstrip()


def _format_monitor_failure_brief(failure: MonitorFailure, n: int) -> str:
    return (
        f"[{n}] {failure.monitor_kind} #{failure.monitor_index} "
        f"({failure.monitor_name}) failed in {failure.location}: "
        f"{type(failure.exception).__name__}: {failure.exception}"
    )


def _format_monitor_failure_detail_header(
    failure: MonitorFailure, n: int
) -> str:
    return (
        f"[{n}] {failure.monitor_kind} #{failure.monitor_index} "
        f"({failure.monitor_name}) failed in {failure.location}"
    )


def _format_monitor_failure_traceback(failure: MonitorFailure) -> str:
    return _format_exc_backtrace(failure.exception)


def format_monitor_failures(failures: tuple[MonitorFailure, ...]) -> str:
    """Pretty-printer for a collection of monitor failures."""
    if not failures:
        return ""

    summary_lines = [
        f"{len(failures)} monitor failure(s) recorded:",
        "",
        *[
            _format_monitor_failure_brief(failure, n)
            for n, failure in enumerate(failures, start=1)
        ],
    ]

    detail_lines = [
        "",
        "Monitor failure details:",
        "",
    ]

    for n, failure in enumerate(failures, start=1):
        detail_lines.append(_format_monitor_failure_detail_header(failure, n))
        detail_lines.append(_format_monitor_failure_traceback(failure))
        detail_lines.append("")

    return "\n".join(summary_lines + detail_lines).rstrip()


def format_internal_exceptions(
    internal_exceptions: tuple[BaseException, ...],
) -> str:
    """Pretty-printer for a collection of raw exception objects."""
    if not internal_exceptions:
        return ""

    lines = [
        "",
        "Internal failures:",
        "",
    ]

    for i, exc in enumerate(internal_exceptions, start=1):
        lines.append(f"[{i}] {type(exc).__name__}: {exc}")
        lines.append(_format_exc_backtrace(exc))
        lines.append("")

    return "\n".join(lines).rstrip()
