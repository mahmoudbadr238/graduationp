"""Sentinel Desktop Security Application - Optimized for fast startup."""

import os
import sys

from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtQml import QQmlApplicationEngine

from .core.config import get_config
from .core.container import configure
from .core.logging_setup import setup_crash_handlers, setup_logging
from .core.perf_monitor import start_perf_monitor
from .core.startup_orchestrator import StartupOrchestrator
from .infra.integrations import print_integration_status
from .infra.privileges import is_admin
from .ui.backend_bridge import BackendBridge
from .ui.gpu_service import get_gpu_service
from .ui.notification_service import NotificationService, get_notification_service
from .ui.settings_service import SettingsService
from .ui.system_snapshot_service import SystemSnapshotService


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
        except Exception:
            # Non-critical: if setting domain fails, continue with defaults
            pass

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
        self.sandbox_lab = None
        self.file_function_service = None
        self.resource_monitor = None
        self.rtp_bridge = None
        self.tray_icon = None
        self._setup_backend()

    def _setup_paths(self):
        """Set up QML import paths and working directory."""
        # Get the absolute path to workspace root
        # When frozen by PyInstaller, use sys._MEIPASS or executable directory
        if getattr(sys, "frozen", False):
            # Running in PyInstaller bundle
            if hasattr(sys, "_MEIPASS"):
                # Temporary folder used by PyInstaller
                workspace_root = sys._MEIPASS
            else:
                # Directory containing the executable
                workspace_root = os.path.dirname(sys.executable)
        else:
            # Running in normal Python environment
            workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Set working directory
        os.chdir(workspace_root)
        print(f"Working directory set to: {workspace_root}")

        # Add QML import paths
        qml_path = os.path.join(workspace_root, "qml")
        self.engine.addImportPath(qml_path)

        # Add subdirectories for component imports
        self.engine.addImportPath(os.path.join(qml_path, "components"))
        self.engine.addImportPath(os.path.join(qml_path, "theme"))
        self.engine.addImportPath(os.path.join(qml_path, "pages"))
        self.engine.addImportPath(os.path.join(qml_path, "ux"))  # For Theme singleton

        # Set QML context properties for component paths
        components_path = os.path.join(qml_path, "components").replace("\\", "/")
        theme_path = os.path.join(qml_path, "theme").replace("\\", "/")
        self.engine.rootContext().setContextProperty("componentPath", components_path)
        self.engine.rootContext().setContextProperty("themePath", theme_path)

        print(f"Component path: {os.path.join(qml_path, 'components')}")
        print(f"QML import paths: {self.engine.importPathList()}")

    def _setup_backend(self):
        """Initialize backend with deferred loading for fast startup."""
        try:
            print("Initializing backend services...")

            # IMMEDIATE: Configure DI container (required for app structure)
            configure()
            print("[OK] Dependency injection container configured")

            # IMMEDIATE: Create backend instance (but defer heavy initialization)
            # This allows QML to reference Backend immediately on load
            self.backend = BackendBridge()
            # Register backend BEFORE loading QML to avoid "Backend not available" warnings
            self.engine.rootContext().setContextProperty("Backend", self.backend)

            # Register sandbox preview image provider for live preview
            try:
                from .ui.sandbox_preview_provider import register_preview_provider

                preview_controller = register_preview_provider(
                    self.engine, self.backend
                )
                if preview_controller:
                    self.engine.rootContext().setContextProperty(
                        "SandboxPreview", preview_controller
                    )
                    print("[OK] Sandbox preview provider registered")
            except ImportError as e:
                print(f"[WARNING] Sandbox preview provider not available: {e}")

            # DEFERRED: Heavy backend initialization (100ms after startup)
            def init_backend_heavy():
                try:
                    # Start live monitoring after UI is ready
                    self.backend.startLive()
                    print("[OK] Backend monitoring started")
                except (ImportError, RuntimeError, OSError) as e:
                    print(f"[WARNING] Backend monitoring failed: {e}")

            self.orchestrator.schedule_deferred(
                100, "Backend Monitoring", init_backend_heavy
            )

            # DEFERRED: GPU service registration only (NOT auto-started to save resources)
            # GPU monitoring will start when user opens the GPU Monitor page
            def init_gpu():
                try:
                    self.gpu_service = get_gpu_service()
                    root_context = self.engine.rootContext()
                    root_context.setContextProperty("GPUService", self.gpu_service)
                    # GPU service is registered but NOT started
                    # It will start when the GPU Monitor page is opened via GPUService.start()
                    print("[OK] GPU service registered (lazy-load - starts on demand)")
                except (ImportError, RuntimeError, OSError) as e:
                    print(f"[WARNING] GPU service initialization failed: {e}")
                    self.gpu_service = None

            self.orchestrator.schedule_deferred(1000, "GPU Backend", init_gpu)

            # IMMEDIATE: System Snapshot Service (cross-platform)
            try:
                self.snapshot_service = SystemSnapshotService()
                # Force initial data collection
                self.snapshot_service._update_metrics()
                self.snapshot_service._update_disk_partitions()
                self.snapshot_service._update_network_interfaces()
                self.engine.rootContext().setContextProperty(
                    "SnapshotService", self.snapshot_service
                )
                self.snapshot_service.start(
                    5000
                )  # Start with 5s interval for lower CPU usage
                print(
                    f"[OK] System Snapshot service: CPU={self.snapshot_service.cpuUsage:.1f}%, MEM={self.snapshot_service.memoryUsage:.1f}%"
                )

                # Connect snapshot service to backend for AI chatbot context
                if self.backend:
                    self.backend.set_snapshot_service(self.snapshot_service)
            except (ImportError, RuntimeError, OSError) as e:
                print(f"[WARNING] System Snapshot service failed: {e}")
                self.snapshot_service = None

            # IMMEDIATE: Settings Service (cross-platform)
            try:
                self.settings_service = SettingsService()
                self.engine.rootContext().setContextProperty(
                    "SettingsService", self.settings_service
                )
                print("[OK] Settings service initialized and exposed to QML")
            except (ImportError, RuntimeError, OSError) as e:
                print(f"[WARNING] Settings service failed: {e}")
                self.settings_service = None

            # IMMEDIATE: VMware Sandbox Lab controller (graceful if VMware is absent)
            try:
                from .sandbox_vmware import SandboxLabController

                self.sandbox_lab = SandboxLabController()
                self.engine.rootContext().setContextProperty(
                    "SandboxLab", self.sandbox_lab
                )
                print("[OK] Sandbox Lab controller registered")
            except Exception as e:
                print(f"[WARNING] Sandbox Lab controller failed: {e}")
                self.sandbox_lab = None
                self.engine.rootContext().setContextProperty("SandboxLab", None)

            # IMMEDIATE: File Function Service (shred + recovery)
            try:
                from .filefunction.backend_bridge import FileFunctionBridge

                self.file_function_service = FileFunctionBridge()
                self.engine.rootContext().setContextProperty(
                    "backend", self.file_function_service
                )
                print("[OK] File Function service registered")
            except (ImportError, RuntimeError, OSError) as e:
                print(f"[WARNING] File Function service failed: {e}")
                self.file_function_service = None

            # IMMEDIATE: Recovery Controller (two-phase scan + selective carve)
            try:
                from .filefunction.recovery_controller import RecoveryController

                self.recovery_controller = RecoveryController()
                self.engine.rootContext().setContextProperty(
                    "RecoveryService", self.recovery_controller
                )
                print("[OK] Recovery controller registered")
            except (ImportError, RuntimeError, OSError) as e:
                print(f"[WARNING] Recovery controller failed: {e}")
                self.recovery_controller = None

            # IMMEDIATE: Notification Service (cross-platform)
            try:
                self.notification_service = get_notification_service()
                self.engine.rootContext().setContextProperty(
                    "NotificationService", self.notification_service
                )
                print("[OK] Notification service initialized and exposed to QML")

                # Connect Snapshot service to notification service for security alerts
                if self.snapshot_service:
                    self.snapshot_service.set_notification_service(
                        self.notification_service
                    )
                    print("[OK] Security notifications connected")
            except (ImportError, RuntimeError, OSError) as e:
                print(f"[WARNING] Notification service failed: {e}")
                self.notification_service = None

            # IMMEDIATE: Resource Monitor (live CPU/RAM/Net dashboard)
            try:
                from .core.resource_monitor import get_resource_monitor_bridge

                self.resource_monitor = get_resource_monitor_bridge()
                self.engine.rootContext().setContextProperty(
                    "ResourceMonitor", self.resource_monitor
                )
                self.resource_monitor.start()
                print("[OK] Resource Monitor registered and started")
            except (ImportError, RuntimeError, OSError) as e:
                print(f"[WARNING] Resource Monitor failed: {e}")
                self.resource_monitor = None

            # IMMEDIATE: Real-Time Protection Bridge
            try:
                from .core.realtime_protection import get_rtp_bridge

                self.rtp_bridge = get_rtp_bridge()
                self.engine.rootContext().setContextProperty(
                    "RTPBridge", self.rtp_bridge
                )
                print("[OK] RTP Bridge registered (not auto-started)")
            except (ImportError, RuntimeError, OSError) as e:
                print(f"[WARNING] RTP Bridge failed: {e}")
                self.rtp_bridge = None

        except (ImportError, RuntimeError, UnicodeEncodeError) as e:
            print(f"[ERROR] Critical backend setup failed: {e}")
            print("Application will continue with limited functionality")

    def _create_qml_engine(self):
        """Load main QML file and create engine."""
        # Load main.qml
        qml_file = os.path.join(os.getcwd(), "qml", "main.qml")
        print(f"Loading QML: {qml_file}")

        # Load the main QML file
        self.engine.load(qml_file)

        # Check that the file was loaded successfully
        if not self.engine.rootObjects():
            raise RuntimeError("Unable to load Sentinel UI (main.qml)")

        # Allow drag-and-drop when running as admin (UIPI bypass)
        self._allow_drag_drop_elevated()

    @staticmethod
    def _allow_drag_drop_elevated():
        """Allow drag-and-drop from non-elevated Explorer to this elevated app.

        Windows UIPI (User Interface Privilege Isolation) blocks drag-and-drop
        messages from lower-privilege processes (like Explorer) to higher-privilege
        processes (our app running as Admin). We call ChangeWindowMessageFilter to
        add WM_DROPFILES, WM_COPYDATA, and WM_COPYGLOBALDATA to the allow list.
        """
        if sys.platform != "win32":
            return

        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32

            # ChangeWindowMessageFilter(UINT message, DWORD dwFlag) -> BOOL
            # dwFlag: MSGFLT_ADD = 1 (allow), MSGFLT_REMOVE = 2
            ChangeWindowMessageFilter = user32.ChangeWindowMessageFilter
            ChangeWindowMessageFilter.argtypes = [wintypes.UINT, wintypes.DWORD]
            ChangeWindowMessageFilter.restype = wintypes.BOOL

            MSGFLT_ADD = 1
            WM_DROPFILES = 0x0233
            WM_COPYDATA = 0x004A
            WM_COPYGLOBALDATA = 0x0049

            ChangeWindowMessageFilter(WM_DROPFILES, MSGFLT_ADD)
            ChangeWindowMessageFilter(WM_COPYDATA, MSGFLT_ADD)
            ChangeWindowMessageFilter(WM_COPYGLOBALDATA, MSGFLT_ADD)

            print("[OK] Drag-and-drop enabled for elevated process (UIPI bypass)")
        except Exception as e:
            print(f"[WARNING] Could not enable drag-and-drop UIPI bypass: {e}")

    def _setup_system_tray(self):
        """Set up QSystemTrayIcon with context menu and alert forwarding."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("[WARNING] System tray not available")
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

        # Connect resource alerts → native Windows toasts
        if self.resource_monitor:
            self.resource_monitor.alertTriggered.connect(self._show_tray_alert)

        # Connect RTP threats → native Windows toasts
        if self.rtp_bridge:
            self.rtp_bridge.threatDetected.connect(
                lambda msg: self._show_tray_alert("🛡️ Sentinel RTP", msg)
            )

        self.tray_icon.show()
        print("[OK] System tray icon active")

    def _on_tray_activated(self, reason):
        """Handle tray icon activation (double-click, etc.)."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_main_window()

    def _show_main_window(self):
        """Bring the main QML window to the foreground."""
        roots = self.engine.rootObjects()
        if roots:
            window = roots[0]
            window.show()
            window.raise_()
            window.requestActivate()

    def _show_and_navigate(self, route):
        """Show the main window and navigate to a specific page."""
        self._show_main_window()
        roots = self.engine.rootObjects()
        if roots:
            # Call QML's loadRoute function
            from PySide6.QtQml import QQmlProperty
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

    def _on_app_quit(self):
        """Handle application quit event."""
        print("Application shutting down...")

        # Stop live monitoring if active
        if self.backend:
            self.backend.stopLive()

        # Stop Resource Monitor
        if self.resource_monitor:
            try:
                self.resource_monitor.stop()
                print("[OK] Resource monitor stopped")
            except Exception as e:
                print(f"[WARNING] Resource monitor cleanup failed: {e}")

        # Stop RTP
        if self.rtp_bridge:
            try:
                self.rtp_bridge.disable()
                print("[OK] RTP stopped")
            except Exception as e:
                print(f"[WARNING] RTP cleanup failed: {e}")

        # Stop GPU service and cleanup subprocess
        if self.gpu_service:
            try:
                self.gpu_service.cleanup()
                print("[OK] GPU service stopped")
            except Exception as e:
                print(f"[WARNING] GPU cleanup failed: {e}")

        # Stop snapshot service timer
        if self.snapshot_service:
            try:
                self.snapshot_service.stop()
                print("[OK] Snapshot service stopped")
            except Exception as e:
                print(f"[WARNING] Snapshot service cleanup failed: {e}")

        # Stop Sandbox Lab timers
        if self.sandbox_lab:
            try:
                self.sandbox_lab.shutdown()
                print("[OK] Sandbox Lab controller stopped")
            except Exception as e:
                print(f"[WARNING] Sandbox Lab cleanup failed: {e}")

        # Hide tray icon
        if self.tray_icon:
            self.tray_icon.hide()

    def run(self):
        """Run the application."""
        try:
            # Check admin rights - single source of truth
            if not is_admin():
                print("[WARNING] Not running with administrative privileges")
                print("  Some security features may be limited")
            else:
                print("[OK] Running with administrator privileges")

            # Print integration status (nmap, VT, etc.)
            print_integration_status()

            # Create QML engine and load UI
            self._create_qml_engine()
            # Set up system tray (AFTER QML loads so the window exists)
            self._setup_system_tray()

            # Stay alive in tray when window is closed
            self.app.setQuitOnLastWindowClosed(False)

            print("[OK] QML UI loaded successfully")
            print("\n=== Sentinel Desktop Security Suite ===")
            print("Application ready. Entering event loop...\n")

            # Start event loop
            exit_code = self.app.exec()
            print(f"\nEvent loop exited with code: {exit_code}")
            return exit_code

        except (RuntimeError, OSError, ImportError) as e:
            print(f"[ERROR] Error: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()
            return 1


def run():
    """Application entry point."""
    return DesktopSecurityApplication().run()
