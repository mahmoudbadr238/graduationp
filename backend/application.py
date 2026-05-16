"""Sentinel Desktop Security Application - Optimized for fast startup."""

import logging
import os
import sys

_log = logging.getLogger(__name__)

from PySide6.QtCore import QThreadPool, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtQml import QQmlApplicationEngine

from backend.runtime import bundle_root
from backend.platform import IS_WINDOWS, IS_LINUX

from .core.config import get_config
from .core.container import configure
from .core.logging_setup import setup_crash_handlers, setup_logging
from .core.perf_monitor import start_perf_monitor
from .core.startup_orchestrator import StartupOrchestrator
from .infra.integrations import print_integration_status
if IS_WINDOWS:
    from .infra.privileges import is_admin
else:
    from .platform.linux.admin import check_admin as is_admin
from .api.backend_bridge import BackendBridge
from .api.gpu_service import get_gpu_service
from .api.notification_service import NotificationService, get_notification_service
from .api.notification_manager import NotificationManager
from .api.settings_service import SettingsService

# Platform-aware imports
if IS_WINDOWS:
    from .api.security_controller import get_security_controller
    from .api.system_snapshot_service import SystemSnapshotService
else:
    from .platform.linux.security_controller import get_security_controller
    from .platform.linux.system_snapshot_service import SystemSnapshotService


