"""
Real-Time Protection (RTP) Engine — Sentinel EDR.

Monitors the Windows OS for new process launches via WMI, runs each
executable through the YARA-based MalwareScanner pipeline, and
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
    │  MalwareScanner.scan_file()  │  ← YARA rules
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
* ``app.scanning.scanner_engine`` — YARA-based file scanning
"""

from __future__ import annotations

import logging
import os
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

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
    action_taken: str = ""        # "terminated", "failed_to_terminate", "allowed"
    timestamp: str = ""
    sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "process_name": self.process_name,
            "executable_path": self.executable_path,
            "matched_rules": self.matched_rules,
            "threat_score": self.threat_score,
            "action_taken": self.action_taken,
            "timestamp": self.timestamp,
            "sha256": self.sha256,
        }

    def to_display_string(self) -> str:
        icon = "🛡️" if self.action_taken == "terminated" else "⚠️"
        return (
            f"{icon} [{self.timestamp}] THREAT NEUTRALIZED\n"
            f"   Process : {self.process_name} (PID {self.pid})\n"
            f"   Path    : {self.executable_path}\n"
            f"   Rules   : {', '.join(self.matched_rules) or 'N/A'}\n"
            f"   Score   : {self.threat_score}/100\n"
            f"   Action  : {self.action_taken.upper()}"
        )


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

# Minimum threat score to trigger auto-kill
KILL_THRESHOLD = 15


# ───────────────────────────────────────────────────────────────────
# Real-Time Protection Worker (QThread)
# ───────────────────────────────────────────────────────────────────


