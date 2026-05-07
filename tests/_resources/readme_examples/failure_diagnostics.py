import sys

import flnr


class FailsOnMarker(flnr.OutputMonitor):
    def __init__(self, marker: bytes) -> None:
        self.marker = marker
        # Output monitors receive data in chunks, so split lines incrementally.
        self.lines = flnr.IncrementalLineSplitter()

    def process(self, data: bytes, ts: float) -> None:
        del ts
        for line in self.lines.feed(data):
            if self.marker in line:
                msg = f"monitor failed on {self.marker.decode()}"
                raise RuntimeError(msg)


cmd = [
    sys.executable,
    "-c",
    "print('alpha'); print('beta'); raise SystemExit(42)",
]

try:
    flnr.run_ex(
        cmd,
        stdout_monitors=[
            FailsOnMarker(b"alpha"),
            FailsOnMarker(b"beta"),
        ],
    )
except flnr.CommandFailedError as exc:
    print(exc)
