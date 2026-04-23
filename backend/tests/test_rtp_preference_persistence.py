"""Focused tests for RTP preference persistence and startup behavior."""

from __future__ import annotations

import tempfile
from types import SimpleNamespace

from PySide6.QtCore import QCoreApplication, QSettings

from backend.application import DesktopSecurityApplication
from backend.core.realtime_protection import RealTimeProtectionBridge


class _FakeWorker:
    def __init__(self) -> None:
        self.stopped = False
        self.waited = False
        self.deleted = False

    def stop(self) -> None:
        self.stopped = True

    def wait(self, _timeout: int) -> None:
        self.waited = True

    def deleteLater(self) -> None:
        self.deleted = True


def _configure_temp_qsettings() -> tuple[QCoreApplication, tempfile.TemporaryDirectory[str], QSettings.Format]:
    app = QCoreApplication.instance() or QCoreApplication([])
    tmpdir = tempfile.TemporaryDirectory()
    old_format = QSettings.defaultFormat()
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, tmpdir.name)
    qs = QSettings("SentinelSecurity", "SentinelApp")
    qs.clear()
    qs.sync()
    return app, tmpdir, old_format


def _cleanup_temp_qsettings(tmpdir: tempfile.TemporaryDirectory[str], old_format: QSettings.Format) -> None:
    QSettings.setDefaultFormat(old_format)
    tmpdir.cleanup()


def test_missing_preference_defaults_on() -> None:
    _app, tmpdir, old_format = _configure_temp_qsettings()
    try:
        has_saved, enabled = RealTimeProtectionBridge._load_persisted_preference()

        assert has_saved is False
        assert enabled is True

        bridge = RealTimeProtectionBridge()
        assert bridge.getConfiguredEnabled() is True
        assert bridge.shouldStartOnLaunch() is True
    finally:
        _cleanup_temp_qsettings(tmpdir, old_format)


def test_saved_off_persists_across_launches() -> None:
    _app, tmpdir, old_format = _configure_temp_qsettings()
    try:
        qs = QSettings("SentinelSecurity", "SentinelApp")
        qs.setValue("rtpEnabled", False)
        qs.sync()

        has_saved, enabled = RealTimeProtectionBridge._load_persisted_preference()

        assert has_saved is True
        assert enabled is False

        bridge = RealTimeProtectionBridge()
        assert bridge.getConfiguredEnabled() is False
        assert bridge.shouldStartOnLaunch() is False
    finally:
        _cleanup_temp_qsettings(tmpdir, old_format)


def test_saved_on_persists_across_launches() -> None:
    _app, tmpdir, old_format = _configure_temp_qsettings()
    try:
        qs = QSettings("SentinelSecurity", "SentinelApp")
        qs.setValue("rtpEnabled", True)
        qs.sync()

        has_saved, enabled = RealTimeProtectionBridge._load_persisted_preference()

        assert has_saved is True
        assert enabled is True

        bridge = RealTimeProtectionBridge()
        assert bridge.getConfiguredEnabled() is True
        assert bridge.shouldStartOnLaunch() is True
    finally:
        _cleanup_temp_qsettings(tmpdir, old_format)


def test_shutdown_runtime_preserves_saved_user_choice() -> None:
    _app, tmpdir, old_format = _configure_temp_qsettings()
    try:
        qs = QSettings("SentinelSecurity", "SentinelApp")
        qs.setValue("rtpEnabled", True)
        qs.sync()

        bridge = RealTimeProtectionBridge()
        bridge._enabled = True
        bridge._worker = _FakeWorker()

        bridge.shutdownRuntime()

        persisted = QSettings("SentinelSecurity", "SentinelApp").value(
            "rtpEnabled", False, type=bool
        )
        assert persisted is True
        assert bridge.getStatus() is False
    finally:
        _cleanup_temp_qsettings(tmpdir, old_format)


def test_disable_persists_user_off_choice() -> None:
    _app, tmpdir, old_format = _configure_temp_qsettings()
    try:
        qs = QSettings("SentinelSecurity", "SentinelApp")
        qs.setValue("rtpEnabled", True)
        qs.sync()

        bridge = RealTimeProtectionBridge()
        bridge._enabled = True
        bridge._worker = _FakeWorker()

        bridge.disable()

        persisted = QSettings("SentinelSecurity", "SentinelApp").value(
            "rtpEnabled", True, type=bool
        )
        assert persisted is False
        assert bridge.getStatus() is False
    finally:
        _cleanup_temp_qsettings(tmpdir, old_format)


def test_application_auto_start_uses_saved_preference() -> None:
    app = DesktopSecurityApplication.__new__(DesktopSecurityApplication)
    enabled_calls: list[str] = []
    bridge = SimpleNamespace(
        shouldStartOnLaunch=lambda: True,
        enable=lambda: enabled_calls.append("enable"),
        getStatus=lambda: True,
    )
    app.rtp_bridge = bridge

    app._auto_start_rtp_if_configured()

    assert enabled_calls == ["enable"]


def test_application_skips_auto_start_when_user_disabled_rtp() -> None:
    app = DesktopSecurityApplication.__new__(DesktopSecurityApplication)
    enabled_calls: list[str] = []
    bridge = SimpleNamespace(
        shouldStartOnLaunch=lambda: False,
        enable=lambda: enabled_calls.append("enable"),
        getStatus=lambda: False,
    )
    app.rtp_bridge = bridge

    app._auto_start_rtp_if_configured()

    assert enabled_calls == []
