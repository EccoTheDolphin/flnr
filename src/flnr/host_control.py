"""Facilities for host to request premature termination."""

import asyncio
import signal
from typing import Final, TypeAlias, TypeGuard

from ._host_control.signals import _ExternalTerminationInterposer
from ._host_control.types import (
    HostTerminationAttachment as HostTerminationAttachment,
)
from ._host_control.waker import (
    _attach_socket_waker,
    _ClosedWakeupSourceError,
    _SocketWakeupSource,
)


class _HostSignalsSentinel:
    def __repr__(self) -> str:
        return "_HostSignalsSentinel"


class _SignalAttachment(HostTerminationAttachment):
    def __init__(self, ext_termination_request: asyncio.Event) -> None:
        self.ext_term_interposer = _ExternalTerminationInterposer(
            [signal.SIGINT, signal.SIGTERM], ext_termination_request
        )
        self.ext_term_interposer.activate()

    async def deactivate(self) -> None:
        assert self.ext_term_interposer is not None
        self.ext_term_interposer.deactivate()


class _NullAttachment(HostTerminationAttachment):
    async def deactivate(self) -> None:
        pass


class HostTerminationRequest:
    """Stable, latched host-termination trigger source.

    This object can be passed to ``run_ex(host_termination=...)`` to let the
    caller control host-side termination requests explicitly, without using
    ``HostTerminationRequest.HOST_SIGNALS``.

    The object is stable and reusable across multiple runs. Once triggered, it
    remains triggered. A run that attaches to an already-triggered request will
    observe termination as soon as supervision starts. This does not prevent
    process creation ahead of time; it only means the run will converge on
    termination immediately after startup.

    .. warning::  Usage of this object is not supported on Windows in the
                  current implementation.

    Creating a HostTerminationRequest allocates OS resources. Those resources
    may be released with ``close()``, but ``close()`` is ordinary lifecycle
    cleanup and must not race with future ``trigger()`` calls.

    ``trigger()`` may be called from a Python signal handler in this
    implementation. ``close()`` does not provide that guarantee.
    """

    #: Sentinel value for ``run_ex(..., host_termination=...)``.
    #:
    #: Passing ``HostTerminationRequest.HOST_SIGNALS`` tells ``run_ex()``
    #: to temporarily install handlers for ``SIGINT`` and ``SIGTERM`` for
    #: the duration of the call.
    #:
    #: Constraints:
    #:
    #: - Unix only
    #: - main Python thread only
    #: - while active, ``flnr`` owns those handlers for the duration of the call
    #: - previous handlers are restored when ``run_ex()`` returns
    #:
    #: This temporarily replaces normal SIGINT/SIGTERM handling for the call.
    #:
    #: Use an **instance** of :py:class:`HostTerminationRequest` if the
    #: application manages handling itself and wants to request termination
    #: explicitly.
    HOST_SIGNALS: Final[_HostSignalsSentinel] = _HostSignalsSentinel()

    def __init__(self) -> None:
        """Initialize a stable host-termination request object."""
        self._source = _SocketWakeupSource()

    def trigger(self) -> None:
        """Trigger host termination request.

        Once triggered, the request remains triggered.

        This method may be called from a Python signal handler in this
        implementation. It is intentionally small and only performs the minimal
        work needed to wake attached runs.

        Repeated calls after the request has already been triggered are
        harmless.
        """
        self._source.trigger()

    def close(self) -> None:
        """Release OS resources owned by this request object.

        This is ordinary lifecycle cleanup. It is not safe to call from a
        Python signal handler, and it must not race with future ``trigger()``
        calls.

        In particular, if this object is still reachable from installed signal
        handlers, callers should not call ``close()``. In that usage mode, the
        object is expected to remain alive for the lifetime of the program, or
        until it has been fully detached from all future signal delivery.

        Once ``close()`` is called, the object is dead and must not be reused
        for later runs.
        """
        try:
            self._source.close()
        except _ClosedWakeupSourceError as exc:
            err_msg = "HostTerminationRequest is already closed"
            raise OSError(err_msg) from exc

    def _attach(
        self,
        loop: asyncio.AbstractEventLoop,
        event: asyncio.Event,
    ) -> HostTerminationAttachment:
        try:
            return _attach_socket_waker(self._source, loop, event)
        except _ClosedWakeupSourceError as exc:
            err_msg = "attempting to use closed HostTerminationRequest"
            raise OSError(err_msg) from exc


# Accepted values for ``run_ex(host_termination=...)``:
#
# - ``None`` leaves host-driven termination handling disabled.
# - ``HostTerminationRequest.HOST_SIGNALS`` installs temporary SIGINT and
#   SIGTERM handling for the duration of the call.
# - ``HostTerminationRequest()`` provides a caller-managed stable trigger
#   source without modifying the host application's signal handlers.
HostTerminationControlType: TypeAlias = (
    HostTerminationRequest | _HostSignalsSentinel | None
)


def _is_host_termination_object(
    value: object,
) -> TypeGuard[HostTerminationControlType]:
    return (
        value is None
        or value is HostTerminationRequest.HOST_SIGNALS
        or isinstance(value, HostTerminationRequest)
    )


def _validate_host_termination_support(
    control: HostTerminationControlType,
    platform: str,
) -> None:
    if platform == "win32" and control is HostTerminationRequest.HOST_SIGNALS:
        error_msg = (
            "HostTerminationRequest.HOST_SIGNALS is not supported on Windows"
        )
        raise RuntimeError(error_msg)


def _attach_host_termination(
    control: HostTerminationControlType,
    loop: asyncio.AbstractEventLoop,
    event: asyncio.Event,
) -> HostTerminationAttachment:
    if control is None:
        return _NullAttachment()
    if control is HostTerminationRequest.HOST_SIGNALS:
        return _SignalAttachment(event)
    assert isinstance(control, HostTerminationRequest)
    return control._attach(loop, event)  # noqa: SLF001
