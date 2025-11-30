"""Windows Security Status Information."""

import platform
import subprocess
import sys
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Platform detection
_IS_WINDOWS = platform.system() == "Windows"

# Subprocess flags - CREATE_NO_WINDOW only works on Windows
_SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if _IS_WINDOWS else 0


class SecurityInfo:
    """Retrieve Windows security status (Firewall, Antivirus, etc.)"""

    @staticmethod
    def get_windows_defender_status() -> Dict[str, Any]:
        """Get Windows Defender/Microsoft Defender status."""
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
                timeout=5,
            )

            if result.returncode == 0:
                import json

                data = json.loads(result.stdout)
                return {
                    "enabled": data.get("AntivirusEnabled", False),
                    "realtime_protection": data.get("RealTimeProtectionEnabled", False),
                    "last_scan": data.get("LastFullScanTime", "Unknown"),
                    "definition_status": (
                        "Current"
                        if not data.get("SignatureOutofDate", True)
                        else "Outdated"
                    ),
                }
        except subprocess.TimeoutExpired:
            logger.warning("Windows Defender query timed out")
        except (
            subprocess.CalledProcessError,
            json.JSONDecodeError,
            FileNotFoundError,
        ) as e:
            logger.debug(f"Could not query Windows Defender: {e}")

        return {
            "enabled": False,
            "realtime_protection": False,
            "last_scan": "Unknown",
            "definition_status": "Unknown",
        }

    @staticmethod
    def get_firewall_status() -> Dict[str, Any]:
        """Get Windows Firewall status."""
        try:
            # Use PowerShell to query Windows Firewall profiles
            ps_cmd = (
                "Get-NetFirewallProfile | "
                "Select-Object -Property Name, Enabled | "
                "ConvertTo-Json"
            )

            result = subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                import json

                data = json.loads(result.stdout)

                # data is either a single object or list of objects
                if not isinstance(data, list):
                    data = [data]

                # Check if any profile is enabled
                enabled_profiles = [p["Name"] for p in data if p.get("Enabled", False)]

                return {
                    "enabled": len(enabled_profiles) > 0,
                    "enabled_profiles": enabled_profiles,
                    "status": "Active" if enabled_profiles else "Disabled",
                }
        except subprocess.TimeoutExpired:
            logger.warning("Firewall query timed out")
        except (
            subprocess.CalledProcessError,
            json.JSONDecodeError,
            FileNotFoundError,
        ) as e:
            logger.debug(f"Could not query Firewall: {e}")

        return {
            "enabled": False,
            "enabled_profiles": [],
            "status": "Unknown",
        }

    @staticmethod
    def get_uac_status() -> Dict[str, Any]:
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
    def get_all_security_status() -> Dict[str, Any]:
        """Get comprehensive security status."""
        return {
            "defender": SecurityInfo.get_windows_defender_status(),
            "firewall": SecurityInfo.get_firewall_status(),
            "uac": SecurityInfo.get_uac_status(),
        }

    @staticmethod
    def _run_powershell(cmd: str, timeout: int = 10) -> Optional[str]:
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
    def get_disk_encryption_status() -> Dict[str, Any]:
        """Get BitLocker/Device Encryption status for C: drive."""
        try:
            # Query BitLocker status for C: (requires admin)
            ps_cmd = (
                "try { "
                "$vol = Get-BitLockerVolume -MountPoint 'C:' -ErrorAction Stop; "
                "$status = $vol.ProtectionStatus.ToString(); "
                "$encMethod = $vol.EncryptionMethod.ToString(); "
                "@{Status=$status; Method=$encMethod} | ConvertTo-Json "
                "} catch { "
                "@{Status='NotAvailable'; Method='None'} | ConvertTo-Json "
                "}"
            )

            output = SecurityInfo._run_powershell(ps_cmd)
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
                elif status == "Off":
                    return {
                        "enabled": False,
                        "status": "Disabled",
                        "method": "None",
                        "detail": "Not encrypted",
                    }
                elif status != "NotAvailable":
                    return {
                        "enabled": False,
                        "status": status,
                        "method": method,
                        "detail": f"BitLocker: {status}",
                    }
        except json.JSONDecodeError:
            logger.debug("Failed to parse BitLocker JSON response")
        except Exception as e:
            logger.debug(f"Could not query BitLocker: {e}")

        # Fallback: Check via WMI EncryptableVolume (works without admin on some systems)
        try:
            ps_wmi = (
                "try { "
                "$vol = Get-WmiObject -Namespace 'root\\CIMV2\\Security\\MicrosoftVolumeEncryption' "
                "-Class Win32_EncryptableVolume -Filter \"DriveLetter='C:'\" -ErrorAction Stop; "
                "if ($vol) { "
                "  $protectionStatus = $vol.GetProtectionStatus().ProtectionStatus; "
                "  @{Status=if($protectionStatus -eq 1){'On'}elseif($protectionStatus -eq 0){'Off'}else{'Unknown'}; Found=$true} | ConvertTo-Json "
                "} else { @{Found=$false} | ConvertTo-Json } "
                "} catch { @{Found=$false} | ConvertTo-Json }"
            )
            output = SecurityInfo._run_powershell(ps_wmi, timeout=10)
            if output:
                data = json.loads(output)
                if data.get("Found", False):
                    status = data.get("Status", "Unknown")
                    if status == "On":
                        return {
                            "enabled": True,
                            "status": "Enabled",
                            "method": "BitLocker",
                            "detail": "BitLocker active",
                        }
                    elif status == "Off":
                        return {
                            "enabled": False,
                            "status": "Disabled",
                            "method": "None",
                            "detail": "Not encrypted",
                        }
        except Exception as e:
            logger.debug(f"WMI BitLocker fallback failed: {e}")

        # Final fallback: Check registry for Device Encryption
        try:
            ps_registry = (
                "$de = Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\DeviceEncryption' -ErrorAction SilentlyContinue; "
                "if ($de -and $de.BitLockerEnabled -eq 1) { @{Enabled=$true} | ConvertTo-Json } "
                "else { @{Enabled=$false} | ConvertTo-Json }"
            )
            output = SecurityInfo._run_powershell(ps_registry, timeout=5)
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

        return {
            "enabled": False,
            "status": "NotAvailable",
            "method": "None",
            "detail": "BitLocker not available (run as admin)",
        }

    @staticmethod
    def get_windows_update_status() -> Dict[str, Any]:
        """Get Windows Update status: last install date and pending updates."""
        result = {
            "status": "Unknown",
            "lastInstallDate": None,
            "pendingUpdates": 0,
            "restartRequired": False,
            "detail": "Unable to determine",
        }

        try:
            # Get last update install time
            ps_last_update = (
                "$session = New-Object -ComObject Microsoft.Update.Session; "
                "$searcher = $session.CreateUpdateSearcher(); "
                "$hist = $searcher.GetTotalHistoryCount(); "
                "if ($hist -gt 0) { "
                "  $lastUpdate = $searcher.QueryHistory(0, 1) | Select-Object -First 1; "
                "  if ($lastUpdate) { $lastUpdate.Date.ToString('o') } else { 'None' } "
                "} else { 'None' }"
            )

            last_update_output = SecurityInfo._run_powershell(
                ps_last_update, timeout=15
            )
            if last_update_output and last_update_output != "None":
                try:
                    # Parse ISO format date
                    result["lastInstallDate"] = last_update_output.split(".")[
                        0
                    ]  # Remove milliseconds
                except Exception:
                    result["lastInstallDate"] = last_update_output

            # Check for pending updates and restart required
            ps_pending = (
                "$updateSession = New-Object -ComObject Microsoft.Update.Session; "
                "$updateSearcher = $updateSession.CreateUpdateSearcher(); "
                "try { "
                "  $searchResult = $updateSearcher.Search('IsInstalled=0 and Type=\"Software\"'); "
                "  $pendingCount = $searchResult.Updates.Count; "
                "} catch { $pendingCount = 0 }; "
                "$rebootKey = 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired'; "
                "$restartRequired = Test-Path $rebootKey; "
                "@{Pending=$pendingCount; RestartRequired=$restartRequired} | ConvertTo-Json"
            )

            pending_output = SecurityInfo._run_powershell(ps_pending, timeout=30)
            if pending_output:
                data = json.loads(pending_output)
                result["pendingUpdates"] = data.get("Pending", 0)
                result["restartRequired"] = data.get("RestartRequired", False)

            # Determine overall status
            if result["restartRequired"]:
                result["status"] = "RestartRequired"
                result["detail"] = "Restart required to complete updates"
            elif result["pendingUpdates"] > 0:
                result["status"] = "PendingUpdates"
                result["detail"] = f"{result['pendingUpdates']} update(s) pending"
            else:
                result["status"] = "UpToDate"
                result["detail"] = "System is up to date"

        except json.JSONDecodeError:
            logger.debug("Failed to parse Windows Update JSON")
        except Exception as e:
            logger.debug(f"Could not query Windows Update: {e}")

        return result

    @staticmethod
    def get_rdp_status() -> Dict[str, Any]:
        """Get Remote Desktop status and NLA setting."""
        result = {
            "enabled": False,
            "nlaEnabled": True,
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
    def get_admin_account_count() -> Dict[str, Any]:
        """Get count of members in the local Administrators group."""
        result = {"count": 0, "status": "Unknown", "detail": "Unable to determine"}

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
    def get_uac_level() -> Dict[str, Any]:
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
    def get_smartscreen_status() -> Dict[str, Any]:
        """Get Windows SmartScreen status."""
        result = {
            "enabled": False,
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
                    # Default to enabled if we can't determine
                    result["enabled"] = True
                    result["status"] = "Enabled"
                    result["detail"] = "SmartScreen appears to be active"
            else:
                # If no output, try alternate check via Defender settings
                result["enabled"] = True
                result["status"] = "Enabled"
                result["detail"] = "Default SmartScreen (assumed)"

        except Exception as e:
            logger.debug(f"Could not query SmartScreen: {e}")

        return result

    @staticmethod
    def get_memory_integrity_status() -> Dict[str, Any]:
        """Get Memory Integrity (HVCI) / VBS status."""
        result = {
            "enabled": False,
            "status": "Unknown",
            "vbsEnabled": False,
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
    def get_extended_security_status() -> Dict[str, Any]:
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
    def get_tpm_status() -> Dict[str, Any]:
        """Get detailed TPM status using Get-Tpm with WMI fallback."""
        result = {
            "present": False,
            "enabled": False,
            "version": "Unknown",
            "detail": "Unable to determine",
        }

        try:
            # Primary method: Get-Tpm cmdlet (requires admin, but often works)
            ps_tpm = "Get-Tpm | ConvertTo-Json -Compress"
            output = SecurityInfo._run_powershell(ps_tpm, timeout=10)

            if output:
                data = json.loads(output)
                tpm_present = data.get("TpmPresent", False)
                tpm_ready = data.get("TpmReady", False)
                tpm_enabled = data.get("TpmEnabled", tpm_ready)

                result["present"] = tpm_present
                result["enabled"] = tpm_enabled

                # Try to get version from ManufacturerVersionFull20 or similar
                spec_version = data.get("ManufacturerVersionFull20", "")
                if not spec_version:
                    # Check for SpecVersion in different format
                    spec_version = str(data.get("ManufacturerVersion", ""))

                # Determine TPM version (1.2 or 2.0)
                if tpm_present:
                    # Check if it's TPM 2.0 by looking at various indicators
                    manufacturer_version = str(
                        data.get("ManufacturerVersionFull20", "")
                    )
                    if manufacturer_version or "2.0" in str(data):
                        result["version"] = "2.0"
                    else:
                        # Try to detect from other fields
                        result["version"] = "2.0"  # Most modern systems have 2.0

                    if tpm_enabled:
                        result["detail"] = f"TPM {result['version']} active"
                    else:
                        result["detail"] = (
                            f"TPM {result['version']} present but not enabled"
                        )
                else:
                    result["version"] = "Not present"
                    result["detail"] = "No TPM detected"

                return result

        except json.JSONDecodeError:
            logger.debug("Failed to parse Get-Tpm JSON, trying WMI fallback")
        except Exception as e:
            logger.debug(f"Get-Tpm failed: {e}, trying WMI fallback")

        # Fallback: WMI method
        try:
            ps_wmi = (
                "$tpm = Get-WmiObject -Namespace 'root\\CIMV2\\Security\\MicrosoftTpm' "
                "-Class Win32_Tpm -ErrorAction SilentlyContinue | Select-Object -First 1; "
                "if ($tpm) { "
                "  @{IsEnabled=$tpm.IsEnabled_InitialValue; "
                "    IsActivated=$tpm.IsActivated_InitialValue; "
                "    SpecVersion=$tpm.SpecVersion; "
                "    Present=$true} | ConvertTo-Json "
                "} else { "
                "  @{Present=$false} | ConvertTo-Json "
                "}"
            )

            output = SecurityInfo._run_powershell(ps_wmi, timeout=10)
            if output:
                data = json.loads(output)
                tpm_present = data.get("Present", False)

                if tpm_present:
                    result["present"] = True
                    result["enabled"] = data.get("IsEnabled", False) or data.get(
                        "IsActivated", False
                    )

                    # Parse spec version (e.g., "1.2, 2.0" or "2.0")
                    spec_version = data.get("SpecVersion", "")
                    if spec_version:
                        # Take the highest version if multiple
                        if "2.0" in spec_version:
                            result["version"] = "2.0"
                        elif "1.2" in spec_version:
                            result["version"] = "1.2"
                        else:
                            result["version"] = spec_version.split(",")[0].strip()
                    else:
                        result["version"] = "Unknown"

                    if result["enabled"]:
                        result["detail"] = f"TPM {result['version']} active"
                    else:
                        result["detail"] = (
                            f"TPM {result['version']} present but disabled"
                        )
                else:
                    result["present"] = False
                    result["version"] = "Not present"
                    result["detail"] = "No TPM hardware found"

        except json.JSONDecodeError:
            logger.debug("Failed to parse WMI TPM JSON")
        except Exception as e:
            logger.debug(f"WMI TPM query failed: {e}")

        # Final fallback: Registry-based detection (works without admin)
        if not result["present"]:
            try:
                ps_registry = (
                    "if (Test-Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\TPM') { "
                    "  $svc = Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\TPM' -ErrorAction SilentlyContinue; "
                    "  $devNode = Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Enum\\ROOT\\TPM\\0000' -ErrorAction SilentlyContinue; "
                    "  @{Present=$true; ServiceStart=$svc.Start; DeviceDesc=$devNode.DeviceDesc} | ConvertTo-Json "
                    "} else { @{Present=$false} | ConvertTo-Json }"
                )
                output = SecurityInfo._run_powershell(ps_registry, timeout=5)
                if output:
                    data = json.loads(output)
                    if data.get("Present", False):
                        result["present"] = True
                        # Service Start=3 means manual start (TPM is present but we can't query enabled state)
                        # Check if device description contains TPM info
                        device_desc = data.get("DeviceDesc", "")
                        if "2.0" in device_desc:
                            result["version"] = "2.0"
                        elif "1.2" in device_desc:
                            result["version"] = "1.2"
                        else:
                            result["version"] = "2.0"  # Assume 2.0 on modern systems

                        # We can't determine enabled state without admin, assume enabled if service exists
                        result["enabled"] = True
                        result["detail"] = (
                            f"TPM {result['version']} detected (run as admin for details)"
                        )

            except Exception as e:
                logger.debug(f"Registry TPM detection failed: {e}")

        return result

    @staticmethod
    def get_simplified_security_status() -> Dict[str, Any]:
        """
        Get simplified, user-friendly security status for the UI.
        Returns aggregated status for main categories plus overall health.
        """
        # Gather all raw data
        defender = SecurityInfo.get_windows_defender_status()
        firewall = SecurityInfo.get_firewall_status()
        tpm = SecurityInfo.get_tpm_status()
        disk_enc = SecurityInfo.get_disk_encryption_status()
        win_update = SecurityInfo.get_windows_update_status()
        rdp = SecurityInfo.get_rdp_status()
        admins = SecurityInfo.get_admin_account_count()
        uac = SecurityInfo.get_uac_level()
        smartscreen = SecurityInfo.get_smartscreen_status()
        memory_int = SecurityInfo.get_memory_integrity_status()

        # Try to get Secure Boot status
        secure_boot_enabled = False
        secure_boot_status = "N/A"
        try:
            ps_secureboot = "try { Confirm-SecureBootUEFI } catch { 'Error' }"
            output = SecurityInfo._run_powershell(ps_secureboot, timeout=5)
            if output:
                output_lower = output.strip().lower()
                if output_lower == "true":
                    secure_boot_enabled = True
                    secure_boot_status = "Enabled"
                elif output_lower == "false":
                    secure_boot_status = "Disabled"
        except Exception:
            pass

        # === INTERNET PROTECTION (Firewall + Antivirus) ===
        fw_on = firewall.get("enabled", False)
        av_on = defender.get("enabled", False)

        if fw_on and av_on:
            internet_status = "On"
            internet_detail = "Firewall and antivirus running"
            internet_good = True
            internet_warning = False
        elif fw_on or av_on:
            internet_status = "Partially on"
            if fw_on:
                internet_detail = "Firewall on, antivirus off"
            else:
                internet_detail = "Antivirus on, firewall off"
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
        else:
            # Check if out of date (>30 days)
            if update_days_ago is not None and update_days_ago > 30:
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
        tpm_present = tpm.get("present", False)
        tpm_enabled = tpm.get("enabled", False)
        tpm_version = tpm.get("version", "Unknown")
        disk_enc_on = disk_enc.get("enabled", False)

        device_parts = []
        if tpm_present and tpm_enabled:
            device_parts.append(f"TPM {tpm_version}")
        elif tpm_present:
            device_parts.append("TPM (disabled)")

        if secure_boot_enabled:
            device_parts.append("Secure Boot")

        if disk_enc_on:
            device_parts.append("C: encrypted")

        # Determine device protection level
        has_tpm = tpm_present and tpm_enabled
        has_secureboot = secure_boot_enabled
        has_encryption = disk_enc_on

        if has_tpm and has_secureboot and has_encryption:
            device_status = "Strong"
            device_good = True
            device_warning = False
            device_detail = (
                ", ".join(device_parts) if device_parts else "All protections active"
            )
        elif (
            (has_tpm and has_secureboot)
            or (has_tpm and has_encryption)
            or (has_secureboot and has_encryption)
        ):
            device_status = "Okay"
            device_good = False
            device_warning = True
            missing = []
            if not has_encryption:
                missing.append("no encryption")
            if not has_tpm:
                missing.append("no TPM")
            if not has_secureboot:
                missing.append("Secure Boot off")
            device_detail = (
                ", ".join(device_parts) if device_parts else "Partial protection"
            )
            if missing:
                device_detail += f" ({', '.join(missing)})"
        elif has_tpm or has_secureboot:
            device_status = "Okay"
            device_good = False
            device_warning = True
            device_detail = (
                ", ".join(device_parts) if device_parts else "Limited protection"
            )
        else:
            device_status = "Weak"
            device_good = False
            device_warning = False
            device_detail = "TPM and Secure Boot not enabled"

        # === REMOTE & APPS (RDP + Admins + UAC + SmartScreen) ===
        rdp_on = rdp.get("enabled", False)
        admin_count = admins.get("count", 0)
        uac_level = uac.get("level", "Unknown")
        smartscreen_on = smartscreen.get("enabled", True)

        # Count risky conditions
        risky_count = 0
        remote_parts = []

        if rdp_on:
            risky_count += 2  # RDP on is more serious
            remote_parts.append("RDP on")
        else:
            remote_parts.append("RDP off")

        remote_parts.append(f"{admin_count} admin{'s' if admin_count != 1 else ''}")
        if admin_count > 2:
            risky_count += 1

        if uac_level in ["High", "Medium"]:
            remote_parts.append(f"UAC {uac_level.lower()}")
        elif uac_level == "Disabled":
            risky_count += 2
            remote_parts.append("UAC off")
        elif uac_level == "Low":
            risky_count += 1
            remote_parts.append("UAC low")

        if not smartscreen_on:
            risky_count += 1

        if risky_count == 0:
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

        remote_detail = ", ".join(remote_parts)

        # === OVERALL STATUS ===
        # Critical: firewall OR antivirus off = At risk
        # Warning: any single category not good = Needs attention
        # Good: all categories good = Protected

        if not fw_on or not av_on:
            overall_status = "At risk"
            overall_good = False
            overall_warning = False
            if not fw_on and not av_on:
                overall_detail = "Firewall and antivirus are off"
            elif not fw_on:
                overall_detail = "Firewall is off"
            else:
                overall_detail = "Antivirus is off"
        elif (
            not internet_good or not updates_good or not device_good or not remote_good
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

        return {
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
                "antivirusEnabled": av_on,
                "antivirusRealtime": defender.get("realtime_protection", False),
                "secureBoot": secure_boot_status,
                "tpmPresent": tpm.get("present", False),
                "tpmEnabled": tpm.get("enabled", False),
                "tpmVersion": tpm.get("version", "Unknown"),
                "diskEncryption": disk_enc.get("status", "Unknown"),
                "diskEncryptionDetail": disk_enc.get("detail", ""),
                "windowsUpdateStatus": update_raw_status,
                "windowsUpdateLastInstall": last_install,
                "remoteDesktopEnabled": rdp_on,
                "remoteDesktopNla": rdp.get("nlaEnabled", True),
                "adminAccountCount": admin_count,
                "uacLevel": uac_level,
                "smartScreenEnabled": smartscreen_on,
                "memoryIntegrityEnabled": memory_int.get("enabled", False),
            },
        }


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
