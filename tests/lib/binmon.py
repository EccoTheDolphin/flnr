import io

import flnr


class BinaryCapture(flnr.OutputMonitor):
    def __init__(self, sink: io.IOBase) -> None:
        self.sink = sink

    def process(self, data: bytes, _: float) -> None:
        self.sink.write(data)
