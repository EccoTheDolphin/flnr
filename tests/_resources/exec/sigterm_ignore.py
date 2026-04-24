import os
import signal
import sys
import time


def main() -> None:
    # Ignore SIGTERM
    signal.signal(signal.SIGTERM, signal.SIG_IGN)

    # Print PID for testing
    pid = os.getpid()
    sys.stdout.write(f"started program that ignores SIGTERM, pid = {pid}.")
    sys.stdout.flush()
    sys.stderr.flush()

    # Hang indefinitely
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
