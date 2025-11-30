"""Cross-platform Settings Service with persistence."""

import json
import os
import platform
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Property, Signal, Slot


class SettingsService(QObject):
    """Cross-platform settings manager with JSON persistence.

    Settings are stored in:
    - Windows: %APPDATA%/Sentinel/settings.json
    - Linux: ~/.config/sentinel/settings.json
    - macOS: ~/Library/Application Support/Sentinel/settings.json
    """

    # Signals
    themeModeChanged = Signal()
    fontSizeChanged = Signal()
    updateIntervalMsChanged = Signal()
    enableGpuMonitoringChanged = Signal()
    startMinimizedChanged = Signal()
    startWithSystemChanged = Signal()
    sendErrorReportsChanged = Signal()
    networkUnitChanged = Signal()
    saveError = Signal(str)  # Emitted when settings cannot be saved

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        # Detect platform
        self._platform = platform.system()
        self._is_windows = self._platform == "Windows"
        self._is_linux = self._platform == "Linux"
        self._is_macos = self._platform == "Darwin"

        # Default settings
        self._theme_mode = "dark"  # "system", "dark", "light"
        self._font_size = "medium"  # "small", "medium", "large"
        self._update_interval_ms = 2000
        self._enable_gpu_monitoring = True
        self._start_minimized = False
        self._start_with_system = False
        self._send_error_reports = False
        self._network_unit = "auto"  # "auto", "bps", "Kbps", "Mbps", "Gbps"

        # Settings file path
        self._settings_path = self._get_settings_path()

        # Load settings
        self._load_settings()

    def _get_settings_path(self) -> Path:
        """Get platform-specific settings file path."""
        if self._is_windows:
            # Windows: %APPDATA%/Sentinel
            base = Path(os.getenv("APPDATA", ""))
        elif self._is_macos:
            # macOS: ~/Library/Application Support/Sentinel
            base = Path.home() / "Library" / "Application Support"
        else:
            # Linux: ~/.config/sentinel
            base = Path.home() / ".config"

        settings_dir = base / "Sentinel"
        settings_dir.mkdir(parents=True, exist_ok=True)
        return settings_dir / "settings.json"

    def _load_settings(self):
        """Load settings from JSON file."""
        try:
            if self._settings_path.exists():
                with open(self._settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self._theme_mode = data.get("themeMode", self._theme_mode)
                self._font_size = data.get("fontSize", self._font_size)
                self._update_interval_ms = data.get(
                    "updateIntervalMs", self._update_interval_ms
                )
                self._enable_gpu_monitoring = data.get(
                    "enableGpuMonitoring", self._enable_gpu_monitoring
                )
                self._start_minimized = data.get(
                    "startMinimized", self._start_minimized
                )
                self._start_with_system = data.get(
                    "startWithSystem", self._start_with_system
                )
                self._send_error_reports = data.get(
                    "sendErrorReports", self._send_error_reports
                )
                self._network_unit = data.get("networkUnit", self._network_unit)

                print(f"[Settings] Loaded from {self._settings_path}")
        except (IOError, json.JSONDecodeError) as e:
            print(f"[Settings] Could not load settings: {e}")

    def _save_settings(self):
        """Save settings to JSON file."""
        try:
            data = {
                "themeMode": self._theme_mode,
                "fontSize": self._font_size,
                "updateIntervalMs": self._update_interval_ms,
                "enableGpuMonitoring": self._enable_gpu_monitoring,
                "startMinimized": self._start_minimized,
                "startWithSystem": self._start_with_system,
                "sendErrorReports": self._send_error_reports,
                "networkUnit": self._network_unit,
            }

            with open(self._settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            print(f"[Settings] Saved to {self._settings_path}")
        except IOError as e:
            error_msg = f"Could not save settings: {e}"
            print(f"[Settings] {error_msg}")
            self.saveError.emit(error_msg)

    # Properties
    @Property(str, notify=themeModeChanged)
    def themeMode(self) -> str:
        return self._theme_mode

    @themeMode.setter
    def themeMode(self, value: str):
        if value in ("system", "dark", "light") and value != self._theme_mode:
            self._theme_mode = value
            self.themeModeChanged.emit()
            self._save_settings()

    @Property(str, notify=fontSizeChanged)
    def fontSize(self) -> str:
        return self._font_size

    @fontSize.setter
    def fontSize(self, value: str):
        if value in ("small", "medium", "large") and value != self._font_size:
            self._font_size = value
            self.fontSizeChanged.emit()
            self._save_settings()

    @Property(int, notify=updateIntervalMsChanged)
    def updateIntervalMs(self) -> int:
        return self._update_interval_ms

    @updateIntervalMs.setter
    def updateIntervalMs(self, value: int):
        if value >= 500 and value != self._update_interval_ms:
            self._update_interval_ms = value
            self.updateIntervalMsChanged.emit()
            self._save_settings()

    @Property(bool, notify=enableGpuMonitoringChanged)
    def enableGpuMonitoring(self) -> bool:
        return self._enable_gpu_monitoring

    @enableGpuMonitoring.setter
    def enableGpuMonitoring(self, value: bool):
        if value != self._enable_gpu_monitoring:
            self._enable_gpu_monitoring = value
            self.enableGpuMonitoringChanged.emit()
            self._save_settings()

    @Property(bool, notify=startMinimizedChanged)
    def startMinimized(self) -> bool:
        return self._start_minimized

    @startMinimized.setter
    def startMinimized(self, value: bool):
        if value != self._start_minimized:
            self._start_minimized = value
            self.startMinimizedChanged.emit()
            self._save_settings()

    @Property(bool, notify=startWithSystemChanged)
    def startWithSystem(self) -> bool:
        return self._start_with_system

    @startWithSystem.setter
    def startWithSystem(self, value: bool):
        if value != self._start_with_system:
            self._start_with_system = value
            self.startWithSystemChanged.emit()
            self._save_settings()

            # Apply autostart on Windows
            if self._is_windows:
                self._set_windows_autostart(value)

    @Property(bool, notify=sendErrorReportsChanged)
    def sendErrorReports(self) -> bool:
        return self._send_error_reports

    @sendErrorReports.setter
    def sendErrorReports(self, value: bool):
        if value != self._send_error_reports:
            self._send_error_reports = value
            self.sendErrorReportsChanged.emit()
            self._save_settings()

    @Property(str, notify=networkUnitChanged)
    def networkUnit(self) -> str:
        """Network throughput display unit: 'auto', 'bps', 'Kbps', 'Mbps', 'Gbps'."""
        return self._network_unit

    @networkUnit.setter
    def networkUnit(self, value: str):
        if (
            value in ["auto", "bps", "Kbps", "Mbps", "Gbps"]
            and value != self._network_unit
        ):
            self._network_unit = value
            self.networkUnitChanged.emit()
            self._save_settings()

    # Platform info properties
    @Property(str, constant=True)
    def platformName(self) -> str:
        return self._platform

    @Property(bool, constant=True)
    def isWindows(self) -> bool:
        return self._is_windows

    @Property(bool, constant=True)
    def isLinux(self) -> bool:
        return self._is_linux

    @Property(bool, constant=True)
    def isMacOS(self) -> bool:
        return self._is_macos

    @Property(bool, constant=True)
    def supportsAutostart(self) -> bool:
        """Whether autostart is supported on this platform."""
        return self._is_windows  # Only Windows for now

    @Property(str, constant=True)
    def settingsPath(self) -> str:
        """Path to the settings file."""
        return str(self._settings_path)

    def _set_windows_autostart(self, enable: bool):
        """Set Windows autostart registry key."""
        if not self._is_windows:
            return

        try:
            import winreg
            import sys

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = "Sentinel"

            # Get executable path
            if getattr(sys, "frozen", False):
                exe_path = sys.executable
            else:
                # Development mode: use python + main.py
                python_exe = sys.executable
                main_py = Path(__file__).parent.parent.parent / "main.py"
                exe_path = f'"{python_exe}" "{main_py}"'

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
            ) as key:
                if enable:
                    winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
                    print(f"[Settings] Autostart enabled: {exe_path}")
                else:
                    try:
                        winreg.DeleteValue(key, app_name)
                        print("[Settings] Autostart disabled")
                    except FileNotFoundError:
                        pass  # Key doesn't exist

        except (ImportError, OSError) as e:
            print(f"[Settings] Could not set autostart: {e}")

    @Slot()
    def resetToDefaults(self):
        """Reset all settings to defaults."""
        self._theme_mode = "dark"
        self._update_interval_ms = 2000
        self._enable_gpu_monitoring = True
        self._start_minimized = False
        self._start_with_system = False
        self._send_error_reports = False
        self._network_unit = "auto"

        # Emit all signals
        self.themeModeChanged.emit()
        self.updateIntervalMsChanged.emit()
        self.enableGpuMonitoringChanged.emit()
        self.startMinimizedChanged.emit()
        self.startWithSystemChanged.emit()
        self.sendErrorReportsChanged.emit()
        self.networkUnitChanged.emit()

        self._save_settings()
