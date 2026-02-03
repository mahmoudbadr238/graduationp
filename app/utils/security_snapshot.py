"""
Security Snapshot: Real-time Windows Defender and Firewall status collection.

Collects ACTUAL local data via PowerShell (no internet, no API):
- Windows Defender: Get-MpComputerStatus, Get-MpPreference
- Windows Firewall: Get-NetFirewallProfile

Features:
- 5-10 second cache to avoid repeated PowerShell calls
- Compact JSON output for chatbot consumption
- Deterministic response template generation
"""

from __future__ import annotations

import json
import logging
import platform
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Platform detection
_IS_WINDOWS = platform.system() == "Windows"
_SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if _IS_WINDOWS else 0


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class DefenderStatus:
    """Windows Defender status from Get-MpComputerStatus and Get-MpPreference."""
    
    # Core protection status
    antivirus_enabled: bool = False
    realtime_protection: bool = False
    tamper_protection: bool | None = None  # May require admin
    behavior_monitoring: bool = False
    
    # Signature/definition status
    signature_age_days: int = -1  # -1 means unknown
    signature_version: str = "Unknown"
    engine_version: str = "Unknown"
    definitions_current: bool = False
    
    # Scan information
    last_quick_scan: str = "Unknown"
    last_full_scan: str = "Unknown"
    full_scan_required: bool = False
    quick_scan_overdue: bool = False
    
    # Query status
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
    """Windows Firewall status from Get-NetFirewallProfile."""
    
    # Per-profile status
    domain_enabled: bool = False
    private_enabled: bool = False
    public_enabled: bool = False
    
    # Per-profile policies
    domain_inbound_policy: str = "Unknown"  # Block, Allow, NotConfigured
    domain_outbound_policy: str = "Unknown"
    private_inbound_policy: str = "Unknown"
    private_outbound_policy: str = "Unknown"
    public_inbound_policy: str = "Unknown"
    public_outbound_policy: str = "Unknown"
    
    # Summary
    all_profiles_enabled: bool = False
    any_profile_disabled: bool = False
    enabled_profiles: list[str] = field(default_factory=list)
    disabled_profiles: list[str] = field(default_factory=list)
    
    # Query status
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
    
    # Metadata
    timestamp: str = ""
    is_admin: bool = False
    collection_time_ms: int = 0
    
    # Summary
    overall_status: str = "Unknown"  # Good, Warning, Critical
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


# ============================================================================
# PowerShell Queries
# ============================================================================

def _run_powershell(cmd: str, timeout: int = 8) -> tuple[bool, str]:
    """Run PowerShell command and return (success, output)."""
    if not _IS_WINDOWS:
        return False, "Not Windows"
    
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_SUBPROCESS_FLAGS,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip() or f"Exit code {result.returncode}"
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except FileNotFoundError:
        return False, "PowerShell not found"
    except Exception as e:
        return False, str(e)


