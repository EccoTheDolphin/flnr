import asyncio
import contextlib
import signal
import threading
from collections.abc import Callable, Sequence
from types import FrameType

_SignalHandler = Callable[[int, FrameType | None], None] | int | None


class _ExternalTerminationInterposer:
    def __call__(self, _: int, __: FrameType | None) -> None:
        assert self._loop is not None
        # loop is closed already, just move on
        with contextlib.suppress(RuntimeError):
            self._loop.call_soon_threadsafe(self._event.set)

    def __init__(
        self, signo_set: Sequence[signal.Signals], ext_rq: asyncio.Event
    ) -> None:
        self._handled_signals = tuple(signo_set)
        self._old_handlers: dict[signal.Signals, _SignalHandler] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._event = ext_rq

    def activate(self) -> None:
        assert threading.current_thread() is threading.main_thread()
        assert self._loop is None
        self._old_handlers = {}
        self._loop = asyncio.get_running_loop()
        for signo in self._handled_signals:
            self._old_handlers[signo] = signal.signal(signo, self)

    def deactivate(self) -> None:
        assert threading.current_thread() is threading.main_thread()
        assert self._loop is not None
        for signo in self._handled_signals:
            signal.signal(signo, self._old_handlers[signo])
