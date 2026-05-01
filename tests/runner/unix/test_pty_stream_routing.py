import errno
import io
import os
import pty
import termios

import pytest

import flnr
from tests._support.utils import PythonCmdBuilder


def _disable_echo(fd: int) -> None:
    attrs = termios.tcgetattr(fd)
    attrs[3] &= ~termios.ECHO
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


def _read_until(fd: int, marker: str) -> str:
    output = io.StringIO()
    monitor = flnr.TextOutputMonitor(sink=output, encoding="latin-1")

    while marker not in output.getvalue():
        try:
            chunk = os.read(fd, 4096)
        except OSError as exc:
            if exc.errno == errno.EIO:
                break
            raise
        monitor.process(chunk, 0.0)
        if not chunk:
            break

    if marker not in output.getvalue():
        err_msg = f"did not find {marker!r}; got {output.getvalue()!r}"
        raise AssertionError(err_msg)
    return output.getvalue()


def _wait_pid(pid: int) -> int:
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)


@pytest.mark.timeout(60)
def test_parent_bound_stdio_works_with_pty(
    py_exec: PythonCmdBuilder,
) -> None:
    pid, master_fd = pty.fork()

    if pid == 0:
        cmd = py_exec("stdin_binding_driver.py", "interactive")
        os.execv(cmd[0], cmd)  # noqa: S606

    try:
        _disable_echo(master_fd)

        output = _read_until(master_fd, "READY\n")
        os.write(master_fd, b"hello from pty\n")
        output += _read_until(master_fd, "ERR:hello from pty\n")

        assert _wait_pid(pid) == 0
        assert "TTY stdin=True stdout=True stderr=True\n" in output
        assert "READY\n" in output
        assert "OUT:hello from pty\n" in output
        assert "ERR:hello from pty\n" in output
    finally:
        # hold your pearls! we don't force-kill the child.  doing so will only
        # add visual noise. OS will do the mop up eventually
        os.close(master_fd)
