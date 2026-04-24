"""
Real-Time Protection (RTP) Engine — Sentinel EDR.

Monitors the Windows OS for new process launches via WMI, runs each
executable through the StaticScanner + Groq NGAV pipeline, and
terminates any process flagged as malicious — in real time.

Architecture
~~~~~~~~~~~~
::

    ┌──────────────────────────────┐
    │      QML / PySide6 UI       │  ← toggle ON / OFF
    └────────────┬─────────────────┘
                 │ enable() / disable()
    ┌────────────▼─────────────────┐
    │  RealTimeProtectionBridge    │  ← QObject exposed to QML
    │  (main thread)              │
    └────────────┬─────────────────┘
                 │ starts / stops
    ┌────────────▼─────────────────┐
    │  RealTimeProtectionWorker    │  ← QThread (COM-initialised)
    │  ┌─────────────────────────┐ │
    │  │ WMI __InstanceCreation  │ │  ← Win32_Process event watcher
    │  │ Event → PID + .exe path │ │
    │  └────────────┬────────────┘ │
    │               ▼              │
    │  StaticScanner.scan_file()   │  ← Groq AI verdict
    │               │              │
    │       ┌───────┴───────┐      │
    │       │ malicious?    │      │
    │       │  YES → kill() │      │
    │       │  NO  → pass   │      │
    │       └───────────────┘      │
    └──────────────────────────────┘

Thread Safety
~~~~~~~~~~~~~
* ``pythoncom.CoInitialize()`` is called at the start of ``run()``
  because WMI requires COM initialisation per-thread.
* All signal emissions are thread-safe (Qt signal/slot mechanism).
* The worker checks ``self._running`` on each iteration and breaks
  cleanly when asked to stop.

Dependencies
~~~~~~~~~~~~
* ``wmi`` + ``pywin32`` (pythoncom) — WMI event watching
* ``psutil`` — process termination with privilege escalation
* ``backend.engines.scanning.static_scanner`` — static + Groq AI file scanning
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

from backend.engines.scanning.decision import (
    DEFAULT_BLOCK_THRESHOLD,
    build_final_decision,
    decision_from_scan_result,
)

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────────────────
# Data Structures
# ───────────────────────────────────────────────────────────────────


@dataclass
class ThreatEvent:
    """Represents a single real-time threat detection event."""

    pid: int
    process_name: str
    executable_path: str
    matched_rules: list[str] = field(default_factory=list)
    threat_score: int = 0
    decision_verdict: str = ""
    decision_action: str = ""
    process_action: str = ""
    file_action: str = ""
    action_reason: str = ""
    action_taken: str = ""        # Process result: terminated, log_only, access_denied, etc.
    file_action_taken: str = ""   # File result: quarantined, skipped, failed, allowed
    timestamp: str = ""
    occurred_at: str = ""
    sha256: str = ""
    publisher: str = ""
    signature_valid: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "process_name": self.process_name,
            "executable_path": self.executable_path,
            "matched_rules": self.matched_rules,
            "threat_score": self.threat_score,
            "decision_verdict": self.decision_verdict,
            "decision_action": self.decision_action,
            "process_action": self.process_action,
            "file_action": self.file_action,
            "action_reason": self.action_reason,
            "action_taken": self.action_taken,
            "file_action_taken": self.file_action_taken,
            "timestamp": self.timestamp,
            "occurred_at": self.occurred_at,
            "sha256": self.sha256,
            "publisher": self.publisher,
            "signature_valid": self.signature_valid,
        }

    def to_display_string(self) -> str:
        icon = "🛡️" if self.action_taken == "terminated" else "⚠️"
        signature_text = (
            "valid"
            if self.signature_valid is True
            else "invalid"
            if self.signature_valid is False
            else "unknown"
        )
        heading = "THREAT EVENT"
        if self.process_action == "log_only":
            heading = "THREAT FLAGGED"
        elif self.process_action == "kill_process" and self.action_taken == "terminated":
            heading = "THREAT BLOCKED"
        return (
            f"{icon} [{self.timestamp}] {heading}\n"
            f"   Process : {self.process_name} (PID {self.pid})\n"
            f"   Path    : {self.executable_path}\n"
            f"   Verdict : {self.decision_verdict or 'Unknown'}\n"
            f"   Rules   : {', '.join(self.matched_rules) or 'N/A'}\n"
            f"   Score   : {self.threat_score}/100\n"
            f"   Decision: {(self.decision_action or 'allow').upper()}\n"
            f"   Process Action: {(self.process_action or 'allow').upper()}\n"
            f"   File Action   : {(self.file_action or 'allow').upper()}\n"
            f"   Reason  : {self.action_reason or 'No enforcement reason recorded.'}\n"
            f"   Result  : {self.action_taken.upper()}\n"
            f"   File Result: {(self.file_action_taken or 'allowed').upper()}\n"
            f"   Publisher: {self.publisher or 'Unknown'}\n"
            f"   Signature: {signature_text.upper()}"
        )


@dataclass(frozen=True)
class EnforcementPlan:
    """Explicit runtime/file action model derived from one final decision."""

    decision_action: str
    process_action: str
    file_action: str
    reason: str
    trusted_install: bool = False
    protected_signed_install: bool = False
    trusted_internal_helper: bool = False
    strong_evidence: bool = False
    publisher: str = ""
    signature_valid: bool | None = None
    fingerprint: tuple[int, int] | None = None


# ───────────────────────────────────────────────────────────────────
# Configuration
# ───────────────────────────────────────────────────────────────────

# System-critical processes that must NEVER be terminated
WHITELISTED_PROCESSES = frozenset({
    "system", "system idle process", "registry", "smss.exe",
    "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe",
    "lsass.exe", "lsm.exe", "svchost.exe", "dwm.exe",
    "explorer.exe", "taskhostw.exe", "runtimebroker.exe",
    "searchhost.exe", "startmenuexperiencehost.exe",
    "shellexperiencehost.exe", "textinputhost.exe",
    "conhost.exe", "dllhost.exe", "sihost.exe",
    "fontdrvhost.exe", "ctfmon.exe", "audiodg.exe",
    # Security software
    "msmpeng.exe", "nissrv.exe", "securityhealthservice.exe",
    "securityhealthsystray.exe", "mpcmdrun.exe",
    # Our own process
    "python.exe", "pythonw.exe", "python3.exe",
})

# WMI polling interval (seconds between event checks)
WMI_POLL_INTERVAL = 0.5

# Final decision score threshold used when no explicit override rule exists.
BLOCK_THRESHOLD = DEFAULT_BLOCK_THRESHOLD
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_WINDOWS_PROTECTED_BROWSER_RULES: dict[str, dict[str, tuple[str, ...]]] = {
    "brave.exe": {
        "publishers": ("brave software",),
        "path_hints": (
            "\\bravesoftware\\brave-browser\\application\\brave.exe",
        ),
    },
    "chrome.exe": {
        "publishers": ("google",),
        "path_hints": (
            "\\google\\chrome\\application\\chrome.exe",
        ),
    },
    "msedge.exe": {
        "publishers": ("microsoft",),
        "path_hints": (
            "\\microsoft\\edge\\application\\msedge.exe",
        ),
    },
    "firefox.exe": {
        "publishers": ("mozilla",),
        "path_hints": (
            "\\mozilla firefox\\firefox.exe",
        ),
    },
}

_LINUX_PROTECTED_BROWSER_RULES: dict[str, dict[str, tuple[str, ...]]] = {
    "brave-browser": {
        "publishers": (),
        "path_hints": (
            "/opt/brave.com/brave/brave-browser",
            "/usr/bin/brave-browser",
        ),
    },
    "google-chrome": {
        "publishers": (),
        "path_hints": (
            "/opt/google/chrome/chrome",
            "/usr/bin/google-chrome",
        ),
    },
    "microsoft-edge": {
        "publishers": (),
        "path_hints": (
            "/opt/microsoft/msedge/msedge",
            "/usr/bin/microsoft-edge",
        ),
    },
    "firefox": {
        "publishers": (),
        "path_hints": (
            "/usr/lib/firefox/firefox",
            "/usr/bin/firefox",
            "/snap/firefox/",
        ),
    },
}

_SENTINEL_INTERNAL_HELPER_NAMES = frozenset({
    "sentinel_gpu_worker.exe",
    "sentinel_url_detonator.exe",
    "sentinel_agent.exe",
})

_SENTINEL_MAIN_PROCESS_NAMES = frozenset({
    "sentinel.exe",
    "sentinel",
})


def _canonical_path(path: str) -> str:
    """Return a stable lowercase absolute path for trust/cache checks."""
    if not path:
        return ""
    try:
        return str(Path(path).resolve(strict=False)).lower()
    except OSError:
        return os.path.abspath(path).lower()


def _path_is_relative_to(path: Path, root: Path) -> bool:
    """Return True when *path* resolves inside *root*."""
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except (OSError, ValueError):
        normalized_path = _canonical_path(str(path))
        normalized_root = _canonical_path(str(root))
        if not normalized_path or not normalized_root:
            return False
        return normalized_path == normalized_root or normalized_path.startswith(
            normalized_root.rstrip("\\/") + os.sep
        )


def _sentinel_trusted_roots() -> tuple[Path, ...]:
    """Return immutable application roots that may contain shipped helpers."""
    try:
        from backend.runtime import app_root, bundle_root

        candidates = [app_root(), bundle_root()]
    except Exception:
        candidates = []

    roots: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=False)
        except OSError:
            resolved = candidate
        key = _canonical_path(str(resolved))
        if not key or key in seen:
            continue
        seen.add(key)
        roots.append(resolved)
    return tuple(roots)


def _is_path_in_sentinel_tree(path: str) -> bool:
    """Return True only for paths rooted in Sentinel's app/bundle tree."""
    if not path:
        return False
    candidate = Path(path)
    return any(_path_is_relative_to(candidate, root) for root in _sentinel_trusted_roots())


