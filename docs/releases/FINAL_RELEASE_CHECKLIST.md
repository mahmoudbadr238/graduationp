# Final Release Checklist

This checklist is the release-facing source of truth for preparing a Sentinel
build for evaluation or distribution.

## Scope

Sentinel is a cross-platform desktop endpoint security application with:

- Windows and Linux desktop support
- local-first monitoring, scanning, and telemetry
- optional cloud-backed Groq AI features
- explicit degraded-mode reporting for optional dependencies

This release does **not** include:

- a central management server
- MSI, DEB, or RPM installers
- fake parity for Windows-only security controls

## Source of truth

Use these documents first:

- [README.md](../../README.md)
- [../QUICKSTART.md](../QUICKSTART.md)
- [../PRIVACY.md](../PRIVACY.md)

Treat `docs/project/`, `docs/development/`, and older release notes as
historical context only.

## Windows release steps

1. Create a clean virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Run diagnostics: `python -m backend --diagnose`.
4. Run focused tests:
   `python -m pytest backend/tests/test_smoke.py backend/tests/test_settings_persistence.py backend/tests/test_theme_persistence.py backend/tests/test_diagnostics.py backend/tests/test_application_close_behavior.py backend/tests/test_backend_bridge_ai.py backend/tests/test_decision_alignment.py backend/tests/test_realtime_protection_runtime.py backend/tests/test_security_truthfulness.py -q`
5. Validate manual flows:
   - startup and shutdown
   - RTP enabled and disabled
   - System Snapshot security cards
   - Scan Center file scan and history
   - Event Viewer
   - Settings persistence
6. If publishing a packaged build, validate the PyInstaller artifact on a clean
   Windows machine before release.
7. Publish only a portable build that has been manually smoke-tested.

## Linux release steps

1. Use `./run_linux.sh` to provision a clean Linux environment.
2. Run diagnostics: `python -m backend --diagnose`.
3. Run focused tests:
   `python -m pytest backend/tests/test_smoke.py backend/tests/test_diagnostics.py backend/tests/test_application_close_behavior.py backend/tests/test_security_truthfulness.py backend/tests/test_platform_paths.py backend/tests/test_linux_security_posture.py -q`
4. Validate manual flows:
   - startup and shutdown
   - RTP enabled and disabled
   - ClamAV detection in Scan Center
   - System Snapshot security cards
   - Event Viewer with `journalctl`
   - Settings persistence
5. Build the Linux package with `./build_linux.sh` on Linux.
6. If distributing source to Linux systems from Windows, create the handoff zip
   with `./pack_linux.ps1`.

## Pre-release validation

Before tagging or publishing:

1. Confirm score, verdict, and enforcement remain aligned in scan results and RTP.
2. Confirm diagnostics report degraded dependencies honestly.
3. Confirm no UI page claims a capability that the backend reports unavailable.
4. Confirm Windows and Linux both respect the saved RTP preference.
5. Confirm ClamAV status is truthful on systems with `clamscan`, `clamd`, or neither.
6. Confirm release docs do not claim unsupported providers, installers, or platform parity.
7. Confirm the shell, navigation labels, and alert controls render without emoji or glyph fallback issues on Windows and Linux.
8. Confirm Settings only exposes supported startup or tray controls and keeps diagnostics wording local-first.

## Post-release known limitations

State these openly in release notes or evaluation material:

- VMware sandbox detonation is Windows-only.
- Windows-specific Defender, UAC, SmartScreen, and TPM integrations do not have Linux equivalents.
- Linux Event Viewer depends on `journalctl` and does not emulate Windows Event Log semantics.
- Packaged Windows builds require clean-machine validation; no MSI installer is provided in this repo.
- Linux packaging is currently a source or portable build workflow; no DEB or RPM is provided.
- Optional AI features require `GROQ_API_KEY` and are unavailable without it.
