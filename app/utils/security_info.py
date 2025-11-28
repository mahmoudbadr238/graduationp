"""Windows Security Status Information."""

import subprocess
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


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
                    "definition_status": "Current" if not data.get("SignatureOutofDate", True) else "Outdated",
                }
        except subprocess.TimeoutExpired:
            logger.warning("Windows Defender query timed out")
        except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
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
        except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    status = SecurityInfo.get_all_security_status()
    import json
    print(json.dumps(status, indent=2, default=str))
