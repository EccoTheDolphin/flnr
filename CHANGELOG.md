# Changelog

User-facing changes to `flnr` are documented here.

## Unreleased

## 0.3.0 - 2026-05-01

### Added

- inherited stdin and parent-bound output support
- added installation instructions.

## 0.2.1 - 2026-04-29

### Added

- added failure diagnostics example covering combined command and monitor
  failures.

### Fixed

- `TextOutputMonitor` disable markers now end with a newline.

## 0.2.0 - 2026-04-27

### Added

- `HostTerminationRequest` now works on Windows. `HOST_SIGNALS` remains
  Unix/POSIX-only.

### Changed

- stdout/stderr routing is now derived automatically from configured output
  monitors.

### Removed

- removed `supports_host_termination_request()`. Explicit host-side termination
  is now supported through `HostTerminationRequest`.
- removed `HostTerminationNotSupportedError`; unsupported host-signal binding now
  fails through normal argument validation.

## 0.1.0 - 2026-04-24

Initial beta release.

### Added

- `run_ex()` for direct-child subprocess supervision.
- structured `ProcessFate` final-state reporting.
- stdout/stderr output monitors.
- environment monitor lifecycle hooks.
- timeout escalation from terminate stage to forced kill.
- state-preserving execution exceptions.
- host termination support on supported platforms.
- zero-runtime-dependency packaging for Python 3.10+.
