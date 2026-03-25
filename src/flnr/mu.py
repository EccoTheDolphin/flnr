"""Collection of various output monitoring utilities."""

from collections.abc import Sequence


class IncrementalLineSplitter:
    """Simple implementation of incremental line splitter."""

    def __init__(self) -> None:
        """Create an incremental line splitter, initialize initial state."""
        self.buf = bytearray()
        self.start = 0

    def _flush(self) -> bytes:
        if self.start < len(self.buf):
            line = bytes(self.buf[self.start :])
            self.buf.clear()
            self.start = 0
            return line
        return b""

    def feed(self, chunk: bytes) -> Sequence[bytes]:
        """Feed a chunk of bytes, get resulting lines as a byte sequence.

        If empty chunk is feed, this transforms currently accumulated bytes
        into a line without newline sequence at the end.
        """
        if not chunk:
            flushed = self._flush()
            if flushed:
                return [flushed]
            return []

        self.buf.extend(chunk)
        lines = []

        while True:
            i = self.buf.find(b"\n", self.start)
            if i == -1:
                break

            line = self.buf[self.start : i + 1]
            lines.append(bytes(line))

            self.start = i + 1

        if self.start > 0 and self.start > len(self.buf) // 2:
            del self.buf[: self.start]
            self.start = 0

        return lines
