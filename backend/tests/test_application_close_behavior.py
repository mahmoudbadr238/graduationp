"""Focused tests for close-to-tray behavior in the desktop application."""

from types import SimpleNamespace

from backend.application import DesktopSecurityApplication


class _FakeQtApp:
    def __init__(self) -> None:
        self.values: list[bool] = []

    def setQuitOnLastWindowClosed(self, value: bool) -> None:
        self.values.append(value)


class _FakeTrayIcon:
    def __init__(self, visible: bool) -> None:
        self._visible = visible

    def isVisible(self) -> bool:
        return self._visible


def _build_application(close_to_tray: bool, tray_visible: bool | None) -> DesktopSecurityApplication:
    app = DesktopSecurityApplication.__new__(DesktopSecurityApplication)
    app.app = _FakeQtApp()
    app.settings_service = SimpleNamespace(closeToTray=close_to_tray)
    app.tray_icon = None if tray_visible is None else _FakeTrayIcon(tray_visible)
    return app


def test_close_to_tray_keeps_process_alive_when_supported() -> None:
    app = _build_application(close_to_tray=True, tray_visible=True)

    app._apply_close_behavior()

    assert app.app.values[-1] is False


def test_close_to_tray_setting_does_not_mask_missing_tray_support() -> None:
    app = _build_application(close_to_tray=True, tray_visible=None)

    app._apply_close_behavior()

    assert app.app.values[-1] is True


def test_disabled_close_to_tray_quits_when_main_window_closes() -> None:
    app = _build_application(close_to_tray=False, tray_visible=True)

    app._apply_close_behavior()

    assert app.app.values[-1] is True