def _get_defender_status() -> DefenderStatus:
    """Query Windows Defender status via PowerShell."""
    status = DefenderStatus()
    
    if not _IS_WINDOWS:
        status.error_message = "Not Windows"
        return status
    
    # Query Get-MpComputerStatus for current state
    ps_cmd = """
    try {
        $status = Get-MpComputerStatus -ErrorAction Stop
        $prefs = Get-MpPreference -ErrorAction SilentlyContinue
        
        @{
            AntivirusEnabled = $status.AntivirusEnabled
            RealTimeProtectionEnabled = $status.RealTimeProtectionEnabled
            IsTamperProtected = $status.IsTamperProtected
            BehaviorMonitorEnabled = $status.BehaviorMonitorEnabled
            AntivirusSignatureAge = $status.AntivirusSignatureAge
            AntivirusSignatureVersion = $status.AntivirusSignatureVersion
            AMEngineVersion = $status.AMEngineVersion
            AntispywareSignatureAge = $status.AntispywareSignatureAge
            DefenderSignaturesOutOfDate = $status.DefenderSignaturesOutOfDate
            QuickScanAge = $status.QuickScanAge
            FullScanAge = $status.FullScanAge
            FullScanRequired = $status.FullScanRequired
            QuickScanOverdue = $status.QuickScanOverdue
            FullScanOverdue = $status.FullScanOverdue
            LastQuickScanTime = if ($status.QuickScanEndTime) { $status.QuickScanEndTime.ToString("yyyy-MM-dd HH:mm") } else { "Never" }
            LastFullScanTime = if ($status.FullScanEndTime) { $status.FullScanEndTime.ToString("yyyy-MM-dd HH:mm") } else { "Never" }
        } | ConvertTo-Json -Compress
    } catch {
        @{ Error = $_.Exception.Message } | ConvertTo-Json -Compress
    }
    """
    
    success, output = _run_powershell(ps_cmd, timeout=10)
    
    if success and output:
        try:
            data = json.loads(output)
            
            if "Error" in data:
                status.error_message = data["Error"]
                return status
            
            status.query_success = True
            status.antivirus_enabled = data.get("AntivirusEnabled", False) or False
            status.realtime_protection = data.get("RealTimeProtectionEnabled", False) or False
            status.tamper_protection = data.get("IsTamperProtected")
            status.behavior_monitoring = data.get("BehaviorMonitorEnabled", False) or False
            
            # Signature info
            sig_age = data.get("AntivirusSignatureAge")
            if sig_age is not None:
                status.signature_age_days = int(sig_age)
            
            status.signature_version = data.get("AntivirusSignatureVersion", "Unknown") or "Unknown"
            status.engine_version = data.get("AMEngineVersion", "Unknown") or "Unknown"
            status.definitions_current = not (data.get("DefenderSignaturesOutOfDate", True) or False)
            
            # Scan info
            status.last_quick_scan = data.get("LastQuickScanTime", "Unknown") or "Unknown"
            status.last_full_scan = data.get("LastFullScanTime", "Unknown") or "Unknown"
            status.full_scan_required = data.get("FullScanRequired", False) or False
            status.quick_scan_overdue = data.get("QuickScanOverdue", False) or False
            
        except json.JSONDecodeError as e:
            status.error_message = f"JSON parse error: {e}"
    else:
        status.error_message = output or "Query failed"
    
    return status


def _get_firewall_status() -> FirewallStatus:
    """Query Windows Firewall status via PowerShell."""
    status = FirewallStatus()
    
    if not _IS_WINDOWS:
        status.error_message = "Not Windows"
        return status
    
    ps_cmd = """
    try {
        $profiles = Get-NetFirewallProfile -ErrorAction Stop | ForEach-Object {
            @{
                Name = $_.Name
                Enabled = $_.Enabled
                DefaultInboundAction = $_.DefaultInboundAction.ToString()
                DefaultOutboundAction = $_.DefaultOutboundAction.ToString()
            }
        }
        @{ Profiles = $profiles } | ConvertTo-Json -Compress -Depth 3
    } catch {
        @{ Error = $_.Exception.Message } | ConvertTo-Json -Compress
    }
    """
    
    success, output = _run_powershell(ps_cmd, timeout=8)
    
    if success and output:
        try:
            data = json.loads(output)
            
            if "Error" in data:
                status.error_message = data["Error"]
                return status
            
            status.query_success = True
            profiles = data.get("Profiles", [])
            
            # Handle single profile (not wrapped in list)
            if isinstance(profiles, dict):
                profiles = [profiles]
            
            for profile in profiles:
                name = profile.get("Name", "").lower()
                enabled = profile.get("Enabled", False)
                inbound = profile.get("DefaultInboundAction", "Unknown")
                outbound = profile.get("DefaultOutboundAction", "Unknown")
                
                if name == "domain":
                    status.domain_enabled = enabled
                    status.domain_inbound_policy = inbound
                    status.domain_outbound_policy = outbound
                elif name == "private":
                    status.private_enabled = enabled
                    status.private_inbound_policy = inbound
                    status.private_outbound_policy = outbound
                elif name == "public":
                    status.public_enabled = enabled
                    status.public_inbound_policy = inbound
                    status.public_outbound_policy = outbound
                
                if enabled:
                    status.enabled_profiles.append(profile.get("Name", name))
                else:
                    status.disabled_profiles.append(profile.get("Name", name))
            
            status.all_profiles_enabled = (
                status.domain_enabled and 
                status.private_enabled and 
                status.public_enabled
            )
            status.any_profile_disabled = (
                not status.domain_enabled or
                not status.private_enabled or
                not status.public_enabled
            )
            
        except json.JSONDecodeError as e:
            status.error_message = f"JSON parse error: {e}"
    else:
        status.error_message = output or "Query failed"
    
    return status


