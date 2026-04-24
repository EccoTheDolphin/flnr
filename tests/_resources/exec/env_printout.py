import os
import sys

sys.stdout.buffer.write(b"--- environment dump start ---\n")
for name, value in sorted(os.environ.items()):
    sys.stdout.buffer.write(f"{name}: {value}\n".encode())
sys.stdout.buffer.write(b"--- environment dump end---\n")
