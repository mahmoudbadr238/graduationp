"""Focused regression coverage for the two Qt Quick Controls modal dialogs."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QTimer, Signal, Slot, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQml import QQmlApplicationEngine


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = Path(__file__).resolve().parents[2]
QML_ROOT = REPO_ROOT / "frontend" / "qml"
ARTIFACT_DIR = REPO_ROOT / "artifacts" / "dialogs"


def _process_events(app: QGuiApplication, timeout_ms: int = 50) -> None:
    """Allow QML bindings and popup layout to settle."""
    done: list[bool] = []

    def _quit() -> None:
        done.append(True)
        app.quit()

    QTimer.singleShot(timeout_ms, _quit)
    app.exec()
    assert done


class _BackendStub(QObject):
    scanFinished = Signal(str, object)
    scanCenterFinished = Signal(object)
    toast = Signal(str, str)
    navigateTo = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.restore_calls: list[str] = []
        self.delete_calls: list[str] = []
        self.quarantine_items: list[dict[str, object]] = [
            {
                "id": "restore-001",
                "original_name": "SuspiciousTool.exe",
                "original_path": r"C:\Temp\SuspiciousTool.exe",
                "quarantined_at": "2026-04-23T18:15:00Z",
                "metadata_quality": "complete",
                "metadata_quality_label": "Complete record",
                "source_label": "Real-time protection",
                "decision_score_label": "98 / 100",
                "decision_verdict_label": "Malicious",
                "decision_action_label": "Block",
                "file_action_label": "Quarantine file",
                "metadata_note": "Full decision metadata retained.",
                "action_reason_label": "Strong corroborating evidence authorizes quarantine.",
                "can_restore": True,
                "can_delete": True,
                "status": "quarantined",
            }
        ]

    @Slot(int, result="QVariant")
    def getUnifiedScanHistory(self, _limit: int) -> list[dict[str, object]]:
        return []

    @Slot(int, result="QVariant")
    def getIncidentHistory(self, _limit: int) -> list[dict[str, object]]:
        return []

    @Slot(result="QVariant")
    def getQuarantineHistory(self) -> list[dict[str, object]]:
        return [dict(item) for item in self.quarantine_items]

    @Slot(int, result="QVariant")
    def getUrlScanHistory(self, _limit: int) -> list[dict[str, object]]:
        return []

    # Set to True to make the next restoreQuarantineItem call return a failure
    fail_restore: bool = False

    @Slot(str, result="QVariant")
    def restoreQuarantineItem(self, quarantine_id: str) -> dict[str, object]:
        self.restore_calls.append(quarantine_id)
        if self.fail_restore:
            return {
                "success": False,
                "message": (
                    r"Failed to restore file to 'C:\Temp\SuspiciousTool.exe': "
                    r"[WinError 5] Access is denied: 'C:\Temp\SuspiciousTool.exe'"
                ),
            }
        self.quarantine_items = [
            {
                **item,
                "status": "restored" if item["id"] == quarantine_id else item.get("status", "quarantined"),
                "can_restore": False if item["id"] == quarantine_id else item.get("can_restore", False),
                "restored_at": "2026-04-23T18:16:00Z" if item["id"] == quarantine_id else item.get("restored_at", ""),
            }
            for item in self.quarantine_items
        ]
        return {
            "success": True,
            "message": "Restore completed.",
            "original_name": "SuspiciousTool.exe",
            "original_path": r"C:\Temp\SuspiciousTool.exe",
            "restored_sha256": "abc123",
            "integrity_verified": True,
            "audit_retained": True,
        }

    @Slot(str, result="QVariant")
    def deleteQuarantineItem(self, quarantine_id: str) -> dict[str, object]:
        self.delete_calls.append(quarantine_id)
        self.quarantine_items = [
            {
                **item,
                "status": "deleted" if item["id"] == quarantine_id else item.get("status", "quarantined"),
                "can_delete": False if item["id"] == quarantine_id else item.get("can_delete", False),
                "deleted_at": "2026-04-23T18:17:00Z" if item["id"] == quarantine_id else item.get("deleted_at", ""),
            }
            for item in self.quarantine_items
        ]
        return {
            "success": True,
            "message": "Delete completed.",
            "original_name": "SuspiciousTool.exe",
            "original_path": r"C:\Temp\SuspiciousTool.exe",
            "audit_retained": True,
        }


class _NotificationServiceStub(QObject):
    unreadCountChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._unread_count = 0

    def _get_unread_count(self) -> int:
        return self._unread_count

    unreadCount = property(_get_unread_count)


class _GPUServiceStub(QObject):
    @Slot(int)
    def start(self, _interval_ms: int) -> None:
        return

    @Slot(result=bool)
    def isRunning(self) -> bool:
        return False


class _SettingsServiceStub(QObject):
    themeModeChanged = Signal()
    fontSizeChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._theme_mode = "dark"
        self._font_size = "medium"

    def _get_theme_mode(self) -> str:
        return self._theme_mode

    def _set_theme_mode(self, value: str) -> None:
        self._theme_mode = value
        self.themeModeChanged.emit()

    themeMode = property(_get_theme_mode, _set_theme_mode)

    def _get_font_size(self) -> str:
        return self._font_size

    def _set_font_size(self, value: str) -> None:
        self._font_size = value
        self.fontSizeChanged.emit()

    fontSize = property(_get_font_size, _set_font_size)


class _SnapshotServiceStub(QObject):
    @property
    def networkInterfaces(self) -> list[dict[str, object]]:
        return []

    @property
    def diskPartitions(self) -> list[dict[str, object]]:
        return []

    @property
    def hiddenDiskPartitions(self) -> list[dict[str, object]]:
        return []

    @property
    def securityInfo(self) -> dict[str, object]:
        return {
            "firewallStatus": "Enabled",
            "firewallName": "Windows Firewall",
            "remoteDesktopStatus": "Disabled",
            "uacLevel": "High",
            "advancedCoverageNote": "",
            "providers": [],
        }

    @Slot()
    def refreshSecurityInfo(self) -> None:
        return


class _SecurityControllerStub(QObject):
    feature_state_updated = Signal(str, bool)
    featureToggled = Signal(str, bool, str)
    featureError = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, bool]] = []

    @Slot(str, bool)
    def toggle_security_feature(self, feature_id: str, enable: bool) -> None:
        self.calls.append((feature_id, enable))
        self.feature_state_updated.emit(feature_id, enable)
        self.featureToggled.emit(feature_id, enable, "ok")


@pytest.fixture(scope="module")
def app() -> QGuiApplication:
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])
    return app


def _load_window(
    app: QGuiApplication,
) -> tuple[QObject, QQmlApplicationEngine, _BackendStub, _SecurityControllerStub]:
    backend = _BackendStub()
    security = _SecurityControllerStub()
    qml_path = QML_ROOT / "main.qml"
    load_errors: list[str] = []
    engine: QQmlApplicationEngine | None = None

    for _attempt in range(3):
        engine = QQmlApplicationEngine()
        warnings: list[str] = []
        engine.warnings.connect(lambda errs, bucket=warnings: bucket.extend(err.toString() for err in errs))

        for path in (
            QML_ROOT,
            QML_ROOT / "pages",
            QML_ROOT / "components",
            QML_ROOT / "theme",
            QML_ROOT / "ui",
            QML_ROOT / "ux",
        ):
            engine.addImportPath(str(path))

        context = engine.rootContext()
        context.setContextProperty("Backend", backend)
        context.setContextProperty("GPUService", _GPUServiceStub())
        context.setContextProperty("SettingsService", _SettingsServiceStub())
        context.setContextProperty("SnapshotService", _SnapshotServiceStub())
        context.setContextProperty("SecurityController", security)
        context.setContextProperty("NotificationService", _NotificationServiceStub())
        context.setContextProperty("RTPBridge", None)

        engine.load(QUrl.fromLocalFile(str(qml_path)))
        if engine.rootObjects():
            break

        load_errors = warnings[:]
        engine.deleteLater()
        _process_events(app, 50)
        engine = None

    assert engine is not None and engine.rootObjects(), "main.qml did not produce a root object:\n" + "\n".join(load_errors)

    window = engine.rootObjects()[0]
    window.setWidth(1400)
    window.setHeight(900)
    window.setProperty("visible", True)
    _process_events(app, 150)
    return window, engine, backend, security


def _save_window_grab(window: QObject, name: str) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    target = ARTIFACT_DIR / name
    pixmap = QQuickWindow.grabWindow(window)
    assert pixmap.save(str(target)), f"failed to save screenshot to {target}"
    return target


def _close_window(app: QGuiApplication, window: QObject, engine: QQmlApplicationEngine) -> None:
    if window is not None:
        window.close()
        _process_events(app, 50)
    engine.deleteLater()
    _process_events(app, 50)


def test_restore_confirmation_dialog_opens_and_wires_accept(app: QGuiApplication) -> None:
    window, engine, backend, _security = _load_window(app)
    try:
        window.setProperty("currentRoute", "history")
        window.setProperty("historyRequestedTab", "quarantine")
        _process_events(app, 150)

        history_page = window.findChild(QObject, "historyPageRoot")
        dialog = window.findChild(QObject, "quarantineActionDialog")
        assert history_page is not None
        assert dialog is not None

        history_page.setProperty("pendingQuarantineAction", "restore")
        history_page.setProperty(
            "pendingQuarantineItem",
            {
                "id": "restore-001",
                "original_name": "SuspiciousTool.exe",
                "original_path": r"C:\Temp\SuspiciousTool.exe",
                "quarantined_at": "2026-04-23T18:15:00Z",
                "metadata_quality": "complete",
                "metadata_quality_label": "Complete record",
                "source_label": "Real-time protection",
                "decision_score_label": "98 / 100",
                "decision_verdict_label": "Malicious",
                "decision_action_label": "Block",
                "file_action_label": "Quarantine file",
                "metadata_note": "Full decision metadata retained.",
                "action_reason_label": "Strong corroborating evidence authorizes quarantine.",
            },
        )
        dialog.open()
        _process_events(app, 250)

        screenshot = _save_window_grab(window, "history_restore_dialog.png")

        assert dialog.property("visible") is True
        assert dialog.property("modal") is True
        assert screenshot.exists()

        dialog.accept()
        _process_events(app, 150)
        assert backend.restore_calls == ["restore-001"]
    finally:
        _close_window(app, window, engine)


def test_restore_result_dialog_dismisses_and_refreshes_history(app: QGuiApplication) -> None:
    window, engine, backend, _security = _load_window(app)
    try:
        window.setProperty("currentRoute", "history")
        window.setProperty("historyRequestedTab", "quarantine")
        _process_events(app, 150)

        history_page = window.findChild(QObject, "historyPageRoot")
        confirm_dialog = window.findChild(QObject, "quarantineActionDialog")
        result_dialog = window.findChild(QObject, "quarantineResultDialog")
        assert history_page is not None
        assert confirm_dialog is not None
        assert result_dialog is not None

        history_page.setProperty("pendingQuarantineAction", "restore")
        history_page.setProperty("pendingQuarantineItem", backend.getQuarantineHistory()[0])
        confirm_dialog.open()
        _process_events(app, 200)
        confirm_dialog.accept()
        _process_events(app, 250)

        screenshot = _save_window_grab(window, "history_restore_result_dialog.png")

        refreshed_items = history_page.property("quarantineItems")
        assert backend.restore_calls == ["restore-001"]
        assert result_dialog.property("visible") is True
        assert result_dialog.property("modal") is True
        assert result_dialog.property("height") > 0
        assert screenshot.exists()
        assert refreshed_items[0]["status"] == "restored"
        assert refreshed_items[0]["can_restore"] is False

        result_dialog.accept()
        _process_events(app, 200)

        assert result_dialog.property("visible") is False
        assert history_page.property("quarantineActionResult") is None

        history_page.setProperty("pendingQuarantineAction", "delete")
        history_page.setProperty("pendingQuarantineItem", refreshed_items[0])
        confirm_dialog.open()
        _process_events(app, 150)
        assert confirm_dialog.property("visible") is True
    finally:
        _close_window(app, window, engine)


def test_security_confirmation_dialog_opens_and_wires_accept(app: QGuiApplication) -> None:
    window, engine, _backend, security = _load_window(app)
    try:
        window.setProperty("currentRoute", "snapshot")
        _process_events(app, 150)

        dialog = window.findChild(QObject, "riskConfirmDialog")
        assert dialog is not None

        dialog.setProperty("featureId", "firewall")
        dialog.setProperty("newState", False)
        dialog.setProperty("featureLabel", "Windows Firewall")
        dialog.open()
        _process_events(app, 250)

        screenshot = _save_window_grab(window, "security_firewall_dialog.png")

        assert dialog.property("visible") is True
        assert dialog.property("modal") is True
        assert screenshot.exists()

        dialog.accept()
        _process_events(app, 150)
        assert security.calls == [("firewall", False)]
    finally:
        _close_window(app, window, engine)


def test_result_dialog_footer_has_nonzero_height(app: QGuiApplication) -> None:
    """Regression guard: the result dialog footer must not collapse in any QML Controls style.

    In Fusion style (QT_QUICK_CONTROLS_STYLE=Fusion), a Button whose height is
    driven only by background.implicitHeight collapses to height 0 because
    QStyle metrics override background.implicitHeight.  After the fix, the footer
    uses Rectangle+MouseArea with explicit implicitHeight: 36, so the footer Item
    must be at least 60px (36 content + 24 vertical padding).
    """
    window, engine, backend, _security = _load_window(app)
    try:
        window.setProperty("currentRoute", "history")
        window.setProperty("historyRequestedTab", "quarantine")
        _process_events(app, 150)

        history_page = window.findChild(QObject, "historyPageRoot")
        result_dialog = window.findChild(QObject, "quarantineResultDialog")
        assert history_page is not None
        assert result_dialog is not None

        # Inject a result directly and open
        history_page.setProperty("quarantineActionResult", {
            "action": "restore",
            "success": True,
            "message": "File restored.",
            "original_name": "SuspiciousTool.exe",
            "original_path": r"C:\Temp\SuspiciousTool.exe",
            "restored_sha256": "abc123",
            "integrity_verified": True,
            "audit_retained": True,
        })
        result_dialog.open()
        _process_events(app, 300)

        assert result_dialog.property("visible") is True

        footer = result_dialog.property("footer")
        assert footer is not None, "Result dialog has no footer item"

        footer_height = footer.height()
        assert footer_height >= 60, (
            f"Footer height {footer_height}px is too small — "
            "the OK button has collapsed (likely Fusion-style height-0 regression). "
            "Footer must be >= 60px (36px button + 24px padding)."
        )

        screenshot = _save_window_grab(window, "result_dialog_footer_height_check.png")
        assert screenshot.exists()

        result_dialog.accept()
        _process_events(app, 200)
        assert result_dialog.property("visible") is False
    finally:
        _close_window(app, window, engine)


def test_delete_confirmation_and_result_dialog(app: QGuiApplication) -> None:
    """Delete confirm → accept → result dialog shows 'File Deleted', cleans up."""
    window, engine, backend, _security = _load_window(app)
    try:
        window.setProperty("currentRoute", "history")
        window.setProperty("historyRequestedTab", "quarantine")
        _process_events(app, 150)

        history_page = window.findChild(QObject, "historyPageRoot")
        confirm_dialog = window.findChild(QObject, "quarantineActionDialog")
        result_dialog = window.findChild(QObject, "quarantineResultDialog")
        assert history_page is not None
        assert confirm_dialog is not None
        assert result_dialog is not None

        history_page.setProperty("pendingQuarantineAction", "delete")
        history_page.setProperty("pendingQuarantineItem", backend.getQuarantineHistory()[0])
        confirm_dialog.open()
        _process_events(app, 200)

        assert confirm_dialog.property("visible") is True
        assert confirm_dialog.property("modal") is True

        confirm_dialog.accept()
        _process_events(app, 250)

        screenshot = _save_window_grab(window, "history_delete_result_dialog.png")

        assert backend.delete_calls == ["restore-001"]
        assert result_dialog.property("visible") is True
        assert result_dialog.property("modal") is True
        assert result_dialog.property("height") > 0
        assert screenshot.exists()

        # Title must be "File Deleted", not the old "Deletion Complete" / "Quarantine Action Result"
        title = result_dialog.property("titleText")
        assert title == "File Deleted", f"Expected 'File Deleted', got {title!r}"

        result_dialog.accept()
        _process_events(app, 200)
        assert result_dialog.property("visible") is False
        assert history_page.property("quarantineActionResult") is None
    finally:
        _close_window(app, window, engine)


def test_restore_failure_result_shows_human_readable_copy(app: QGuiApplication) -> None:
    """When restore fails with a permission error, result dialog shows clean copy, not raw exception."""
    window, engine, backend, _security = _load_window(app)
    try:
        backend.fail_restore = True

        window.setProperty("currentRoute", "history")
        window.setProperty("historyRequestedTab", "quarantine")
        _process_events(app, 150)

        history_page = window.findChild(QObject, "historyPageRoot")
        confirm_dialog = window.findChild(QObject, "quarantineActionDialog")
        result_dialog = window.findChild(QObject, "quarantineResultDialog")
        assert history_page is not None
        assert confirm_dialog is not None
        assert result_dialog is not None

        history_page.setProperty("pendingQuarantineAction", "restore")
        history_page.setProperty("pendingQuarantineItem", backend.getQuarantineHistory()[0])
        confirm_dialog.open()
        _process_events(app, 200)
        confirm_dialog.accept()
        _process_events(app, 250)

        screenshot = _save_window_grab(window, "history_restore_result_failure.png")

        assert result_dialog.property("visible") is True
        assert result_dialog.property("height") > 0
        assert screenshot.exists()

        # Title must be "Restore Failed", not generic "Quarantine Action Result"
        title = result_dialog.property("titleText")
        assert title == "Restore Failed", f"Expected 'Restore Failed', got {title!r}"

        # Body must be human-readable, not the raw WinError text
        body = result_dialog.property("bodyText")
        assert "WinError" not in body, f"Raw exception leaked into bodyText: {body!r}"
        assert "Access is denied" not in body, f"Raw OS error leaked into bodyText: {body!r}"
        assert "denied" in body.lower(), f"Expected access-denied explanation in bodyText: {body!r}"

        result_dialog.accept()
        _process_events(app, 200)
        assert result_dialog.property("visible") is False
        assert history_page.property("quarantineActionResult") is None
    finally:
        backend.fail_restore = False
        _close_window(app, window, engine)
