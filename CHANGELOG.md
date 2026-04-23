# Changelog

All notable release-facing changes to Sentinel are documented here.

The goal of this file is to describe the shipped product honestly. Historical
implementation notes and older project reports remain under `docs/`, but they
are not treated as release notes.

## [1.0.0] - 2026-04-22

### Release hardening

- aligned scan score, verdict, and enforcement so RTP and the UI use the same
  normalized final decision object
- fixed Windows Real-Time Protection process launch monitoring so live process
  scan activity is actually surfaced instead of silently dropped
- made RTP preference persistence follow the user's last action, with a safe
  first-run default of enabled
- corrected ClamAV detection and status normalization so Linux/UI/runtime paths
  no longer disagree about installation state
- improved Security page truthfulness for Windows and Linux by separating real
  `On`, `Off`, `Unknown`, `Unavailable`, and degraded states

### Cross-platform behavior

- Linux Real-Time Protection is now documented and reported honestly as a
  process-polling implementation
- Windows-specific controls such as Defender, UAC, TPM, and VMware sandbox are
  still reported as Windows-only rather than being faked on Linux
- runtime paths now favor platform-native locations while still reading older
  legacy data locations when present

### Diagnostics and supportability

- diagnostics now report degraded optional dependencies explicitly instead of
  presenting partial capability as healthy
- exported diagnostics remain local JSON and include feature-level availability
  details for support and troubleshooting
- crash, log, and runtime paths are documented through the platform path layer

### Packaging and release notes

- Linux packaging helper now uses repo-relative paths instead of hardcoded
  drive letters
- release-facing docs were corrected to match the current Groq-only AI model,
  current platform support, and current runtime path behavior
- added a final release checklist with Windows/Linux validation steps and known
  limitations that should be stated openly before shipping

### Known limitations carried into this release

- VMware sandbox detonation remains Windows-only
- Linux Event Viewer depends on `journalctl` and does not emulate Windows Event
  Log semantics
- no MSI, DEB, or RPM installer is included in this repository; current release
  packaging is a portable build/source distribution workflow
- there is no central management or policy server in this release
