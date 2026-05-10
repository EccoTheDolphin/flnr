import os
import signal
import sys
import threading
import time


def install_process_timeout(timeout_s: float, exit_code: int = 124) -> None:
    def exit_process() -> None:
        os._exit(exit_code)

    timer = threading.Timer(timeout_s, exit_process)
    timer.daemon = True
    timer.start()


def main() -> None:
    install_process_timeout(60)
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
