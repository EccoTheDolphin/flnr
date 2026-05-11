import os
import subprocess
import sys
from pathlib import Path

ATTIC_ROOT = Path(__file__).parent.resolve()
REPO_ROOT = ATTIC_ROOT.parent.resolve()

print(f"changing working directory to: {REPO_ROOT}")
os.chdir(REPO_ROOT)

for file in sorted((ATTIC_ROOT / "experiments").glob("*.py")):
    cmd = [sys.executable, file]
    print()
    print("---", file.name, "---")
    print(f"running: {cmd}")
    sys.stdout.flush()
    subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        check=True,
    )
