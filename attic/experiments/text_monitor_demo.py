import sys
import time

import flnr

flnr.run_ex(
    [
        sys.executable,
        "tests/_resources/exec/ln_print.py",
        "tests/_resources/data/default.txt",
        "utf-8",
        "1.0",
    ],
    stdout_monitors=[
        flnr.TextOutputMonitor(sink=sys.stdout),
        flnr.TextOutputMonitor(sink=sys.stdout, timestamp_precision=3),
        flnr.TextOutputMonitor(
            sink=sys.stdout,
            timestamp_precision=3,
            timestamp_base=time.monotonic(),
        ),
    ],
)
