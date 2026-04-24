import flnr

# Unix-only example.
# Once the subprocess starts, SIGTERM or SIGINT sent to the host process will
# cause the child to undergo the graceful termination procedure defined by
# `flnr`.
fate = flnr.run_ex(
    ["make", "integration-tests"],
    host_termination=flnr.HostTerminationRequest.HOST_SIGNALS,
)
