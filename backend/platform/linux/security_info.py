"""
Linux Security Status Information.

Replaces backend/utils/security_info.py on Linux.
Uses ufw, clamscan, and standard Linux tools instead of
WMI, PowerShell, and Windows Defender.
"""

import json
import logging
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

logger = logging.getLogger(__name__)


class SecurityInfo:
    """Retrieve Linux security status (Firewall, AV, etc.)"""

    _is_admin: bool | None = None
    _cache: dict[str, Any] = {}
    _cache_time: float = 0
    _cache_ttl: float = 60.0

    @staticmethod
    def _check_admin() -> bool:
        if SecurityInfo._is_admin is not None:
            return SecurityInfo._is_admin
        SecurityInfo._is_admin = os.geteuid() == 0
        return SecurityInfo._is_admin

    @staticmethod
    def _run_cmd(cmd: list[str], timeout: int = 5) -> str:
        """Run a command and return stdout."""
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
            )
            return (proc.stdout or "").strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return ""

    # ------------------------------------------------------------------
    # Firewall (UFW)
    # ------------------------------------------------------------------
    @staticmethod
    def get_firewall_status() -> dict[str, Any]:
        result: dict[str, Any] = {
            "found": False,
            "enabled": False,
            "name": "UFW",
            "status": "Unknown",
        }
        if not shutil.which("ufw"):
            result["status"] = "Not Installed"
            return result

        result["found"] = True
        output = SecurityInfo._run_cmd(["sudo", "ufw", "status"])
        if "Status: active" in output:
            result["enabled"] = True
            result["status"] = "Active"
        elif "Status: inactive" in output:
            result["enabled"] = False
            result["status"] = "Inactive"
        return result

    # ------------------------------------------------------------------
    # Antivirus (ClamAV)
    # ------------------------------------------------------------------
    @staticmethod
    def get_antivirus_status() -> dict[str, Any]:
        result: dict[str, Any] = {
            "found": False,
            "enabled": False,
            "name": "",
            "realtime_protection": False,
            "up_to_date": False,
        }
        clamscan = shutil.which("clamscan") or shutil.which("clamdscan")
        if not clamscan:
            return result

        result["found"] = True
        result["name"] = "ClamAV"

        # Check version to confirm working install
        output = SecurityInfo._run_cmd([clamscan, "--version"])
        if output:
            result["enabled"] = True

        # Check if clamd daemon is running (real-time)
        if shutil.which("clamdscan"):
            daemon_out = SecurityInfo._run_cmd(["pgrep", "-x", "clamd"])
            result["realtime_protection"] = bool(daemon_out.strip())

        # Check freshclam for update status
        freshclam = shutil.which("freshclam")
        if freshclam:
            result["up_to_date"] = True  # Assume up to date if freshclam exists

        return result

    # Alias for compatibility
    get_windows_defender_status = get_antivirus_status

    # ------------------------------------------------------------------
    # Disk Encryption (LUKS)
    # ------------------------------------------------------------------
    @staticmethod
    def get_disk_encryption_status() -> dict[str, Any]:
        result: dict[str, Any] = {
            "encrypted": False,
            "method": "None",
            "status": "Not Encrypted",
        }
        output = SecurityInfo._run_cmd(["lsblk", "-o", "NAME,TYPE,FSTYPE", "--json"])
        if output:
            try:
                data = json.loads(output)
                devices = data.get("blockdevices", [])
                for dev in devices:
                    if dev.get("fstype") == "crypto_LUKS":
                        result["encrypted"] = True
                        result["method"] = "LUKS"
                        result["status"] = "Encrypted"
                        break
                    for child in dev.get("children", []):
                        if child.get("fstype") == "crypto_LUKS":
                            result["encrypted"] = True
                            result["method"] = "LUKS"
                            result["status"] = "Encrypted"
                            break
            except (json.JSONDecodeError, KeyError):
                pass
        return result

    # ------------------------------------------------------------------
    # System Updates
    # ------------------------------------------------------------------
    @staticmethod
    def get_update_status() -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": "Unknown",
            "pending_updates": 0,
        }
        # Try apt (Debian/Ubuntu)
        if shutil.which("apt"):
            output = SecurityInfo._run_cmd(
                ["apt", "list", "--upgradable"], timeout=10,
            )
            if output:
                lines = [l for l in output.strip().splitlines() if "/" in l]
                result["pending_updates"] = len(lines)
                result["status"] = (
                    "Up to Date" if len(lines) == 0 else f"{len(lines)} updates available"
                )
        return result

    # Alias for compatibility
    get_windows_update_status = get_update_status

    # ------------------------------------------------------------------
    # SSH Status (replaces RDP)
    # ------------------------------------------------------------------
    @staticmethod
    def get_ssh_status() -> dict[str, Any]:
        result: dict[str, Any] = {
            "enabled": False,
            "status": "Disabled",
        }
        output = SecurityInfo._run_cmd(["systemctl", "is-active", "sshd"])
        if output.strip() == "active":
            result["enabled"] = True
            result["status"] = "Enabled"
        else:
            output2 = SecurityInfo._run_cmd(["systemctl", "is-active", "ssh"])
            if output2.strip() == "active":
                result["enabled"] = True
                result["status"] = "Enabled"
        return result

    # Alias for compatibility
    get_rdp_status = get_ssh_status

    # ------------------------------------------------------------------
    # Admin Accounts
    # ------------------------------------------------------------------
    @staticmethod
    def get_admin_account_count() -> dict[str, Any]:
        result: dict[str, Any] = {"count": 0, "accounts": []}
        try:
            with open("/etc/group") as f:
                for line in f:
                    if line.startswith("sudo:") or line.startswith("wheel:"):
                        members = line.strip().split(":")[-1]
                        if members:
                            result["accounts"] = members.split(",")
                            result["count"] = len(result["accounts"])
                        break
        except OSError:
            pass
        return result

    # ------------------------------------------------------------------
    # No-ops for Windows-only features (keeps interface compatible)
    # ------------------------------------------------------------------
    @staticmethod
    def get_uac_status() -> dict[str, Any]:
        return {"status": "N/A (Linux)", "enabled": False}

    @staticmethod
    def get_uac_level() -> dict[str, Any]:
        return {"level": "N/A", "status": "N/A (Linux)"}

    @staticmethod
    def get_tpm_status() -> dict[str, Any]:
        result: dict[str, Any] = {"found": False, "version": "N/A"}
        if os.path.exists("/sys/class/tpm/tpm0"):
            result["found"] = True
            try:
                with open("/sys/class/tpm/tpm0/tpm_version_major") as f:
                    result["version"] = f.read().strip()
            except OSError:
                result["version"] = "Unknown"
        return result

    @staticmethod
    def get_smartscreen_status() -> dict[str, Any]:
        return {"status": "N/A (Linux)"}

    @staticmethod
    def get_memory_integrity_status() -> dict[str, Any]:
        return {"status": "N/A (Linux)"}

    # ------------------------------------------------------------------
    # Aggregate
    # ------------------------------------------------------------------
    @staticmethod
    def get_basic_security_status() -> dict[str, Any]:
        return {
            "defender": SecurityInfo.get_antivirus_status(),
            "firewall": SecurityInfo.get_firewall_status(),
            "uac": SecurityInfo.get_uac_status(),
        }

    @staticmethod
    def get_extended_security_status() -> dict[str, Any]:
        return {
            "diskEncryption": SecurityInfo.get_disk_encryption_status(),
            "windowsUpdate": SecurityInfo.get_update_status(),
            "remoteDesktop": SecurityInfo.get_ssh_status(),
            "adminAccounts": SecurityInfo.get_admin_account_count(),
            "uacLevel": SecurityInfo.get_uac_level(),
            "smartScreen": SecurityInfo.get_smartscreen_status(),
            "memoryIntegrity": SecurityInfo.get_memory_integrity_status(),
        }

    @staticmethod
    def get_all_security_status() -> dict[str, Any]:
        now = time.time()
        if (
            SecurityInfo._cache
            and (now - SecurityInfo._cache_time) < SecurityInfo._cache_ttl
        ):
            return SecurityInfo._cache

        SecurityInfo._check_admin()

        tasks = {
            "defender": SecurityInfo.get_antivirus_status,
            "firewall": SecurityInfo.get_firewall_status,
            "tpm": SecurityInfo.get_tpm_status,
            "disk_enc": SecurityInfo.get_disk_encryption_status,
            "updates": SecurityInfo.get_update_status,
            "ssh": SecurityInfo.get_ssh_status,
            "admins": SecurityInfo.get_admin_account_count,
        }

        result: dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(fn): key for key, fn in tasks.items()}
            for future in as_completed(futures, timeout=15):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as exc:
                    logger.warning("Security check '%s' failed: %s", key, exc)
                    result[key] = {"status": "Error", "error": str(exc)}

        SecurityInfo._cache = result
        SecurityInfo._cache_time = time.time()
        return result