def _check_admin() -> bool:
    """Check if running as administrator."""
    if not _IS_WINDOWS:
        return False
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _assess_overall_status(snapshot: SecuritySnapshot) -> tuple[str, list[str]]:
    """Assess overall security status and generate key findings."""
    findings = []
    issues = 0
    critical = 0
    
    # Check Defender
    if snapshot.defender.query_success:
        if snapshot.defender.realtime_protection:
            findings.append("✅ Real-time protection is ON")
        else:
            findings.append("❌ Real-time protection is OFF")
            critical += 1
        
        if snapshot.defender.antivirus_enabled:
            findings.append("✅ Windows Defender antivirus is enabled")
        else:
            findings.append("❌ Windows Defender antivirus is disabled")
            critical += 1
        
        if snapshot.defender.definitions_current:
            findings.append(f"✅ Virus definitions are current (age: {snapshot.defender.signature_age_days} days)")
        elif snapshot.defender.signature_age_days > 7:
            findings.append(f"⚠️ Virus definitions are {snapshot.defender.signature_age_days} days old")
            issues += 1
        elif snapshot.defender.signature_age_days >= 0:
            findings.append(f"✅ Virus definitions are {snapshot.defender.signature_age_days} days old")
        
        if snapshot.defender.tamper_protection is True:
            findings.append("✅ Tamper protection is ON")
        elif snapshot.defender.tamper_protection is False:
            findings.append("⚠️ Tamper protection is OFF")
            issues += 1
        
        if snapshot.defender.full_scan_required:
            findings.append("⚠️ Full scan is required")
            issues += 1
    else:
        findings.append("⚠️ Could not query Defender status")
        issues += 1
    
    # Check Firewall
    if snapshot.firewall.query_success:
        if snapshot.firewall.all_profiles_enabled:
            findings.append("✅ All firewall profiles are enabled (Domain, Private, Public)")
        elif snapshot.firewall.enabled_profiles:
            enabled = ", ".join(snapshot.firewall.enabled_profiles)
            disabled = ", ".join(snapshot.firewall.disabled_profiles)
            findings.append(f"⚠️ Firewall partially enabled: {enabled} ON, {disabled} OFF")
            issues += 1
        else:
            findings.append("❌ All firewall profiles are disabled")
            critical += 1
    else:
        findings.append("⚠️ Could not query Firewall status")
        issues += 1
    
    # Determine overall status
    if critical > 0:
        status = "Critical"
    elif issues > 0:
        status = "Warning"
    else:
        status = "Good"
    
    return status, findings


# ============================================================================
# Cached Snapshot Manager
# ============================================================================

