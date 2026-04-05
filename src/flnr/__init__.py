"""flnr (le flâneur).

-- If a producer can outpace a consumer, something must grow, block, or die.
   (independently rediscovered, like most unpleasant truths)
"""

from .exceptions import CommandFailedError as CommandFailedError
from .exceptions import FlnrExceptionBaseError as FlnrExceptionBaseError
from .exceptions import MonitorFailedError as MonitorFailedError
from .flnr import ExecutionTimeouts as ExecutionTimeouts
from .flnr import run_shell_ex as run_shell_ex
from .monitors import OutputMonitor as OutputMonitor
from .monitors import ProcessMonitor as ProcessMonitor
from .monitors import ProcessTerminationReason as ProcessTerminationReason
from .mu import IncrementalLineSplitter as IncrementalLineSplitter
