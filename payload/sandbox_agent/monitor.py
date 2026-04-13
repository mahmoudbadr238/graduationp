"""Behavioral Monitor — captures process/file/registry/network changes.

Extracted from *agent_payload.py*.  Runs background threads that diff
system state against a baseline captured before payload detonation.

Compatible with the host-side ``C:\\Sandbox\\report.json`` pipeline.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("sentinel_agent")

IS_WINDOWS = os.name == "nt"

# Optional dependencies
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    log.warning("psutil not available — behavioral monitoring disabled")

HAS_WMI = False
if IS_WINDOWS:
    try:
        import wmi as _wmi  # type: ignore[import-untyped]
        HAS_WMI = True
    except ImportError:
        log.warning("wmi not available — registry monitoring disabled")


REPORT_PATH = Path(r"C:\Sandbox\report.json")


class BehavioralMonitor:
    """Thread-safe system state change monitor.

    Usage::

        mon = BehavioralMonitor()
        mon.capture_baseline()
        mon.start_monitoring()
        # ... run the sample ...
        mon.stop_monitoring()
        report = mon.get_report()
    """

    WATCH_DIRS: list[str] = (
        [
            os.environ.get("TEMP", r"C:\Temp"),
            os.environ.get("USERPROFILE", r"C:\Users"),
            r"C:\Windows\System32",
            r"C:\Windows\SysWOW64",
            r"C:\ProgramData",
        ]
        if IS_WINDOWS
        else ["/tmp", os.path.expanduser("~"), "/var"]
    )

    def __init__(self) -> None:
        self.monitoring = False
        self.start_time: datetime | None = None
        self._lock = threading.Lock()

        self._baseline_pids: set[int] = set()
        self._baseline_files: dict[str, float] = {}
        self._baseline_conns: set[tuple] = set()

        self.processes: list[dict[str, Any]] = []
        self.files_created: list[str] = []
        self.files_modified: list[str] = []
        self.files_deleted: list[str] = []
        self.registry_modified: list[str] = []
        self.network_connections: list[dict[str, Any]] = []

    # ── Baseline ──────────────────────────────────────────────────────────

    def capture_baseline(self) -> None:
        if not HAS_PSUTIL:
            return
        log.info("Capturing behavioral baseline…")
        for p in psutil.process_iter(["pid"]):
            try:
                self._baseline_pids.add(p.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        for d in self.WATCH_DIRS:
            self._scan_dir(d, self._baseline_files, depth=2)
        for c in psutil.net_connections(kind="inet"):
            try:
                self._baseline_conns.add(self._conn_key(c))
            except Exception:
                pass
        log.info(
            "Baseline: %d procs, %d files, %d conns",
            len(self._baseline_pids),
            len(self._baseline_files),
            len(self._baseline_conns),
        )

    # ── Start / Stop ──────────────────────────────────────────────────────

    def start_monitoring(self) -> None:
        if not HAS_PSUTIL:
            return
        self.monitoring = True
        self.start_time = datetime.now()
        for target in (self._watch_procs, self._watch_files, self._watch_net):
            threading.Thread(target=target, daemon=True).start()
        if IS_WINDOWS and HAS_WMI:
            threading.Thread(target=self._watch_registry, daemon=True).start()
        log.info("Behavioral monitoring started")

    def stop_monitoring(self) -> None:
        self.monitoring = False
        time.sleep(1)
        log.info("Behavioral monitoring stopped")

    # ── Report ────────────────────────────────────────────────────────────

    def get_report(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": "completed",
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": datetime.now().isoformat(),
                "processes": list(self.processes),
                "files_created": list(self.files_created),
                "files_modified": list(self.files_modified),
                "files_deleted": list(self.files_deleted),
                "registry_modified": list(self.registry_modified),
                "network_connections": list(self.network_connections),
                "summary": {
                    "new_processes": len(self.processes),
                    "files_created": len(self.files_created),
                    "files_modified": len(self.files_modified),
                    "files_deleted": len(self.files_deleted),
                    "registry_changes": len(self.registry_modified),
                    "network_connections": len(self.network_connections),
                },
            }

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _conn_key(c: Any) -> tuple:
        return (
            c.laddr.ip if c.laddr else None,
            c.laddr.port if c.laddr else None,
            c.raddr.ip if c.raddr else None,
            c.raddr.port if c.raddr else None,
            c.status,
        )

    @staticmethod
    def _scan_dir(path: str, out: dict[str, float], depth: int = 2) -> None:
        if depth <= 0:
            return
        try:
            for entry in os.scandir(path):
                try:
                    if entry.is_file(follow_symlinks=False):
                        out[entry.path] = entry.stat().st_mtime
                    elif entry.is_dir(follow_symlinks=False):
                        BehavioralMonitor._scan_dir(entry.path, out, depth - 1)
                except (PermissionError, OSError):
                    pass
        except (PermissionError, OSError):
            pass

    # ── Polling threads ───────────────────────────────────────────────────

    def _watch_procs(self) -> None:
        while self.monitoring:
            try:
                for p in psutil.process_iter(["pid", "name", "cmdline", "ppid", "exe"]):
                    if p.pid in self._baseline_pids:
                        continue
                    try:
                        info = p.info
                        with self._lock:
                            if not any(e["pid"] == p.pid for e in self.processes):
                                self.processes.append({
                                    "pid": p.pid,
                                    "name": info["name"],
                                    "cmdline": " ".join(info["cmdline"] or []),
                                    "parent_pid": info["ppid"],
                                    "exe": info["exe"],
                                    "time": datetime.now().isoformat(),
                                })
                                log.info("[+] New process: %s (PID %d)", info["name"], p.pid)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except Exception as exc:
                log.debug("Process monitor error: %s", exc)
            time.sleep(0.5)

    def _watch_files(self) -> None:
        while self.monitoring:
            try:
                current: dict[str, float] = {}
                for d in self.WATCH_DIRS:
                    self._scan_dir(d, current, depth=2)
                with self._lock:
                    for path, mtime in current.items():
                        if path not in self._baseline_files:
                            if path not in self.files_created:
                                self.files_created.append(path)
                                log.info("[+] File created: %s", path)
                        elif mtime > self._baseline_files[path]:
                            if path not in self.files_modified:
                                self.files_modified.append(path)
                                log.info("[+] File modified: %s", path)
                    for path in self._baseline_files:
                        if path not in current and path not in self.files_deleted:
                            self.files_deleted.append(path)
                            log.info("[+] File deleted: %s", path)
            except Exception as exc:
                log.debug("File monitor error: %s", exc)
            time.sleep(2)

    def _watch_net(self) -> None:
        while self.monitoring:
            try:
                for c in psutil.net_connections(kind="inet"):
                    try:
                        key = self._conn_key(c)
                        if key in self._baseline_conns:
                            continue
                        cd = {
                            "local_addr": f"{key[0]}:{key[1]}" if key[0] else None,
                            "remote_addr": f"{key[2]}:{key[3]}" if key[2] else None,
                            "status": key[4],
                            "time": datetime.now().isoformat(),
                        }
                        with self._lock:
                            if not any(
                                e["local_addr"] == cd["local_addr"]
                                and e["remote_addr"] == cd["remote_addr"]
                                for e in self.network_connections
                            ):
                                self.network_connections.append(cd)
                                log.info("[+] Network: %s → %s", cd["local_addr"], cd["remote_addr"])
                    except Exception:
                        pass
            except Exception as exc:
                log.debug("Network monitor error: %s", exc)
            time.sleep(1)

    def _watch_registry(self) -> None:
        if not HAS_WMI:
            return
        KEYS = [
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            r"Software\Microsoft\Windows\CurrentVersion\RunOnce",
        ]
        HIVES = {0x80000001: "HKCU", 0x80000002: "HKLM"}
        try:
            c = _wmi.WMI()
            baseline: dict[str, set[str]] = {}
            for hive_int in HIVES:
                for subkey in KEYS:
                    tag = f"{HIVES[hive_int]}\\{subkey}"
                    try:
                        _, names = c.StdRegProv.EnumValues(hDefKey=hive_int, sSubKeyName=subkey)
                        baseline[tag] = set(names) if names else set()
                    except Exception:
                        baseline[tag] = set()

            while self.monitoring:
                for hive_int in HIVES:
                    for subkey in KEYS:
                        tag = f"{HIVES[hive_int]}\\{subkey}"
                        try:
                            _, names = c.StdRegProv.EnumValues(hDefKey=hive_int, sSubKeyName=subkey)
                            current = set(names) if names else set()
                            for val in current - baseline.get(tag, set()):
                                entry = f"{tag}\\{val}"
                                with self._lock:
                                    if entry not in self.registry_modified:
                                        self.registry_modified.append(entry)
                                        log.info("[+] Registry: %s", entry)
                        except Exception:
                            pass
                time.sleep(2)
        except Exception as exc:
            log.warning("WMI registry watcher error: %s", exc)


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_report(
    monitor: BehavioralMonitor,
    target: Path,
    agent_trace: list[dict] | None = None,
    agent_trace_summary: dict | None = None,
    agent_memory_summary: dict | None = None,
    exit_code: int | None = None,
) -> None:
    """Write the behavioral report as JSON for host-side collection.

    Optionally includes agent trace data (observed state, actions, etc.)
    """
    report = monitor.get_report()
    report["sample_path"] = str(target)
    report["sample_name"] = target.name
    report["sample_exit_code"] = exit_code

    if agent_trace is not None:
        report["agent_trace"] = agent_trace
    if agent_trace_summary is not None:
        report["agent_trace_summary"] = agent_trace_summary
    if agent_memory_summary is not None:
        report["agent_memory"] = agent_memory_summary

    try:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
        log.info("Behavioral report written → %s", REPORT_PATH)
    except OSError as exc:
        log.error("Failed to write report: %s", exc)
