"""
Linux Security Snapshot: Real-time ClamAV and UFW status collection.

Replaces backend/utils/security_snapshot.py on Linux.
Uses clamscan and ufw instead of PowerShell/Windows Defender.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DefenderStatus:
    """AV status (ClamAV on Linux)."""

    antivirus_enabled: bool = False
    realtime_protection: bool = False
    tamper_protection: bool | None = None
    behavior_monitoring: bool = False
    signature_age_days: int = -1
    signature_version: str = "Unknown"
    engine_version: str = "Unknown"
    definitions_current: bool = False
    last_quick_scan: str = "Unknown"
    last_full_scan: str = "Unknown"
    full_scan_required: bool = False
    quick_scan_overdue: bool = False
    query_success: bool = False
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "antivirus_enabled": self.antivirus_enabled,
            "realtime_protection": self.realtime_protection,
            "tamper_protection": self.tamper_protection,
            "behavior_monitoring": self.behavior_monitoring,
            "signature_age_days": self.signature_age_days,
            "signature_version": self.signature_version,
            "engine_version": self.engine_version,
            "definitions_current": self.definitions_current,
            "last_quick_scan": self.last_quick_scan,
            "last_full_scan": self.last_full_scan,
            "full_scan_required": self.full_scan_required,
            "quick_scan_overdue": self.quick_scan_overdue,
            "query_success": self.query_success,
            "error_message": self.error_message,
        }


@dataclass
class FirewallStatus:
    """UFW Firewall status on Linux."""

    domain_enabled: bool = False
    private_enabled: bool = False
    public_enabled: bool = False
    domain_inbound_policy: str = "N/A"
    domain_outbound_policy: str = "N/A"
    private_inbound_policy: str = "N/A"
    private_outbound_policy: str = "N/A"
    public_inbound_policy: str = "N/A"
    public_outbound_policy: str = "N/A"
    all_profiles_enabled: bool = False
    any_profile_disabled: bool = False
    enabled_profiles: list[str] = field(default_factory=list)
    disabled_profiles: list[str] = field(default_factory=list)
    query_success: bool = False
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_enabled": self.domain_enabled,
            "private_enabled": self.private_enabled,
            "public_enabled": self.public_enabled,
            "domain_inbound_policy": self.domain_inbound_policy,
            "domain_outbound_policy": self.domain_outbound_policy,
            "private_inbound_policy": self.private_inbound_policy,
            "private_outbound_policy": self.private_outbound_policy,
            "public_inbound_policy": self.public_inbound_policy,
            "public_outbound_policy": self.public_outbound_policy,
            "all_profiles_enabled": self.all_profiles_enabled,
            "any_profile_disabled": self.any_profile_disabled,
            "enabled_profiles": self.enabled_profiles,
            "disabled_profiles": self.disabled_profiles,
            "query_success": self.query_success,
            "error_message": self.error_message,
        }


@dataclass
class SecuritySnapshot:
    """Complete security snapshot for chatbot use."""

    defender: DefenderStatus = field(default_factory=DefenderStatus)
    firewall: FirewallStatus = field(default_factory=FirewallStatus)
    timestamp: str = ""
    is_admin: bool = False
    collection_time_ms: int = 0
    overall_status: str = "Unknown"
    key_findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "defender": self.defender.to_dict(),
            "firewall": self.firewall.to_dict(),
            "timestamp": self.timestamp,
            "is_admin": self.is_admin,
            "collection_time_ms": self.collection_time_ms,
            "overall_status": self.overall_status,
            "key_findings": self.key_findings,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


def _get_defender_status() -> DefenderStatus:
    """Query ClamAV status on Linux."""
    status = DefenderStatus()
    clamscan = shutil.which("clamscan") or shutil.which("clamdscan")
    if not clamscan:
        status.error_message = "ClamAV not installed"
        return status

    try:
        result = subprocess.run(
            [clamscan, "--version"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            status.query_success = True
            status.antivirus_enabled = True
            version_line = result.stdout.strip().split("/")
            if len(version_line) >= 2:
                status.signature_version = version_line[1].strip()
            status.engine_version = version_line[0].strip() if version_line else "ClamAV"
            status.definitions_current = True
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        status.error_message = str(e)

    # Check clamd daemon for real-time protection
    try:
        proc = subprocess.run(
            ["pgrep", "-x", "clamd"],
            capture_output=True, text=True, timeout=3,
        )
        status.realtime_protection = bool(proc.stdout.strip())
    except Exception:
        pass

    return status


def _get_firewall_status() -> FirewallStatus:
    """Query UFW firewall status on Linux."""
    status = FirewallStatus()
    if not shutil.which("ufw"):
        status.error_message = "UFW not installed"
        return status

    try:
        result = subprocess.run(
            ["ufw", "status", "verbose"],
            capture_output=True, text=True, timeout=5,
        )
        output = result.stdout or ""
        if "Status: active" in output:
            status.query_success = True
            status.domain_enabled = True
            status.private_enabled = True
            status.public_enabled = True
            status.all_profiles_enabled = True
            status.any_profile_disabled = False
            status.enabled_profiles = ["UFW"]

            # Parse default policies
            for line in output.splitlines():
                if "Default:" in line:
                    if "deny" in line.lower():
                        status.public_inbound_policy = "Block"
                    elif "allow" in line.lower():
                        status.public_inbound_policy = "Allow"
        elif "Status: inactive" in output:
            status.query_success = True
            status.any_profile_disabled = True
            status.disabled_profiles = ["UFW"]
        else:
            status.error_message = "Could not determine UFW status"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        status.error_message = str(e)

    return status


def _check_admin() -> bool:
    return os.geteuid() == 0


def _assess_overall_status(snapshot: SecuritySnapshot) -> tuple[str, list[str]]:
    findings = []
    issues = 0
    critical = 0

    if snapshot.defender.query_success:
        if snapshot.defender.antivirus_enabled:
            findings.append("✅ ClamAV antivirus is installed")
        else:
            findings.append("❌ ClamAV antivirus is not available")
            critical += 1

        if snapshot.defender.realtime_protection:
            findings.append("✅ ClamAV daemon (clamd) is running")
        else:
            findings.append("⚠️ ClamAV daemon (clamd) is not running")
            issues += 1
    else:
        findings.append("⚠️ Could not query antivirus status")
        issues += 1

    if snapshot.firewall.query_success:
        if snapshot.firewall.all_profiles_enabled:
            findings.append("✅ UFW Firewall is active")
        else:
            findings.append("❌ UFW Firewall is inactive")
            critical += 1
    else:
        findings.append("⚠️ Could not query firewall status")
        issues += 1

    if critical > 0:
        status = "Critical"
    elif issues > 0:
        status = "Warning"
    else:
        status = "Good"

    return status, findings


class SecuritySnapshotManager:
    _instance: SecuritySnapshotManager | None = None
    _lock = threading.Lock()

    def __init__(self):
        self._cache: SecuritySnapshot | None = None
        self._cache_time: float = 0
        self._cache_ttl: float = 7.0
        self._collection_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> SecuritySnapshotManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_snapshot(self, force_refresh: bool = False) -> SecuritySnapshot:
        now = time.time()
        if not force_refresh and self._cache and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        with self._collection_lock:
            if not force_refresh and self._cache and (now - self._cache_time) < self._cache_ttl:
                return self._cache

            start = time.time()
            snapshot = self._collect_snapshot()
            snapshot.collection_time_ms = int((time.time() - start) * 1000)
            self._cache = snapshot
            self._cache_time = time.time()
            return snapshot

    def _collect_snapshot(self) -> SecuritySnapshot:
        snapshot = SecuritySnapshot()
        snapshot.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        snapshot.is_admin = _check_admin()
        snapshot.defender = _get_defender_status()
        snapshot.firewall = _get_firewall_status()
        snapshot.overall_status, snapshot.key_findings = _assess_overall_status(snapshot)
        return snapshot

    def invalidate_cache(self):
        self._cache = None
        self._cache_time = 0


def get_security_snapshot(force_refresh: bool = False) -> SecuritySnapshot:
    manager = SecuritySnapshotManager.get_instance()
    return manager.get_snapshot(force_refresh)


def prewarm_security_snapshot() -> None:
    def _prewarm():
        try:
            manager = SecuritySnapshotManager.get_instance()
            manager.get_snapshot(force_refresh=True)
            logger.info("Security snapshot cache pre-warmed")
        except Exception as e:
            logger.warning(f"Security snapshot pre-warm failed: {e}")

    thread = threading.Thread(target=_prewarm, daemon=True, name="SecuritySnapshotPrewarm")
    thread.start()
