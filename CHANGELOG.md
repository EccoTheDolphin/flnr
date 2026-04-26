# Changelog

User-facing changes to `flnr` are documented here.

## Unreleased

### Added

- automatic stdout/stderr routing based on configured output monitors.
- changelog

## 0.1.0 - 2026-04-24

Initial beta release.

### Added

- `run_ex()` for direct-child subprocess supervision.
- structured `ProcessFate` final-state reporting.
- stdout/stderr output monitors.
- environment monitor lifecycle hooks.
- timeout escalation from graceful termination to forced kill.
- state-preserving execution exceptions.
- host termination support on supported platforms.
- zero-runtime-dependency packaging for Python 3.10+.