class RealTimeProtectionWorker(QThread):
    """Background thread that monitors new process launches via WMI.

    Signals
    -------
    threat_detected(str)
        JSON-serialisable string describing the threat event.
    process_scanned(str)
        Short status line for every scanned process (for live console).
    status_changed(str)
        Worker lifecycle events ("started", "stopped", "error: ...").
    stats_updated(int, int, int)
        (total_scanned, threats_found, threats_killed) — periodic stats.
    """

    threat_detected = Signal(str)
    process_scanned = Signal(str)
    status_changed = Signal(str)
    stats_updated = Signal(int, int, int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._running = False
        self._scanner = None

        # Statistics
        self._total_scanned = 0
        self._threats_found = 0
        self._threats_killed = 0

        # Cache of recently scanned paths (avoid re-scanning same exe)
        self._scan_cache: dict[str, bool] = {}
        self._cache_max = 5000

    # ─────────────────────────────────────────────────────────────
    # Public control
    # ─────────────────────────────────────────────────────────────

    def stop(self) -> None:
        """Request the worker to stop gracefully."""
        self._running = False

    # ─────────────────────────────────────────────────────────────
    # Thread entry point
    # ─────────────────────────────────────────────────────────────

    def run(self) -> None:  # noqa: D401
        """WMI process-creation watcher loop (runs in background thread)."""

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

        # ── Initialise the malware scanner ──
        try:
            from ..scanning.scanner_engine import get_malware_scanner
            self._scanner = get_malware_scanner()
            if not self._scanner.is_available:
                logger.warning(
                    "RTP: MalwareScanner not fully available — "
                    "using fallback pattern matching"
                )
        except Exception as exc:
            logger.warning("RTP: Could not load scanner: %s", exc)
            self._scanner = None

        # ── Set up WMI event watcher ──
        self._running = True
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
                try:
                    new_process = event.TargetInstance
                    pid = int(new_process.ProcessId)
                    name = (new_process.Name or "unknown").lower()
                    exe_path = new_process.ExecutablePath or ""
                except Exception:
                    continue


                # ── Skip whitelisted / system processes ──
                if name in WHITELISTED_PROCESSES:
                    continue

                if not exe_path or not Path(exe_path).exists():
                    continue

                # ── Check scan cache ──
                if exe_path.lower() in self._scan_cache:
                    was_malicious = self._scan_cache[exe_path.lower()]
                    if was_malicious:
                        self._kill_process(pid, name, exe_path, psutil,
                                           cached=True)
                    continue

                # ── Scan the executable ──
                self._total_scanned += 1
                self.process_scanned.emit(
                    f"[{self._total_scanned}] Scanning: {name} (PID {pid})"
                )

                is_malicious = False
                matched_rules: list[str] = []
                threat_score = 0
                sha256 = ""

                if self._scanner:
                    try:
                        result = self._scanner.scan_file(exe_path)
                        is_malicious = result.get("is_malicious", False)
                        threat_score = result.get("score", 0)
                        sha256 = result.get("file_info", {}).get("sha256", "")
                        matched_rules = [
                            r.get("rule_name", "unknown")
                            for r in result.get("matched_rules", [])
                        ]

                        # Apply kill threshold
                        if threat_score < KILL_THRESHOLD:
                            is_malicious = False

                    except Exception as scan_exc:
                        logger.debug(
                            "RTP: Scan error for %s: %s", name, scan_exc
                        )

                # ── Update cache ──
                if len(self._scan_cache) >= self._cache_max:
                    # Evict oldest half
                    keys = list(self._scan_cache.keys())
                    for k in keys[: len(keys) // 2]:
                        del self._scan_cache[k]
                self._scan_cache[exe_path.lower()] = is_malicious

                # ── Take action ──
                if is_malicious:
                    self._kill_process(
                        pid, name, exe_path, psutil,
                        matched_rules=matched_rules,
                        threat_score=threat_score,
                        sha256=sha256,
                    )

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
    # Kill logic
    # ─────────────────────────────────────────────────────────────

    def _kill_process(
        self,
        pid: int,
        name: str,
        exe_path: str,
        psutil_mod: Any,
        *,
        matched_rules: list[str] | None = None,
        threat_score: int = 0,
        sha256: str = "",
        cached: bool = False,
    ) -> None:
        """Attempt to terminate a malicious process."""
        self._threats_found += 1
        action = "failed_to_terminate"

        try:
            proc = psutil_mod.Process(pid)
            # Double-check the process is still what we think it is
            if proc.name().lower() == name or cached:
                proc.kill()
                action = "terminated"
                self._threats_killed += 1
                logger.warning(
                    "RTP: KILLED malicious process %s (PID %d)", name, pid
                )
        except psutil_mod.NoSuchProcess:
            action = "already_exited"
            logger.debug("RTP: Process %d already exited", pid)
        except psutil_mod.AccessDenied:
            action = "access_denied"
            logger.warning(
                "RTP: Access denied killing %s (PID %d) — "
                "run as Administrator for full protection",
                name, pid,
            )
        except Exception as exc:
            logger.error("RTP: Failed to kill %s (PID %d): %s", name, pid, exc)

        event = ThreatEvent(
            pid=pid,
            process_name=name,
            executable_path=exe_path,
            matched_rules=matched_rules or [],
            threat_score=threat_score,
            action_taken=action,
            timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
            sha256=sha256,
        )

        self.threat_detected.emit(event.to_display_string())

        # Auto-quarantine the executable (best-effort)
        if action == "terminated":
            try:
                from ..scanning.quarantine_manager import get_quarantine_vault
                vault = get_quarantine_vault()
                vault.quarantine_file(exe_path)
                logger.info("RTP: Auto-quarantined %s", exe_path)
            except Exception as q_exc:
                logger.debug("RTP: Auto-quarantine failed: %s", q_exc)


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

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._worker: RealTimeProtectionWorker | None = None
        self._enabled = False
        self._lock = threading.Lock()
        self._threat_log: list[str] = []

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
        with self._lock:
            if self._enabled:
                return
            self._enabled = True

        self._worker = RealTimeProtectionWorker(parent=self)
        self._worker.threat_detected.connect(self._on_threat)
        self._worker.process_scanned.connect(self.processScanned)
        self._worker.status_changed.connect(self._on_status)
        self._worker.stats_updated.connect(self.statsUpdated)
        self._worker.start()

        self.protectionStatusChanged.emit(True)
        logger.info("RTP Bridge: Protection ENABLED")

    @Slot()
    def disable(self) -> None:
        """Stop real-time protection."""
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
        logger.info("RTP Bridge: Protection DISABLED")

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
    def getThreatLog(self) -> str:
        """Return the full threat log as a newline-separated string."""
        return "\n\n".join(self._threat_log) if self._threat_log else ""

    @Slot()
    def clearThreatLog(self) -> None:
        """Clear the threat log."""
        self._threat_log.clear()

    # ── Private Slots ──

    def _on_threat(self, message: str) -> None:
        """Handle a threat event from the worker."""
        self._threat_log.append(message)
        self.threatDetected.emit(message)

    def _on_status(self, status: str) -> None:
        """Handle worker lifecycle status changes."""
        self.statusMessage.emit(status)
        if status.startswith("error:"):
            logger.error("RTP Bridge: Worker error — %s", status)
            with self._lock:
                self._enabled = False
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