class DesktopSecurityApplication:
    """Main application class with optimized startup and thread pool management."""

    def __init__(self):
        # Initialize logging first (before any imports)
        setup_logging("Sentinel")
        setup_crash_handlers("Sentinel")

        # Start lightweight performance monitoring (logs to sentinel.log)
        # Use 15-second interval to reduce CPU overhead
        start_perf_monitor(interval_seconds=15)

        # Load configuration
        self.config = get_config()

        # Set Controls style to Fusion to enable full customization
        os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Fusion")

        # Create Qt application
        self.app = QApplication(sys.argv)

        # Set application properties
        self.app.setApplicationName("Sentinel")
        self.app.setOrganizationName("SecuritySuite")
        # Ensure QSettings has required identifiers
        # organizationDomain is required on some platforms to initialize QSettings
        try:
            self.app.setOrganizationDomain("sentinel.local")
        except RuntimeError as exc:
            _log.debug("Could not set organization domain: %s", exc)

        # Configure thread pool for background tasks
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(4)

        # Create startup orchestrator for deferred initialization
        self.orchestrator = StartupOrchestrator()

        # Create QML engine
        self.engine = QQmlApplicationEngine()

        # Connect to application closing
        self.app.aboutToQuit.connect(self._on_app_quit)  # Set up paths
        self._setup_paths()

        # Initialize backend
        self.backend = None
        self.gpu_service = None
        self.snapshot_service = None
        self.settings_service = None
        self.notification_service = None
        self.notification_manager = None
        self.sandbox_lab = None
        self.file_function_service = None
        self.security_controller = None
        self.resource_monitor = None
        self.rtp_bridge = None
        self.tray_icon = None
        self._setup_backend()

    def _setup_paths(self):
        """Set up QML import paths and working directory."""
        workspace_root = str(bundle_root())

        # Set working directory
        os.chdir(workspace_root)
        _log.debug("Working directory set to: %s", workspace_root)

        # Add QML import paths
        qml_path = os.path.join(workspace_root, "frontend", "qml")
        self.engine.addImportPath(qml_path)

        # Add subdirectories for component imports
        self.engine.addImportPath(os.path.join(qml_path, "components"))
        self.engine.addImportPath(os.path.join(qml_path, "theme"))
        self.engine.addImportPath(os.path.join(qml_path, "pages"))
        self.engine.addImportPath(os.path.join(qml_path, "ux"))  # For Theme singleton
        self.engine.addImportPath(os.path.join(qml_path, "ui"))   # For ThemeManager singleton

        # Set QML context properties for component paths
        components_path = os.path.join(qml_path, "components").replace("\\", "/")
        theme_path = os.path.join(qml_path, "theme").replace("\\", "/")
        self.engine.rootContext().setContextProperty("componentPath", components_path)
        self.engine.rootContext().setContextProperty("themePath", theme_path)

        _log.debug("QML import paths configured (%d paths)", len(self.engine.importPathList()))

    def _setup_backend(self):
        """Initialize backend with deferred loading for fast startup."""
        try:
            _log.info("Initializing backend services")

            # IMMEDIATE: Configure DI container (required for app structure)
            configure()
            _log.info("Dependency injection container configured")

            # IMMEDIATE: Create backend instance (but defer heavy initialization)
            # This allows QML to reference Backend immediately on load
            self.backend = BackendBridge()
            # Register backend BEFORE loading QML to avoid "Backend not available" warnings
            self.engine.rootContext().setContextProperty("Backend", self.backend)

            # Register sandbox preview image provider for live preview (Windows only)
            if IS_WINDOWS:
                try:
                    from .api.sandbox_preview_provider import register_preview_provider

                    preview_controller = register_preview_provider(
                        self.engine, self.backend
                    )
                    if preview_controller:
                        self.engine.rootContext().setContextProperty(
                            "SandboxPreview", preview_controller
                        )
                        _log.info("Sandbox preview provider registered")
                except ImportError as e:
                    _log.warning("Sandbox preview provider not available: %s", e)

            # DEFERRED: Heavy backend initialization (100ms after startup)
            def init_backend_heavy():
                try:
                    # Start live monitoring after UI is ready
                    self.backend.startLive()
                    _log.info("Backend monitoring started")
                except (ImportError, RuntimeError, OSError) as e:
                    _log.warning("Backend monitoring failed: %s", e)

            self.orchestrator.schedule_deferred(
                100, "Backend Monitoring", init_backend_heavy
            )

            # PLACEHOLDER: Register null so QML gpuServiceAvailable binding tracks this
            # property reactively from startup (avoids typeof-undefined gotcha).
            self.engine.rootContext().setContextProperty("GPUService", None)

            # DEFERRED: GPU service registration only (NOT auto-started to save resources)
            # GPU monitoring will start when user opens the GPU Monitor page
            def init_gpu():
                try:
                    self.gpu_service = get_gpu_service()
                    root_context = self.engine.rootContext()
                    root_context.setContextProperty("GPUService", self.gpu_service)
                    # GPU service is registered but NOT started
                    # It will start when the GPU Monitor page is opened via GPUService.start()
                    _log.info("GPU service registered (lazy-load — starts on demand)")
                except (ImportError, RuntimeError, OSError) as e:
                    _log.warning("GPU service initialization failed: %s", e)
                    self.gpu_service = None

            self.orchestrator.schedule_deferred(1000, "GPU Backend", init_gpu)

            # PLACEHOLDER: Register None so QML doesn't error on missing property
            self.engine.rootContext().setContextProperty("SnapshotService", None)

            # DEFERRED: System Snapshot Service (200ms after startup)
            def init_snapshot():
                try:
                    self.snapshot_service = SystemSnapshotService()
                    self.snapshot_service._update_metrics()
                    self.snapshot_service._update_disk_partitions()
                    self.snapshot_service._update_network_interfaces()
                    self.engine.rootContext().setContextProperty(
                        "SnapshotService", self.snapshot_service
                    )
                    self.snapshot_service.start(5000)
                    _log.info(
                        "System Snapshot service ready (CPU=%.1f%%, MEM=%.1f%%)",
                        self.snapshot_service.cpuUsage,
                        self.snapshot_service.memoryUsage,
                    )
                    if self.backend:
                        self.backend.set_snapshot_service(self.snapshot_service)
                except (ImportError, RuntimeError, OSError) as e:
                    _log.warning("System Snapshot service failed: %s", e)
                    self.snapshot_service = None

            self.orchestrator.schedule_deferred(200, "Snapshot Service", init_snapshot)

            # PLACEHOLDER for QML
            self.engine.rootContext().setContextProperty("SecurityController", None)

            # DEFERRED: Security Controller (300ms)
            def init_security_controller():
                try:
                    self.security_controller = get_security_controller()
                    self.engine.rootContext().setContextProperty(
                        "SecurityController", self.security_controller
                    )
                    _log.info("Security Controller registered")
                except (ImportError, RuntimeError, OSError) as e:
                    _log.warning("Security Controller failed: %s", e)
                    self.security_controller = None

            self.orchestrator.schedule_deferred(300, "Security Controller", init_security_controller)

            # IMMEDIATE: Settings Service (cross-platform)
            try:
                self.settings_service = SettingsService()
                self.engine.rootContext().setContextProperty(
                    "SettingsService", self.settings_service
                )

                # Apply saved font size globally on startup
                self._apply_global_font(self.settings_service.fontSizePixels)

                # Keep global font in sync whenever the user changes it
                self.settings_service.globalFontChanged.connect(
                    self._apply_global_font
                )
                self.settings_service.closeToTrayChanged.connect(
                    self._apply_close_behavior
                )

                _log.info("Settings service initialized")
            except (ImportError, RuntimeError, OSError) as e:
                _log.warning("Settings service failed: %s", e)
                self.settings_service = None

            # IMMEDIATE: VMware Sandbox Lab controller (Windows only)
            if IS_WINDOWS:
                try:
                    from .engines.sandbox_vmware import SandboxLabController

                    self.sandbox_lab = SandboxLabController()
                    self.engine.rootContext().setContextProperty(
                        "SandboxLab", self.sandbox_lab
                    )
                    _log.info("Sandbox Lab controller registered")
                except Exception as e:
                    _log.warning("Sandbox Lab controller failed: %s", e)
                    self.sandbox_lab = None
                    self.engine.rootContext().setContextProperty("SandboxLab", None)
            else:
                self.sandbox_lab = None
                self.engine.rootContext().setContextProperty("SandboxLab", None)
                _log.debug("Sandbox Lab not available on this platform")

            # IMMEDIATE: File Function Service (shred + recovery)
            try:
                # Route secure_delete to platform-specific version before
                # importing FileFunctionBridge (which uses it at module level)
                if IS_LINUX:
                    import backend.utils.secure_delete as _sd_mod
                    from backend.platform.linux.secure_delete import (
                        validate_target as _vt,
                        shred_file as _sf,
                    )
                    _sd_mod.validate_target = _vt
                    _sd_mod.shred_file = _sf

                from .engines.filefunction.backend_bridge import FileFunctionBridge

                self.file_function_service = FileFunctionBridge()
                self.engine.rootContext().setContextProperty(
                    "backend", self.file_function_service
                )
                _log.info("File Function service registered")
            except (ImportError, RuntimeError, OSError) as e:
                _log.warning("File Function service failed: %s", e)
                self.file_function_service = None

            # IMMEDIATE: Recovery Controller
            # Windows: Win32 CreateFile + sector-aligned reads
            # Linux:   direct open('/dev/sdX','rb') — requires root
            try:
                from .engines.filefunction.recovery_controller import RecoveryController

                self.recovery_controller = RecoveryController()
                self.engine.rootContext().setContextProperty(
                    "RecoveryService", self.recovery_controller
                )
                _log.info("Recovery controller registered")
            except Exception as e:
                _log.warning("Recovery controller failed: %s", e)
                self.recovery_controller = None
                self.engine.rootContext().setContextProperty("RecoveryService", None)

            # PLACEHOLDER for QML
            self.engine.rootContext().setContextProperty("NotificationService", None)
            self.engine.rootContext().setContextProperty("NotificationManager", None)

            # DEFERRED: Notification Service (400ms)
            def init_notifications():
                try:
                    self.notification_service = get_notification_service()
                    self.engine.rootContext().setContextProperty(
                        "NotificationService", self.notification_service
                    )
                    _log.info("Notification service initialized")

                    self.notification_manager = NotificationManager(
                        self.notification_service
                    )
                    self.engine.rootContext().setContextProperty(
                        "NotificationManager", self.notification_manager
                    )
                    _log.info("NotificationManager created")

                    if self.snapshot_service:
                        self.snapshot_service.set_notification_service(
                            self.notification_service
                        )
                        _log.info("Security notifications connected")
                except (ImportError, RuntimeError, OSError) as e:
                    _log.warning("Notification service failed: %s", e)
                    self.notification_service = None

            self.orchestrator.schedule_deferred(400, "Notifications", init_notifications)

            # PLACEHOLDER for QML
            self.engine.rootContext().setContextProperty("ResourceMonitor", None)

            # DEFERRED: Resource Monitor (500ms)
            def init_resource_monitor():
                try:
                    from .core.resource_monitor import get_resource_monitor_bridge

                    self.resource_monitor = get_resource_monitor_bridge()
                    self.engine.rootContext().setContextProperty(
                        "ResourceMonitor", self.resource_monitor
                    )
                    self.resource_monitor.start()
                    _log.info("Resource Monitor registered and started")
                except (ImportError, RuntimeError, OSError) as e:
                    _log.warning("Resource Monitor failed: %s", e)
                    self.resource_monitor = None

            self.orchestrator.schedule_deferred(500, "Resource Monitor", init_resource_monitor)

            # IMMEDIATE: Real-Time Protection Bridge
            try:
                from .core.realtime_protection import get_rtp_bridge

                self.rtp_bridge = get_rtp_bridge()
                self.engine.rootContext().setContextProperty(
                    "RTPBridge", self.rtp_bridge
                )
                _log.info("RTP Bridge registered")

                self.orchestrator.schedule_deferred(
                    500, "RTP Auto-Start", self._auto_start_rtp_if_configured
                )
            except (ImportError, RuntimeError, OSError) as e:
                _log.warning("RTP Bridge failed: %s", e)
                self.rtp_bridge = None

        except (ImportError, RuntimeError, UnicodeEncodeError) as e:
            _log.critical("Critical backend setup failed: %s", e)
            _log.warning("Application will continue with limited functionality")

    def _apply_global_font(self, pixel_size: int):
        """Set the application-wide default font size (affects all QML text)."""
        font = self.app.font()
        font.setPixelSize(pixel_size)
        self.app.setFont(font)
        _log.debug("Global font size set to %dpx", pixel_size)

    def _create_qml_engine(self):
        """Load main QML file and create engine."""
        # Load main.qml
        qml_file = os.path.join(os.getcwd(), "frontend", "qml", "main.qml")
        _log.info("Loading QML: %s", qml_file)

        # Load the main QML file
        self.engine.load(qml_file)

        # Check that the file was loaded successfully
        if not self.engine.rootObjects():
            raise RuntimeError("Unable to load Sentinel UI (main.qml)")

        # Allow drag-and-drop when running as admin (UIPI bypass)
        self._allow_drag_drop_elevated()

        # IMMEDIATE: VMware window embedder (Win32 SetParent integration)
        self._init_vmware_embedder()

    def _allow_drag_drop_elevated(self):
        """Enable native WM_DROPFILES drag-and-drop for elevated process.

        Qt Quick's DropArea uses OLE drag-and-drop which is blocked by UIPI
        when running elevated. We use the Win32 WM_DROPFILES pathway instead:
        1. ChangeWindowMessageFilterEx on the actual HWND
        2. DragAcceptFiles to opt into WM_DROPFILES
        3. Native event filter to intercept WM_DROPFILES and forward to QML
        """
        if sys.platform != "win32":
            return

        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            shell32 = ctypes.windll.shell32

            # Get the HWND from the root QML window
            root_objects = self.engine.rootObjects()
            if not root_objects:
                return
            window = root_objects[0]
            hwnd = int(window.winId())

            # --- Per-window message filter (more reliable than global) ---
            ChangeWindowMessageFilterEx = user32.ChangeWindowMessageFilterEx
            ChangeWindowMessageFilterEx.argtypes = [
                wintypes.HWND, wintypes.UINT, wintypes.DWORD, wintypes.LPVOID
            ]
            ChangeWindowMessageFilterEx.restype = wintypes.BOOL

            MSGFLT_ALLOW = 1
            WM_DROPFILES = 0x0233
            WM_COPYDATA = 0x004A
            WM_COPYGLOBALDATA = 0x0049

            ChangeWindowMessageFilterEx(hwnd, WM_DROPFILES, MSGFLT_ALLOW, None)
            ChangeWindowMessageFilterEx(hwnd, WM_COPYDATA, MSGFLT_ALLOW, None)
            ChangeWindowMessageFilterEx(hwnd, WM_COPYGLOBALDATA, MSGFLT_ALLOW, None)

            # --- Also set the global filter as fallback ---
            ChangeWindowMessageFilter = user32.ChangeWindowMessageFilter
            ChangeWindowMessageFilter.argtypes = [wintypes.UINT, wintypes.DWORD]
            ChangeWindowMessageFilter.restype = wintypes.BOOL
            MSGFLT_ADD = 1
            ChangeWindowMessageFilter(WM_DROPFILES, MSGFLT_ADD)
            ChangeWindowMessageFilter(WM_COPYDATA, MSGFLT_ADD)
            ChangeWindowMessageFilter(WM_COPYGLOBALDATA, MSGFLT_ADD)

            # --- Enable WM_DROPFILES on the window ---
            shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
            shell32.DragAcceptFiles(hwnd, True)

            # --- Install native event filter to catch WM_DROPFILES ---
            from backend.utils.drop_event_filter import DropEventFilter
            self._drop_filter = DropEventFilter(hwnd, parent=self.app)
            if hasattr(self, 'file_function_service') and self.file_function_service:
                self._drop_filter.fileDropped.connect(
                    self.file_function_service.fileDropped.emit
                )
            self.app.installNativeEventFilter(self._drop_filter)

            _log.info("Drag-and-drop enabled for elevated process (UIPI + WM_DROPFILES)")
        except Exception as e:
            _log.warning("Could not enable drag-and-drop UIPI bypass: %s", e)

    def _init_vmware_embedder(self):
        """Create the VMware window embedder and wire it to the backend bridge."""
        if sys.platform != "win32":
            return
        try:
            from .engines.sandbox_vmware.window_embedder import VmwareWindowEmbedder

            self.vmware_embedder = VmwareWindowEmbedder(parent=self.app)
            self.engine.rootContext().setContextProperty(
                "VmwareEmbedder", self.vmware_embedder,
            )

            # Wire embedder into BackendBridge (QML WindowContainer handles parenting)
            if self.backend is not None:
                self.backend.set_vmware_embedder(self.vmware_embedder)

            _log.info("VMware window embedder registered")
        except Exception as e:
            _log.warning("VMware window embedder failed: %s", e)

    def _setup_system_tray(self):
        """Set up QSystemTrayIcon with context menu and alert forwarding."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            _log.warning("System tray not available")
            return

        # Icon — try to load app icon, fall back to built-in
        icon_path = os.path.join(os.getcwd(), "resources", "sentinel_icon.png")
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            icon = QIcon.fromTheme("security-high")
            if icon.isNull():
                # Fallback — create a simple icon from application style
                from PySide6.QtGui import QPixmap, QPainter, QColor
                pixmap = QPixmap(64, 64)
                pixmap.fill(QColor(0, 0, 0, 0))
                painter = QPainter(pixmap)
                painter.setBrush(QColor("#6366f1"))
                painter.setPen(QColor("#6366f1"))
                painter.drawEllipse(4, 4, 56, 56)
                painter.setPen(QColor("white"))
                font = painter.font()
                font.setPixelSize(32)
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(pixmap.rect(), 0x0084, "S")  # AlignCenter
                painter.end()
                icon = QIcon(pixmap)

        self.tray_icon = QSystemTrayIcon(icon, self.app)
        self.tray_icon.setToolTip("Sentinel — Endpoint Security Suite")

        # Context menu
        menu = QMenu()

        show_action = menu.addAction("Show Dashboard")
        show_action.triggered.connect(self._show_main_window)

        menu.addSeparator()

        monitor_action = menu.addAction("System Monitor")
        monitor_action.triggered.connect(lambda: self._show_and_navigate("system-monitor"))

        menu.addSeparator()

        quit_action = menu.addAction("Quit Sentinel")
        quit_action.triggered.connect(self._quit_from_tray)

        self.tray_icon.setContextMenu(menu)

        # Double-click tray icon → show window
        self.tray_icon.activated.connect(self._on_tray_activated)

        # Bind the tray icon to the NotificationManager so toasts work
        if self.notification_manager:
            self.notification_manager.set_tray_icon(self.tray_icon)
            _log.info("NotificationManager linked to system tray icon")

        # Connect resource alerts → unified notification manager (QML + toast)
        if self.resource_monitor:
            if self.notification_manager:
                self.resource_monitor.alertTriggered.connect(
                    lambda title, msg: self.notification_manager.notify(
                        title, msg, "warning"
                    )
                )
            else:
                self.resource_monitor.alertTriggered.connect(self._show_tray_alert)

        # Connect RTP threats → unified notification manager (QML + toast)
        if self.rtp_bridge:
            if self.notification_manager:
                self.rtp_bridge.threatDetected.connect(
                    lambda msg: self.notification_manager.notify(
                        "🛡️ Sentinel RTP", msg, "error"
                    )
                )
            else:
                self.rtp_bridge.threatDetected.connect(
                    lambda msg: self._show_tray_alert("🛡️ Sentinel RTP", msg)
                )

        self.tray_icon.show()
        _log.info("System tray icon active")

    def _close_to_tray_supported(self) -> bool:
        """Return True when the current session can keep running in the tray."""
        return bool(self.tray_icon and self.tray_icon.isVisible())

    def _apply_close_behavior(self) -> None:
        """Apply the user's close-window behavior safely.

        If the tray is unavailable, closing the main window should still quit
        even when the setting is enabled.
        """
        close_to_tray_requested = bool(
            self.settings_service
            and getattr(self.settings_service, "closeToTray", False)
        )
        keep_running_in_tray = (
            close_to_tray_requested and self._close_to_tray_supported()
        )

        self.app.setQuitOnLastWindowClosed(not keep_running_in_tray)

        if close_to_tray_requested and not self._close_to_tray_supported():
            _log.info(
                "Close-to-tray requested but system tray is unavailable; closing the window will quit Sentinel"
            )
        else:
            _log.debug(
                "Window close behavior set to: %s",
                "tray" if keep_running_in_tray else "quit",
            )

    def _on_tray_activated(self, reason):
        """Handle tray icon activation (double-click, etc.)."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_main_window()

    def _show_main_window(self):
        """Bring the main QML window to the foreground."""
        roots = self.engine.rootObjects()
        if roots:
            window = roots[0]
            if hasattr(window, "showNormal"):
                window.showNormal()
            else:
                window.show()
            if hasattr(window, "setVisible"):
                window.setVisible(True)
            window.raise_()
            window.requestActivate()

    def _show_main_window_on_startup(self):
        """Force the main window visible after the event loop starts."""
        roots = self.engine.rootObjects()
        if not roots:
            return

        window = roots[0]
        if hasattr(window, "showNormal"):
            window.showNormal()
        else:
            window.show()
        if hasattr(window, "setVisible"):
            window.setVisible(True)
        if hasattr(window, "raise_"):
            window.raise_()
        if hasattr(window, "requestActivate"):
            window.requestActivate()
        _log.info("Main window shown on startup")

    def _show_and_navigate(self, route):
        """Show the main window and navigate to a specific page."""
        self._show_main_window()
        roots = self.engine.rootObjects()
        if roots:
            # Call QML's loadRoute function
            roots[0].setProperty("currentRoute", route)

    def _show_tray_alert(self, title, message):
        """Show a native Windows Action Center toast notification."""
        if self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                title,
                message[:256],  # Windows truncates long messages
                QSystemTrayIcon.MessageIcon.Warning,
                5000,  # 5 seconds
            )

    def _quit_from_tray(self):
        """Actually quit the application from the tray menu."""
        if self.tray_icon:
            self.tray_icon.hide()
        self.app.quit()

    def _auto_start_rtp_if_configured(self) -> None:
        """Start RTP on launch using the persisted user preference."""
        if not self.rtp_bridge:
            return

        if self.rtp_bridge.shouldStartOnLaunch():
            self.rtp_bridge.enable()
            if self.rtp_bridge.getStatus():
                _log.info("RTP auto-started")
            else:
                _log.info("RTP startup requested by saved preference but runtime is unavailable")
        else:
            _log.info("RTP skipped (disabled by saved user preference)")

    def _on_app_quit(self):
        """Handle application quit event."""
        _log.info("Application shutting down")

        # Stop live monitoring if active
        if self.backend:
            self.backend.stopLive()

        # Stop Resource Monitor
        if self.resource_monitor:
            try:
                self.resource_monitor.stop()
                _log.info("Resource monitor stopped")
            except Exception as e:
                _log.warning("Resource monitor cleanup failed: %s", e)

        # Stop RTP
        if self.rtp_bridge:
            try:
                self.rtp_bridge.shutdownRuntime()
                _log.info("RTP stopped")
            except Exception as e:
                _log.warning("RTP cleanup failed: %s", e)

        # Stop GPU service and cleanup subprocess
        if self.gpu_service:
            try:
                self.gpu_service.cleanup()
                _log.info("GPU service stopped")
            except Exception as e:
                _log.warning("GPU cleanup failed: %s", e)

        # Stop snapshot service timer
        if self.snapshot_service:
            try:
                self.snapshot_service.stop()
                _log.info("Snapshot service stopped")
            except Exception as e:
                _log.warning("Snapshot service cleanup failed: %s", e)

        # Stop Sandbox Lab timers
        if self.sandbox_lab:
            try:
                self.sandbox_lab.shutdown()
                _log.info("Sandbox Lab controller stopped")
            except Exception as e:
                _log.warning("Sandbox Lab cleanup failed: %s", e)

        # Hide tray icon
        if self.tray_icon:
            self.tray_icon.hide()

    def run(self):
        """Run the application."""
        try:
            # Check admin rights - single source of truth
            if not is_admin():
                _log.warning("Not running with administrative privileges — some features may be limited")
            else:
                _log.info("Running with administrator privileges")

            # Log integration status (nmap, etc.)
            print_integration_status()

            # Create QML engine and load UI
            self._create_qml_engine()
            # Set up system tray (AFTER QML loads so the window exists)
            self._setup_system_tray()

            # Honor the user's close behavior once tray availability is known.
            self._apply_close_behavior()

            # QML's visible:true is not always enough for packaged elevated builds.
            # Force the root window to a normal foreground state once the event loop starts.
            QTimer.singleShot(0, self._show_main_window_on_startup)

            _log.info("QML UI loaded — entering event loop")

            # Start event loop
            exit_code = self.app.exec()
            _log.info("Event loop exited with code %d", exit_code)
            return exit_code

        except (RuntimeError, OSError, ImportError) as e:
            _log.critical("Fatal startup error: %s", e, exc_info=True)
            return 1


def run():
    """Application entry point."""
    return DesktopSecurityApplication().run()
