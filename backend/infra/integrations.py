"""Integration availability helpers for optional external tools."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

_log = logging.getLogger(__name__)

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_WINDOWS_CLAMAV_PATHS = (
    r"C:\Program Files\ClamAV\clamscan.exe",
    r"C:\Program Files (x86)\ClamAV\clamscan.exe",
    r"C:\ClamAV\clamscan.exe",
    r"C:\Program Files\ClamAV\clamdscan.exe",
    r"C:\Program Files (x86)\ClamAV\clamdscan.exe",
    r"C:\ClamAV\clamdscan.exe",
)


def _run_quick_command(args: list[str]) -> subprocess.CompletedProcess[str] | None:
    """Run a short-lived probe command and return the completed process."""
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=_CREATE_NO_WINDOW,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None


def _is_clamd_active(
    runner: Callable[[list[str]], subprocess.CompletedProcess[str] | None] = _run_quick_command,
) -> bool:
    """Best-effort check for an active clamd daemon on Linux."""
    for probe in (["pgrep", "-x", "clamd"], ["systemctl", "is-active", "clamav-daemon"]):
        result = runner(probe)
        if result and result.returncode == 0:
            return True
    return False


def nmap_available() -> bool:
    """Return True if nmap is found in PATH."""
    return shutil.which("nmap") is not None


def get_clamav_status(
    *,
    which: Callable[[str], str | None] = shutil.which,
    path_exists: Callable[[str], bool] = os.path.exists,
    runner: Callable[[list[str]], subprocess.CompletedProcess[str] | None] = _run_quick_command,
    is_windows: bool | None = None,
) -> dict[str, Any]:
    """Return normalized ClamAV availability for UI, diagnostics, and scanners."""
    if is_windows is None:
        is_windows = os.name == "nt"

    status: dict[str, Any] = {
        "available": False,
        "status": "not_installed",
        "label": "Not installed",
        "detail": "ClamAV scanner tools were not found.",
        "scannerPath": "",
        "scannerKind": "",
        "daemonActive": False,
        "daemonClientAvailable": False,
    }

    try:
        scanner_path = which("clamscan") or which("clamdscan")
        detection_source = "path"

        if not scanner_path and is_windows:
            for candidate in _WINDOWS_CLAMAV_PATHS:
                if path_exists(candidate):
                    scanner_path = candidate
                    detection_source = "fallback"
                    break

        daemon_client_path = which("clamdscan")
        if not daemon_client_path and is_windows:
            for candidate in _WINDOWS_CLAMAV_PATHS:
                if candidate.lower().endswith("clamdscan.exe") and path_exists(candidate):
                    daemon_client_path = candidate
                    break

        daemon_active = False if is_windows else _is_clamd_active(runner)
        scanner_kind = Path(scanner_path).name.lower() if scanner_path else ""

        status.update(
            {
                "available": bool(scanner_path),
                "scannerPath": scanner_path or "",
                "scannerKind": scanner_kind,
                "daemonActive": daemon_active,
                "daemonClientAvailable": bool(daemon_client_path),
            }
        )

        if daemon_active and scanner_path:
            status.update(
                {
                    "status": "daemon_available",
                    "label": "Daemon available",
                    "detail": "ClamAV scanner and clamd daemon are available.",
                }
            )
        elif scanner_path:
            detail = "ClamAV command-line scanner is available."
            if detection_source == "fallback":
                detail = "ClamAV scanner is available from a detected install path."
            status.update(
                {
                    "status": "scanner_available",
                    "label": "Scanner available",
                    "detail": detail,
                }
            )
        elif daemon_active:
            status.update(
                {
                    "status": "unavailable",
                    "label": "Unavailable",
                    "detail": "clamd is running but no usable clamscan/clamdscan client was found.",
                }
            )

        return status
    except Exception as exc:  # noqa: BLE001 - probe must not crash startup/UI
        _log.warning("ClamAV detection failed: %s", exc)
        status.update(
            {
                "status": "detection_failed",
                "label": "Detection failed",
                "detail": str(exc),
            }
        )
        return status


def clamav_available() -> bool:
    """Return True if ClamAV scanner tooling is available."""
    return bool(get_clamav_status()["available"])


def get_integration_status() -> dict[str, bool]:
    """Return availability of all optional external integrations."""
    return {
        "nmap": nmap_available(),
        "clamav": clamav_available(),
    }


def print_integration_status() -> None:
    """Log availability of each optional integration at startup."""
    status = get_integration_status()
    clamav = get_clamav_status()

    if not status["nmap"]:
        _log.warning(
            "Network scanner (nmap) not found - Network Scan page will be unavailable"
        )
    if not status["clamav"]:
        _log.info(
            "ClamAV not found - antivirus engine will be skipped during file scans"
        )
    else:
        _log.info("ClamAV status: %s", clamav["label"])
