"""
Linux Security Controller — UFW-based firewall toggle.

Same QObject interface as the Windows SecurityController so QML
bindings work identically. RDP and UAC are not applicable on Linux.
"""

import logging
import subprocess

from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger(__name__)


class SecurityController(QObject):
    """
    Backend controller for toggling OS security features on Linux.

    Supported feature IDs:
        - "firewall"  : UFW Firewall

    Signals:
        featureToggled(feature_id, enabled, message)
        featureError(feature_id, message)
    """

    featureToggled = Signal(str, bool, str)
    featureError = Signal(str, str)
    feature_state_updated = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)

    @Slot(str, bool)
    def toggle_security_feature(self, feature_id: str, enable: bool) -> None:
        """Toggle the specified security feature on or off."""
        dispatch = {
            "firewall": self._toggle_firewall,
        }

        handler = dispatch.get(feature_id)
        if handler is None:
            msg = f"Feature not available on Linux: {feature_id}"
            logger.warning(msg)
            self.featureError.emit(feature_id, msg)
            return

        try:
            handler(enable)
        except Exception as exc:
            msg = f"Failed to {'enable' if enable else 'disable'} {feature_id}: {exc}"
            logger.exception(msg)
            self.featureError.emit(feature_id, msg)

    def _toggle_firewall(self, enable: bool) -> None:
        cmd_arg = "enable" if enable else "disable"
        result = subprocess.run(
            ["sudo", "ufw", cmd_arg],
            capture_output=True,
            text=True,
            timeout=15,
            input="y\n",  # Auto-confirm ufw prompts
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"ufw returned {result.returncode}: {err}")

        action = "enabled" if enable else "disabled"
        logger.info("UFW Firewall %s", action)
        self.feature_state_updated.emit("firewall", enable)
        self.featureToggled.emit(
            "firewall", enable, f"UFW Firewall {action}."
        )


_instance: SecurityController | None = None


def get_security_controller() -> SecurityController:
    global _instance
    if _instance is None:
        _instance = SecurityController()
    return _instance
