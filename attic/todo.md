- bind stdout/stderr to parent. this is required for interactive tooling
- explicit stdin binding. also for interactive tooling.
- add observability (dump to log file) of trigger events (with timestamp).
- add a way to query trigger state.
- figure out how to deal with race condition of HOST_SIGNALS shortcut
  during the period where process has finished execution and we restore the
  handlers.
- consider implementing HOST_SIGNALS in terms of trigger object. This could
  theoretically give us a better shared machinery story. HOST_SIGNALS itself
  remains Unix signal shortcut.
- figure out reasonable behavior for HOST_SIGNALS propagation back to host.
  new exception perhaps?
- draining tests are more brittle than originally expected. We have at least
  one sporadic failure where a direct child (not even grandchild) was unable
  to produce output to establish proper bootstrap - it was killed by 1-second
  timeout. We need to refactor fixtures to add traceability markers and
  distinguish invalid setup attempts from actual drain failures. retry/backoff
  should only apply to invalid setup attempts.
- introduce new error for OutputMonitorDisableReason, to indicate broken pipe
- ensure “Stall Canary” tracks actual process()/observe() duration.
- assert lifecycle state machine actually enters kill path when terminate
  timeout expires
- add post-mortem monitor failure snapshots
- introduce a heartbeat monitor
- text monitor: add ability to flush on each line vs batch-flush on process call.
- asyncio.to_thread adapter
- generate `__all__` symbol.
