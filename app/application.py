"""Sentinel Desktop Security Application - Optimized for fast startup."""

import os
import sys

import psutil
from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from .core.config import get_config
from .core.container import configure
from .core.logging_setup import setup_crash_handlers, setup_logging
from .core.startup_orchestrator import StartupOrchestrator
from .infra.integrations import print_integration_status
from .infra.privileges import is_admin
from .ui.backend_bridge import BackendBridge
from .ui.gpu_service import get_gpu_service
from .ui.system_snapshot_service import SystemSnapshotService
from .ui.settings_service import SettingsService


class DesktopSecurityApplication:
    """Main application class with optimized startup and thread pool management."""

    def __init__(self):
        # Initialize logging first (before any imports)
        setup_logging("Sentinel")
        setup_crash_handlers("Sentinel")

        # Load configuration
        self.config = get_config()

        # Set Controls style to Fusion to enable full customization
        os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Fusion")

        # Create Qt application
        self.app = QGuiApplication(sys.argv)

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

            # DEFERRED: GPU service (300ms after UI loads, non-blocking)
            def init_gpu():
                try:
                    self.gpu_service = get_gpu_service()
                    root_context = self.engine.rootContext()
                    root_context.setContextProperty("GPUService", self.gpu_service)
                    # Auto-start GPU service with 2s interval for dashboard display
                    self.gpu_service.start(2000)
                    print("[OK] GPU service initialized, started, and exposed to QML")
                except (ImportError, RuntimeError, OSError) as e:
                    print(f"[WARNING] GPU service initialization failed: {e}")
                    self.gpu_service = None

            self.orchestrator.schedule_deferred(300, "GPU Backend", init_gpu)
            
            # IMMEDIATE: System Snapshot Service (cross-platform)
            try:
                self.snapshot_service = SystemSnapshotService()
                # Force initial data collection
                self.snapshot_service._update_metrics()
                self.snapshot_service._update_disk_partitions()
                self.snapshot_service._update_network_interfaces()
                self.engine.rootContext().setContextProperty("SnapshotService", self.snapshot_service)
                self.snapshot_service.start(2000)  # Start with 2s interval
                print(f"[OK] System Snapshot service: CPU={self.snapshot_service.cpuUsage:.1f}%, MEM={self.snapshot_service.memoryUsage:.1f}%")
            except (ImportError, RuntimeError, OSError) as e:
                print(f"[WARNING] System Snapshot service failed: {e}")
                self.snapshot_service = None
            
            # IMMEDIATE: Settings Service (cross-platform)
            try:
                self.settings_service = SettingsService()
                self.engine.rootContext().setContextProperty("SettingsService", self.settings_service)
                print("[OK] Settings service initialized and exposed to QML")
            except (ImportError, RuntimeError, OSError) as e:
                print(f"[WARNING] Settings service failed: {e}")
                self.settings_service = None

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

    def _on_app_quit(self):
        """Handle application quit event."""
        print("Application shutting down...")

        # Stop live monitoring if active
        if self.backend:
            self.backend.stopLive()

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
