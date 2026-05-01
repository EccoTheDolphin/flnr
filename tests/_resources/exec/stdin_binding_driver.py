import io
import sys

import flnr


def _child() -> None:
    data = sys.stdin.buffer.read()
    if data:
        sys.stdout.buffer.write(data)
    else:
        sys.stdout.buffer.write(b"<empty>")
    sys.stdout.buffer.flush()


def _run_child(*, inherit_stdin: bool) -> None:
    stdin = flnr.INHERIT_STDIN if inherit_stdin else None
    output = io.BytesIO()
    flnr.run_ex(
        [sys.executable, __file__, "child"],
        stdin=stdin,
        stdout_monitors=[flnr.BinaryOutputMonitor(sink=output)],
    )
    sys.stdout.buffer.write(output.getvalue())
    sys.stdout.buffer.flush()


def _interactive_child() -> None:
    sys.stdout.write(
        "TTY "
        f"stdin={sys.stdin.isatty()} "
        f"stdout={sys.stdout.isatty()} "
        f"stderr={sys.stderr.isatty()}\n"
    )
    sys.stdout.write("READY\n")
    sys.stdout.flush()

    line = sys.stdin.readline()
    sys.stdout.write(f"OUT:{line}")
    sys.stdout.flush()
    sys.stderr.write(f"ERR:{line}")
    sys.stderr.flush()


def _run_interactive_child() -> None:
    flnr.run_ex(
        [sys.executable, __file__, "interactive_child"],
        stdin=flnr.INHERIT_STDIN,
        stdout_monitors=flnr.BIND_TO_PARENT,
        stderr_monitors=flnr.BIND_TO_PARENT,
        merge_std_streams=False,
    )


if __name__ == "__main__":
    match sys.argv[1]:
        case "child":
            _child()
        case "inherit_stdin":
            _run_child(inherit_stdin=True)
        case "default_stdin":
            _run_child(inherit_stdin=False)
        case "interactive_child":
            _interactive_child()
        case "interactive":
            _run_interactive_child()
        case _:
            err_msg = "unknown test type"
            raise ValueError(err_msg)
