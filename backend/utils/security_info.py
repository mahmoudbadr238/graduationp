"""Windows Security Status Information."""

import json
import logging
import platform
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

logger = logging.getLogger(__name__)

# Subprocess flags - CREATE_NO_WINDOW only works on Windows
_IS_WINDOWS = sys.platform == "win32"
_SUBPROCESS_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class SecurityInfo:
    """Retrieve Windows security status (Firewall, Antivirus, etc.)"""

    # Flag to track if we're running as admin
    _is_admin: bool | None = None

    # Cache for security status (to avoid repeated slow queries)
    _cache: dict[str, Any] = {}
    _cache_time: float = 0
    _cache_ttl: float = 60.0  # Cache for 60 seconds

    @staticmethod
    def clear_cache() -> None:
        """Clear the cached simplified security snapshot."""
        SecurityInfo._cache = {}
        SecurityInfo._cache_time = 0

    @staticmethod
    def _check_admin() -> bool:
        """Check if running with admin privileges."""
        if SecurityInfo._is_admin is not None:
            return SecurityInfo._is_admin
        try:
            import ctypes

            SecurityInfo._is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            SecurityInfo._is_admin = False
        return SecurityInfo._is_admin

    @staticmethod
    def _decode_product_state(product_state: int) -> dict[str, bool]:
        """Decode the WMI productState bitmask for AV/Firewall products.

        The productState is a 3-byte hex value: 0xXXYYZZ
        - XX (bits 23-16): product owner / signer
        - YY (bits 15-8): product state flags
            bit 12 (0x1000): product is enabled / actively running
        - ZZ (bits 7-0): definition status
            bit 4 (0x10): definitions are up to date (0 = current, 1 = outdated)

        Returns dict with 'enabled' and 'up_to_date' booleans.
        """
        enabled = bool(product_state & 0x1000)
        # Bit 4 of the low byte: 0 means current, non-zero means outdated
        up_to_date = (product_state & 0x0010) == 0
        return {"enabled": enabled, "up_to_date": up_to_date}

    @staticmethod
    def get_antivirus_via_wmi() -> dict[str, Any]:
        """Query SecurityCenter2 for all registered AV products.

        Returns the first actively-running product, or a summary of what was found.
        Falls back gracefully if WMI is unavailable.
        """
        result: dict[str, Any] = {
            "found": False,
            "enabled": False,
            "name": "",
            "realtime_protection": False,
            "up_to_date": False,
            "all_products": [],
        }
        try:
            import wmi

            c = wmi.WMI(namespace=r"root\SecurityCenter2")
            products = c.AntiVirusProduct()

            for product in products:
                display_name = getattr(product, "displayName", "Unknown AV")
                state_int = int(getattr(product, "productState", 0))
                decoded = SecurityInfo._decode_product_state(state_int)
                entry = {
                    "name": display_name,
                    "enabled": decoded["enabled"],
                    "up_to_date": decoded["up_to_date"],
                    "productState": state_int,
                }
                result["all_products"].append(entry)

                # Accept the first actively-running product as the primary AV
                if decoded["enabled"] and not result["found"]:
                    result["found"] = True
                    result["enabled"] = True
                    result["name"] = display_name
                    result["realtime_protection"] = True  # enabled ≈ real-time
                    result["up_to_date"] = decoded["up_to_date"]

            # If products exist but none is enabled, report the first one anyway
            if result["all_products"] and not result["found"]:
                first = result["all_products"][0]
                result["found"] = True
                result["name"] = first["name"]

            logger.info(
                "[SecurityInfo] WMI AV products: %s",
                [(p["name"], p["enabled"]) for p in result["all_products"]],
            )
        except ImportError:
            logger.debug("wmi module not available, skipping WMI AV query")
        except Exception as e:
            logger.debug(f"WMI AntiVirusProduct query failed: {e}")
        return result

    @staticmethod
    def get_firewall_via_wmi() -> dict[str, Any]:
        """Query SecurityCenter2 for all registered Firewall products.

        Returns the first actively-running product, or a summary of what was found.
        Falls back gracefully if WMI is unavailable.
        """
        result: dict[str, Any] = {
            "found": False,
            "enabled": False,
            "name": "",
            "all_products": [],
        }
        try:
            import wmi

            c = wmi.WMI(namespace=r"root\SecurityCenter2")
            products = c.FirewallProduct()

            for product in products:
                display_name = getattr(product, "displayName", "Unknown Firewall")
                state_int = int(getattr(product, "productState", 0))
                decoded = SecurityInfo._decode_product_state(state_int)
                entry = {
                    "name": display_name,
                    "enabled": decoded["enabled"],
                    "productState": state_int,
                }
                result["all_products"].append(entry)

                if decoded["enabled"] and not result["found"]:
                    result["found"] = True
                    result["enabled"] = True
                    result["name"] = display_name

            if result["all_products"] and not result["found"]:
                first = result["all_products"][0]
                result["found"] = True
                result["name"] = first["name"]

            logger.info(
                "[SecurityInfo] WMI Firewall products: %s",
                [(p["name"], p["enabled"]) for p in result["all_products"]],
            )
        except ImportError:
            logger.debug("wmi module not available, skipping WMI Firewall query")
        except Exception as e:
            logger.debug(f"WMI FirewallProduct query failed: {e}")
        return result

    @staticmethod
    def get_windows_defender_status() -> dict[str, Any]:
        """Get antivirus status — WMI SecurityCenter2 first, PowerShell fallback."""

        # ── PRIMARY: WMI SecurityCenter2 (detects ANY registered AV) ──
        wmi_av = SecurityInfo.get_antivirus_via_wmi()
        if wmi_av["found"] and wmi_av["enabled"]:
            return {
                "enabled": True,
                "realtime_protection": wmi_av["realtime_protection"],
                "name": wmi_av["name"],
                "up_to_date": wmi_av["up_to_date"],
                "all_products": wmi_av["all_products"],
                "last_scan": "N/A",
                "definition_status": "Current" if wmi_av["up_to_date"] else "Outdated",
                "status": "query_success",
                "source": "wmi",
            }

        # ── FALLBACK: PowerShell Get-MpComputerStatus (Windows Defender only) ──
        try:
            # Use PowerShell to query Windows Defender status
            ps_cmd = (
                "Get-MpComputerStatus | "
                "Select-Object -Property "
                "AntivirusEnabled, "
                "AntispywareEnabled, "
                "RealTimeProtectionEnabled, "
                "LastFullScanTime, "
                "LastQuickScanTime, "
                "FullScanOverdue, "
                "SignatureOutofDate "
                "| ConvertTo-Json"
            )

            result = subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=8,  # Increased timeout
                creationflags=_SUBPROCESS_FLAGS,
            )

            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                return {
                    "enabled": data.get("AntivirusEnabled", False),
                    "realtime_protection": data.get("RealTimeProtectionEnabled", False),
                    "name": "Windows Defender",
                    "last_scan": data.get("LastFullScanTime", "Unknown"),
                    "definition_status": (
                        "Current"
                        if not data.get("SignatureOutofDate", True)
                        else "Outdated"
                    ),
                    "status": "query_success",
                    "source": "powershell",
                }
        except subprocess.TimeoutExpired:
            logger.warning("Windows Defender query timed out")
        except (
            subprocess.CalledProcessError,
            json.JSONDecodeError,
            FileNotFoundError,
        ) as e:
            logger.debug(f"Could not query Windows Defender: {e}")

        # If WMI found products but none enabled, report that
        if wmi_av["found"] and not wmi_av["enabled"]:
            return {
                "enabled": False,
                "realtime_protection": False,
                "name": wmi_av["name"],
                "all_products": wmi_av["all_products"],
                "last_scan": "Unknown",
                "definition_status": "Unknown",
                "status": "query_success",
                "source": "wmi",
            }

        # Return "Requires Admin" status if not admin
        if not SecurityInfo._check_admin():
            return {
                "enabled": None,  # Unknown
                "realtime_protection": None,
                "name": "",
                "last_scan": "Requires Admin",
                "definition_status": "Requires Admin",
                "status": "requires_admin",
            }

        return {
            "enabled": False,
            "realtime_protection": False,
            "name": "",
            "last_scan": "Unknown",
            "definition_status": "Unknown",
        }

    @staticmethod
    def get_firewall_status() -> dict[str, Any]:
        """Multi-layered firewall detection: WMI → psutil service → netsh.

        Layer 1 – WMI SecurityCenter2 FirewallProduct (third-party firewalls).
        Layer 2 – psutil service check for 'mpssvc' (Windows Defender Firewall).
        Layer 3 – netsh advfirewall profile state parsing (last resort).
        """

        # ── LAYER 1: WMI SecurityCenter2 (third-party firewalls) ─────────
        wmi_fw = SecurityInfo.get_firewall_via_wmi()
        if wmi_fw["found"] and wmi_fw["enabled"]:
            return {
                "enabled": True,
                "name": wmi_fw["name"],
                "all_products": wmi_fw["all_products"],
                "enabled_profiles": [],
                "status": "Active",
                "source": "wmi",
            }

        # ── LAYER 2: psutil service check for Windows Defender Firewall ──
        try:
            import psutil

            for svc in psutil.win_service_iter():
                if svc.name().lower() == "mpssvc":
                    info = svc.as_dict()
                    if info.get("status") == "running":
                        logger.info(
                            "[SecurityInfo] mpssvc service is running"
                        )
                        return {
                            "enabled": True,
                            "name": "Windows Defender Firewall",
                            "all_products": wmi_fw.get("all_products", []),
                            "enabled_profiles": [],
                            "status": "Active",
                            "source": "psutil_service",
                        }
                    break  # found the service but it's not running
        except ImportError:
            logger.debug("psutil not available, skipping service check")
        except Exception as e:
            logger.debug("psutil mpssvc check failed: %s", e)

        # ── LAYER 3: netsh advfirewall (parse profile states) ────────────
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "show", "allprofiles", "state"],
                capture_output=True,
                text=True,
                timeout=8,
                creationflags=_SUBPROCESS_FLAGS,
            )

            if result.returncode == 0 and result.stdout.strip():
                # Output contains lines like "State    ON" per profile
                active_profiles: list[str] = []
                current_profile = ""
                for line in result.stdout.splitlines():
                    stripped = line.strip()
                    # Profile header lines: "Domain Profile Settings:",
                    # "Private Profile Settings:", "Public Profile Settings:"
                    if "profile" in stripped.lower() and "settings" in stripped.lower():
                        current_profile = stripped.split()[0]  # "Domain" / "Private" / "Public"
                    if stripped.lower().startswith("state") and "on" in stripped.lower():
                        active_profiles.append(current_profile or "Unknown")

                if active_profiles:
                    logger.info(
                        "[SecurityInfo] netsh: active firewall profiles %s",
                        active_profiles,
                    )
                    return {
                        "enabled": True,
                        "name": "Windows Firewall (Netsh)",
                        "all_products": wmi_fw.get("all_products", []),
                        "enabled_profiles": active_profiles,
                        "status": "Active",
                        "source": "netsh",
                    }
        except subprocess.TimeoutExpired:
            logger.warning("netsh firewall query timed out")
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
            logger.debug("netsh firewall check failed: %s", e)

        # ── ALL LAYERS EXHAUSTED ─────────────────────────────────────────
        # If WMI found products but none enabled, report that
        if wmi_fw["found"] and not wmi_fw["enabled"]:
            return {
                "enabled": False,
                "name": wmi_fw["name"],
                "all_products": wmi_fw["all_products"],
                "enabled_profiles": [],
                "status": "Disabled",
                "source": "wmi",
            }

        if not SecurityInfo._check_admin():
            return {
                "enabled": None,
                "name": "",
                "enabled_profiles": [],
                "status": "Requires Admin",
            }

        return {
            "enabled": False,
            "name": "",
            "enabled_profiles": [],
            "status": "Unknown",
        }

    @staticmethod
    def get_uac_status() -> dict[str, Any]:
        """Get User Access Control (UAC) status."""
        try:
            # Check UAC registry value
            ps_cmd = (
                "Get-ItemProperty -Path 'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\System' "
                "-Name 'ConsentPromptBehaviorAdmin' 2>/dev/null | "
                "Select-Object -ExpandProperty 'ConsentPromptBehaviorAdmin'"
            )

            result = subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                try:
                    value = int(result.stdout.strip())
                    # 0 = disabled, 2 = enabled
                    enabled = value != 0
                    return {
                        "enabled": enabled,
                        "status": "Enabled" if enabled else "Disabled",
                    }
                except ValueError:
                    pass
        except subprocess.TimeoutExpired:
            logger.warning("UAC query timed out")
        except FileNotFoundError:
            pass

        return {
            "enabled": True,
            "status": "Unknown",
        }

    @staticmethod
    def get_all_security_status() -> dict[str, Any]:
        """Get comprehensive security status."""
        return {
            "defender": SecurityInfo.get_windows_defender_status(),
            "firewall": SecurityInfo.get_firewall_status(),
            "uac": SecurityInfo.get_uac_status(),
        }

    @staticmethod
    def _run_powershell(cmd: str, timeout: int = 10) -> str | None:
        """Helper to run PowerShell commands safely."""
        if not _IS_WINDOWS:
            return None
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=_SUBPROCESS_FLAGS,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ) as e:
            logger.debug(f"PowerShell command failed: {e}")
        return None

    @staticmethod
    def get_disk_encryption_status() -> dict[str, Any]:
        """Get BitLocker/Device Encryption status for C: drive."""
        # First check registry for Device Encryption (fast, works without admin)
        try:
            ps_registry = (
                "$de = Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\DeviceEncryption' -ErrorAction SilentlyContinue; "
                "if ($de -and $de.BitLockerEnabled -eq 1) { @{Enabled=$true} | ConvertTo-Json -Compress } "
                "else { @{Enabled=$false} | ConvertTo-Json -Compress }"
            )
            output = SecurityInfo._run_powershell(ps_registry, timeout=2)
            if output:
                data = json.loads(output)
                if data.get("Enabled", False):
                    return {
                        "enabled": True,
                        "status": "Enabled",
                        "method": "Device Encryption",
                        "detail": "Device Encryption active",
                    }
        except Exception as e:
            logger.debug(f"Registry encryption check failed: {e}")

        # Try Get-BitLockerVolume if admin
        if SecurityInfo._check_admin():
            try:
                ps_cmd = (
                    "try { "
                    "$vol = Get-BitLockerVolume -MountPoint 'C:' -ErrorAction Stop; "
                    "@{Status=$vol.ProtectionStatus.ToString(); Method=$vol.EncryptionMethod.ToString()} | ConvertTo-Json -Compress "
                    "} catch { "
                    "@{Status='NoVolume'; Method='None'; Error=$_.Exception.Message} | ConvertTo-Json -Compress "
                    "}"
                )

                output = SecurityInfo._run_powershell(ps_cmd, timeout=3)
                if output:
                    data = json.loads(output)
                    status = data.get("Status", "Unknown")
                    method = data.get("Method", "None")

                    if status == "On":
                        return {
                            "enabled": True,
                            "status": "Enabled",
                            "method": method,
                            "detail": f"BitLocker ({method})",
                        }
                    if status == "Off":
                        return {
                            "enabled": False,
                            "status": "Not Encrypted",
                            "method": "None",
                            "detail": "BitLocker available but not enabled",
                        }
                    if status == "NoVolume" or "does not have" in data.get("Error", ""):
                        return {
                            "enabled": False,
                            "status": "Not Encrypted",
                            "method": "None",
                            "detail": "Drive not encrypted",
                        }
            except Exception as e:
                logger.debug(f"Could not query BitLocker: {e}")

        # Without admin rights we cannot truthfully call the drive unencrypted.
        if not SecurityInfo._check_admin():
            return {
                "enabled": None,
                "status": "Unknown",
                "method": "Unknown",
                "detail": "Run as administrator to verify BitLocker or device encryption.",
            }

        # Query failed even with admin rights - keep the state honest.
        return {
            "enabled": None,
            "status": "Unknown",
            "method": "Unknown",
            "detail": "Sentinel could not determine disk encryption status.",
        }

    @staticmethod
    def get_windows_update_status() -> dict[str, Any]:
        """Get Windows Update status: last install date and pending updates."""
        result = {
            "status": "Unknown",
            "lastInstallDate": None,
            "pendingUpdates": 0,
            "restartRequired": False,
            "detail": "Unable to determine",
        }

        try:
            # Fast check: Registry-based restart required check
            ps_quick = (
                "$rebootKey = 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired'; "
                "$restartRequired = Test-Path $rebootKey; "
                "@{RestartRequired=$restartRequired} | ConvertTo-Json -Compress"
            )
            quick_output = SecurityInfo._run_powershell(ps_quick, timeout=2)
            if quick_output:
                data = json.loads(quick_output)
                result["restartRequired"] = data.get("RestartRequired", False)

            ps_pending = (
                "$session = New-Object -ComObject Microsoft.Update.Session; "
                "$searcher = $session.CreateUpdateSearcher(); "
                "$count = ($searcher.Search(\"IsInstalled=0 and IsHidden=0\").Updates).Count; "
                "$count"
            )
            pending_output = SecurityInfo._run_powershell(ps_pending, timeout=5)
            if pending_output and pending_output.isdigit():
                result["pendingUpdates"] = int(pending_output)

            # Get last update time (COM object, but with short timeout)
            ps_last_update = (
                "$session = New-Object -ComObject Microsoft.Update.Session; "
                "$searcher = $session.CreateUpdateSearcher(); "
                "$hist = $searcher.GetTotalHistoryCount(); "
                "if ($hist -gt 0) { "
                "  $lastUpdate = $searcher.QueryHistory(0, 1) | Select-Object -First 1; "
                "  if ($lastUpdate) { $lastUpdate.Date.ToString('yyyy-MM-dd HH:mm') } else { 'None' } "
                "} else { 'None' }"
            )
            last_update_output = SecurityInfo._run_powershell(ps_last_update, timeout=5)
            if last_update_output and last_update_output != "None":
                result["lastInstallDate"] = last_update_output

            # Determine overall status based on what we know
            if result["restartRequired"]:
                result["status"] = "RestartRequired"
                result["detail"] = "Restart required to complete updates"
            elif result["pendingUpdates"] > 0:
                result["status"] = "PendingUpdates"
                result["detail"] = f"{result['pendingUpdates']} updates are pending"
            elif result["lastInstallDate"]:
                result["status"] = "UpToDate"
                result["detail"] = f"Last update: {result['lastInstallDate']}"
            else:
                result["status"] = "Unknown"
                result["detail"] = "Could not determine update status"

        except json.JSONDecodeError:
            logger.debug("Failed to parse Windows Update JSON")
        except Exception as e:
            logger.debug(f"Could not query Windows Update: {e}")

        return result

    @staticmethod
    def get_rdp_status() -> dict[str, Any]:
        """Get Remote Desktop status and NLA setting."""
        result = {
            "enabled": None,
            "nlaEnabled": None,
            "status": "Unknown",
            "detail": "Unable to determine",
        }

        try:
            # Check RDP enabled status via registry
            ps_rdp = (
                "$rdpKey = 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server'; "
                "$rdpEnabled = (Get-ItemProperty -Path $rdpKey -Name 'fDenyTSConnections' -ErrorAction SilentlyContinue).fDenyTSConnections; "
                "$nlaKey = 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp'; "
                "$nlaEnabled = (Get-ItemProperty -Path $nlaKey -Name 'UserAuthentication' -ErrorAction SilentlyContinue).UserAuthentication; "
                "@{RdpDisabled=$rdpEnabled; NlaEnabled=$nlaEnabled} | ConvertTo-Json"
            )

            output = SecurityInfo._run_powershell(ps_rdp)
            if output:
                data = json.loads(output)
                # fDenyTSConnections: 0 = RDP enabled, 1 = RDP disabled
                rdp_disabled = data.get("RdpDisabled", 1)
                nla_enabled = data.get("NlaEnabled", 1)

                result["enabled"] = rdp_disabled == 0
                result["nlaEnabled"] = nla_enabled == 1

                if result["enabled"]:
                    result["status"] = "Enabled"
                    if result["nlaEnabled"]:
                        result["detail"] = "RDP enabled with NLA"
                    else:
                        result["detail"] = "RDP enabled, NLA disabled (less secure)"
                else:
                    result["status"] = "Disabled"
                    result["detail"] = "Remote Desktop is disabled"

        except json.JSONDecodeError:
            logger.debug("Failed to parse RDP JSON")
        except Exception as e:
            logger.debug(f"Could not query RDP status: {e}")

        return result

    @staticmethod
    def get_admin_account_count() -> dict[str, Any]:
        """Get count of members in the local Administrators group."""
        result = {"count": None, "status": "Unknown", "detail": "Unable to determine"}

        try:
            ps_admins = (
                "$admins = Get-LocalGroupMember -Group 'Administrators' -ErrorAction SilentlyContinue; "
                "if ($admins) { $admins.Count } else { 0 }"
            )

            output = SecurityInfo._run_powershell(ps_admins)
            if output:
                count = int(output)
                result["count"] = count

                if count <= 2:
                    result["status"] = "Good"
                    result["detail"] = f"{count} admin(s)"
                elif count == 3:
                    result["status"] = "Warning"
                    result["detail"] = f"{count} admins (review recommended)"
                else:
                    result["status"] = "Risk"
                    result["detail"] = f"{count} admins (too many)"

        except (ValueError, TypeError):
            logger.debug("Failed to parse admin count")
        except Exception as e:
            logger.debug(f"Could not query admin count: {e}")

        return result

    @staticmethod
    def get_uac_level() -> dict[str, Any]:
        """Get detailed UAC level (High/Medium/Low/Disabled)."""
        result = {
            "level": "Unknown",
            "status": "Unknown",
            "detail": "Unable to determine",
        }

        try:
            # Query both UAC registry values
            ps_uac = (
                "$regPath = 'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\System'; "
                "$enableLUA = (Get-ItemProperty -Path $regPath -Name 'EnableLUA' -ErrorAction SilentlyContinue).EnableLUA; "
                "$consentAdmin = (Get-ItemProperty -Path $regPath -Name 'ConsentPromptBehaviorAdmin' -ErrorAction SilentlyContinue).ConsentPromptBehaviorAdmin; "
                "$promptOnSecure = (Get-ItemProperty -Path $regPath -Name 'PromptOnSecureDesktop' -ErrorAction SilentlyContinue).PromptOnSecureDesktop; "
                "@{EnableLUA=$enableLUA; ConsentAdmin=$consentAdmin; PromptSecure=$promptOnSecure} | ConvertTo-Json"
            )

            output = SecurityInfo._run_powershell(ps_uac)
            if output:
                data = json.loads(output)
                enable_lua = data.get("EnableLUA", 1)
                consent_admin = data.get("ConsentAdmin", 5)
                prompt_secure = data.get("PromptSecure", 1)

                if enable_lua == 0:
                    result["level"] = "Disabled"
                    result["status"] = "Disabled"
                    result["detail"] = "UAC is completely disabled"
                elif consent_admin == 0:
                    result["level"] = "Low"
                    result["status"] = "Low"
                    result["detail"] = "No prompts for admins"
                elif consent_admin == 5 and prompt_secure == 1:
                    result["level"] = "High"
                    result["status"] = "High"
                    result["detail"] = "Secure desktop prompts"
                elif consent_admin == 5:
                    result["level"] = "Medium"
                    result["status"] = "Medium"
                    result["detail"] = "Prompts without secure desktop"
                else:
                    result["level"] = "Medium"
                    result["status"] = "Medium"
                    result["detail"] = "Custom UAC settings"

        except json.JSONDecodeError:
            logger.debug("Failed to parse UAC JSON")
        except Exception as e:
            logger.debug(f"Could not query UAC level: {e}")

        return result

    @staticmethod
    def get_smartscreen_status() -> dict[str, Any]:
        """Get Windows SmartScreen status."""
        result = {
            "enabled": None,
            "status": "Unknown",
            "detail": "Unable to determine",
        }

        try:
            # Query SmartScreen registry setting
            ps_smartscreen = (
                "$regPath = 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer'; "
                "$smartScreen = (Get-ItemProperty -Path $regPath -Name 'SmartScreenEnabled' -ErrorAction SilentlyContinue).SmartScreenEnabled; "
                "if ($smartScreen -eq $null) { "
                "  $regPath2 = 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\System'; "
                "  $smartScreen = (Get-ItemProperty -Path $regPath2 -Name 'EnableSmartScreen' -ErrorAction SilentlyContinue).EnableSmartScreen; "
                "}; "
                "$smartScreen"
            )

            output = SecurityInfo._run_powershell(ps_smartscreen)
            if output:
                output_lower = output.lower()
                if output_lower in ["on", "requireadmin", "warn", "1", "2"]:
                    result["enabled"] = True
                    result["status"] = "Enabled"
                    result["detail"] = "SmartScreen is protecting your PC"
                elif output_lower in ["off", "0"]:
                    result["enabled"] = False
                    result["status"] = "Disabled"
                    result["detail"] = "SmartScreen protection is off"
                else:
                    result["detail"] = f"Unexpected SmartScreen value: {output}"

        except Exception as e:
            logger.debug(f"Could not query SmartScreen: {e}")

        return result

    @staticmethod
    def get_memory_integrity_status() -> dict[str, Any]:
        """Get Memory Integrity (HVCI) / VBS status."""
        result = {
            "enabled": None,
            "status": "Unknown",
            "vbsEnabled": None,
            "detail": "Unable to determine",
        }

        try:
            # Query Device Guard / VBS status
            ps_hvci = (
                "$vbs = Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\\Microsoft\\Windows\\DeviceGuard -ErrorAction SilentlyContinue; "
                "if ($vbs) { "
                "  @{VBSState=$vbs.VirtualizationBasedSecurityStatus; "
                "    HVCIRunning=($vbs.SecurityServicesRunning -contains 2); "
                "    VBSRunning=($vbs.VirtualizationBasedSecurityStatus -eq 2)} | ConvertTo-Json "
                "} else { "
                "  @{VBSState=0; HVCIRunning=$false; VBSRunning=$false} | ConvertTo-Json "
                "}"
            )

            output = SecurityInfo._run_powershell(ps_hvci)
            if output:
                data = json.loads(output)
                hvci_running = data.get("HVCIRunning", False)
                vbs_running = data.get("VBSRunning", False)

                result["vbsEnabled"] = vbs_running
                result["enabled"] = hvci_running

                if hvci_running:
                    result["status"] = "Enabled"
                    result["detail"] = "Memory Integrity is active"
                elif vbs_running:
                    result["status"] = "Partial"
                    result["detail"] = "VBS enabled, HVCI not running"
                else:
                    result["status"] = "Disabled"
                    result["detail"] = "Memory Integrity is off"

        except json.JSONDecodeError:
            logger.debug("Failed to parse HVCI JSON")
        except Exception as e:
            logger.debug(f"Could not query Memory Integrity: {e}")

        return result

    @staticmethod
    def get_extended_security_status() -> dict[str, Any]:
        """Get all extended security metrics."""
        return {
            "diskEncryption": SecurityInfo.get_disk_encryption_status(),
            "windowsUpdate": SecurityInfo.get_windows_update_status(),
            "remoteDesktop": SecurityInfo.get_rdp_status(),
            "adminAccounts": SecurityInfo.get_admin_account_count(),
            "uacLevel": SecurityInfo.get_uac_level(),
            "smartScreen": SecurityInfo.get_smartscreen_status(),
            "memoryIntegrity": SecurityInfo.get_memory_integrity_status(),
        }

    @staticmethod
    def get_tpm_status() -> dict[str, Any]:
        """Get TPM status using tpmtool (works without admin)."""
        result = {
            "present": None,
            "enabled": None,
            "status": "Unknown",
            "version": "Unknown",
            "detail": "Unable to determine",
        }

        # Use tpmtool - works without admin and is fast
        try:
            proc = subprocess.run(
                ["tpmtool", "getdeviceinformation"],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=_SUBPROCESS_FLAGS,
            )
            if proc.returncode == 0 and proc.stdout:
                output = proc.stdout
                # Parse tpmtool output
                if "-TPM Present: True" in output:
                    result["present"] = True
                    result["enabled"] = True
                    result["status"] = "Present"

                    # Extract version
                    for line in output.splitlines():
                        if "-TPM Version:" in line:
                            version = line.split(":")[-1].strip()
                            result["version"] = version
                            break

                    result["detail"] = f"TPM {result['version']} active"
                elif "-TPM Present: False" in output:
                    result["present"] = False
                    result["enabled"] = False
                    result["status"] = "Not present"
                    result["detail"] = "No TPM hardware found"
                return result
        except FileNotFoundError:
            logger.debug("tpmtool not found, falling back to registry")
        except subprocess.TimeoutExpired:
            logger.debug("tpmtool timed out")
        except Exception as e:
            logger.debug(f"tpmtool failed: {e}")

        # Fallback: Registry check
        try:
            ps_registry = (
                "$result = @{Present=$false}; "
                "if (Test-Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\TPM') { "
                "  $result.Present = $true "
                "}; "
                "$result | ConvertTo-Json -Compress"
            )
            output = SecurityInfo._run_powershell(ps_registry, timeout=2)
            if output:
                data = json.loads(output)
                if data.get("Present", False):
                    result["present"] = True
                    result["enabled"] = True
                    result["version"] = "2.0"  # Assume 2.0 on modern systems
                    result["detail"] = "TPM detected (run as admin for details)"

        except Exception as e:
            logger.debug(f"Registry TPM check failed: {e}")

        return result

    @staticmethod
    def get_simplified_security_status() -> dict[str, Any]:
        """
        Get simplified, user-friendly security status for the UI.
        Returns aggregated status for main categories plus overall health.
        Uses parallel execution for faster results.
        """
        # Check cache first
        now = time.time()
        if (
            SecurityInfo._cache
            and (now - SecurityInfo._cache_time) < SecurityInfo._cache_ttl
        ):
            return SecurityInfo._cache

        # Check if running as admin
        SecurityInfo._check_admin()

        # Run all queries in parallel for speed
        results = {}
        queries = {
            "defender": SecurityInfo.get_windows_defender_status,
            "firewall": SecurityInfo.get_firewall_status,
            "tpm": SecurityInfo.get_tpm_status,
            "disk_enc": SecurityInfo.get_disk_encryption_status,
            "win_update": SecurityInfo.get_windows_update_status,
            "rdp": SecurityInfo.get_rdp_status,
            "admins": SecurityInfo.get_admin_account_count,
            "uac": SecurityInfo.get_uac_level,
            "smartscreen": SecurityInfo.get_smartscreen_status,
            "memory_int": SecurityInfo.get_memory_integrity_status,
        }

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(func): name for name, func in queries.items()}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result(timeout=10)
                except Exception as e:
                    logger.debug(f"Query {name} failed: {e}")
                    results[name] = {}

        defender = results.get("defender", {})
        firewall = results.get("firewall", {})
        tpm = results.get("tpm", {})
        disk_enc = results.get("disk_enc", {})
        win_update = results.get("win_update", {})
        rdp = results.get("rdp", {})
        admins = results.get("admins", {})
        uac = results.get("uac", {})
        smartscreen = results.get("smartscreen", {})
        memory_int = results.get("memory_int", {})

        # Try to get Secure Boot status
        secure_boot_enabled = None
        secure_boot_status = "Unknown"
        try:
            ps_secureboot = "try { Confirm-SecureBootUEFI } catch { 'Error' }"
            output = SecurityInfo._run_powershell(ps_secureboot, timeout=2)
            if output:
                output_lower = output.strip().lower()
                if output_lower == "true":
                    secure_boot_enabled = True
                    secure_boot_status = "Enabled"
                elif output_lower == "false":
                    secure_boot_enabled = False
                    secure_boot_status = "Disabled"
                elif output_lower != "error":
                    secure_boot_status = output.strip()
        except Exception:
            pass

        capabilities = {
            "firewall": True,
            "antivirus": True,
            "secureBoot": secure_boot_enabled is not None,
            "tpm": tpm.get("present") is not None,
            "diskEncryption": disk_enc.get("enabled") is not None,
            "updates": True,
            "remoteDesktop": rdp.get("enabled") is not None,
            "localAdmins": admins.get("count") is not None,
            "uac": uac.get("level", "Unknown") != "Unknown",
            "smartScreen": smartscreen.get("enabled") is not None,
            "memoryIntegrity": memory_int.get("enabled") is not None
            or memory_int.get("status") in {"Enabled", "Disabled", "Partial"},
        }

        # === INTERNET PROTECTION (Firewall + Antivirus) ===
        # Check if data requires admin
        fw_requires_admin = firewall.get("status") == "Requires Admin"
        av_requires_admin = defender.get("status") == "requires_admin"

        fw_on = firewall.get("enabled") if not fw_requires_admin else None
        av_on = defender.get("enabled") if not av_requires_admin else None
        av_realtime = defender.get("realtime_protection")

        # Extract product display names
        av_name = defender.get("name", "") or "Antivirus"
        fw_name = firewall.get("name", "") or "Firewall"

        if fw_requires_admin or av_requires_admin:
            # Cannot determine status without admin rights
            internet_status = "Checking"
            internet_detail = "Run as Administrator for accurate status"
            internet_good = False
            internet_warning = True
        elif fw_on is None or av_on is None:
            unknown_controls = []
            if fw_on is None:
                unknown_controls.append("firewall")
            if av_on is None:
                unknown_controls.append("antivirus")
            internet_status = "Unknown"
            internet_detail = (
                "Sentinel could not verify "
                + " and ".join(unknown_controls)
                + " status."
            )
            internet_good = False
            internet_warning = True
        elif fw_on and av_on:
            internet_status = "On"
            internet_detail = f"{av_name} and {fw_name} running"
            internet_good = True
            internet_warning = False
        elif fw_on or av_on:
            internet_status = "Partially on"
            if fw_on:
                internet_detail = f"{fw_name} on, antivirus off"
            else:
                internet_detail = f"{av_name} on, firewall off"
            internet_good = False
            internet_warning = True
        else:
            internet_status = "Off"
            internet_detail = "Firewall and antivirus are off"
            internet_good = False
            internet_warning = False

        # === UPDATES ===
        update_raw_status = win_update.get("status", "Unknown")
        last_install = win_update.get("lastInstallDate", "")

        # Format last install date nicely
        update_last_str = ""
        update_days_ago = None
        if last_install:
            try:
                from datetime import datetime

                # Parse ISO date
                dt = datetime.fromisoformat(
                    last_install.replace("Z", "+00:00").split("+")[0]
                )
                update_days_ago = (datetime.now() - dt).days
                update_last_str = dt.strftime("%d %b %Y")
            except Exception:
                update_last_str = (
                    last_install[:10] if len(last_install) >= 10 else last_install
                )

        if update_raw_status == "UpToDate":
            updates_status = "Up to date"
            updates_good = True
            updates_warning = False
        elif update_raw_status == "RestartRequired":
            updates_status = "Restart needed"
            updates_good = False
            updates_warning = True
        elif update_raw_status == "PendingUpdates":
            updates_status = "Updates available"
            updates_good = False
            updates_warning = True
        # Check if out of date (>30 days)
        elif update_days_ago is not None and update_days_ago > 30:
            updates_status = "Out of date"
            updates_good = False
            updates_warning = False  # Red
        else:
            updates_status = "Unknown"
            updates_good = False
            updates_warning = True

        updates_detail = (
            f"Last updated: {update_last_str}"
            if update_last_str
            else "Check Windows Update"
        )

        # === DEVICE PROTECTION (TPM + Secure Boot + Disk Encryption) ===
        tpm_present = tpm.get("present")
        tpm_enabled = tpm.get("enabled")
        tpm_version = tpm.get("version", "Unknown")
        disk_enc_on = disk_enc.get("enabled")

        device_parts = []
        unavailable_device_parts = []
        supported_device_checks = 0
        good_device_checks = 0

        has_tpm = tpm_present is True and tpm_enabled is True
        has_secureboot = secure_boot_enabled is True
        has_encryption = disk_enc_on is True

        if capabilities["tpm"]:
            supported_device_checks += 1
            if has_tpm:
                good_device_checks += 1
                device_parts.append(f"TPM {tpm_version}")
            elif tpm_present is True:
                device_parts.append("TPM disabled")
            else:
                device_parts.append("No TPM")
        else:
            unavailable_device_parts.append("TPM")

        if capabilities["secureBoot"]:
            supported_device_checks += 1
            if has_secureboot:
                good_device_checks += 1
                device_parts.append("Secure Boot")
            else:
                device_parts.append("Secure Boot off")
        else:
            unavailable_device_parts.append("Secure Boot")

        if capabilities["diskEncryption"]:
            supported_device_checks += 1
            if has_encryption:
                good_device_checks += 1
                device_parts.append("C: encrypted")
            else:
                device_parts.append("Drive not encrypted")
        else:
            unavailable_device_parts.append("disk encryption")

        if supported_device_checks == 0:
            device_status = "Unavailable"
            device_good = False
            device_warning = True
            device_detail = "Sentinel could not verify any supported device-hardening features on this system."
        elif good_device_checks == supported_device_checks:
            device_status = "Strong"
            device_good = True
            device_warning = False
            device_detail = ", ".join(device_parts) if device_parts else "All verified protections active"
        elif good_device_checks > 0:
            device_status = "Okay"
            device_good = False
            device_warning = True
            device_detail = ", ".join(device_parts) if device_parts else "Partial protection"
        else:
            device_status = "Weak"
            device_good = False
            device_warning = False
            device_detail = ", ".join(device_parts) if device_parts else "Verified device protections are off"

        if unavailable_device_parts:
            suffix = "Additional checks unavailable: " + ", ".join(unavailable_device_parts) + "."
            device_detail = f"{device_detail}. {suffix}" if device_detail else suffix

        # === REMOTE & APPS (RDP + Admins + UAC + SmartScreen) ===
        rdp_on = rdp.get("enabled")
        admin_count = admins.get("count")
        uac_level = uac.get("level", "Unknown")
        smartscreen_on = smartscreen.get("enabled")

        # Count risky conditions
        risky_count = 0
        remote_parts = []
        unavailable_remote_parts = []
        supported_remote_checks = 0

        if capabilities["remoteDesktop"]:
            supported_remote_checks += 1
            if rdp_on is True:
                risky_count += 2  # RDP on is more serious
                remote_parts.append("RDP on")
            else:
                remote_parts.append("RDP off")
        else:
            unavailable_remote_parts.append("Remote Desktop")

        if capabilities["localAdmins"]:
            supported_remote_checks += 1
            remote_parts.append(f"{admin_count} admin{'s' if admin_count != 1 else ''}")
            if admin_count > 2:
                risky_count += 1
        else:
            unavailable_remote_parts.append("local admin count")

        if capabilities["uac"]:
            supported_remote_checks += 1
            if uac_level in ["High", "Medium"]:
                remote_parts.append(f"UAC {uac_level.lower()}")
            elif uac_level == "Disabled":
                risky_count += 2
                remote_parts.append("UAC off")
            elif uac_level == "Low":
                risky_count += 1
                remote_parts.append("UAC low")
        else:
            unavailable_remote_parts.append("UAC")

        if capabilities["smartScreen"]:
            supported_remote_checks += 1
            if smartscreen_on is False:
                risky_count += 1
                remote_parts.append("SmartScreen off")
        else:
            unavailable_remote_parts.append("SmartScreen")

        if supported_remote_checks == 0:
            remote_status = "Unavailable"
            remote_good = False
            remote_warning = True
            remote_detail = "Sentinel could not verify any supported remote access or app hardening checks on this system."
        elif risky_count == 0:
            remote_status = "Safe"
            remote_good = True
            remote_warning = False
        elif risky_count <= 2 and not rdp_on and uac_level != "Disabled":
            remote_status = "Review"
            remote_good = False
            remote_warning = True
        else:
            remote_status = "Risky"
            remote_good = False
            remote_warning = False

        if supported_remote_checks > 0:
            remote_detail = ", ".join(remote_parts)
        if unavailable_remote_parts:
            prefix = "; " if remote_detail else ""
            remote_detail += prefix + "Additional checks unavailable: " + ", ".join(unavailable_remote_parts)

        # === OVERALL STATUS ===
        # Critical: firewall OR antivirus off = At risk
        # Warning: any single category not good = Needs attention
        # Good: all categories good = Protected

        has_unknown = (
            internet_status == "Unknown"
            or updates_status == "Unknown"
            or (supported_device_checks > 0 and device_status == "Unknown")
            or (supported_remote_checks > 0 and remote_status == "Unknown")
        )

        if fw_on is False or av_on is False:
            overall_status = "At risk"
            overall_good = False
            overall_warning = False
            if fw_on is False and av_on is False:
                overall_detail = "Firewall and antivirus are off"
            elif fw_on is False:
                overall_detail = "Firewall is off"
            else:
                overall_detail = "Antivirus is off"
        elif has_unknown:
            overall_status = "Needs attention"
            overall_good = False
            overall_warning = True
            overall_detail = "Some protections could not be verified"
        elif (
            not internet_good
            or not updates_good
            or (supported_device_checks > 0 and not device_good)
            or (supported_remote_checks > 0 and not remote_good)
        ):
            overall_status = "Needs attention"
            overall_good = False
            overall_warning = True
            overall_detail = "Some protections need review"
        else:
            overall_status = "Protected"
            overall_good = True
            overall_warning = False
            overall_detail = "All key protections are on"

        result = {
            # Overall status card
            "overall": {
                "status": overall_status,
                "detail": overall_detail,
                "isGood": overall_good,
                "isWarning": overall_warning,
            },
            # 4 simplified cards
            "internetProtection": {
                "status": internet_status,
                "detail": internet_detail,
                "isGood": internet_good,
                "isWarning": internet_warning,
            },
            "updates": {
                "status": updates_status,
                "detail": updates_detail,
                "isGood": updates_good,
                "isWarning": updates_warning,
            },
            "deviceProtection": {
                "status": device_status,
                "detail": device_detail,
                "isGood": device_good,
                "isWarning": device_warning,
            },
            "remoteAndApps": {
                "status": remote_status,
                "detail": remote_detail,
                "isGood": remote_good,
                "isWarning": remote_warning,
            },
            # TPM details for binding
            "tpm": tpm,
            # Raw data for advanced section
            "raw": {
                "firewallEnabled": fw_on,
                "firewallStatus": (
                    "Requires Admin"
                    if fw_requires_admin
                    else ("Enabled" if fw_on is True else ("Disabled" if fw_on is False else "Unknown"))
                ),
                "firewallName": fw_name,
                "antivirusEnabled": av_on,
                "antivirusStatus": (
                    "Admin required"
                    if av_requires_admin
                    else ("On" if av_on is True else ("Off" if av_on is False else "Unknown"))
                ),
                "antivirusName": av_name,
                "antivirusRealtime": av_realtime,
                "antivirusDetail": defender.get("definition_status", "Unknown"),
                "secureBoot": secure_boot_status,
                "tpmPresent": tpm.get("present"),
                "tpmEnabled": tpm.get("enabled"),
                "tpmVersion": tpm.get("version", "Unknown"),
                "diskEncryption": disk_enc.get("status", "Unknown"),
                "diskEncryptionDetail": disk_enc.get("detail", ""),
                "windowsUpdateStatus": update_raw_status,
                "windowsUpdateLastInstall": last_install,
                "windowsUpdateDetail": win_update.get("detail", ""),
                "remoteDesktopEnabled": rdp_on,
                "remoteDesktopStatus": rdp.get("status", "Unknown"),
                "remoteDesktopDetail": rdp.get("detail", ""),
                "remoteDesktopNla": rdp.get("nlaEnabled"),
                "adminAccountCount": admin_count,
                "adminAccountDetail": admins.get("detail", ""),
                "uacLevel": uac_level,
                "uacDetail": uac.get("detail", ""),
                "smartScreenEnabled": smartscreen_on,
                "smartScreenStatus": smartscreen.get("status", "Unknown"),
                "smartScreenDetail": smartscreen.get("detail", ""),
                "memoryIntegrityEnabled": memory_int.get("enabled"),
                "memoryIntegrityStatus": memory_int.get("status", "Unknown"),
                "memoryIntegrityDetail": memory_int.get("detail", ""),
                "capabilities": capabilities,
            },
        }

        # Cache the result
        SecurityInfo._cache = result
        SecurityInfo._cache_time = time.time()

        return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    status = SecurityInfo.get_all_security_status()
    print("=== Basic Security Status ===")
    print(json.dumps(status, indent=2, default=str))

    print("\n=== Extended Security Status ===")
    extended = SecurityInfo.get_extended_security_status()
    print(json.dumps(extended, indent=2, default=str))

    print("\n=== TPM Status ===")
    tpm = SecurityInfo.get_tpm_status()
    print(json.dumps(tpm, indent=2, default=str))

    print("\n=== Simplified Security Status ===")
    simplified = SecurityInfo.get_simplified_security_status()
    print(json.dumps(simplified, indent=2, default=str))
