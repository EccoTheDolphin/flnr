import sys
import time
from pathlib import Path

input_file = Path(sys.argv[1])
encoding = sys.argv[2]
delay = float(sys.argv[3])

for line in input_file.read_text(encoding=encoding).splitlines():
    print(line, file=sys.stdout)
    sys.stdout.flush()
    time.sleep(delay)
