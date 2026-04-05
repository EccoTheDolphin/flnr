from typing import TextIO

import flnr


class TextOutputMonitor(flnr.OutputMonitor):
    r"""Reference implementation of monitor for text output.

    Its purpose is to write decoded text lines to a file-like sink. It is
    intended to be used to monitor output of processes that produce
    relatively small amount of data during their lifetime (2-3 Kb per second
    is fine). This implementation is not intended to serve as universal
    high-frequency-capable-catch-all monitor.

    The monitor buffers incoming bytes across calls, splits on newlines,
    decodes each complete line with the given encoding (invalid bytes
    replaced by 'Unicode Replace Character'), and writes to the sink.
    Optionally flushes after each write. An empty chunk (``b""``)
    flushes any remaining partial line.

    **Line endings:**
    The monitor normalises line endings to a single ``\n`` (i.e., a trailing
    ``\r`` before the newline is removed). The underlying text sink then
    applies the platform-specific line ending convention e.g., ``\r\n`` on
    Windows). This ensures consistent behaviour across platforms.
    """

    def __init__(
        self,
        *,
        sink: TextIO,
        encoding: str = "latin-1",
        auto_flush: bool = True,
    ) -> None:
        """Define how data is processed by the monitor.

        :param sink: output stream to send processed result
        :param encoding: encoding of the data. The logger decodes input
                         data line by line with `replace` error-handling
                         policy. Defaults to `latin-1` (which never fails).
        :param auto_flush: flush output stream after each write to sink.
                            Defaults to true to ensure that data is flushed as
                            soon as it is available.
        """
        self.sink = sink
        self.encoding = encoding
        self.auto_flush = auto_flush

        self.ils = flnr.IncrementalLineSplitter()

    def process(self, data: bytes, _: float) -> None:
        """Process a chunk of subprocess output.

        Feeds the chunk to an internal line splitter. Any complete lines
        (including the newline) are decoded and written to the sink.
        Partial lines are buffered across calls. An empty chunk (``b""``)
        flushes any remaining partial line without a newline.
        """
        for line in self.ils.feed(data):
            normalized_line = line
            if line.endswith(b"\r\n"):
                normalized_line = line[:-2] + b"\n"
            decoded = normalized_line.decode(self.encoding, errors="replace")
            self.sink.write(decoded)
            if self.auto_flush:
                self.sink.flush()