def _is_sentinel_internal_helper_path(process_name: str, exe_path: str) -> bool:
    """Return True for exact Sentinel-shipped helper names inside app roots."""
    name = (process_name or Path(exe_path).name or "").lower()
    path_name = Path(exe_path).name.lower()
    if name not in _SENTINEL_INTERNAL_HELPER_NAMES:
        return False
    if path_name != name:
        return False
    return _is_path_in_sentinel_tree(exe_path)


def _is_sentinel_main_process_path(exe_path: str) -> bool:
    """Return True for Sentinel's own main executable inside app roots."""
    if not exe_path:
        return False
    if Path(exe_path).name.lower() not in _SENTINEL_MAIN_PROCESS_NAMES:
        return False
    return _is_path_in_sentinel_tree(exe_path)


def _parent_is_current_sentinel_app(parent_pid: int | None, psutil_mod: Any | None) -> bool:
    """Validate that a helper launch came directly from this Sentinel runtime."""
    if parent_pid is None or parent_pid <= 0:
        return False
    if parent_pid == os.getpid():
        return True
    if psutil_mod is None:
        return False

    try:
        parent = psutil_mod.Process(parent_pid)
        parent_exe = str(parent.exe() or "")
    except Exception:
        return False
    return _is_sentinel_main_process_path(parent_exe)


def _is_trusted_sentinel_internal_helper(
    process_name: str,
    exe_path: str,
    *,
    parent_pid: int | None = None,
    psutil_mod: Any | None = None,
) -> bool:
    """Return True only for Sentinel helpers launched by Sentinel from its tree."""
    return _is_sentinel_internal_helper_path(
        process_name,
        exe_path,
    ) and _parent_is_current_sentinel_app(parent_pid, psutil_mod)


def _file_fingerprint(exe_path: str) -> tuple[int, int] | None:
    """Return a cheap fingerprint for cache-safety checks."""
    try:
        stat_result = Path(exe_path).stat()
    except OSError:
        return None
    return int(stat_result.st_size), int(stat_result.st_mtime_ns)


def _is_trusted_install_path(exe_path: str) -> bool:
    """Return True for known application install roots, not temp/user-writable paths."""
    normalized = _canonical_path(exe_path)
    if not normalized:
        return False

    if sys.platform == "win32":
        trusted_roots: list[str] = []
        for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
            value = os.environ.get(env_name, "").strip()
            if value:
                trusted_roots.append(_canonical_path(value))
        programs_root = os.path.join(
            os.environ.get("LocalAppData", "").strip(),
            "Programs",
        ).strip("\\/")
        if programs_root:
            trusted_roots.append(_canonical_path(programs_root))
        return any(
            normalized == root or normalized.startswith(root + os.sep)
            for root in trusted_roots
            if root
        )

    trusted_roots = (
        "/usr/bin",
        "/usr/local/bin",
        "/usr/lib",
        "/opt",
        "/snap",
    )
    return any(
        normalized == root or normalized.startswith(root + os.sep)
        for root in trusted_roots
    )


def _is_protected_browser_install(
    process_name: str,
    exe_path: str,
    publisher: str,
    signature_valid: bool | None,
) -> bool:
    """Return True for mainstream browser installs that should never be destroyed on weak evidence."""
    name_key = (process_name or "").lower()
    normalized_path = _canonical_path(exe_path)
    publisher_lower = (publisher or "").lower()
    rules = (
        _WINDOWS_PROTECTED_BROWSER_RULES
        if sys.platform == "win32"
        else _LINUX_PROTECTED_BROWSER_RULES
    )
    rule = rules.get(name_key)
    if not rule:
        return False

    path_matches = any(fragment in normalized_path for fragment in rule["path_hints"])
    publisher_matches = bool(signature_valid is True) and any(
        token in publisher_lower for token in rule["publishers"]
    )
    return path_matches or publisher_matches


def _is_windows_system_path(exe_path: str) -> bool:
    """Return True for executables rooted under the active Windows directory."""
    if sys.platform != "win32":
        return False
    normalized = _canonical_path(exe_path)
    system_root = _canonical_path(os.environ.get("SystemRoot") or r"C:\Windows")
    if not normalized or not system_root:
        return False
    return (
        normalized == system_root
        or normalized.startswith(system_root + "\\")
        or normalized.startswith(system_root + "/")
    )


def _has_explicit_enforcement_override(decision_data: dict[str, Any]) -> bool:
    """Return True when the final decision was explicitly forced by a rule/operator."""
    enforcement_source = str(decision_data.get("enforcement_source") or "").strip().lower()
    override_type = str(decision_data.get("override_type") or "").strip().lower()
    return enforcement_source == "explicit_override" or bool(override_type)


