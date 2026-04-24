"""Reference output monitors and output-processing helpers."""

import io
import math
import operator
import time
from collections.abc import Sequence
from typing import TextIO

from flnr.monitors import OutputMonitor, OutputMonitorDisableReason

_DEFAULT_ILS_BUFFER_LIMIT = 10 * 1024 * 1024


class IncrementalLineSplitter:
    """Incrementally split byte chunks into newline-terminated records."""

    def __init__(self, buffer_limit: int = _DEFAULT_ILS_BUFFER_LIMIT) -> None:
        """Create an incremental line splitter.

        ``buffer_limit`` defines how much trailing data may be retained
        internally while waiting for a newline.

        If buffered tail data grows beyond this limit before a newline is seen,
        the splitter emits that tail early as a fragment. This prevents
        unbounded carry-over memory growth for newline-starved input.

        This value limits retained internal buffer state. It does not provide a
        strict global memory cap for arbitrarily large chunks passed to
        ``feed()``.

        :raises ValueError: if ``buffer_limit`` is not greater than zero.
        """
        if buffer_limit <= 0:
            err_msg = "buffer limit should be > 0"
            raise ValueError(err_msg)
        self._buf = bytearray()
        self._start = 0
        self._buffer_sz_limit = buffer_limit

    def _flush(self) -> bytes:
        if self._start < len(self._buf):
            line = bytes(self._buf[self._start :])
            self._buf.clear()
            self._start = 0
            return line
        return b""

    def feed(self, chunk: bytes) -> Sequence[bytes]:
        """Feed a chunk of bytes, get resulting lines as a byte sequence.

        If an empty chunk is fed, this transforms currently accumulated bytes
        into a line without newline sequence at the end.

        .. note:: If buffered trailing data grows beyond ``buffer_limit``
                  before a newline is seen, the buffered tail is emitted early
                  as a fragment to keep carry-over memory bounded.

        :rtype: collections.abc.Sequence[bytes]
        """
        if not chunk:
            flushed = self._flush()
            if flushed:
                return [flushed]
            return []

        self._buf.extend(chunk)

        lines = []

        while True:
            i = self._buf.find(b"\n", self._start)
            if i == -1:
                break

            line = self._buf[self._start : i + 1]
            lines.append(bytes(line))

            self._start = i + 1

        # If buffered trailing data grows too large, emit the remaining tail
        # early.  This preserves data while preventing unbounded carry-over
        # growth
        if (len(self._buf) - self._start) > self._buffer_sz_limit:
            tail = self._buf[self._start :]
            lines.append(bytes(tail))
            self._start = len(self._buf)

        if self._start > 0 and self._start > len(self._buf) // 2:
            del self._buf[: self._start]
            self._start = 0

        return lines


def _validate_timestamp_precision(value: int | None) -> None:
    if value is None:
        return

    not_validated_error = (
        "timestamp_precision must be integer between 0 and 9 or None"
    )
    if isinstance(value, bool):
        raise TypeError(not_validated_error)

    try:
        precision = operator.index(value)
    except TypeError as exc:
        raise TypeError(not_validated_error) from exc

    max_timestamp_precision = 9
    if not 0 <= precision <= max_timestamp_precision:
        raise ValueError(not_validated_error)


def _validate_timestamp_base(value: float | None) -> None:
    if value is None:
        return

    not_validated_error = (
        "timestamp_base must be finite non-negative real number or None"
    )
    if isinstance(value, bool):
        raise TypeError(not_validated_error)

    if not isinstance(value, (int, float)):
        raise TypeError(not_validated_error)

    if not math.isfinite(value):
        raise ValueError(not_validated_error)

    if value < 0:
        raise ValueError(not_validated_error)


