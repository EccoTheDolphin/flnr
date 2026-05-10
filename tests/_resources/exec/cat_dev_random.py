import os
import sys
import threading


def install_process_timeout(timeout_s: float, exit_code: int = 124) -> None:
    def exit_process() -> None:
        os._exit(exit_code)

    timer = threading.Timer(timeout_s, exit_process)
    timer.daemon = True
    timer.start()


install_process_timeout(60)
while True:
    sys.stdout.buffer.write(os.urandom(1))
