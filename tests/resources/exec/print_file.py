import shutil
import sys
from pathlib import Path

with Path(sys.argv[1]).open("rb") as f:
    shutil.copyfileobj(f, sys.stdout.buffer)
sys.stdout.flush()
