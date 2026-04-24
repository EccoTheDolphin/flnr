import os
import sys

while True:
    sys.stdout.buffer.write(os.urandom(1))
