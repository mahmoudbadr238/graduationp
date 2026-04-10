"""Unified Notification Manager — dispatches to QML tab AND Windows Action Center.

Every alert in the application should flow through this manager so that:
1. The in-app QML Notification Tab is updated (via NotificationService).
2. A native Windows 11 toast is pushed through QSystemTrayIcon.showMessage().

Usage:
    manager = NotificationManager(notification_service, tray_icon)
    manager.notify("Malware Detected", "Trojan found in download.exe", "error")
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QSystemTrayIcon

from .notification_service import NotificationService

logger = logging.getLogger(__name__)

# Map our notification types to QSystemTrayIcon message icons
_ICON_MAP: dict[str, QSystemTrayIcon.MessageIcon] = {
    "info": QSystemTrayIcon.MessageIcon.Information,
    "success": QSystemTrayIcon.MessageIcon.Information,
    "warning": QSystemTrayIcon.MessageIcon.Warning,
    "error": QSystemTrayIcon.MessageIcon.Critical,
}


class NotificationManager(QObject):
    """Unified notification dispatcher: QML tab + native OS toast."""

    # Re-exported for convenience — callers can connect to this instead of
    # reaching into NotificationService directly.
    notificationDispatched = Signal(str, str, str, str)  # id, title, message, type

    def __init__(
        self,
        notification_service: NotificationService,
        tray_icon: QSystemTrayIcon | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = notification_service
        self._tray: QSystemTrayIcon | None = tray_icon

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_tray_icon(self, tray_icon: QSystemTrayIcon) -> None:
        """Late-bind the tray icon (set after system tray is ready)."""
        self._tray = tray_icon

    @Slot(str, str, str, result=str)
    def notify(
        self,
        title: str,
        message: str,
        notification_type: str = "info",
        *,
        toast: bool = True,
        toast_duration_ms: int = 5000,
    ) -> str:
        """Push an alert to BOTH the QML tab and the Windows Action Center.

        Args:
            title:              Short heading.
            message:            Body text (max ~256 chars for toast).
            notification_type:  "info" | "success" | "warning" | "error".
            toast:              Whether to also trigger a native OS toast.
            toast_duration_ms:  How long the toast stays visible (ms).

        Returns:
            The notification ID from NotificationService.
        """
        # 1️⃣  In-app QML notification tab
        nid = self._service.push(title, message, notification_type)

        # 2️⃣  Native Windows Action Center toast
        if toast:
            self._send_toast(title, message, notification_type, toast_duration_ms)

        self.notificationDispatched.emit(nid, title, message, notification_type)
        logger.info(
            "Notification dispatched [%s] %s — toast=%s", notification_type, title, toast
        )
        return nid

    @Slot(str, str, str, str, str, result=str)
    def notifyRich(
        self,
        title: str,
        summary: str,
        notification_type: str = "info",
        action_label: str = "",
        action_payload_json: str = "",
        *,
        toast: bool = True,
        toast_duration_ms: int = 5000,
    ) -> str:
        """Push a rich actionable notification + native toast.

        Same as ``notify`` but forwards to ``NotificationService.pushRich``
        so the QML delegate can show an action button.
        """
        nid = self._service.pushRich(
            title, summary, notification_type, action_label, action_payload_json
        )

        if toast:
            self._send_toast(title, summary, notification_type, toast_duration_ms)

        self.notificationDispatched.emit(nid, title, summary, notification_type)
        return nid

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _send_toast(
        self,
        title: str,
        message: str,
        notification_type: str,
        duration_ms: int,
    ) -> None:
        """Forward to QSystemTrayIcon.showMessage for a Windows toast."""
        if not self._tray or not self._tray.isVisible():
            return
        icon = _ICON_MAP.get(notification_type, QSystemTrayIcon.MessageIcon.Information)
        self._tray.showMessage(title, message[:256], icon, duration_ms)
