"""Focused regression coverage for Security tab post-toggle refresh behavior."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QJSValue, QQmlApplicationEngine

from backend.api.system_snapshot_service import SystemSnapshotService


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = Path(__file__).resolve().parents[2]
QML_ROOT = REPO_ROOT / "frontend" / "qml"
PAGES_IMPORT_URL = (QML_ROOT / "pages").as_posix()


def _process_events(app: QGuiApplication, timeout_ms: int = 50) -> None:
    done: list[bool] = []

    def _quit() -> None:
        done.append(True)
        app.quit()

    QTimer.singleShot(timeout_ms, _quit)
    app.exec()
    assert done


def _to_variant(value):
    if isinstance(value, QJSValue):
        return value.toVariant()
    return value


def _security_payload(
    *,
    firewall_enabled: bool = True,
    rdp_enabled: bool = False,
    uac_level: str = "High",
) -> dict[str, object]:
    overall = {
        "status": "Protected",
        "detail": "All key protections are on",
        "isGood": True,
        "isWarning": False,
    }
    internet = {
        "status": "Protected",
        "detail": "Firewall and antivirus are enabled",
        "isGood": True,
        "isWarning": False,
    }
    remote = {
        "status": "Safe",
        "detail": "Remote Desktop is off and UAC is on",
        "isGood": True,
        "isWarning": False,
    }

    if not firewall_enabled:
        overall = {
            "status": "Needs attention",
            "detail": "Firewall is off",
            "isGood": False,
            "isWarning": True,
        }
        internet = {
            "status": "Review",
            "detail": "Firewall is disabled",
            "isGood": False,
            "isWarning": True,
        }

    if rdp_enabled:
        overall = {
            "status": "Needs attention",
            "detail": "Remote Desktop is on",
            "isGood": False,
            "isWarning": True,
        }
        remote = {
            "status": "Review",
            "detail": "Remote Desktop is enabled",
            "isGood": False,
            "isWarning": True,
        }

    if uac_level == "Disabled":
        overall = {
            "status": "Needs attention",
            "detail": "UAC is off",
            "isGood": False,
            "isWarning": True,
        }
        remote = {
            "status": "Review",
            "detail": "UAC is disabled",
            "isGood": False,
            "isWarning": True,
        }

    return {
        "simplified": {
            "overall": overall,
            "internetProtection": internet,
            "updates": {
                "status": "Protected",
                "detail": "System is up to date",
                "isGood": True,
                "isWarning": False,
            },
            "deviceProtection": {
                "status": "Strong",
                "detail": "Secure Boot and TPM are enabled",
                "isGood": True,
                "isWarning": False,
            },
            "remoteAndApps": remote,
            "tpm": {
                "present": True,
                "enabled": True,
                "version": "2.0",
                "detail": "TPM ready",
            },
            "raw": {
                "firewallEnabled": firewall_enabled,
                "firewallStatus": "Enabled" if firewall_enabled else "Disabled",
                "firewallName": "Windows Firewall",
                "antivirusStatus": "On",
                "antivirusName": "Defender",
                "antivirusRealtime": True,
                "antivirusDetail": "Definitions up to date",
                "secureBoot": "Enabled",
                "diskEncryption": "Enabled",
                "diskEncryptionDetail": "",
                "windowsUpdateStatus": "UpToDate",
                "windowsUpdateDetail": "",
                "remoteDesktopEnabled": rdp_enabled,
                "remoteDesktopStatus": "Enabled" if rdp_enabled else "Disabled",
                "remoteDesktopDetail": "",
                "remoteDesktopNla": True,
                "adminAccountCount": 1,
                "adminAccountDetail": "1 admin account",
                "uacLevel": uac_level,
                "uacDetail": (
                    "Secure desktop prompts"
                    if uac_level != "Disabled"
                    else "UAC is completely disabled"
                ),
                "smartScreenStatus": "Enabled",
                "smartScreenDetail": "",
                "memoryIntegrityStatus": "Enabled",
                "memoryIntegrityDetail": "",
                "capabilities": {
                    "firewall": True,
                    "rdp": True,
                    "uac": True,
                    "secureBoot": True,
                    "tpm": True,
                    "diskEncryption": True,
                    "updates": True,
                    "localAdmins": True,
                    "smartScreen": True,
                    "memoryIntegrity": True,
                },
            },
        },
        "providers": [],
    }


class _SnapshotServiceHarness(SystemSnapshotService):
    def __init__(self) -> None:
        super().__init__()
        self._timer.stop()
        self._security_info = _security_payload()
        self.pending_info: dict[str, object] | None = None
        self.refresh_calls = 0

    @Slot()
    def refreshSecurityInfo(self) -> None:
        self.refresh_calls += 1
        if self.pending_info is not None:
            self._security_info = self.pending_info
            self.pending_info = None
            self.securityInfoChanged.emit()


class _SecurityControllerHarness(QObject):
    feature_state_updated = Signal(str, bool)
    featureToggled = Signal(str, bool, str)
    featureError = Signal(str, str)

    def __init__(self, snapshot: _SnapshotServiceHarness) -> None:
        super().__init__()
        self.snapshot = snapshot
        self.calls: list[tuple[str, bool]] = []
        self.fail_next = False

    @Slot(str, bool)
    def toggle_security_feature(self, feature_id: str, enable: bool) -> None:
        self.calls.append((feature_id, enable))

        if self.fail_next:
            self.fail_next = False
            self.featureError.emit(feature_id, "toggle failed")
            return

        if feature_id == "firewall":
            self.snapshot.pending_info = _security_payload(firewall_enabled=enable)
        elif feature_id == "rdp":
            self.snapshot.pending_info = _security_payload(rdp_enabled=enable)
        elif feature_id == "uac":
            self.snapshot.pending_info = _security_payload(
                uac_level="High" if enable else "Disabled"
            )

        self.feature_state_updated.emit(feature_id, enable)
        self.featureToggled.emit(feature_id, enable, "ok")


class _NotificationServiceStub(QObject):
    unreadCountChanged = Signal()

    @Property(int, constant=True)
    def unreadCount(self) -> int:
        return 0


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

    @Property(str, constant=True)
    def themeMode(self) -> str:
        return "dark"

    @Property(str, constant=True)
    def fontSize(self) -> str:
        return "medium"


@pytest.fixture(scope="module")
def app() -> QGuiApplication:
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])
    return app


def _load_snapshot_window(
    app: QGuiApplication,
) -> tuple[QObject, QQmlApplicationEngine, _SnapshotServiceHarness, _SecurityControllerHarness]:
    engine = QQmlApplicationEngine()
    warnings: list[str] = []
    engine.warnings.connect(
        lambda errs, bucket=warnings: bucket.extend(err.toString() for err in errs)
    )

    for path in (
        QML_ROOT,
        QML_ROOT / "pages",
        QML_ROOT / "components",
        QML_ROOT / "theme",
        QML_ROOT / "ui",
        QML_ROOT / "ux",
    ):
        engine.addImportPath(str(path))

    snapshot = _SnapshotServiceHarness()
    security = _SecurityControllerHarness(snapshot)

    context = engine.rootContext()
    context.setContextProperty("Backend", QObject())
    context.setContextProperty("GPUService", _GPUServiceStub())
    context.setContextProperty("SettingsService", _SettingsServiceStub())
    context.setContextProperty("SnapshotService", snapshot)
    context.setContextProperty("SecurityController", security)
    context.setContextProperty("NotificationService", _NotificationServiceStub())
    context.setContextProperty("RTPBridge", None)

    wrapper_qml = f"""
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "file:///{PAGES_IMPORT_URL}" as Pages

