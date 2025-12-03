"""Notification Service - Manages application notifications for QML."""

import logging
import uuid
from datetime import datetime
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot, Property

logger = logging.getLogger(__name__)


class NotificationService(QObject):
    """
    Service for managing application notifications.

    Exposes notifications to QML and provides methods for managing them.
    Notifications are stored in memory and persist for the application session.
    """

    # Signals
    notificationReceived = Signal(str, str, str, str)  # id, title, message, type
    notificationListUpdated = Signal()
    notificationCountChanged = Signal()

    def __init__(self):
        super().__init__()
        self._notifications: list[dict[str, Any]] = []
        self._unread_count = 0
        logger.info("NotificationService initialized")

    @Slot(str, str, str, result=str)
    def push(self, title: str, message: str, notification_type: str = "info") -> str:
        """
        Push a new notification.

        Args:
            title: Notification title
            message: Notification message
            notification_type: One of "info", "warning", "error", "success"

        Returns:
            The notification ID
        """
        notification_id = str(uuid.uuid4())[:8]

        notification = {
            "id": notification_id,
            "title": title,
            "message": message,
            "type": notification_type,
            "time": datetime.now().strftime("%H:%M"),
            "timestamp": datetime.now().isoformat(),
            "read": False,
        }

        # Insert at beginning (newest first)
        self._notifications.insert(0, notification)
        self._unread_count += 1

        # Limit to 100 notifications
        if len(self._notifications) > 100:
            self._notifications = self._notifications[:100]

        logger.info(f"Notification pushed: [{notification_type}] {title}")

        # Emit signals
        self.notificationReceived.emit(
            notification_id, title, message, notification_type
        )
        self.notificationListUpdated.emit()
        self.notificationCountChanged.emit()

        return notification_id

    @Slot(result=list)
    def getNotifications(self) -> list[dict[str, Any]]:
        """Get all notifications as a list of dicts for QML."""
        return self._notifications

    @Slot(str, result=bool)
    def clearNotification(self, notification_id: str) -> bool:
        """
        Clear a specific notification by ID.

        Args:
            notification_id: The notification ID to clear

        Returns:
            True if found and removed, False otherwise
        """
        for i, notif in enumerate(self._notifications):
            if notif["id"] == notification_id:
                was_unread = not notif.get("read", False)
                del self._notifications[i]
                if was_unread:
                    self._unread_count = max(0, self._unread_count - 1)
                self.notificationListUpdated.emit()
                self.notificationCountChanged.emit()
                logger.debug(f"Notification cleared: {notification_id}")
                return True
        return False

    @Slot()
    def clearAll(self) -> None:
        """Clear all notifications."""
        self._notifications.clear()
        self._unread_count = 0
        self.notificationListUpdated.emit()
        self.notificationCountChanged.emit()
        logger.info("All notifications cleared")

    @Slot()
    def markAllRead(self) -> None:
        """Mark all notifications as read."""
        for notif in self._notifications:
            notif["read"] = True
        self._unread_count = 0
        self.notificationCountChanged.emit()
        logger.debug("All notifications marked as read")

    @Slot(str)
    def markRead(self, notification_id: str) -> None:
        """Mark a specific notification as read."""
        for notif in self._notifications:
            if notif["id"] == notification_id and not notif.get("read", False):
                notif["read"] = True
                self._unread_count = max(0, self._unread_count - 1)
                self.notificationCountChanged.emit()
                break

    @Property(int, notify=notificationCountChanged)
    def unreadCount(self) -> int:
        """Get the count of unread notifications."""
        return self._unread_count

    @Property(int, notify=notificationListUpdated)
    def totalCount(self) -> int:
        """Get total notification count."""
        return len(self._notifications)


# Singleton instance
_notification_service: NotificationService | None = None


def get_notification_service() -> NotificationService:
    """Get the singleton NotificationService instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
