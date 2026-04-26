# Changelog

User-facing changes to `flnr` are documented here.

## Unreleased

### Added

- Automatic standard stream routing based on supplied output monitors
- Changelog

## 0.1.0 - 2026-04-24

Initial beta release.

### Added

- Added `run_ex()` for direct-child subprocess supervision.
- Added structured `ProcessFate` final-state reporting.
- Added stdout/stderr output monitors.
- Added environment monitor lifecycle hooks.
- Added timeout escalation from graceful termination to forced kill.
- Added state-preserving execution exceptions.
- Added host termination support on supported platforms.
- Added zero-runtime-dependency packaging for Python 3.10+.
