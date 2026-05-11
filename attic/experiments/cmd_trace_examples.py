import logging
import os
import sys
import tempfile
from pathlib import Path

import flnr

_MANDATORY_ENV: dict[str, str] = {}
if sys.platform.startswith("win32"):
    _MANDATORY_ENV["SYSTEMROOT"] = os.environ["SYSTEMROOT"]


def flush_line() -> None:
    print()
    sys.stdout.flush()


logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("commands")

PROGRAM_TO_RUN = "tests/_resources/exec/py_true.py"

logger.info("--simple command trace---")
flnr.run_ex([sys.executable, PROGRAM_TO_RUN], tracer=flnr.CommandTracer(logger))

flush_line()
logger.info("---trace with PATH and LD_LIBRARY_PATH---")
flnr.run_ex(
    [sys.executable, Path(PROGRAM_TO_RUN).resolve()],
    tracer=flnr.CommandTracer.with_selected_environment(
        logger, ["PATH", "LD_LIBRARY_PATH"]
    ),
    cwd=Path(tempfile.gettempdir()),
)

flush_line()
logger.info("---trace with changed env---")
flnr.run_ex(
    [sys.executable, PROGRAM_TO_RUN],
    env=os.environ
    | {
        "ENV1": "val1",
        "env2": "val2",
        "PATH": os.pathsep.join(
            ["/usr/lo ca l/bin", "/usr/local", os.environ["PATH"]],
        ),
    },
    tracer=flnr.CommandTracer.with_changed_environment(logger),
)

flush_line()
logger.info("---trace with cleared env---")
flnr.run_ex(
    [sys.executable, PROGRAM_TO_RUN],
    env={
        "ENV1": "val1",
        "env2": "val2",
        "PATH": os.pathsep.join(
            ["/usr/lo ca l/bin", "/usr/local", os.environ["PATH"]]
        ),
    }
    | _MANDATORY_ENV,
    tracer=flnr.CommandTracer.with_recreated_environment(logger),
    stdout_monitors=flnr.BIND_TO_PARENT,
    stderr_monitors=flnr.BIND_TO_PARENT,
)

flush_line()
HIDDEN_STYLE_VAR = "FLNR_INTERNAL_COMMAND_TRACE_STYLE"
logger.info("---secret mode not available via API---")
old_value = os.environ.get(HIDDEN_STYLE_VAR)
try:
    os.environ[HIDDEN_STYLE_VAR] = "multiline"
    flnr.run_ex(
        [sys.executable, PROGRAM_TO_RUN],
        env=os.environ
        | {
            "ENV1": "val1",
            "env2": "val2",
            "PATH": os.pathsep.join(
                ["/usr/lo ca l/bin", "/usr/local", os.environ["PATH"]]
            ),
        },
        tracer=flnr.CommandTracer.with_changed_environment(logger),
        stdout_monitors=flnr.BIND_TO_PARENT,
        stderr_monitors=flnr.BIND_TO_PARENT,
    )
finally:
    if old_value is None:
        os.environ.pop(HIDDEN_STYLE_VAR, None)
    else:
        os.environ[HIDDEN_STYLE_VAR] = old_value
