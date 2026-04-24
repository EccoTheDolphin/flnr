import sys

import flnr

# No output monitors are configured in this minimal example,
# so the child's stdout is intentionally discarded.
fate = flnr.run_ex(
    [sys.executable, "-c", "print('hello')"],
    timeouts=flnr.ExecutionTimeouts(run=5.0),
)

print(f"returncode: {fate.returncode}")
print(f"termination_decision: {fate.termination_decision}")
print(f"termination_method: {fate.termination_method}")
# This will print something like:
# returncode=0, decision=no_intervention, method=none
print(fate)