class TextOutputMonitor(OutputMonitor):
    r"""Reference monitor for line-oriented text output.

    This monitor buffers incoming bytes, emits complete records terminated by
    ``\n``, normalizes a trailing ``\r\n`` to ``\n``, decodes the result with
    the configured encoding using ``errors="replace"``, and writes the
    resulting text to a text sink.

    Buffered partial data is flushed when the monitor is disabled.

    Optional timestamping prefixes each emitted line with a monotonic
    timestamp. If ``timestamp_base`` is provided, timestamps are emitted
    relative to that monotonic timestamp value. Disable markers, when enabled,
    are appended as a diagnostic footer and keep their embedded raw monotonic
    timestamp values regardless of the configured timestamp style.
    """

    def __init__(
        self,
        *,
        sink: TextIO,
        ils_buffer_limit: int = _DEFAULT_ILS_BUFFER_LIMIT,
        encoding: str = "latin-1",
        auto_flush: bool = True,
        timestamp_precision: int | None = None,
        timestamp_base: float | None = None,
        append_disable_marker: bool = False,
    ) -> None:
        """Configure how text output is decoded and written.

        :param sink:
            Text sink that receives decoded output.
        :param ils_buffer_limit:
            Maximum amount of trailing data retained by the internal
            incremental line splitter while waiting for a newline.
        :param encoding:
            Encoding used to decode subprocess output. Decoding always uses
            ``errors="replace"``. Defaults to ``latin-1``.
        :param auto_flush:
            If ``True``, flush the sink after each write.
        :param timestamp_precision:
            If set, enables timestamping and controls the number of
            fractional digits written in the timestamp prefix. Must be between
            0 and 9 inclusive.
        :param timestamp_base:
            Optional monotonic timestamp value used to emit timestamps
            relative to that value. This parameter is only valid when
            ``timestamp_precision`` is set.
        :param append_disable_marker:
            If ``True``, append a diagnostic footer when the monitor is
            disabled. The footer includes the disable reason together with raw
            monotonic creation and end-of-watch timestamps.
        :raises ValueError:
            If timestamp parameters are inconsistent or invalid.
        :raises TypeError:
            If timestamp parameter types are invalid.
        """
        _validate_timestamp_precision(timestamp_precision)
        _validate_timestamp_base(timestamp_base)

        if timestamp_base is not None and timestamp_precision is None:
            err_msg = (
                "timestamp_base is specified, "
                "but timestamp_precision is missing"
            )
            raise ValueError(err_msg)

        self.sink = sink
        self.encoding = encoding
        self.auto_flush = auto_flush
        self.timestamp_precision = timestamp_precision
        self.timestamp_base = timestamp_base
        self.append_disable_marker = append_disable_marker

        self.ils = IncrementalLineSplitter(buffer_limit=ils_buffer_limit)
        self.ts_created = time.monotonic()

    def process(self, data: bytes, ts: float) -> None:
        """Process a chunk of subprocess output.

        Complete lines are decoded and written to the sink immediately.
        Partial lines are buffered across calls. An empty chunk (``b""``)
        flushes any buffered tail without adding a newline.

        If timestamping is enabled, each emitted line is prefixed with the
        timestamp associated with this call.
        """
        for line in self.ils.feed(data):
            normalized_line = line
            if line.endswith(b"\r\n"):
                normalized_line = line[:-2] + b"\n"
            decoded = normalized_line.decode(self.encoding, errors="replace")
            if self.timestamp_precision is not None:
                tsl = (
                    ts - self.timestamp_base
                    if self.timestamp_base is not None
                    else ts
                )
                self.sink.write(f"[{tsl:.{self.timestamp_precision}f}] ")
            self.sink.write(decoded)
            if self.auto_flush:
                self.sink.flush()

    def on_disable(self, reason: OutputMonitorDisableReason, ts: float) -> None:
        """Flush buffered data and optionally append a diagnostic footer."""
        # flush out remaining fragment (if any)
        self.process(b"", ts)
        self.sink.flush()
        if self.append_disable_marker:
            self.sink.write(
                f"\n[flnr] !! text output monitor disabled: {reason}"
                f"\n[flnr] !! monitor was created @ monotonic {self.ts_created}"
                f"\n[flnr] !! end of watch @ monotonic {ts}"
            )
            self.sink.flush()


class BinaryOutputMonitor(OutputMonitor):
    """Built-in monitor that forwards raw output bytes to a binary sink."""

    def __init__(self, *, sink: io.IOBase) -> None:
        """Bind the monitor to a writable binary sink."""
        self.sink = sink

    def process(self, data: bytes, _: float) -> None:
        """Write a chunk of raw output bytes to the sink."""
        self.sink.write(data)

    def on_disable(self, _: OutputMonitorDisableReason, __: float) -> None:
        """Flush the sink when monitoring ends."""
        self.sink.flush()
