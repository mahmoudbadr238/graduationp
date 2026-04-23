"""Integration tests for QSettings-backed settings persistence."""

import sys
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QSettings

from backend.api.settings_service import SettingsService


class TestSettingsPersistence(unittest.TestCase):
    def setUp(self) -> None:
        self._app = QCoreApplication.instance() or QCoreApplication([])
        self._tmpdir = tempfile.TemporaryDirectory()
        self._old_format = QSettings.defaultFormat()
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, self._tmpdir.name)

    def tearDown(self) -> None:
        QSettings.setDefaultFormat(self._old_format)
        self._tmpdir.cleanup()

    def test_font_size_persists_across_instances(self) -> None:
        first = SettingsService()
        first.fontSize = "large"
        first._qs.sync()

        second = SettingsService()

        self.assertEqual(second.fontSize, "large")

    def test_close_to_tray_alias_persists_across_instances(self) -> None:
        first = SettingsService()
        first.closeToTray = True
        first._qs.sync()

        second = SettingsService()

        self.assertTrue(second.closeToTray)
        self.assertTrue(second.startMinimized)

    def test_autostart_enable_is_ignored_when_unsupported(self) -> None:
        with patch.object(sys, "platform", "linux"):
            service = SettingsService()
            service.startWithSystem = True
            self.assertFalse(service.startWithSystem)

    def test_autostart_calls_windows_registry_helper_when_supported(self) -> None:
        with patch.object(sys, "platform", "win32"):
            service = SettingsService()
            with patch.object(service, "_set_windows_autostart") as autostart:
                service.startWithSystem = True

            self.assertTrue(service.startWithSystem)
            autostart.assert_called_once_with(True)


if __name__ == "__main__":
    unittest.main()
