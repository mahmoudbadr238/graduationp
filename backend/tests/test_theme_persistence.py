"""Integration tests for theme persistence in SettingsService."""

import tempfile
import unittest

from PySide6.QtCore import QCoreApplication, QSettings

from backend.api.settings_service import SettingsService


class TestThemePersistence(unittest.TestCase):
    def setUp(self) -> None:
        self._app = QCoreApplication.instance() or QCoreApplication([])
        self._tmpdir = tempfile.TemporaryDirectory()
        self._old_format = QSettings.defaultFormat()
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, self._tmpdir.name)

    def tearDown(self) -> None:
        QSettings.setDefaultFormat(self._old_format)
        self._tmpdir.cleanup()

    def test_theme_mode_persists_across_instances(self) -> None:
        first = SettingsService()
        first.themeMode = "dark"
        first._qs.sync()

        second = SettingsService()

        self.assertEqual(second.themeMode, "dark")


if __name__ == "__main__":
    unittest.main()
