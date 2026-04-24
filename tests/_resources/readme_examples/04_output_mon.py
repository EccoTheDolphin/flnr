import io
import pathlib
import sys

import flnr


class ThroughputMonitor(flnr.OutputMonitor):
    def __init__(self, *, sink: io.IOBase) -> None:
        self.sink = sink
        self.bytes_received = 0

    def process(self, data: bytes, ts: float) -> None:
        self.bytes_received += len(data)
        msg = f"{ts:.3f}s total {self.bytes_received} bytes\n"
        self.sink.write(msg.encode("latin-1"))

    def on_disable(self, _: flnr.OutputMonitorDisableReason, __: float) -> None:
        pass


# Noise generator as a single expression
noisy_stream = "import os\nwhile True:\n    os.write(1, os.urandom(1024))"

# Simulating a long-running process by generating infinite random noise.
# We decode as latin-1 so arbitrary bytes always become text at the monitor
# boundary. The sink still writes UTF-8 on purpose: decoding policy belongs
# to the monitor, not to the destination file.
try:
    with (
        pathlib.Path("throughput.id-11e1a300.log").open("wb") as throughput_log,
        pathlib.Path("binary.id-243f6a88.bin").open("wb") as binary_log,
        pathlib.Path("text.id-5f3759df.txt").open("w", encoding="utf-8") as txt,
    ):
        flnr.run_ex(
            [sys.executable, "-c", noisy_stream],
            stdout_monitors=[
                ThroughputMonitor(sink=throughput_log),
                flnr.BinaryOutputMonitor(sink=binary_log),
                flnr.TextOutputMonitor(
                    sink=txt, encoding="latin-1", timestamp_precision=3
                ),
            ],
            # stop the process after 3 seconds of execution.
            timeouts=flnr.ExecutionTimeouts(run=3.0, output_drain=1.0),
        )
except flnr.CommandFailedError as e:
    # The run timeout expired; the process was successfully terminated.
    print(e)
# After the process is terminated due to timeout, the resulting files contain:
# throughput records (as defined by the custom monitor), raw output with random
# noise produced by the script, and the same output transcoded from
# latin-1 to UTF-8 with timestamps at line boundaries.
