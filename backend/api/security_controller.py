"""
Security Controller - Interactive toggle for OS security features.
Exposes slot-based API for QML to enable/disable Firewall, RDP, and UAC.
All operations require Administrator privileges and use native Windows APIs.
"""

import logging
import subprocess
import sys
import winreg

from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger(__name__)

# Registry paths
_TERMINAL_SERVER_KEY = r"System\CurrentControlSet\Control\Terminal Server"
_UAC_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"


class SecurityController(QObject):
    """
    Backend controller for toggling OS security features.

    Supported feature IDs:
        - "firewall"  : Windows Firewall (all profiles)
        - "rdp"       : Remote Desktop Protocol
        - "uac"       : User Account Control

    Signals:
        featureToggled(feature_id, enabled, message)
        featureError(feature_id, message)
    """

    featureToggled = Signal(str, bool, str)  # feature_id, new_state, human message
    featureError = Signal(str, str)  # feature_id, error message
    feature_state_updated = Signal(str, bool)  # feature_id, confirmed new state

    def __init__(self, parent=None):
        super().__init__(parent)

    # ------------------------------------------------------------------
    # Public slot – single entry point for QML
    # ------------------------------------------------------------------
    @Slot(str, bool)
    def toggle_security_feature(self, feature_id: str, enable: bool) -> None:
        """Toggle the specified security feature on or off."""
        dispatch = {
            "firewall": self._toggle_firewall,
            "rdp": self._toggle_rdp,
            "uac": self._toggle_uac,
        }

        handler = dispatch.get(feature_id)
        if handler is None:
            msg = f"Unknown feature: {feature_id}"
            logger.warning(msg)
            self.featureError.emit(feature_id, msg)
            return

        try:
            handler(enable)
        except Exception as exc:
            msg = f"Failed to {'enable' if enable else 'disable'} {feature_id}: {exc}"
            logger.exception(msg)
            self.featureError.emit(feature_id, msg)

    # ------------------------------------------------------------------
    # Firewall
    # ------------------------------------------------------------------
    def _toggle_firewall(self, enable: bool) -> None:
        state_arg = "on" if enable else "off"
        result = subprocess.run(
            ["netsh", "advfirewall", "set", "allprofiles", "state", state_arg],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"netsh returned {result.returncode}: {err}")

        action = "enabled" if enable else "disabled"
        logger.info("Firewall %s (all profiles)", action)
        self.feature_state_updated.emit("firewall", enable)
        self.featureToggled.emit(
            "firewall", enable, f"Windows Firewall {action} for all profiles."
        )

    # ------------------------------------------------------------------
    # Remote Desktop (RDP)
    # ------------------------------------------------------------------
    def _toggle_rdp(self, enable: bool) -> None:
        # fDenyTSConnections: 0 = allow RDP, 1 = deny RDP
        deny_value = 0 if enable else 1

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, _TERMINAL_SERVER_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, "fDenyTSConnections", 0, winreg.REG_DWORD, deny_value)

        action = "enabled" if enable else "disabled"
        logger.info("Remote Desktop %s (fDenyTSConnections=%d)", action, deny_value)
        self.feature_state_updated.emit("rdp", enable)
        self.featureToggled.emit(
            "rdp", enable, f"Remote Desktop {action}."
        )

    # ------------------------------------------------------------------
    # UAC  (enable = full prompts, disable = never notify)
    # ------------------------------------------------------------------
    def _toggle_uac(self, enable: bool) -> None:
        # EnableLUA: 1 = UAC on, 0 = UAC off (requires reboot)
        lua_value = 1 if enable else 0
        # ConsentPromptBehaviorAdmin: 5 = prompt for consent (default), 0 = no prompt
        consent_value = 5 if enable else 0

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, _UAC_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, "EnableLUA", 0, winreg.REG_DWORD, lua_value)
            winreg.SetValueEx(
                key, "ConsentPromptBehaviorAdmin", 0, winreg.REG_DWORD, consent_value
            )

        action = "enabled" if enable else "disabled"
        logger.info("UAC %s (EnableLUA=%d, ConsentPrompt=%d)", action, lua_value, consent_value)
        self.feature_state_updated.emit("uac", enable)
        self.featureToggled.emit(
            "uac",
            enable,
            f"User Account Control {action}. A reboot is required for the change to take effect.",
        )


# Singleton
_instance: SecurityController | None = None


def get_security_controller() -> SecurityController:
    global _instance
    if _instance is None:
        _instance = SecurityController()
    return _instance