class SecuritySnapshotManager:
    """Manager for security snapshot with caching."""
    
    _instance: SecuritySnapshotManager | None = None
    _lock = threading.Lock()
    
    def __init__(self):
        self._cache: SecuritySnapshot | None = None
        self._cache_time: float = 0
        self._cache_ttl: float = 7.0  # 7 seconds cache
        self._collecting = False
        self._collection_lock = threading.Lock()
    
    @classmethod
    def get_instance(cls) -> SecuritySnapshotManager:
        """Get singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def get_snapshot(self, force_refresh: bool = False) -> SecuritySnapshot:
        """
        Get security snapshot (cached for 5-10 seconds).
        
        Args:
            force_refresh: Force a fresh collection, ignoring cache
        
        Returns:
            SecuritySnapshot with current status
        """
        now = time.time()
        
        # Return cached if valid
        if not force_refresh and self._cache and (now - self._cache_time) < self._cache_ttl:
            logger.debug(f"Returning cached snapshot (age: {now - self._cache_time:.1f}s)")
            return self._cache
        
        # Collect new snapshot
        with self._collection_lock:
            # Double-check cache (another thread may have updated it)
            if not force_refresh and self._cache and (now - self._cache_time) < self._cache_ttl:
                return self._cache
            
            start = time.time()
            snapshot = self._collect_snapshot()
            snapshot.collection_time_ms = int((time.time() - start) * 1000)
            
            # Update cache
            self._cache = snapshot
            self._cache_time = time.time()
            
            logger.info(f"Security snapshot collected in {snapshot.collection_time_ms}ms")
            return snapshot
    
    def _collect_snapshot(self) -> SecuritySnapshot:
        """Collect fresh security snapshot."""
        snapshot = SecuritySnapshot()
        snapshot.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        snapshot.is_admin = _check_admin()
        
        # Collect Defender and Firewall status
        snapshot.defender = _get_defender_status()
        snapshot.firewall = _get_firewall_status()
        
        # Assess overall status
        snapshot.overall_status, snapshot.key_findings = _assess_overall_status(snapshot)
        
        return snapshot
    
    def invalidate_cache(self):
        """Invalidate cached snapshot."""
        self._cache = None
        self._cache_time = 0


# ============================================================================
# Public API
# ============================================================================

def get_security_snapshot(force_refresh: bool = False) -> SecuritySnapshot:
    """
    Get current security snapshot (cached for 5-10 seconds).
    
    Collects:
    - Windows Defender status (real-time protection, signatures, scans)
    - Windows Firewall status (all profiles, policies)
    
    Args:
        force_refresh: Force fresh collection, ignoring cache
    
    Returns:
        SecuritySnapshot with current status
    """
    manager = SecuritySnapshotManager.get_instance()
    return manager.get_snapshot(force_refresh)


def get_security_snapshot_json(force_refresh: bool = False) -> str:
    """Get security snapshot as compact JSON string."""
    return get_security_snapshot(force_refresh).to_json()


def prewarm_security_snapshot() -> None:
    """
    Pre-warm the security snapshot cache in a background thread.
    
    Call this at app startup to avoid delay on first chatbot security question.
    The PowerShell queries can take 3-5 seconds on first call.
    """
    def _prewarm():
        try:
            manager = SecuritySnapshotManager.get_instance()
            manager.get_snapshot(force_refresh=True)
            logger.info("Security snapshot cache pre-warmed")
        except Exception as e:
            logger.warning(f"Security snapshot pre-warm failed: {e}")
    
    thread = threading.Thread(target=_prewarm, daemon=True, name="SecuritySnapshotPrewarm")
    thread.start()


# ============================================================================
# Response Templates
# ============================================================================

def generate_defender_response(snapshot: SecuritySnapshot) -> dict[str, Any]:
    """
    Generate deterministic response template for Defender questions.
    
    Returns dict with:
        - quick_status: 2-4 bullet lines
        - what_this_means: 3-6 sentences
        - what_you_can_do: 2-5 steps (only if needed)
    """
    defender = snapshot.defender
    
    # Quick Status (2-4 bullets)
    quick_status = []
    
    if defender.query_success:
        if defender.realtime_protection:
            quick_status.append("✅ Real-time protection: ON")
        else:
            quick_status.append("❌ Real-time protection: OFF")
        
        if defender.antivirus_enabled:
            quick_status.append("✅ Antivirus: Enabled")
        else:
            quick_status.append("❌ Antivirus: Disabled")
        
        if defender.signature_age_days >= 0:
            if defender.signature_age_days <= 1:
                quick_status.append(f"✅ Definitions: Up to date")
            elif defender.signature_age_days <= 7:
                quick_status.append(f"✅ Definitions: {defender.signature_age_days} days old")
            else:
                quick_status.append(f"⚠️ Definitions: {defender.signature_age_days} days old (outdated)")
        
        if defender.last_quick_scan != "Unknown" and defender.last_quick_scan != "Never":
            quick_status.append(f"📅 Last quick scan: {defender.last_quick_scan}")
    else:
        quick_status.append("⚠️ Could not query Defender status")
        quick_status.append(f"ℹ️ Reason: {defender.error_message}")
    
    # What This Means (3-6 sentences)
    what_this_means = []
    
    if defender.query_success:
        if defender.realtime_protection and defender.antivirus_enabled:
            what_this_means.append(
                "Your Windows Defender is actively protecting your computer in real-time."
            )
            what_this_means.append(
                "Files are scanned automatically when you open, download, or run them."
            )
        elif not defender.realtime_protection:
            what_this_means.append(
                "Real-time protection is turned off, which means files are NOT being scanned automatically."
            )
            what_this_means.append(
                "This leaves your computer vulnerable to malware and viruses until you enable it."
            )
        
        if defender.definitions_current:
            what_this_means.append(
                "Your virus definitions are current, so Defender can detect the latest known threats."
            )
        elif defender.signature_age_days > 7:
            what_this_means.append(
                f"Your virus definitions are {defender.signature_age_days} days old, "
                "which means Defender might miss new threats."
            )
        
        if defender.tamper_protection is True:
            what_this_means.append(
                "Tamper protection is on, preventing malware from disabling your security."
            )
        elif defender.tamper_protection is False:
            what_this_means.append(
                "Tamper protection is off. Malware could potentially disable your security settings."
            )
        
        if defender.full_scan_required:
            what_this_means.append(
                "Windows recommends running a full scan to check for threats."
            )
    else:
        what_this_means.append(
            "I couldn't query Windows Defender status directly."
        )
        what_this_means.append(
            "This might be because Defender is not installed, or there's a permissions issue."
        )
    
    # What You Can Do (2-5 steps, only if needed)
    what_you_can_do = []
    
    if defender.query_success:
        needs_action = False
        
        if not defender.realtime_protection:
            what_you_can_do.append(
                "Enable real-time protection: Open Windows Security → Virus & threat protection → Turn ON Real-time protection"
            )
            needs_action = True
        
        if not defender.antivirus_enabled:
            what_you_can_do.append(
                "Enable Defender: Open Windows Security → Virus & threat protection → Manage settings → Turn ON Microsoft Defender Antivirus"
            )
            needs_action = True
        
        if defender.signature_age_days > 7:
            what_you_can_do.append(
                "Update definitions: Open Windows Security → Virus & threat protection → Check for updates"
            )
            needs_action = True
        
        if defender.full_scan_required or defender.quick_scan_overdue:
            what_you_can_do.append(
                "Run a scan: Open Windows Security → Virus & threat protection → Quick scan (or Full scan)"
            )
            needs_action = True
        
        if defender.tamper_protection is False:
            what_you_can_do.append(
                "Enable tamper protection: Windows Security → Virus & threat protection → Manage settings → Turn ON Tamper protection"
            )
            needs_action = True
        
        if not needs_action:
            what_you_can_do.append("No action needed - your protection is working correctly!")
    else:
        what_you_can_do.append(
            "Check if Windows Defender is installed and running"
        )
        what_you_can_do.append(
            "Open Windows Security from the Start menu to check your protection status"
        )
    
    return {
        "quick_status": quick_status,
        "what_this_means": what_this_means,
        "what_you_can_do": what_you_can_do,
        "severity": "critical" if not defender.realtime_protection else ("warning" if defender.signature_age_days > 7 else "good"),
    }


def generate_firewall_response(snapshot: SecuritySnapshot) -> dict[str, Any]:
    """
    Generate deterministic response template for Firewall questions.
    
    Returns dict with:
        - quick_status: 2-4 bullet lines
        - what_this_means: 3-6 sentences
        - what_you_can_do: 2-5 steps (only if needed)
    """
    firewall = snapshot.firewall
    
    # Quick Status (2-4 bullets)
    quick_status = []
    
    if firewall.query_success:
        if firewall.all_profiles_enabled:
            quick_status.append("✅ All firewall profiles: ON")
        else:
            if firewall.enabled_profiles:
                quick_status.append(f"✅ Enabled: {', '.join(firewall.enabled_profiles)}")
            if firewall.disabled_profiles:
                quick_status.append(f"❌ Disabled: {', '.join(firewall.disabled_profiles)}")
        
        # Show policies for public profile (most important)
        if firewall.public_enabled:
            quick_status.append(f"🛡️ Public network: Inbound {firewall.public_inbound_policy}, Outbound {firewall.public_outbound_policy}")
    else:
        quick_status.append("⚠️ Could not query Firewall status")
        quick_status.append(f"ℹ️ Reason: {firewall.error_message}")
    
    # What This Means (3-6 sentences)
    what_this_means = []
    
    if firewall.query_success:
        if firewall.all_profiles_enabled:
            what_this_means.append(
                "Your Windows Firewall is fully enabled on all network types (Domain, Private, and Public)."
            )
            what_this_means.append(
                "This blocks unauthorized incoming connections and protects your computer from network-based attacks."
            )
            
            if firewall.public_inbound_policy == "Block":
                what_this_means.append(
                    "Incoming connections on public networks are blocked by default, which is the safest setting."
                )
            else:
                what_this_means.append(
                    f"Incoming connections on public networks are set to '{firewall.public_inbound_policy}', "
                    "which may allow some unsolicited connections."
                )
        
        elif firewall.any_profile_disabled:
            disabled = ", ".join(firewall.disabled_profiles)
            what_this_means.append(
                f"Your firewall is disabled for {disabled} networks."
            )
            what_this_means.append(
                "This means your computer is less protected when connected to those network types."
            )
            
            if "Public" in firewall.disabled_profiles:
                what_this_means.append(
                    "⚠️ The Public profile being disabled is especially risky on open Wi-Fi networks."
                )
        
        else:
            what_this_means.append(
                "Your Windows Firewall is completely disabled."
            )
            what_this_means.append(
                "Your computer is vulnerable to network-based attacks and unauthorized access."
            )
    else:
        what_this_means.append(
            "I couldn't query Windows Firewall status directly."
        )
        what_this_means.append(
            "The firewall service might not be running, or there's a permissions issue."
        )
    
    # What You Can Do (2-5 steps, only if needed)
    what_you_can_do = []
    
    if firewall.query_success:
        if firewall.any_profile_disabled:
            disabled = ", ".join(firewall.disabled_profiles)
            what_you_can_do.append(
                f"Enable disabled profiles: Open Windows Security → Firewall & network protection → Click on '{firewall.disabled_profiles[0]}' → Turn ON"
            )
            what_you_can_do.append(
                "Alternatively: Control Panel → Windows Defender Firewall → Turn Windows Defender Firewall on or off"
            )
        
        if not firewall.all_profiles_enabled and not firewall.enabled_profiles:
            what_you_can_do.append(
                "Enable firewall: Open Windows Security → Firewall & network protection → Enable for all profiles"
            )
        
        if firewall.public_inbound_policy != "Block" and firewall.public_enabled:
            what_you_can_do.append(
                "Consider blocking inbound connections on public networks for better security"
            )
        
        if not what_you_can_do:
            what_you_can_do.append("No action needed - your firewall is configured correctly!")
    else:
        what_you_can_do.append(
            "Check if Windows Firewall service is running (services.msc → Windows Defender Firewall)"
        )
        what_you_can_do.append(
            "Open Windows Security from the Start menu to check your firewall status"
        )
    
    return {
        "quick_status": quick_status,
        "what_this_means": what_this_means,
        "what_you_can_do": what_you_can_do,
        "severity": "critical" if not firewall.enabled_profiles else ("warning" if firewall.any_profile_disabled else "good"),
    }


def generate_overall_security_response(snapshot: SecuritySnapshot) -> dict[str, Any]:
    """
    Generate deterministic response template for general security status questions.
    
    Returns dict with:
        - quick_status: 2-4 bullet lines
        - what_this_means: 3-6 sentences
        - what_you_can_do: 2-5 steps (only if needed)
    """
    defender = snapshot.defender
    firewall = snapshot.firewall
    
    # Quick Status
    quick_status = []
    quick_status.append(f"🔒 Overall Status: {snapshot.overall_status}")
    
    if defender.query_success:
        if defender.realtime_protection:
            quick_status.append("✅ Defender: Real-time protection ON")
        else:
            quick_status.append("❌ Defender: Real-time protection OFF")
    
    if firewall.query_success:
        if firewall.all_profiles_enabled:
            quick_status.append("✅ Firewall: All profiles enabled")
        elif firewall.enabled_profiles:
            quick_status.append(f"⚠️ Firewall: Only {', '.join(firewall.enabled_profiles)} enabled")
        else:
            quick_status.append("❌ Firewall: All profiles disabled")
    
    # What This Means
    what_this_means = []
    
    if snapshot.overall_status == "Good":
        what_this_means.append(
            "Your Windows security protections are working correctly."
        )
        what_this_means.append(
            "Real-time protection is scanning files as you use them, and your firewall is blocking unauthorized access."
        )
    elif snapshot.overall_status == "Warning":
        what_this_means.append(
            "Your security has some issues that should be addressed."
        )
        for finding in snapshot.key_findings:
            if "⚠️" in finding:
                what_this_means.append(finding.replace("⚠️ ", ""))
    else:  # Critical
        what_this_means.append(
            "Your security has critical issues that need immediate attention."
        )
        for finding in snapshot.key_findings:
            if "❌" in finding:
                what_this_means.append(finding.replace("❌ ", ""))
    
    # What You Can Do
    what_you_can_do = []
    
    if not defender.realtime_protection:
        what_you_can_do.append(
            "Enable real-time protection: Windows Security → Virus & threat protection → Turn ON"
        )
    
    if firewall.any_profile_disabled:
        what_you_can_do.append(
            "Enable firewall: Windows Security → Firewall & network protection → Enable all profiles"
        )
    
    if defender.signature_age_days > 7:
        what_you_can_do.append(
            "Update virus definitions: Windows Security → Virus & threat protection → Check for updates"
        )
    
    if not what_you_can_do:
        what_you_can_do.append("No action needed - your security is in good shape!")
    
    return {
        "quick_status": quick_status,
        "what_this_means": what_this_means,
        "what_you_can_do": what_you_can_do,
        "severity": snapshot.overall_status.lower(),
    }
