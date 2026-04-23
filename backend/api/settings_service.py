"""Sentinel Settings Engine — QSettings-backed persistence with global effects."""

import logging
import platform
import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, QSettings, Signal, Slot

_log = logging.getLogger(__name__)


# Font-size label → pixel-size mapping
_FONT_SIZE_MAP = {"small": 12, "medium": 14, "large": 16}
_FONT_SIZE_LABELS = {v: k for k, v in _FONT_SIZE_MAP.items()}


class SettingsService(QObject):
    """Persistent settings manager using QSettings (Windows registry / INI).

    All user preferences are written immediately on change and survive restarts.
    """

    # Signals
    themeModeChanged = Signal()
    fontSizeChanged = Signal()
    globalFontChanged = Signal(int)  # Emitted with pixel size for app.setFont()
    liveMonitoringChanged = Signal()
    updateIntervalMsChanged = Signal()
    enableGpuMonitoringChanged = Signal()
    closeToTrayChanged = Signal()
    startMinimizedChanged = Signal()
    startWithSystemChanged = Signal()
    sendErrorReportsChanged = Signal()
    networkUnitChanged = Signal()
    saveError = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

        self._platform = platform.system()

        # QSettings persists to Windows Registry under
        # HKEY_CURRENT_USER\Software\SentinelSecurity\SentinelApp
        self._qs = QSettings("SentinelSecurity", "SentinelApp")

        # Load persisted values (with sane defaults)
        self._theme_mode: str = self._qs.value("themeMode", "dark")
        self._font_size: str = self._qs.value("fontSize", "medium")
        self._live_monitoring: bool = self._qs.value("liveMonitoring", True, type=bool)
        self._update_interval_ms: int = self._qs.value(
            "updateIntervalMs", 2000, type=int
        )
        self._enable_gpu_monitoring: bool = self._qs.value(
            "enableGpuMonitoring", True, type=bool
        )
        self._start_minimized: bool = self._qs.value(
            "startMinimized", False, type=bool
        )
        self._start_with_system: bool = self._qs.value(
            "startWithSystem", False, type=bool
        )
        self._send_error_reports: bool = self._qs.value(
            "sendErrorReports", False, type=bool
        )
        self._network_unit: str = self._qs.value("networkUnit", "auto")

        # Autostart is Windows-only today; do not carry a stale enabled value
        # onto unsupported platforms.
        if sys.platform != "win32" and self._start_with_system:
            self._start_with_system = False
            self._qs.setValue("startWithSystem", False)

        _log.debug("Loaded from QSettings (scope=%s)", self._qs.fileName())

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @Property(str, notify=themeModeChanged)
    def themeMode(self) -> str:
        return self._theme_mode

    @themeMode.setter
    def themeMode(self, value: str):
        if value in ("system", "dark", "light") and value != self._theme_mode:
            self._theme_mode = value
            self._qs.setValue("themeMode", value)
            self.themeModeChanged.emit()

    @Property(str, notify=fontSizeChanged)
    def fontSize(self) -> str:
        return self._font_size

    @fontSize.setter
    def fontSize(self, value: str):
        if value in ("small", "medium", "large") and value != self._font_size:
            self._font_size = value
            self._qs.setValue("fontSize", value)
            self.fontSizeChanged.emit()
            self.globalFontChanged.emit(_FONT_SIZE_MAP.get(value, 14))

    @Property(int, notify=fontSizeChanged)
    def fontSizePixels(self) -> int:
        """The current font size as a pixel value (12 / 14 / 16)."""
        return _FONT_SIZE_MAP.get(self._font_size, 14)

    @Property(bool, notify=liveMonitoringChanged)
    def liveMonitoring(self) -> bool:
        return self._live_monitoring

    @liveMonitoring.setter
    def liveMonitoring(self, value: bool):
        if value != self._live_monitoring:
            self._live_monitoring = value
            self._qs.setValue("liveMonitoring", value)
            self.liveMonitoringChanged.emit()

    @Property(int, notify=updateIntervalMsChanged)
    def updateIntervalMs(self) -> int:
        return self._update_interval_ms

    @updateIntervalMs.setter
    def updateIntervalMs(self, value: int):
        if value >= 500 and value != self._update_interval_ms:
            self._update_interval_ms = value
            self._qs.setValue("updateIntervalMs", value)
            self.updateIntervalMsChanged.emit()

    @Property(bool, notify=enableGpuMonitoringChanged)
    def enableGpuMonitoring(self) -> bool:
        return self._enable_gpu_monitoring

    @enableGpuMonitoring.setter
    def enableGpuMonitoring(self, value: bool):
        if value != self._enable_gpu_monitoring:
            self._enable_gpu_monitoring = value
            self._qs.setValue("enableGpuMonitoring", value)
            self.enableGpuMonitoringChanged.emit()

    @Property(bool, notify=closeToTrayChanged)
    def closeToTray(self) -> bool:
        return self._start_minimized

    @closeToTray.setter
    def closeToTray(self, value: bool):
        if value != self._start_minimized:
            self._start_minimized = value
            self._qs.setValue("startMinimized", value)
            self.closeToTrayChanged.emit()
            self.startMinimizedChanged.emit()

    @Property(bool, notify=startMinimizedChanged)
    def startMinimized(self) -> bool:
        return self._start_minimized

    @startMinimized.setter
    def startMinimized(self, value: bool):
        self.closeToTray = value

    @Property(bool, notify=startWithSystemChanged)
    def startWithSystem(self) -> bool:
        return self._start_with_system

    @startWithSystem.setter
    def startWithSystem(self, value: bool):
        normalized = bool(value) if self.supportsAutostart else False
        if value and not self.supportsAutostart:
            _log.info("Ignoring autostart enable request on unsupported platform")

        if normalized != self._start_with_system:
            self._start_with_system = normalized
            self._qs.setValue("startWithSystem", normalized)
            self.startWithSystemChanged.emit()
            if self.supportsAutostart:
                self._set_windows_autostart(normalized)

    @Property(bool, notify=sendErrorReportsChanged)
    def sendErrorReports(self) -> bool:
        return self._send_error_reports

    @sendErrorReports.setter
    def sendErrorReports(self, value: bool):
        if value != self._send_error_reports:
            self._send_error_reports = value
            self._qs.setValue("sendErrorReports", value)
            self.sendErrorReportsChanged.emit()

    @Property(str, notify=networkUnitChanged)
    def networkUnit(self) -> str:
        return self._network_unit

    @networkUnit.setter
    def networkUnit(self, value: str):
        if (
            value in ("auto", "bps", "Kbps", "Mbps", "Gbps")
            and value != self._network_unit
        ):
            self._network_unit = value
            self._qs.setValue("networkUnit", value)
            self.networkUnitChanged.emit()

    # ------------------------------------------------------------------
    # Platform info (constant)
    # ------------------------------------------------------------------
    @Property(str, constant=True)
    def platformName(self) -> str:
        return self._platform

    @Property(bool, constant=True)
    def isWindows(self) -> bool:
        return sys.platform == "win32"

    @Property(bool, constant=True)
    def supportsAutostart(self) -> bool:
        return sys.platform == "win32"

    @Property(bool, constant=True)
    def supportsCloseToTray(self) -> bool:
        try:
            from PySide6.QtWidgets import QApplication, QSystemTrayIcon

            return (
                QApplication.instance() is not None
                and QSystemTrayIcon.isSystemTrayAvailable()
            )
        except (ImportError, RuntimeError):
            return False

    @Property(str, constant=True)
    def settingsPath(self) -> str:
        return self._qs.fileName()

    # ------------------------------------------------------------------
    # Run on Startup — Windows Registry
    # ------------------------------------------------------------------
    def _set_windows_autostart(self, enable: bool):
        """Add/remove Sentinel from HKCU\\...\\Run via winreg (Windows only)."""
        if sys.platform != "win32":
            return
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = "Sentinel"

            if getattr(sys, "frozen", False):
                # PyInstaller bundle — the .exe itself
                exe_path = f'"{sys.executable}"'
            else:
                # Dev mode — quote both python and script paths
                python_exe = Path(sys.executable).resolve()
                main_py = Path(__file__).resolve().parent.parent.parent / "main.py"
                exe_path = f'"{python_exe}" "{main_py}"'

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
            ) as key:
                if enable:
                    winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
                    _log.info("Autostart enabled: %s", exe_path)
                else:
                    try:
                        winreg.DeleteValue(key, app_name)
                        _log.info("Autostart disabled")
                    except FileNotFoundError:
                        pass
        except OSError as e:
            error_msg = f"Could not set autostart: {e}"
            _log.warning("Autostart registry error: %s", e)
            self.saveError.emit(error_msg)

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------
    @Slot()
    def resetToDefaults(self):
        """Reset all settings to defaults and clear the registry startup entry."""
        self._theme_mode = "dark"
        self._font_size = "medium"
        self._live_monitoring = True
        self._update_interval_ms = 2000
        self._enable_gpu_monitoring = True
        self._start_minimized = False
        self._start_with_system = False
        self._send_error_reports = False
        self._network_unit = "auto"

        self._set_windows_autostart(False)

        # Persist
        self._qs.setValue("themeMode", self._theme_mode)
        self._qs.setValue("fontSize", self._font_size)
        self._qs.setValue("liveMonitoring", self._live_monitoring)
        self._qs.setValue("updateIntervalMs", self._update_interval_ms)
        self._qs.setValue("enableGpuMonitoring", self._enable_gpu_monitoring)
        self._qs.setValue("startMinimized", self._start_minimized)
        self._qs.setValue("startWithSystem", self._start_with_system)
        self._qs.setValue("sendErrorReports", self._send_error_reports)
        self._qs.setValue("networkUnit", self._network_unit)

        # Notify all listeners
        self.themeModeChanged.emit()
        self.fontSizeChanged.emit()
        self.globalFontChanged.emit(_FONT_SIZE_MAP["medium"])
        self.liveMonitoringChanged.emit()
        self.updateIntervalMsChanged.emit()
        self.enableGpuMonitoringChanged.emit()
        self.closeToTrayChanged.emit()
        self.startMinimizedChanged.emit()
        self.startWithSystemChanged.emit()
        self.sendErrorReportsChanged.emit()
        self.networkUnitChanged.emit()

        _log.info("Settings reset to defaults")