Window {{
    width: 1400
    height: 900
    visible: true

    Pages.SystemSnapshot {{
        anchors.fill: parent
        currentTabIndex: 3
    }}
}}
"""

    engine.loadData(
        wrapper_qml.encode("utf-8"),
        QUrl("file:///D:/graduationp/frontend/qml/test_security_toggle_wrapper.qml"),
    )
    assert engine.rootObjects(), "SystemSnapshot wrapper did not load:\n" + "\n".join(
        warnings
    )

    window = engine.rootObjects()[0]
    _process_events(app, 400)
    return window, engine, snapshot, security


def _close_window(app: QGuiApplication, window: QObject, engine: QQmlApplicationEngine) -> None:
    window.close()
    _process_events(app, 50)
    engine.deleteLater()
    _process_events(app, 50)


def _open_and_accept_risk_dialog(
    app: QGuiApplication,
    window: QObject,
    *,
    feature_id: str,
    new_state: bool,
    feature_label: str,
) -> None:
    dialog = window.findChild(QObject, "riskConfirmDialog")
    assert dialog is not None

    dialog.setProperty("featureId", feature_id)
    dialog.setProperty("newState", new_state)
    dialog.setProperty("featureLabel", feature_label)
    dialog.open()
    _process_events(app, 120)
    dialog.accept()
    _process_events(app, 250)


def test_firewall_toggle_refreshes_card_and_summaries_after_success(
    app: QGuiApplication,
) -> None:
    window, engine, snapshot, security = _load_snapshot_window(app)
    try:
        firewall_card = window.findChild(QObject, "firewallSecurityCard")
        security_column = window.findChild(QObject, "securityColumn")
        assert firewall_card is not None
        assert security_column is not None

        assert firewall_card.property("value") == "On"
        assert firewall_card.property("toggleChecked") is True
        assert _to_variant(security_column.property("overall"))["status"] == "Protected"

        _open_and_accept_risk_dialog(
            app,
            window,
            feature_id="firewall",
            new_state=False,
            feature_label="Windows Firewall",
        )

        raw = _to_variant(security_column.property("raw"))
        internet = _to_variant(security_column.property("internet"))
        overall = _to_variant(security_column.property("overall"))

        assert security.calls == [("firewall", False)]
        assert snapshot.refresh_calls >= 1
        assert firewall_card.property("value") == "Off"
        assert firewall_card.property("toggleChecked") is False
        assert firewall_card.property("isWarning") is True
        assert raw["firewallStatus"] == "Disabled"
        assert internet["status"] == "Review"
        assert overall["status"] == "Needs attention"

        _process_events(app, 1700)
        assert snapshot.refresh_calls >= 2
    finally:
        _close_window(app, window, engine)


def test_rdp_toggle_refreshes_visible_state_without_second_click(
    app: QGuiApplication,
) -> None:
    window, engine, snapshot, security = _load_snapshot_window(app)
    try:
        rdp_card = window.findChild(QObject, "rdpSecurityCard")
        security_column = window.findChild(QObject, "securityColumn")
        assert rdp_card is not None
        assert security_column is not None

        assert rdp_card.property("value") == "Off"
        assert rdp_card.property("toggleChecked") is False
        assert _to_variant(security_column.property("remote"))["status"] == "Safe"

        _open_and_accept_risk_dialog(
            app,
            window,
            feature_id="rdp",
            new_state=True,
            feature_label="Remote Desktop",
        )

        raw = _to_variant(security_column.property("raw"))
        remote = _to_variant(security_column.property("remote"))
        overall = _to_variant(security_column.property("overall"))

        assert security.calls == [("rdp", True)]
        assert snapshot.refresh_calls >= 1
        assert rdp_card.property("value") == "On"
        assert rdp_card.property("toggleChecked") is True
        assert rdp_card.property("isWarning") is True
        assert raw["remoteDesktopStatus"] == "Enabled"
        assert remote["status"] == "Review"
        assert overall["status"] == "Needs attention"
    finally:
        _close_window(app, window, engine)


def test_failed_toggle_does_not_falsely_refresh_or_change_visible_state(
    app: QGuiApplication,
) -> None:
    window, engine, snapshot, security = _load_snapshot_window(app)
    try:
        firewall_card = window.findChild(QObject, "firewallSecurityCard")
        security_column = window.findChild(QObject, "securityColumn")
        assert firewall_card is not None
        assert security_column is not None

        security.fail_next = True

        _open_and_accept_risk_dialog(
            app,
            window,
            feature_id="firewall",
            new_state=False,
            feature_label="Windows Firewall",
        )

        raw = _to_variant(security_column.property("raw"))
        overall = _to_variant(security_column.property("overall"))

        assert security.calls == [("firewall", False)]
        assert snapshot.refresh_calls == 0
        assert firewall_card.property("value") == "On"
        assert firewall_card.property("toggleChecked") is True
        assert raw["firewallStatus"] == "Enabled"
        assert overall["status"] == "Protected"
    finally:
        _close_window(app, window, engine)
