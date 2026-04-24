import signal

import flnr

terminator = flnr.HostTerminationRequest()
# SIGINT causes the trigger to fire, which causes the subprocess to enter
# the graceful termination procedure defined by `flnr`.
signal.signal(signal.SIGINT, lambda _, __: terminator.trigger())

fate = flnr.run_ex(
    ["make", "integration-tests"],
    host_termination=terminator,
)

# Note that the terminator object is kept alive for the duration of the script.
# Although `terminator` has a `.close()` method for releasing resources,
# calling it while signals may still arrive races with `.trigger()`.
