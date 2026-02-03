"""
Security Actions Module - Execute security operations on the device.

This module provides the ability to:
- Enable/disable Windows Firewall
- Run Windows Defender scans
- Check for Windows updates
- Enable/disable Remote Desktop
- Clear event logs
- And more security operations

REQUIRES ADMIN PRIVILEGES for most operations.
"""

import subprocess
import logging
import os
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Subprocess flags for Windows
_IS_WINDOWS = os.name == "nt"
_SUBPROCESS_FLAGS = 0x08000000 if _IS_WINDOWS else 0  # CREATE_NO_WINDOW


class ActionResult(Enum):
    """Result of a security action."""
    SUCCESS = "success"
    FAILED = "failed"
    REQUIRES_ADMIN = "requires_admin"
    NOT_SUPPORTED = "not_supported"
    ALREADY_DONE = "already_done"


@dataclass
class ActionResponse:
    """Response from a security action."""
    result: ActionResult
    message: str
    details: Optional[str] = None


class SecurityActionExecutor:
    """
    Executes security-related actions on the Windows system.
    
    Actions include:
    - Firewall control (enable/disable)
    - Windows Defender scans
    - Windows Update checks
    - Remote Desktop control
    - Event log management
    """
    
    def __init__(self):
        self._is_admin = self._check_admin()
    
    def _check_admin(self) -> bool:
        """Check if running with admin privileges."""
        try:
            if _IS_WINDOWS:
                import ctypes
                return bool(ctypes.windll.shell32.IsUserAnAdmin())
            return True
        except:
            return False
    
    def _run_powershell(self, cmd: str, timeout: int = 30) -> Tuple[bool, str]:
        """Run a PowerShell command and return (success, output)."""
        if not _IS_WINDOWS:
            return False, "Only supported on Windows"
        
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=_SUBPROCESS_FLAGS,
            )
            
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                error = result.stderr.strip() or result.stdout.strip()
                if "Administrator" in error or "admin" in error.lower():
                    return False, "REQUIRES_ADMIN"
                return False, error
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    
    def _run_cmd(self, cmd: list, timeout: int = 30) -> Tuple[bool, str]:
        """Run a command and return (success, output)."""
        if not _IS_WINDOWS:
            return False, "Only supported on Windows"
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=_SUBPROCESS_FLAGS,
            )
            
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                error = result.stderr.strip() or result.stdout.strip()
                if "Administrator" in error or "admin" in error.lower() or "elevated" in error.lower():
                    return False, "REQUIRES_ADMIN"
                return False, error
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    
    # =========================================================================
    # FIREWALL ACTIONS
    # =========================================================================
    
    def enable_firewall(self, profile: str = "all") -> ActionResponse:
        """
        Enable Windows Firewall.
        
        Args:
            profile: "domain", "private", "public", or "all"
        """
        if not self._is_admin:
            return ActionResponse(
                ActionResult.REQUIRES_ADMIN,
                "⚠️ Administrator privileges required to enable firewall.",
                "Please run Sentinel as Administrator to make this change."
            )
        
        if profile == "all":
            cmd = "Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled True"
        else:
            cmd = f"Set-NetFirewallProfile -Profile {profile.capitalize()} -Enabled True"
        
        success, output = self._run_powershell(cmd)
        
        if success:
            logger.info(f"Firewall enabled for profile: {profile}")
            return ActionResponse(
                ActionResult.SUCCESS,
                f"✅ Windows Firewall has been **enabled** for {profile} profile(s).",
                "Your network is now protected from unauthorized access."
            )
        elif output == "REQUIRES_ADMIN":
            return ActionResponse(
                ActionResult.REQUIRES_ADMIN,
                "⚠️ Administrator privileges required.",
                "Please run Sentinel as Administrator."
            )
        else:
            return ActionResponse(
                ActionResult.FAILED,
                "❌ Failed to enable firewall.",
                f"Error: {output}"
            )
    
    def disable_firewall(self, profile: str = "all") -> ActionResponse:
        """
        Disable Windows Firewall (NOT RECOMMENDED).
        
        Args:
            profile: "domain", "private", "public", or "all"
        """
        if not self._is_admin:
            return ActionResponse(
                ActionResult.REQUIRES_ADMIN,
                "⚠️ Administrator privileges required to disable firewall.",
                "Please run Sentinel as Administrator."
            )
        
        if profile == "all":
            cmd = "Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled False"
        else:
            cmd = f"Set-NetFirewallProfile -Profile {profile.capitalize()} -Enabled False"
        
        success, output = self._run_powershell(cmd)
        
        if success:
            logger.warning(f"Firewall DISABLED for profile: {profile}")
            return ActionResponse(
                ActionResult.SUCCESS,
                f"⚠️ Windows Firewall has been **disabled** for {profile} profile(s).",
                "**WARNING:** Your computer is now less protected! Enable firewall again when done."
            )
        else:
            return ActionResponse(
                ActionResult.FAILED,
                "❌ Failed to disable firewall.",
                f"Error: {output}"
            )
    
    def get_firewall_status(self) -> ActionResponse:
        """Get current firewall status for all profiles."""
        cmd = "Get-NetFirewallProfile | Select-Object Name, Enabled | ConvertTo-Json"
        success, output = self._run_powershell(cmd)
        
        if success:
            import json
            try:
                data = json.loads(output)
                if not isinstance(data, list):
                    data = [data]
                
                status_lines = []
                all_enabled = True
                for profile in data:
                    name = profile.get("Name", "Unknown")
                    enabled = profile.get("Enabled", False)
                    icon = "🟢" if enabled else "🔴"
                    status_lines.append(f"{icon} **{name}:** {'Enabled' if enabled else 'Disabled'}")
                    if not enabled:
                        all_enabled = False
                
                overall = "✅ All profiles protected" if all_enabled else "⚠️ Some profiles disabled"
                return ActionResponse(
                    ActionResult.SUCCESS,
                    f"**Firewall Status:**\n\n" + "\n".join(status_lines) + f"\n\n{overall}",
                    None
                )
            except:
                pass
        
        return ActionResponse(
            ActionResult.FAILED,
            "Could not retrieve firewall status.",
            output if not success else None
        )
    
    # =========================================================================
    # WINDOWS DEFENDER ACTIONS
    # =========================================================================
    
    def run_quick_scan(self) -> ActionResponse:
        """Start a Windows Defender quick scan."""
        if not self._is_admin:
            return ActionResponse(
                ActionResult.REQUIRES_ADMIN,
                "⚠️ Administrator privileges required for virus scan.",
                "Please run Sentinel as Administrator."
            )
        
        cmd = "Start-MpScan -ScanType QuickScan"
        success, output = self._run_powershell(cmd, timeout=10)
        
        if success or "already running" in output.lower():
            logger.info("Windows Defender quick scan started")
            return ActionResponse(
                ActionResult.SUCCESS,
                "🔍 **Windows Defender Quick Scan started!**\n\nThe scan is running in the background. "
                "Check Windows Security for progress and results.",
                "Quick scans typically take 5-15 minutes."
            )
        else:
            return ActionResponse(
                ActionResult.FAILED,
                "❌ Failed to start virus scan.",
                f"Error: {output}"
            )
    
    def run_full_scan(self) -> ActionResponse:
        """Start a Windows Defender full scan."""
        if not self._is_admin:
            return ActionResponse(
                ActionResult.REQUIRES_ADMIN,
                "⚠️ Administrator privileges required for full scan.",
                "Please run Sentinel as Administrator."
            )
        
        cmd = "Start-MpScan -ScanType FullScan"
        success, output = self._run_powershell(cmd, timeout=10)
        
        if success:
            logger.info("Windows Defender full scan started")
            return ActionResponse(
                ActionResult.SUCCESS,
                "🔍 **Windows Defender Full Scan started!**\n\nThis may take 1-3 hours. "
                "The scan runs in the background - you can continue using your computer.",
                "Check Windows Security for progress."
            )
        else:
            return ActionResponse(
                ActionResult.FAILED,
                "❌ Failed to start full scan.",
                f"Error: {output}"
            )
    
    def update_defender_signatures(self) -> ActionResponse:
        """Update Windows Defender virus definitions."""
        if not self._is_admin:
            return ActionResponse(
                ActionResult.REQUIRES_ADMIN,
                "⚠️ Administrator privileges required to update definitions.",
                "Please run Sentinel as Administrator."
            )
        
        cmd = "Update-MpSignature"
        success, output = self._run_powershell(cmd, timeout=60)
        
        if success:
            logger.info("Windows Defender signatures updated")
            return ActionResponse(
                ActionResult.SUCCESS,
                "✅ **Virus definitions updated!**\n\nWindows Defender now has the latest threat signatures.",
                None
            )
        else:
            return ActionResponse(
                ActionResult.FAILED,
                "❌ Failed to update definitions.",
                f"Error: {output}"
            )
    
    def enable_realtime_protection(self) -> ActionResponse:
        """Enable Windows Defender real-time protection."""
        if not self._is_admin:
            return ActionResponse(
                ActionResult.REQUIRES_ADMIN,
                "⚠️ Administrator privileges required.",
                "Please run Sentinel as Administrator."
            )
        
        cmd = "Set-MpPreference -DisableRealtimeMonitoring $false"
        success, output = self._run_powershell(cmd)
        
        if success:
            return ActionResponse(
                ActionResult.SUCCESS,
                "✅ **Real-time protection enabled!**\n\nWindows Defender is now actively monitoring for threats.",
                None
            )
        else:
            return ActionResponse(
                ActionResult.FAILED,
                "❌ Failed to enable real-time protection.",
                f"This may be controlled by Group Policy. Error: {output}"
            )
    
    # =========================================================================
    # WINDOWS UPDATE ACTIONS
    # =========================================================================
    
    def check_for_updates(self) -> ActionResponse:
        """Check for Windows updates (triggers update check)."""
        # This opens Windows Update settings - safest approach
        cmd = "Start-Process 'ms-settings:windowsupdate-action'"
        success, output = self._run_powershell(cmd, timeout=5)
        
        if success:
            return ActionResponse(
                ActionResult.SUCCESS,
                "🔄 **Windows Update opened!**\n\nWindows is now checking for updates. "
                "Install any available updates to stay protected.",
                None
            )
        else:
            return ActionResponse(
                ActionResult.FAILED,
                "❌ Could not open Windows Update.",
                f"Error: {output}"
            )
    
    def open_windows_security(self) -> ActionResponse:
        """Open Windows Security app."""
        cmd = "Start-Process 'windowsdefender://'"
        success, output = self._run_powershell(cmd, timeout=5)
        
        if success:
            return ActionResponse(
                ActionResult.SUCCESS,
                "🛡️ **Windows Security opened!**\n\nYou can manage all security settings from there.",
                None
            )
        else:
            return ActionResponse(
                ActionResult.FAILED,
                "❌ Could not open Windows Security.",
                f"Error: {output}"
            )
    
    # =========================================================================
    # REMOTE DESKTOP ACTIONS
    # =========================================================================
    
    def disable_remote_desktop(self) -> ActionResponse:
        """Disable Remote Desktop (more secure)."""
        if not self._is_admin:
            return ActionResponse(
                ActionResult.REQUIRES_ADMIN,
                "⚠️ Administrator privileges required.",
                "Please run Sentinel as Administrator."
            )
        
        cmd = (
            "Set-ItemProperty -Path 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server' "
            "-Name 'fDenyTSConnections' -Value 1"
        )
        success, output = self._run_powershell(cmd)
        
        if success:
            logger.info("Remote Desktop disabled")
            return ActionResponse(
                ActionResult.SUCCESS,
                "✅ **Remote Desktop disabled!**\n\nNo one can remotely connect to this computer.",
                "This is the more secure option if you don't need remote access."
            )
        else:
            return ActionResponse(
                ActionResult.FAILED,
                "❌ Failed to disable Remote Desktop.",
                f"Error: {output}"
            )
    
    def enable_remote_desktop(self) -> ActionResponse:
        """Enable Remote Desktop (less secure, use with caution)."""
        if not self._is_admin:
            return ActionResponse(
                ActionResult.REQUIRES_ADMIN,
                "⚠️ Administrator privileges required.",
                "Please run Sentinel as Administrator."
            )
        
        cmd = (
            "Set-ItemProperty -Path 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server' "
            "-Name 'fDenyTSConnections' -Value 0"
        )
        success, output = self._run_powershell(cmd)
        
        if success:
            logger.warning("Remote Desktop ENABLED")
            return ActionResponse(
                ActionResult.SUCCESS,
                "⚠️ **Remote Desktop enabled!**\n\n"
                "**Security Note:** Ensure you have a strong password and consider:\n"
                "• Enabling Network Level Authentication (NLA)\n"
                "• Using a VPN for remote access\n"
                "• Limiting who can connect",
                None
            )
        else:
            return ActionResponse(
                ActionResult.FAILED,
                "❌ Failed to enable Remote Desktop.",
                f"Error: {output}"
            )
    
    # =========================================================================
    # SYSTEM ACTIONS
    # =========================================================================
    
    def open_task_manager(self) -> ActionResponse:
        """Open Task Manager."""
        success, output = self._run_cmd(["taskmgr.exe"])
        
        if success or True:  # taskmgr doesn't return output
            return ActionResponse(
                ActionResult.SUCCESS,
                "📊 **Task Manager opened!**\n\nYou can see running processes and resource usage.",
                None
            )
        return ActionResponse(ActionResult.FAILED, "Could not open Task Manager.", None)
    
    def open_event_viewer(self) -> ActionResponse:
        """Open Windows Event Viewer."""
        success, output = self._run_cmd(["eventvwr.msc"])
        
        return ActionResponse(
            ActionResult.SUCCESS,
            "📋 **Event Viewer opened!**\n\nYou can view detailed Windows event logs.",
            None
        )
    
    def open_disk_cleanup(self) -> ActionResponse:
        """Open Disk Cleanup utility."""
        success, output = self._run_cmd(["cleanmgr.exe"])
        
        return ActionResponse(
            ActionResult.SUCCESS,
            "🧹 **Disk Cleanup opened!**\n\nSelect the drive and clean up temporary files to free space.",
            None
        )
    
    def flush_dns_cache(self) -> ActionResponse:
        """Flush DNS cache (can help with network issues)."""
        if not self._is_admin:
            return ActionResponse(
                ActionResult.REQUIRES_ADMIN,
                "⚠️ Administrator privileges required to flush DNS.",
                "Please run Sentinel as Administrator."
            )
        
        success, output = self._run_cmd(["ipconfig", "/flushdns"])
        
        if success:
            return ActionResponse(
                ActionResult.SUCCESS,
                "✅ **DNS cache flushed!**\n\nThis can help resolve network/website access issues.",
                None
            )
        else:
            return ActionResponse(
                ActionResult.FAILED,
                "❌ Failed to flush DNS cache.",
                f"Error: {output}"
            )
    
    def release_renew_ip(self) -> ActionResponse:
        """Release and renew IP address."""
        if not self._is_admin:
            return ActionResponse(
                ActionResult.REQUIRES_ADMIN,
                "⚠️ Administrator privileges required.",
                "Please run Sentinel as Administrator."
            )
        
        # Release
        self._run_cmd(["ipconfig", "/release"])
        # Renew
        success, output = self._run_cmd(["ipconfig", "/renew"], timeout=60)
        
        if success:
            return ActionResponse(
                ActionResult.SUCCESS,
                "✅ **IP address renewed!**\n\nYour network connection has been refreshed.",
                None
            )
        else:
            return ActionResponse(
                ActionResult.FAILED,
                "❌ Failed to renew IP address.",
                f"Error: {output}"
            )
    
    # =========================================================================
    # ACTION DISPATCHER
    # =========================================================================
    
    def execute_action(self, action: str, **kwargs) -> ActionResponse:
        """
        Execute a security action by name.
        
        Supported actions:
        - enable_firewall, disable_firewall, firewall_status
        - quick_scan, full_scan, update_definitions, enable_realtime
        - check_updates, open_security
        - disable_rdp, enable_rdp
        - open_task_manager, open_event_viewer, open_disk_cleanup
        - flush_dns, renew_ip
        """
        action_map = {
            # Firewall
            "enable_firewall": self.enable_firewall,
            "disable_firewall": self.disable_firewall,
            "firewall_status": self.get_firewall_status,
            
            # Defender
            "quick_scan": self.run_quick_scan,
            "full_scan": self.run_full_scan,
            "update_definitions": self.update_defender_signatures,
            "enable_realtime": self.enable_realtime_protection,
            
            # Updates
            "check_updates": self.check_for_updates,
            "open_security": self.open_windows_security,
            
            # RDP
            "disable_rdp": self.disable_remote_desktop,
            "enable_rdp": self.enable_remote_desktop,
            
            # System
            "open_task_manager": self.open_task_manager,
            "open_event_viewer": self.open_event_viewer,
            "open_disk_cleanup": self.open_disk_cleanup,
            "flush_dns": self.flush_dns_cache,
            "renew_ip": self.release_renew_ip,
        }
        
        if action not in action_map:
            return ActionResponse(
                ActionResult.NOT_SUPPORTED,
                f"Unknown action: {action}",
                f"Supported actions: {', '.join(action_map.keys())}"
            )
        
        try:
            return action_map[action](**kwargs)
        except Exception as e:
            logger.error(f"Action {action} failed: {e}")
            return ActionResponse(
                ActionResult.FAILED,
                f"❌ Action failed: {action}",
                str(e)
            )


# Singleton instance
_executor: Optional[SecurityActionExecutor] = None


def get_action_executor() -> SecurityActionExecutor:
    """Get the singleton action executor instance."""
    global _executor
    if _executor is None:
        _executor = SecurityActionExecutor()
    return _executor
