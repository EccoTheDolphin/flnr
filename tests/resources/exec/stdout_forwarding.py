#!/usr/bin/env python3

import os
import subprocess
import sys
import time
from pathlib import Path

if len(sys.argv) > 1:
    print(f"second process started: pid={os.getpid()}")
    for i in range(10):
        print(f"tick count: {i}")
        sys.stdout.flush()
        time.sleep(2)
    sys.exit(0)

script_path = Path(__file__).resolve()
print(f"first process started: pid={os.getpid()}")
sys.stdout.flush()

subprocess.Popen(  # noqa: S603
    [sys.executable, script_path, "child"],
    stdout=sys.stdout,
    stderr=sys.stderr,
    start_new_session=True,
)
time.sleep(10)
