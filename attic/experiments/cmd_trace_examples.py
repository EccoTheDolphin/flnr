import logging
import os
import sys
from pathlib import Path

import flnr

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("commands")

PROGRAM_TO_RUN = "tests/_resources/exec/py_true.py"

logger.info("--simple command trace---")
flnr.run_ex([sys.executable, PROGRAM_TO_RUN], tracer=flnr.CommandTracer(logger))

print()
logger.info("---trace with PATH and LD_LIBRARY_PATH---")
flnr.run_ex(
    [sys.executable, Path(PROGRAM_TO_RUN).resolve()],
    tracer=flnr.CommandTracer.with_selected_environment(
        logger, ["PATH", "LD_LIBRARY_PATH"]
    ),
    cwd=Path("/tmp"),  # noqa: S108
)

print()
logger.info("---trace with changed env---")
flnr.run_ex(
    [sys.executable, PROGRAM_TO_RUN],
    env=os.environ
    | {
        "ENV1": "val1",
        "env2": "val2",
        "PATH": "/usr/lo ca l/bin:/usr/local:" + os.environ["PATH"],
    },
    tracer=flnr.CommandTracer.with_changed_environment(logger),
)

print()
logger.info("---trace with cleared env---")
flnr.run_ex(
    [sys.executable, PROGRAM_TO_RUN],
    env={
        "ENV1": "val1",
        "env2": "val2",
        "PATH": "/usr/lo ca l/bin:/usr/local:" + os.environ["PATH"],
    },
    tracer=flnr.CommandTracer.with_recreated_environment(logger),
)

print()
HIDDEN_STYLE_VAR = "FLNR_INTERNAL_COMMAND_TRACE_STYLE"
logger.info("---secret mode not available via API---")
os.environ[HIDDEN_STYLE_VAR] = "multiline"
flnr.run_ex(
    [sys.executable, PROGRAM_TO_RUN],
    env=os.environ
    | {
        "ENV1": "val1",
        "env2": "val2",
        "PATH": "/usr/lo ca l/bin:/usr/local:" + os.environ["PATH"],
    },
    tracer=flnr.CommandTracer.with_changed_environment(logger),
)
del os.environ[HIDDEN_STYLE_VAR]