def _decision_supports_destructive_enforcement(
    decision_data: dict[str, Any],
) -> tuple[bool, str]:
    """Return whether the final decision is complete enough for kill/quarantine actions."""
    if _has_explicit_enforcement_override(decision_data):
        return True, ""

    action = str(decision_data.get("action") or "").strip().lower()
    score = int(decision_data.get("score", 0) or 0)
    verdict = str(
        decision_data.get("verdict_code")
        or decision_data.get("verdict_label")
        or ""
    ).strip().lower()

    if action != "block":
        return False, " The final decision does not request blocking."
    if score <= 0:
        return False, " The final decision is missing a positive threat score."
    if verdict in {"", "unknown", "safe", "suspicious"}:
        return (
            False,
            " The final decision verdict is incomplete and cannot authorize destructive action.",
        )
    return True, ""


def _probe_windows_signature(path: str) -> tuple[bool | None, str]:
    """Best-effort Authenticode fallback when the scanner could not confirm signature trust."""
    if sys.platform != "win32":
        return None, ""

    literal_path = str(path).replace("'", "''")
    command = (
        "$s = Get-AuthenticodeSignature -LiteralPath '"
        + literal_path
        + "'; "
        "$subject = ''; "
        "if ($s.SignerCertificate) { $subject = $s.SignerCertificate.Subject }; "
        "Write-Output ($s.Status.ToString() + '|' + $subject)"
    )

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            creationflags=_CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return None, ""

    output = (result.stdout or "").strip()
    if "|" not in output:
        return None, ""

    status, subject = output.split("|", 1)
    status_text = status.strip().lower()
    publisher = subject.strip()

    if status_text == "valid":
        return True, publisher
    if status_text in {"notsigned", "unknownerror", "notsupportedfileformat"}:
        return None, publisher
    return False, publisher


def _probe_rtp_capability(platform_name: str | None = None) -> dict[str, str]:
    """Return the current RTP capability without starting the worker."""
    platform_name = platform_name or sys.platform

    if platform_name == "win32":
        missing: list[str] = []
        for module_name, label in (
            ("pythoncom", "pywin32"),
            ("wmi", "wmi"),
            ("psutil", "psutil"),
        ):
            try:
                __import__(module_name)
            except ImportError:
                missing.append(label)

        if missing:
            return {
                "state": "degraded",
                "detail": "Windows RTP requires: " + ", ".join(missing),
            }
        return {
            "state": "available",
            "detail": "Monitoring new process launches via WMI.",
        }

    if platform_name.startswith("linux"):
        try:
            __import__("psutil")
        except ImportError:
            return {
                "state": "degraded",
                "detail": "Linux RTP requires psutil for process polling.",
            }
        return {
            "state": "available",
            "detail": "Monitoring new process launches via process polling.",
        }

    return {
        "state": "unsupported",
        "detail": "Real-Time Protection is only implemented for Windows and Linux.",
    }


def _extract_windows_process_event(event: Any) -> tuple[int, str, str, int | None] | None:
    """Normalize a WMI process-creation event into process metadata."""
    process_obj = getattr(event, "TargetInstance", None)
    if process_obj is None:
        process_obj = event

    try:
        pid = int(getattr(process_obj, "ProcessId"))
        name = (getattr(process_obj, "Name") or "unknown").lower()
        exe_path = getattr(process_obj, "ExecutablePath") or ""
    except (AttributeError, TypeError, ValueError):
        return None

    parent_pid: int | None = None
    try:
        raw_parent_pid = getattr(process_obj, "ParentProcessId")
        if raw_parent_pid is not None:
            parent_pid = int(raw_parent_pid)
    except (AttributeError, TypeError, ValueError):
        parent_pid = None

    return pid, name, exe_path, parent_pid


# ───────────────────────────────────────────────────────────────────
# Real-Time Protection Worker (QThread)
# ───────────────────────────────────────────────────────────────────


