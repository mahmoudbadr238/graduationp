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
        """Process-creation watcher loop (runs in background thread).

        On Windows: uses WMI __InstanceCreationEvent.
        On Linux: uses psutil process polling.
        """

        import sys
        if sys.platform != "win32":
            self._run_linux()
            return

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

                # Timestamp used for all signals related to this process
                ts = datetime.now(timezone.utc).strftime("%H:%M:%S")

                # ── Check scan cache ──
                if exe_path.lower() in self._scan_cache:
                    was_malicious = self._scan_cache[exe_path.lower()]
                    if was_malicious:
                        self._kill_process(pid, name, exe_path, psutil,
                                           cached=True)
                        self.process_detected.emit(ts, name, str(pid))
                    else:
                        self.process_detected.emit(ts, name, str(pid))
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
                        threat_score = int(result.score or 0)
                        is_malicious = threat_score >= KILL_THRESHOLD
                        sha256 = result.sha256 or ""

                        groq = result.groq_analysis or {}
                        if groq.get("verdict"):
                            matched_rules = [f"Groq:{groq.get('verdict')}"]

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

        # ── Initialise the static scanner ──
        try:
            from backend.engines.scanning.static_scanner import StaticScanner
            self._scanner = StaticScanner()
        except Exception as exc:
            logger.warning("RTP-Linux: Could not load scanner: %s", exc)
            self._scanner = None

        self._running = True
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
                        ["pid", "name", "exe", "status"]
                    ):
                        try:
                            info = proc.info
                            pid = info["pid"]
                            current_pids.add(pid)

                            if pid in seen_pids:
                                continue  # Already seen

                            name = (info.get("name") or "unknown").lower()
                            exe_path = info.get("exe") or ""

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

                            # ── Check scan cache ──
                            cache_key = exe_path.lower()
                            if cache_key in self._scan_cache:
                                was_malicious = self._scan_cache[cache_key]
                                if was_malicious:
                                    self._kill_process(
                                        pid, name, exe_path, psutil, cached=True
                                    )
                                self.process_detected.emit(ts, name, str(pid))
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
                                    threat_score = int(result.score or 0)
                                    is_malicious = threat_score >= KILL_THRESHOLD
                                    sha256 = result.sha256 or ""

                                    groq = result.groq_analysis or {}
                                    if groq.get("verdict"):
                                        matched_rules = [
                                            f"Groq:{groq.get('verdict')}"
                                        ]

                                    if threat_score < KILL_THRESHOLD:
                                        is_malicious = False

                                except Exception as scan_exc:
                                    logger.debug(
                                        "RTP-Linux: Scan error for %s: %s",
                                        name, scan_exc,
                                    )

                            # ── Update cache ──
                            if len(self._scan_cache) >= self._cache_max:
                                keys = list(self._scan_cache.keys())
                                for k in keys[: len(keys) // 2]:
                                    del self._scan_cache[k]
                            self._scan_cache[cache_key] = is_malicious

                            # ── Take action ──
                            if is_malicious:
                                self._kill_process(
                                    pid, name, exe_path, psutil,
                                    matched_rules=matched_rules,
                                    threat_score=threat_score,
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
                from backend.engines.scanning.quarantine_manager import get_quarantine_vault
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
    new_event_log = Signal(str)  # Pre-formatted log line for QML console

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._worker: RealTimeProtectionWorker | None = None
        self._enabled = False
        self._lock = threading.Lock()
        self._threat_log: list[str] = []
        self._blocked_pids: set[str] = set()  # PIDs recently blocked, for log formatting

        # Secure-by-default: always auto-start RTP on boot.
        # Defer the actual enable() to the event loop so the QThread
        # starts after Qt is fully initialised.
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self.enable)

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
        self._persist_rtp_state(False)
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

    @staticmethod
    def _persist_rtp_state(enabled: bool) -> None:
        """Save the RTP enabled state to QSettings for next launch."""
        from PySide6.QtCore import QSettings
        qs = QSettings("SentinelSecurity", "SentinelApp")
        qs.setValue("rtpEnabled", enabled)

    def _on_threat(self, message: str) -> None:
        """Handle a threat event from the worker."""
        self._threat_log.append(message)
        self.threatDetected.emit(message)
        # Track the PID so _on_process_detected knows it was blocked
        # (extract PID from output like "PID 1234")
        try:
            # ThreatEvent.to_display_string contains "PID <num>"
            for part in message.split():
                if part.rstrip(")").isdigit() and "PID" in message:
                    self._blocked_pids.add(part.rstrip(")"))
                    break
        except Exception:
            pass

    def _on_process_detected(self, timestamp: str, name: str, pid: str) -> None:
        """Format and emit a log line for every detected process."""
        if pid in self._blocked_pids:
            self._blocked_pids.discard(pid)
            log_line = f"[{timestamp}] RTP: Blocked {name} (PID: {pid})"
        else:
            log_line = f"[{timestamp}] RTP: Allowed {name} (PID: {pid})"
        self.new_event_log.emit(log_line)

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
