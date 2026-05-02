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
- introduce new error for OutputMonitorDisableReason, to indicate broken pipe
- ensure “Stall Canary” tracks actual process()/observe() duration.
- assert lifecycle state machine actually enters kill path when terminate
  timeout expires
- add post-mortem monitor failure snapshots
- introduce a heartbeat monitor
- text monitor: add ability to flush on each line vs batch-flush on process call.
- asyncio.to_thread adapter
- generate `__all__` symbol.
