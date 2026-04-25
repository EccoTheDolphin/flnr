"""Facilities for host to request premature termination."""

import asyncio
import os
import signal
import sys
from functools import cache
from typing import Final, Protocol, TypeAlias, TypeGuard

from ._signal_interposer import _ExternalTerminationInterposer


class _HostTerminationBinding(Protocol):
    def activate(
        self,
        loop: asyncio.AbstractEventLoop,
        event: asyncio.Event,
    ) -> None: ...
    def deactivate(self) -> None: ...


class _HostSignalsSentinel:
    def __repr__(self) -> str:
        return "_HostSignalsSentinel"


@cache
def supports_host_termination_request() -> bool:
    """Return whether explicit host termination requests are supported."""
    # technically, host HostTerminationRequest could be create starting
    # from python 3.12 on windows. However, such object would effectively
    # be useless, since current implementation of binder interface requires
    # add_reader to be supported for pipes. Windows implementation does not
    # support those. We could switch to socket pair for portability to
    # allevate this restriction, bbut we are not there at the moment.
    return not sys.platform.startswith("win")


class HostTerminationNotSupportedError(RuntimeError):
    """Raised when host termination requests are not supported."""


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
        if not supports_host_termination_request():
            error_msg = (
                "HostTerminationRequest is not supported on this platform"
            )
            raise HostTerminationNotSupportedError(error_msg)

        self._r_fd = -1
        self._w_fd = -1
        try:
            self._r_fd, self._w_fd = os.pipe()
            os.set_blocking(self._r_fd, False)
            os.set_blocking(self._w_fd, False)
        except:
            if self._r_fd != -1:
                os.close(self._r_fd)
            if self._w_fd != -1:
                os.close(self._w_fd)
            raise

    def trigger(self) -> None:
        """Trigger host termination request.

        Once triggered, the request remains triggered.

        This method may be called from a Python signal handler in this
        implementation. It is intentionally small and only performs the minimal
        work needed to wake attached runs.

        Repeated calls after the request has already been triggered are
        harmless.
        """
        try:
            os.write(self._w_fd, b"\x04")
        except BlockingIOError:
            # The pipe is full, meaning a trigger is already pending. Safe to
            # ignore.
            pass
        except OSError:
            # The request may have been closed by the caller already.
            pass

    def _reader_endpoint(self) -> int:
        return self._r_fd

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
        r_fd = self._r_fd
        w_fd = self._w_fd
        self._r_fd = -1
        self._w_fd = -1
        os.close(r_fd)
        os.close(w_fd)


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


class _HostTerminationRequestBinding(_HostTerminationBinding):
    def __init__(self, control: HostTerminationRequest) -> None:
        self._reader_fd = -1
        self._control = control
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ext_termination_request: asyncio.Event | None = None

    def _close_reader(self) -> None:
        if self._reader_fd == -1:
            return
        fd = self._reader_fd
        self._reader_fd = -1
        os.close(fd)

    def _detach(self) -> None:
        assert self._loop is not None
        try:
            self._loop.remove_reader(self._reader_fd)
        finally:
            self._loop = None
            self._close_reader()

    def _notify(self) -> None:
        assert self._loop is not None
        assert self._ext_termination_request is not None
        self._detach()
        self._ext_termination_request.set()

    def activate(
        self,
        loop: asyncio.AbstractEventLoop,
        ext_termination_request: asyncio.Event,
    ) -> None:
        assert self._loop is None
        try:
            self._reader_fd = os.dup(self._control._reader_endpoint())  # noqa: SLF001
            os.set_blocking(self._reader_fd, False)
            loop.add_reader(self._reader_fd, self._notify)
            self._ext_termination_request = ext_termination_request
            self._loop = loop
        finally:
            if self._loop is None:
                self._ext_termination_request = None
                self._close_reader()

    def deactivate(self) -> None:
        if self._loop is not None:
            self._detach()


class _HostSignalsBinding(_HostTerminationBinding):
    def __init__(self) -> None:
        self.ext_term_interposer: _ExternalTerminationInterposer | None = None

    def activate(
        self,
        _: asyncio.AbstractEventLoop,
        ext_termination_request: asyncio.Event,
    ) -> None:
        self.ext_term_interposer = _ExternalTerminationInterposer(
            [signal.SIGINT, signal.SIGTERM], ext_termination_request
        )
        self.ext_term_interposer.activate()

    def deactivate(self) -> None:
        assert self.ext_term_interposer is not None
        self.ext_term_interposer.deactivate()


class _NullTerminationBinding(_HostTerminationBinding):
    def activate(
        self,
        _: asyncio.AbstractEventLoop,
        __: asyncio.Event,
    ) -> None:
        pass

    def deactivate(self) -> None:
        pass


def _validate_host_termination_support(
    control: HostTerminationControlType,
    platform: str,
) -> None:
    if platform == "win32" and isinstance(control, HostTerminationRequest):
        error_msg = (
            "HostTerminationRequest() is not supported on Windows "
            "in the current implementation"
        )
        raise RuntimeError(error_msg)
    if platform == "win32" and control is HostTerminationRequest.HOST_SIGNALS:
        error_msg = (
            "HostTerminationRequest.HOST_SIGNALS is not supported on Windows "
            "in the current implementation"
        )
        raise RuntimeError(error_msg)


def _make_host_termination_binding(
    control: HostTerminationControlType,
) -> _HostTerminationBinding:
    if control is None:
        return _NullTerminationBinding()
    if control is HostTerminationRequest.HOST_SIGNALS:
        return _HostSignalsBinding()
    assert isinstance(control, HostTerminationRequest)
    return _HostTerminationRequestBinding(control)
