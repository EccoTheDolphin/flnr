import asyncio
import select
import socket

from flnr._async_utils import _cancel_tasks
from flnr._host_control.types import HostTerminationAttachment


class _ClosedWakeupSourceError(Exception):
    pass


class _SocketWakeupSource:
    def __init__(self) -> None:
        reader: socket.socket | None = None
        writer: socket.socket | None = None
        try:
            reader, writer = socket.socketpair()
            notblocking = False
            writer.setblocking(notblocking)
        except:
            if reader is not None:
                reader.close()
            if writer is not None:
                writer.close()
            raise

        self._reader: socket.socket | None = reader
        self._writer: socket.socket | None = writer

    def trigger(self) -> None:
        try:
            writer = self._writer
            # unfortunately, this still races with .close
            if writer is None:
                return
            writer.send(b"\x04")
        except BlockingIOError:
            pass
        except OSError:
            pass

    def dup_reader(self) -> socket.socket:
        if self._reader is None:
            error_msg = "attempting to use closed wakeup source"
            raise _ClosedWakeupSourceError(error_msg)
        return self._reader.dup()

    def close(self) -> None:
        reader = self._reader
        writer = self._writer

        if reader is None or writer is None:
            error_msg = "calling close on a closed wakeup source"
            raise _ClosedWakeupSourceError(error_msg)

        self._reader = None
        self._writer = None

        try:
            reader.close()
        finally:
            writer.close()


class _AsyncLoopReaderAttachment(HostTerminationAttachment):
    def __init__(
        self,
        reader: socket.socket,
        loop: asyncio.AbstractEventLoop,
        ext_termination_request: asyncio.Event,
    ) -> None:
        self._attachment: (
            tuple[asyncio.AbstractEventLoop, socket.socket] | None
        ) = (loop, reader)
        self._ext_termination_request = ext_termination_request

        loop.add_reader(reader, self._notify)

    def _detach(self) -> None:
        attachment = self._attachment
        self._attachment = None

        if attachment is None:
            return

        loop, reader = attachment
        try:
            loop.remove_reader(reader)
        finally:
            reader.close()

    def _notify(self) -> None:
        try:
            self._detach()
        finally:
            self._ext_termination_request.set()

    async def deactivate(self) -> None:
        self._detach()


_POLL_PERIOD = 0.05


class _PollingWakeupAttachment(HostTerminationAttachment):
    def __init__(
        self,
        *,
        reader: socket.socket,
        loop: asyncio.AbstractEventLoop,
        event: asyncio.Event,
        poll_interval: float = _POLL_PERIOD,
    ) -> None:
        self._reader = reader
        self._event = event
        self._task = loop.create_task(
            self._poll(reader, poll_interval),
            name="host_termination.poll_socket",
        )

    async def _poll(self, reader: socket.socket, poll_interval: float) -> None:
        while True:
            try:
                readable, _, _ = select.select([reader], [], [], 0)
            except OSError:
                return

            if readable:
                self._event.set()
                return

            await asyncio.sleep(poll_interval)

    async def deactivate(self) -> None:
        try:
            await _cancel_tasks(self._task)
        finally:
            self._reader.close()


def _attach_socket_waker(
    source: _SocketWakeupSource,
    loop: asyncio.AbstractEventLoop,
    event: asyncio.Event,
) -> HostTerminationAttachment:

    reader = source.dup_reader()

    try:
        return _AsyncLoopReaderAttachment(reader, loop, event)
    except (NotImplementedError, RuntimeError, OSError):
        pass

    try:
        return _PollingWakeupAttachment(reader=reader, loop=loop, event=event)
    except:
        reader.close()
        raise