class RealTimeProtectionWorker(QThread):
    """Background thread that monitors new process launches via WMI.

    Signals
    -------
    process_detected(str, str, str)
        Emitted for every new non-whitelisted process:
        (timestamp "HH:MM:SS", process_name, pid_as_string).
    threat_detected(str)
        JSON-serialisable string describing the threat event.
    process_scanned(str)
        Short status line for every scanned process (for live console).
    status_changed(str)
        Worker lifecycle events ("started", "stopped", "error: ...").
    stats_updated(int, int, int)
        (total_scanned, threats_found, threats_killed) — periodic stats.
    """

    process_detected = Signal(str, str, str)
    threat_detected = Signal(str)
    threat_recorded = Signal(dict)
    process_scanned = Signal(str)
    status_changed = Signal(str)
    stats_updated = Signal(int, int, int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._running = False
        self._scanner = None
        self._scanner_ready = False
        self._scanner_detail = "Scanner not initialized."
        self._monitoring_running = False
        self._monitoring_backend = ""

        # Statistics
        self._total_scanned = 0
        self._threats_found = 0
        self._threats_killed = 0

        # Cache of recently scanned paths (avoid re-scanning same exe)
        self._scan_cache: dict[str, dict[str, Any]] = {}
        self._cache_max = 5000

    # ─────────────────────────────────────────────────────────────
    # Public control
    # ─────────────────────────────────────────────────────────────

    def stop(self) -> None:
        """Request the worker to stop gracefully."""
        self._running = False

    def _cache_scan_decision(
        self,
        exe_path: str,
        decision: dict[str, Any],
        *,
        sha256: str = "",
        scan_context: dict[str, Any] | None = None,
    ) -> None:
        """Store the final normalized decision for a scanned executable."""
        if len(self._scan_cache) >= self._cache_max:
            keys = list(self._scan_cache.keys())
            for key in keys[: len(keys) // 2]:
                del self._scan_cache[key]
        context = dict(scan_context or {})
        fingerprint = context.get("fingerprint") or _file_fingerprint(exe_path)
        context["fingerprint"] = fingerprint
        self._scan_cache[exe_path.lower()] = {
            "decision": dict(decision),
            "sha256": sha256,
            "scan_context": context,
            "fingerprint": fingerprint,
        }

    def _get_cached_scan_entry(self, exe_path: str) -> dict[str, Any] | None:
        """Return a cache entry only when the on-disk binary still matches."""
        key = exe_path.lower()
        entry = self._scan_cache.get(key)
        if not entry:
            return None

        current_fingerprint = _file_fingerprint(exe_path)
        cached_fingerprint = entry.get("fingerprint")
        if not current_fingerprint or not cached_fingerprint:
            self._scan_cache.pop(key, None)
            return None

        if tuple(cached_fingerprint) != tuple(current_fingerprint):
            self._scan_cache.pop(key, None)
            return None

        return entry

    def _scan_process_decision(
        self,
        exe_path: str,
    ) -> tuple[dict[str, Any], str, dict[str, Any]]:
        """Run the shared scan decision path for an executable."""
        empty_context = {
            "signature_valid": None,
            "publisher": "",
            "strong_evidence": False,
            "fingerprint": _file_fingerprint(exe_path),
        }
        if not self._scanner:
            decision = build_final_decision(
                score=0,
                verdict="Unknown",
                policy="static",
                scan_failed=True,
                action_reason="Static scanner unavailable; process allowed.",
                enforcement_source="scanner_unavailable",
            )
            return decision.to_dict(), "", empty_context

        result = self._scanner.scan_file(exe_path)
        sha256 = getattr(result, "sha256", "") or ""
        decision = decision_from_scan_result(result).to_dict()

        signature = getattr(result, "signature", {})
        if not isinstance(signature, dict):
            signature = {}
        signature_valid = signature.get("valid")
        publisher = str(signature.get("subject", "") or "")

        if (
            sys.platform == "win32"
            and decision.get("action") == "block"
            and signature_valid is None
        ):
            probed_valid, probed_publisher = _probe_windows_signature(exe_path)
            if probed_valid is not None or probed_publisher:
                signature_valid = probed_valid
                if probed_publisher:
                    publisher = publisher or probed_publisher

        clamav = getattr(result, "clamav", {})
        if not isinstance(clamav, dict):
            clamav = {}

        scan_context = {
            "signature_valid": signature_valid,
            "publisher": publisher,
            "strong_evidence": bool(
                clamav.get("infected")
                or decision.get("enforcement_source") == "explicit_override"
                or decision.get("override_type")
            ),
            "fingerprint": _file_fingerprint(exe_path),
        }
        return decision, sha256, scan_context

    def _build_enforcement_plan(
        self,
        process_name: str,
        exe_path: str,
        decision: dict[str, Any] | None,
        *,
        scan_context: dict[str, Any] | None = None,
    ) -> EnforcementPlan:
        """Derive explicit process/file actions from one normalized decision."""
        decision_data = decision if isinstance(decision, dict) else {}
        context = dict(scan_context or {})

        decision_action = str(decision_data.get("action") or "allow")
        base_reason = str(
            decision_data.get("action_reason")
            or "No enforcement reason recorded."
        )
        signature_valid = context.get("signature_valid")
        if signature_valid not in {True, False, None}:
            signature_valid = None
        publisher = str(context.get("publisher") or "")
        strong_evidence = bool(context.get("strong_evidence"))
        fingerprint = context.get("fingerprint") or _file_fingerprint(exe_path)
        parent_pid = context.get("parent_pid")
        if parent_pid is not None:
            try:
                parent_pid = int(parent_pid)
            except (TypeError, ValueError):
                parent_pid = None
        psutil_mod = context.get("psutil_mod")
        trusted_internal_helper = _is_trusted_sentinel_internal_helper(
            process_name,
            exe_path,
            parent_pid=parent_pid,
            psutil_mod=psutil_mod,
        )
        trusted_install = _is_trusted_install_path(exe_path)
        explicit_override = _has_explicit_enforcement_override(decision_data)
        decision_complete, completeness_reason = _decision_supports_destructive_enforcement(
            decision_data
        )
        protected_browser = _is_protected_browser_install(
            process_name,
            exe_path,
            publisher,
            signature_valid,
        )
        protected_system_binary = bool(
            _is_windows_system_path(exe_path) and signature_valid is not False
        )
        protected_signed_install = bool(signature_valid is True and trusted_install)
        protected_install = bool(
            protected_browser or protected_system_binary or protected_signed_install
        )

        if decision_action != "block":
            return EnforcementPlan(
                decision_action=decision_action,
                process_action="allow",
                file_action="allow",
                reason=base_reason,
                trusted_install=trusted_install,
                protected_signed_install=protected_signed_install,
                trusted_internal_helper=trusted_internal_helper,
                strong_evidence=strong_evidence,
                publisher=publisher,
                signature_valid=signature_valid,
                fingerprint=fingerprint,
            )

        if trusted_internal_helper:
            return EnforcementPlan(
                decision_action=decision_action,
                process_action="log_only",
                file_action="allow",
                reason=(
                    base_reason
                    + " Enforcement downgraded to log_only because this executable"
                    " is a Sentinel-shipped internal helper launched by Sentinel"
                    " from the application tree."
                ),
                trusted_install=trusted_install,
                protected_signed_install=protected_signed_install,
                trusted_internal_helper=True,
                strong_evidence=strong_evidence,
                publisher=publisher,
                signature_valid=signature_valid,
                fingerprint=fingerprint,
            )

        if not decision_complete:
            return EnforcementPlan(
                decision_action=decision_action,
                process_action="log_only",
                file_action="allow",
                reason=(
                    base_reason
                    + completeness_reason
                    + " Enforcement downgraded to log_only until a complete final"
                    " decision is available."
                ),
                trusted_install=trusted_install,
                protected_signed_install=protected_signed_install,
                trusted_internal_helper=trusted_internal_helper,
                strong_evidence=strong_evidence,
                publisher=publisher,
                signature_valid=signature_valid,
                fingerprint=fingerprint,
            )

        if protected_install and not explicit_override:
            return EnforcementPlan(
                decision_action=decision_action,
                process_action="log_only",
                file_action="allow",
                reason=(
                    base_reason
                    + " Enforcement downgraded to log_only because this is a protected"
                    " signed/system or mainstream installed application."
                    " Sentinel requires an explicit override before taking"
                    " destructive action against this class of software."
                ),
                trusted_install=trusted_install,
                protected_signed_install=protected_signed_install,
                trusted_internal_helper=trusted_internal_helper,
                strong_evidence=strong_evidence,
                publisher=publisher,
                signature_valid=signature_valid,
                fingerprint=fingerprint,
            )

        if strong_evidence:
            file_action = "quarantine_file"
            reason = (
                base_reason
                + " Strong corroborating evidence authorizes process kill and file quarantine."
            )
        else:
            file_action = "allow"
            if protected_signed_install:
                reason = (
                    base_reason
                    + " File quarantine skipped because signed software in a trusted"
                    " install path requires stronger evidence than a score-only block."
                )
            else:
                reason = (
                    base_reason
                    + " File quarantine skipped because score-only evidence never"
                    " authorizes destructive file action."
                )

        return EnforcementPlan(
            decision_action=decision_action,
            process_action="kill_process",
            file_action=file_action,
            reason=reason,
            trusted_install=trusted_install,
            protected_signed_install=protected_signed_install,
            trusted_internal_helper=trusted_internal_helper,
            strong_evidence=strong_evidence,
            publisher=publisher,
            signature_valid=signature_valid,
            fingerprint=fingerprint,
        )

    def _execute_process_action(
        self,
        pid: int,
        name: str,
        exe_path: str,
        psutil_mod: Any,
        *,
        process_action: str,
        cached: bool = False,
    ) -> str:
        """Apply the process portion of an enforcement plan."""
        if process_action == "log_only":
            logger.warning(
                "RTP: Flagged %s (PID %d) but skipped kill due to safety guardrail",
                name,
                pid,
            )
            return "logged_only"
        if process_action != "kill_process":
            return "allowed"

        try:
            proc = psutil_mod.Process(pid)
            if proc.name().lower() != name:
                logger.warning(
                    "RTP: Process identity mismatch for PID %d: expected %s, got %s",
                    pid,
                    name,
                    proc.name().lower(),
                )
                return "identity_mismatch"

            path_verified = False
            if hasattr(proc, "exe"):
                try:
                    live_path = str(proc.exe() or "")
                    if live_path:
                        path_verified = True
                        if _canonical_path(live_path) != _canonical_path(exe_path):
                            logger.warning(
                                "RTP: Skipped kill for PID %d because executable path changed "
                                "(expected=%s, live=%s)",
                                pid,
                                exe_path,
                                live_path,
                            )
                            return "path_mismatch"
                except psutil_mod.AccessDenied:
                    if cached:
                        logger.warning(
                            "RTP: Skipped cached kill for PID %d because path verification was denied",
                            pid,
                        )
                        return "identity_unverified"
                except Exception as exc:
                    if cached:
                        logger.warning(
                            "RTP: Skipped cached kill for PID %d because path verification failed: %s",
                            pid,
                            exc,
                        )
                        return "identity_unverified"

            if cached and not path_verified:
                logger.warning(
                    "RTP: Skipped cached kill for PID %d because the executable path could not be verified",
                    pid,
                )
                return "identity_unverified"

            proc.kill()
            self._threats_killed += 1
            logger.warning("RTP: KILLED malicious process %s (PID %d)", name, pid)
            return "terminated"
        except psutil_mod.NoSuchProcess:
            logger.debug("RTP: Process %d already exited", pid)
            return "already_exited"
        except psutil_mod.AccessDenied:
            logger.warning(
                "RTP: Access denied killing %s (PID %d) — "
                "run as Administrator for full protection",
                name,
                pid,
            )
            return "access_denied"
        except Exception as exc:
            logger.error("RTP: Failed to kill %s (PID %d): %s", name, pid, exc)
            return "failed_to_terminate"

    def _execute_file_action(
        self,
        exe_path: str,
        *,
        file_action: str,
        plan: EnforcementPlan,
        decision_data: dict[str, Any],
        process_result: str,
        process_name: str,
        pid: int,
        sha256: str,
    ) -> str:
        """Apply the file portion of an enforcement plan."""
        if file_action == "allow":
            return "guardrail_allow" if plan.decision_action == "block" else "allowed"

        if process_result != "terminated":
            return "skipped_process_not_terminated"

        if file_action == "quarantine_file":
            try:
                from backend.engines.scanning.quarantine_manager import get_quarantine_vault

                vault = get_quarantine_vault()
                result = vault.quarantine_file(
                    exe_path,
                    metadata={
                        "enforcement_source": "rtp",
                        "source_detail": "process_scanner",
                        "decision_action": plan.decision_action,
                        "decision_enforcement_source": str(
                            decision_data.get("enforcement_source") or ""
                        ),
                        "override_type": str(decision_data.get("override_type") or ""),
                        "process_action": plan.process_action,
                        "file_action": plan.file_action,
                        "action_reason": plan.reason,
                        "decision_score": int(decision_data.get("score", 0) or 0),
                        "decision_verdict": str(
                            decision_data.get("verdict_label", "Unknown") or "Unknown"
                        ),
                        "allow_protected_quarantine": _has_explicit_enforcement_override(
                            decision_data
                        ),
                        "process_name": process_name,
                        "pid": pid,
                        "sha256": sha256,
                        "publisher": plan.publisher,
                        "signature_valid": plan.signature_valid,
                        "strong_evidence": plan.strong_evidence,
                        "matched_rules": list(decision_data.get("triggered_rules") or []),
                    },
                )
                if result.get("success"):
                    logger.info("RTP: Quarantined %s after strong-evidence block", exe_path)
                    return "quarantined"
                logger.warning(
                    "RTP: Quarantine failed for %s: %s",
                    exe_path,
                    result.get("message", "unknown error"),
                )
                return "quarantine_failed"
            except Exception as exc:
                logger.warning("RTP: Quarantine failed for %s: %s", exe_path, exc)
                return "quarantine_failed"

        if file_action == "delete_file":
            logger.warning("RTP: delete_file is not implemented and was skipped for %s", exe_path)
            return "delete_not_supported"

        return "allowed"

    # ─────────────────────────────────────────────────────────────
    # Thread entry point
    # ─────────────────────────────────────────────────────────────

    def run(self) -> None:  # noqa: D401
        """Process-creation watcher loop (runs in background thread).

        On Windows: uses WMI __InstanceCreationEvent.
        On Linux: uses psutil process polling.
        """

        import sys
        if sys.platform != "win32":
            self._run_linux()
            return

        self._monitoring_backend = "WMI process watcher"

        # ── COM initialisation (REQUIRED for WMI on background threads) ──
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception as exc:
            self.status_changed.emit(f"error: COM init failed — {exc}")
            logger.error("RTP: COM initialisation failed: %s", exc)
            return

        try:
            import wmi
            import psutil
        except ImportError as exc:
            self.status_changed.emit(
                f"error: Missing dependency — {exc}. "
                "Install with: pip install wmi psutil pywin32"
            )
            logger.error("RTP: Missing dependency: %s", exc)
            return

        # ── Initialise the static scanner ──
        try:
            from backend.engines.scanning.static_scanner import StaticScanner

            self._scanner = StaticScanner()
            self._scanner_ready = True
            self._scanner_detail = "Static scanner loaded."
        except Exception as exc:
            logger.warning("RTP: Could not load scanner: %s", exc)
            self._scanner = None
            self._scanner_ready = False
            self._scanner_detail = f"Static scanner unavailable: {exc}"

        # ── Set up WMI event watcher ──
        self._running = True
        self._monitoring_running = True
        self.status_changed.emit("started")
        logger.info("RTP: Real-Time Protection ENABLED")

        try:
            c = wmi.WMI()

            # Use a raw WQL event subscription with WITHIN clause.
            # Windows requires the WITHIN polling interval for
            # __InstanceCreationEvent (extrinsic event) — the
            # watch_for() shorthand omits it on many editions.
            wql = (
                "SELECT * FROM __InstanceCreationEvent "
                "WITHIN 1 "
                "WHERE TargetInstance ISA 'Win32_Process'"
            )
            watcher = c.watch_for(raw_wql=wql, wmi_class="__InstanceCreationEvent")

            while self._running:
                try:
                    # This blocks until a new process event arrives
                    # or the timeout expires
                    event = watcher(timeout_ms=int(WMI_POLL_INTERVAL * 1000))
                except wmi.x_wmi_timed_out:
                    # No new process in this interval — just loop
                    continue
                except Exception as wmi_exc:
                    if self._running:
                        logger.debug("RTP: WMI watcher error: %s", wmi_exc)
                    continue

                if not self._running:
                    break

                # ── Extract process info from TargetInstance ──
                process_info = _extract_windows_process_event(event)
                if process_info is None:
                    continue
                pid, name, exe_path, parent_pid = process_info


                # ── Skip whitelisted / system processes ──
                if name in WHITELISTED_PROCESSES:
                    continue

                if not exe_path or not Path(exe_path).exists():
                    continue

                # Timestamp used for all signals related to this process
                ts = datetime.now(timezone.utc).strftime("%H:%M:%S")

                if _is_trusted_sentinel_internal_helper(
                    name,
                    exe_path,
                    parent_pid=parent_pid,
                    psutil_mod=psutil,
                ):
                    logger.info(
                        "RTP: Allowed trusted Sentinel internal helper %s (PID %d)",
                        exe_path,
                        pid,
                    )
                    self.process_detected.emit(ts, name, str(pid))
                    continue

                # ── Check scan cache ──
                cache_entry = self._get_cached_scan_entry(exe_path)
                if cache_entry:
                    cached_decision = cache_entry.get("decision", {})
                    scan_context = dict(cache_entry.get("scan_context", {}) or {})
                    scan_context["parent_pid"] = parent_pid
                    scan_context["psutil_mod"] = psutil
                    plan = self._build_enforcement_plan(
                        name,
                        exe_path,
                        cached_decision,
                        scan_context=scan_context if isinstance(scan_context, dict) else None,
                    )
                    if plan.process_action != "allow":
                        self._apply_enforcement(
                            pid,
                            name,
                            exe_path,
                            psutil,
                            decision=cached_decision,
                            plan=plan,
                            sha256=str(cache_entry.get("sha256", "") or ""),
                            cached=True,
                        )
                    self.process_detected.emit(ts, name, str(pid))
                    continue

                # ── Scan the executable ──
                self._total_scanned += 1
                self.process_scanned.emit(
                    f"[{self._total_scanned}] Scanning: {name} (PID {pid})"
                )

                decision_data = build_final_decision(
                    score=0,
                    verdict="Unknown",
                    policy="static",
                    scan_failed=True,
                    action_reason="Process scan did not complete; process allowed.",
                ).to_dict()
                sha256 = ""
                scan_context: dict[str, Any] = {
                    "signature_valid": None,
                    "publisher": "",
                    "strong_evidence": False,
                    "fingerprint": _file_fingerprint(exe_path),
                    "parent_pid": parent_pid,
                    "psutil_mod": psutil,
                }

                try:
                    decision_data, sha256, scan_context = self._scan_process_decision(exe_path)
                    scan_context["parent_pid"] = parent_pid
                    scan_context["psutil_mod"] = psutil
                except Exception as scan_exc:
                    logger.debug("RTP: Scan error for %s: %s", name, scan_exc)
                    decision_data = build_final_decision(
                        score=0,
                        verdict="Unknown",
                        policy="static",
                        scan_failed=True,
                        action_reason=f"Scan error: {scan_exc}",
                    ).to_dict()

                # ── Update cache ──
                self._cache_scan_decision(
                    exe_path,
                    decision_data,
                    sha256=sha256,
                    scan_context=scan_context,
                )

                # ── Take action ──
                plan = self._build_enforcement_plan(
                    name,
                    exe_path,
                    decision_data,
                    scan_context=scan_context,
                )
                if plan.process_action != "allow":
                    self._apply_enforcement(
                        pid,
                        name,
                        exe_path,
                        psutil,
                        decision=decision_data,
                        plan=plan,
                        sha256=sha256,
                    )

                # ── Emit process detection AFTER scan verdict is known ──
                self.process_detected.emit(ts, name, str(pid))

                # ── Periodic stats ──
                if self._total_scanned % 10 == 0:
                    self.stats_updated.emit(
                        self._total_scanned,
                        self._threats_found,
                        self._threats_killed,
                    )

        except Exception as exc:
            if self._running:
                logger.exception("RTP: Fatal error in watcher loop")
                self.status_changed.emit(f"error: {exc}")
        finally:
            self._running = False
            self._monitoring_running = False
            self.status_changed.emit("stopped")
            logger.info(
                "RTP: Real-Time Protection DISABLED "
                "(scanned=%d, threats=%d, killed=%d)",
                self._total_scanned,
                self._threats_found,
                self._threats_killed,
            )
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────
    # Linux RTP — psutil process polling
    # ─────────────────────────────────────────────────────────────

    # System / kernel processes that must never be scanned or killed
    _LINUX_SKIP_PROCESSES = frozenset({
        "systemd", "kthreadd", "ksoftirqd", "kworker", "rcu_gp",
        "rcu_par_gp", "rcu_sched", "migration", "cpuhp",
        "init", "bash", "sh", "dash", "zsh", "fish",
        "sshd", "cron", "atd", "dbus-daemon", "rsyslogd",
        "journald", "systemd-journald", "systemd-logind",
        "systemd-udevd", "systemd-resolved", "systemd-timesyncd",
        "networkd", "systemd-networkd", "agetty", "login",
        "polkitd", "accounts-daemon", "udisksd",
        # Python itself (our own process)
        "python", "python3", "python3.10", "python3.11", "python3.12",
    })

    def _run_linux(self) -> None:
        """Linux RTP implementation using psutil process polling.

        Polls ``psutil.process_iter()`` every ~1 second, tracking
        which PIDs have already been seen.  New executables are
        scanned through the StaticScanner pipeline.
        """
        import psutil
        self._monitoring_backend = "process polling"

        # ── Initialise the static scanner ──
        try:
            from backend.engines.scanning.static_scanner import StaticScanner
            self._scanner = StaticScanner()
            self._scanner_ready = True
            self._scanner_detail = "Static scanner loaded."
        except Exception as exc:
            logger.warning("RTP-Linux: Could not load scanner: %s", exc)
            self._scanner = None
            self._scanner_ready = False
            self._scanner_detail = f"Static scanner unavailable: {exc}"

        self._running = True
        self._monitoring_running = True
        self.status_changed.emit("started")
        logger.info("RTP-Linux: Real-Time Protection ENABLED (psutil polling)")

        # Snapshot current PIDs so we only scan truly *new* processes
        seen_pids: set[int] = set()
        try:
            for proc in psutil.process_iter(["pid"]):
                seen_pids.add(proc.info["pid"])
        except Exception:
            pass

        try:
            while self._running:
                time.sleep(WMI_POLL_INTERVAL)
                if not self._running:
                    break

                try:
                    current_pids: set[int] = set()
                    for proc in psutil.process_iter(
                        ["pid", "name", "exe", "ppid", "status"]
                    ):
                        try:
                            info = proc.info
                            pid = info["pid"]
                            current_pids.add(pid)

                            if pid in seen_pids:
                                continue  # Already seen

                            name = (info.get("name") or "unknown").lower()
                            exe_path = info.get("exe") or ""
                            parent_pid = info.get("ppid")

                            # Skip kernel threads and system processes
                            if not exe_path:
                                seen_pids.add(pid)
                                continue

                            base_name = name.replace(".exe", "")
                            if base_name in self._LINUX_SKIP_PROCESSES:
                                seen_pids.add(pid)
                                continue

                            # Skip kernel threads (no executable)
                            if info.get("status") == psutil.STATUS_ZOMBIE:
                                seen_pids.add(pid)
                                continue

                            # Mark as seen
                            seen_pids.add(pid)

                            if not Path(exe_path).exists():
                                continue

                            ts = datetime.now(timezone.utc).strftime("%H:%M:%S")

                            if _is_trusted_sentinel_internal_helper(
                                name,
                                exe_path,
                                parent_pid=parent_pid,
                                psutil_mod=psutil,
                            ):
                                logger.info(
                                    "RTP-Linux: Allowed trusted Sentinel internal helper %s (PID %d)",
                                    exe_path,
                                    pid,
                                )
                                self.process_detected.emit(ts, name, str(pid))
                                continue

                            # ── Check scan cache ──
                            cache_entry = self._get_cached_scan_entry(exe_path)
                            if cache_entry:
                                cached_decision = cache_entry.get("decision", {})
                                scan_context = dict(cache_entry.get("scan_context", {}) or {})
                                scan_context["parent_pid"] = parent_pid
                                scan_context["psutil_mod"] = psutil
                                plan = self._build_enforcement_plan(
                                    name,
                                    exe_path,
                                    cached_decision,
                                    scan_context=scan_context if isinstance(scan_context, dict) else None,
                                )
                                if plan.process_action != "allow":
                                    self._apply_enforcement(
                                        pid,
                                        name,
                                        exe_path,
                                        psutil,
                                        decision=cached_decision,
                                        plan=plan,
                                        sha256=str(cache_entry.get("sha256", "") or ""),
                                        cached=True,
                                    )
                                self.process_detected.emit(ts, name, str(pid))
                                continue

                            # ── Scan the executable ──
                            self._total_scanned += 1
                            self.process_scanned.emit(
                                f"[{self._total_scanned}] Scanning: {name} (PID {pid})"
                            )

                            decision_data = build_final_decision(
                                score=0,
                                verdict="Unknown",
                                policy="static",
                                scan_failed=True,
                                action_reason="Process scan did not complete; process allowed.",
                            ).to_dict()
                            sha256 = ""
                            scan_context: dict[str, Any] = {
                                "signature_valid": None,
                                "publisher": "",
                                "strong_evidence": False,
                                "fingerprint": _file_fingerprint(exe_path),
                                "parent_pid": parent_pid,
                                "psutil_mod": psutil,
                            }

                            try:
                                decision_data, sha256, scan_context = self._scan_process_decision(exe_path)
                                scan_context["parent_pid"] = parent_pid
                                scan_context["psutil_mod"] = psutil
                            except Exception as scan_exc:
                                logger.debug(
                                    "RTP-Linux: Scan error for %s: %s",
                                    name, scan_exc,
                                )
                                decision_data = build_final_decision(
                                    score=0,
                                    verdict="Unknown",
                                    policy="static",
                                    scan_failed=True,
                                    action_reason=f"Scan error: {scan_exc}",
                                ).to_dict()

                            # ── Update cache ──
                            self._cache_scan_decision(
                                exe_path,
                                decision_data,
                                sha256=sha256,
                                scan_context=scan_context,
                            )

                            # ── Take action ──
                            plan = self._build_enforcement_plan(
                                name,
                                exe_path,
                                decision_data,
                                scan_context=scan_context,
                            )
                            if plan.process_action != "allow":
                                self._apply_enforcement(
                                    pid,
                                    name,
                                    exe_path,
                                    psutil,
                                    decision=decision_data,
                                    plan=plan,
                                    sha256=sha256,
                                )

                            self.process_detected.emit(ts, name, str(pid))

                            # ── Periodic stats ──
                            if self._total_scanned % 10 == 0:
                                self.stats_updated.emit(
                                    self._total_scanned,
                                    self._threats_found,
                                    self._threats_killed,
                                )

                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue

                    # Prune seen_pids of exited processes to prevent unbounded growth
                    seen_pids &= current_pids

                except Exception as poll_exc:
                    if self._running:
                        logger.debug("RTP-Linux: Polling error: %s", poll_exc)
                    time.sleep(1)

        except Exception as exc:
            if self._running:
                logger.exception("RTP-Linux: Fatal error in polling loop")
                self.status_changed.emit(f"error: {exc}")
        finally:
            self._running = False
            self._monitoring_running = False
            self.status_changed.emit("stopped")
            logger.info(
                "RTP-Linux: Real-Time Protection DISABLED "
                "(scanned=%d, threats=%d, killed=%d)",
                self._total_scanned,
                self._threats_found,
                self._threats_killed,
            )

    # ─────────────────────────────────────────────────────────────
    # Kill logic
    # ─────────────────────────────────────────────────────────────

    def _apply_enforcement(
        self,
        pid: int,
        name: str,
        exe_path: str,
        psutil_mod: Any,
        *,
        decision: dict[str, Any] | None = None,
        plan: EnforcementPlan | None = None,
        sha256: str = "",
        cached: bool = False,
    ) -> None:
        """Apply the final process/file enforcement plan for a scanned executable."""
        self._threats_found += 1
        decision_data = decision if isinstance(decision, dict) else {}
        enforcement_plan = (
            plan
            if isinstance(plan, EnforcementPlan)
            else self._build_enforcement_plan(name, exe_path, decision_data)
        )
        process_result = self._execute_process_action(
            pid,
            name,
            exe_path,
            psutil_mod,
            process_action=enforcement_plan.process_action,
            cached=cached,
        )
        file_result = self._execute_file_action(
            exe_path,
            file_action=enforcement_plan.file_action,
            plan=enforcement_plan,
            decision_data=decision_data,
            process_result=process_result,
            process_name=name,
            pid=pid,
            sha256=sha256,
        )

        occurred_at = datetime.now(timezone.utc)
        event = ThreatEvent(
            pid=pid,
            process_name=name,
            executable_path=exe_path,
            matched_rules=list(decision_data.get("triggered_rules") or []),
            threat_score=int(decision_data.get("score", 0) or 0),
            decision_verdict=str(decision_data.get("verdict_label", "Unknown") or "Unknown"),
            decision_action=enforcement_plan.decision_action,
            process_action=enforcement_plan.process_action,
            file_action=enforcement_plan.file_action,
            action_reason=enforcement_plan.reason,
            action_taken=process_result,
            file_action_taken=file_result,
            timestamp=occurred_at.strftime("%H:%M:%S"),
            occurred_at=occurred_at.isoformat(timespec="seconds"),
            sha256=sha256,
            publisher=enforcement_plan.publisher,
            signature_valid=enforcement_plan.signature_valid,
        )

        display_message = event.to_display_string()
        event_payload = event.to_dict()
        event_payload["display_message"] = display_message
        self.threat_recorded.emit(event_payload)
        self.threat_detected.emit(display_message)


# ───────────────────────────────────────────────────────────────────
# Real-Time Protection Bridge (QObject — exposed to QML)
# ───────────────────────────────────────────────────────────────────


class RealTimeProtectionBridge(QObject):
    """PySide6 bridge that exposes RTP controls and live events to QML.

    Signals
    -------
    protectionStatusChanged(bool)
        Emitted when RTP is enabled or disabled.
    threatDetected(str)
        Forwarded from the worker — human-readable threat event.
    processScanned(str)
        Forwarded from the worker — short scan status line.
    statusMessage(str)
        Lifecycle status ("started", "stopped", "error: ...").
    statsUpdated(int, int, int)
        (total_scanned, threats_found, threats_killed).
    """

    protectionStatusChanged = Signal(bool)
    threatDetected = Signal(str)
    processScanned = Signal(str)
    statusMessage = Signal(str)
    statsUpdated = Signal(int, int, int)
    new_event_log = Signal(str)  # Pre-formatted log line for QML console
    capabilityChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._worker: RealTimeProtectionWorker | None = None
        self._enabled = False
        self._lock = threading.Lock()
        self._threat_log: list[str] = []
        self._process_outcomes: dict[str, str] = {}
        self._capability = _probe_rtp_capability()
        self._last_status_message = self._capability["detail"]

    # ── Properties ──

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def threat_log(self) -> list[str]:
        return list(self._threat_log)

    # ── Public Slots ──

    @Slot()
    def enable(self) -> None:
        """Start real-time protection."""
        if self._capability["state"] != "available":
            self._last_status_message = self._capability["detail"]
            self.statusMessage.emit(self._last_status_message)
            return

        with self._lock:
            if self._enabled:
                return
            self._enabled = True

        self._worker = RealTimeProtectionWorker(parent=self)
        self._worker.threat_detected.connect(self._on_threat)
        self._worker.threat_recorded.connect(self._on_threat_recorded)
        self._worker.process_scanned.connect(self.processScanned)
        self._worker.process_detected.connect(self._on_process_detected)
        self._worker.status_changed.connect(self._on_status)
        self._worker.stats_updated.connect(self.statsUpdated)
        self._worker.start()

        self.protectionStatusChanged.emit(True)
        self._persist_rtp_state(True)
        logger.info("RTP Bridge: Protection ENABLED")

    @Slot()
    def disable(self) -> None:
        """Stop real-time protection."""
        self._stop_runtime(persist_preference=True)

    @Slot()
    def shutdownRuntime(self) -> None:
        """Stop RTP for application shutdown without changing user preference."""
        self._stop_runtime(persist_preference=False)

    def _stop_runtime(self, *, persist_preference: bool) -> None:
        """Stop the runtime worker and optionally persist the user's intent."""
        with self._lock:
            if not self._enabled:
                return
            self._enabled = False

        if self._worker:
            self._worker.stop()
            self._worker.wait(5000)  # Wait up to 5 seconds
            self._worker.deleteLater()
            self._worker = None

        self.protectionStatusChanged.emit(False)
        if persist_preference:
            self._persist_rtp_state(False)
            logger.info("RTP Bridge: Protection DISABLED")
        else:
            logger.info("RTP Bridge: Protection stopped for shutdown")

    @Slot()
    def toggle(self) -> None:
        """Toggle real-time protection on/off."""
        if self._enabled:
            self.disable()
        else:
            self.enable()

    @Slot(result=bool)
    def getStatus(self) -> bool:
        """Return whether RTP is currently enabled."""
        return self._enabled

    @Slot(result=str)
    def getCapabilityState(self) -> str:
        """Return capability state: available, degraded, or unsupported."""
        return self._capability["state"]

    @Slot(result=str)
    def getCapabilityDetail(self) -> str:
        """Return the current capability/detail message."""
        return self._capability["detail"]

    @Slot(result=str)
    def getLastStatusMessage(self) -> str:
        """Return the latest worker or capability status message."""
        return self._last_status_message

    @staticmethod
    def _get_settings():
        from PySide6.QtCore import QSettings

        return QSettings("SentinelSecurity", "SentinelApp")

    @classmethod
    def _load_persisted_preference(cls) -> tuple[bool, bool]:
        """Return (has_saved_preference, configured_enabled)."""
        qs = cls._get_settings()
        if qs.contains("rtpEnabled"):
            return True, qs.value("rtpEnabled", False, type=bool)
        return False, True

    @Slot(result=bool)
    def getConfiguredEnabled(self) -> bool:
        """Return whether RTP is enabled in persisted settings."""
        _has_saved, enabled = self._load_persisted_preference()
        return enabled

    @Slot(result=bool)
    def shouldStartOnLaunch(self) -> bool:
        """Return whether RTP should be started on this launch."""
        return self.getConfiguredEnabled()

    @Slot(result=str)
    def getMonitoringState(self) -> str:
        """Return the runtime monitoring state."""
        if self._capability["state"] == "unsupported":
            return "unsupported"
        if self._capability["state"] == "degraded" and not self._enabled:
            return "blocked"
        if self._enabled and self._worker and self._worker._monitoring_running:
            return "running"
        if self._enabled and self._worker:
            return "starting"
        return "disabled"

    @Slot(result=str)
    def getProcessScannerState(self) -> str:
        """Return the process-scanner runtime state."""
        if self._capability["state"] == "unsupported":
            return "unsupported"
        if self._capability["state"] == "degraded" and not self._enabled:
            return "blocked"
        if not self._enabled:
            return "disabled"
        if not self._worker:
            return "starting"
        if self._worker._scanner_ready:
            return "running"
        if self._worker._monitoring_running:
            return "degraded"
        return "starting"

    @Slot(result=str)
    def getRuntimeDetail(self) -> str:
        """Return a truthful RTP runtime summary for the System Monitor page."""
        if self._capability["state"] == "unsupported":
            return self._capability["detail"]

        if self._capability["state"] == "degraded" and not self._enabled:
            return self._capability["detail"]

        configured = "on" if self.getConfiguredEnabled() else "off"
        monitoring_state = self.getMonitoringState()
        scanner_state = self.getProcessScannerState()

        if monitoring_state == "running" and self._worker:
            backend = self._worker._monitoring_backend or "process monitoring"
            if scanner_state == "running":
                return (
                    f"Configured {configured}. Monitoring running via {backend}. "
                    "Process scanner active."
                )
            return (
                f"Configured {configured}. Monitoring running via {backend}. "
                f"Process scanner degraded. {self._worker._scanner_detail}"
            )

        if monitoring_state == "starting":
            return f"Configured {configured}. Starting process monitor."

        if monitoring_state == "blocked":
            return self._capability["detail"]

        if not self.getConfiguredEnabled():
            return "Disabled in settings."

        return self._last_status_message or self._capability["detail"]

    @Slot(result=str)
    def getThreatLog(self) -> str:
        """Return the full threat log as a newline-separated string."""
        return "\n\n".join(self._threat_log) if self._threat_log else ""

    @Slot()
    def clearThreatLog(self) -> None:
        """Clear the threat log."""
        self._threat_log.clear()

    # ── Private Slots ──

    @staticmethod
    def _persist_rtp_state(enabled: bool) -> None:
        """Save the RTP enabled state to QSettings for next launch."""
        qs = RealTimeProtectionBridge._get_settings()
        qs.setValue("rtpEnabled", enabled)
        qs.sync()

    def _on_threat(self, message: str) -> None:
        """Handle a threat event from the worker."""
        self._threat_log.append(message)
        self.threatDetected.emit(message)
        pid_match = re.search(r"\(PID (\d+)\)", message)
        if not pid_match:
            return

        pid = pid_match.group(1)
        if "Process Action: LOG_ONLY" in message:
            self._process_outcomes[pid] = "flagged"
        elif "Process Action: KILL_PROCESS" in message:
            self._process_outcomes[pid] = "blocked"

    def _on_threat_recorded(self, event: dict[str, Any]) -> None:
        """Persist structured incidents for the unified History page."""
        try:
            from backend.engines.history.incident_repo import IncidentHistoryRepo

            IncidentHistoryRepo().append(event, raw_message="")
        except Exception as exc:
            logger.warning("RTP Bridge: could not persist incident history: %s", exc)

    def _on_process_detected(self, timestamp: str, name: str, pid: str) -> None:
        """Format and emit a log line for every detected process."""
        outcome = self._process_outcomes.pop(pid, "")
        if outcome == "blocked":
            log_line = f"[{timestamp}] RTP: Blocked {name} (PID: {pid})"
        elif outcome == "flagged":
            log_line = f"[{timestamp}] RTP: Flagged {name} (PID: {pid})"
        else:
            log_line = f"[{timestamp}] RTP: Allowed {name} (PID: {pid})"
        self.new_event_log.emit(log_line)

    def _on_status(self, status: str) -> None:
        """Handle worker lifecycle status changes."""
        self._last_status_message = status
        self.statusMessage.emit(status)
        if status == "started":
            self._capability = _probe_rtp_capability()
            self.capabilityChanged.emit()
        if status.startswith("error:"):
            logger.error("RTP Bridge: Worker error — %s", status)
            with self._lock:
                self._enabled = False
            self._capability = {
                "state": "degraded",
                "detail": status[6:].strip() or "Real-Time Protection failed to start.",
            }
            self.capabilityChanged.emit()
            self.protectionStatusChanged.emit(False)


# ───────────────────────────────────────────────────────────────────
# Module-level convenience
# ───────────────────────────────────────────────────────────────────

_bridge: RealTimeProtectionBridge | None = None
_bridge_lock = threading.Lock()


def get_rtp_bridge() -> RealTimeProtectionBridge:
    """Return the singleton ``RealTimeProtectionBridge`` instance."""
    global _bridge
    with _bridge_lock:
        if _bridge is None:
            _bridge = RealTimeProtectionBridge()
        return _bridge
