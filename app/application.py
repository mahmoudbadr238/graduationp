"""Sentinel Desktop Security Application."""
import os
import sys
import psutil
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from .core.container import configure, DI
from .ui.backend_bridge import BackendBridge


class DesktopSecurityApplication:
    """Main application class with OOP backend architecture."""
    
    def __init__(self):
        # Set Controls style to Fusion to enable full customization
        os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Fusion")
        
        # Create Qt application
        self.app = QGuiApplication(sys.argv)

        # Set application properties
        self.app.setApplicationName("Sentinel")
        self.app.setOrganizationName("SecuritySuite")

        # Create QML engine
        self.engine = QQmlApplicationEngine()

        # Connect to application closing
        self.app.aboutToQuit.connect(self._on_app_quit)

        # Set up paths
        self._setup_paths()
        
        # Initialize backend
        self.backend = None
        self._setup_backend()

    def _setup_paths(self):
        """Set up QML import paths and working directory."""
        # Get the absolute path to workspace root
        # When frozen by PyInstaller, use sys._MEIPASS or executable directory
        if getattr(sys, 'frozen', False):
            # Running in PyInstaller bundle
            if hasattr(sys, '_MEIPASS'):
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
        qml_path = os.path.join(workspace_root, "qml")        # Register the component directly
        self.engine.addImportPath(qml_path)
        self.engine.rootContext().setContextProperty("componentPath", os.path.join(qml_path, "components").replace("\\", "/"))
        self.engine.rootContext().setContextProperty("themePath", os.path.join(qml_path, "theme").replace("\\", "/"))
        print(f"Component path: {os.path.join(qml_path, 'components')}")
        print(f"QML import paths: {self.engine.importPathList()}")
    
    def _setup_backend(self):
        """Initialize OOP backend with dependency injection."""
        try:
            print("Initializing backend services...")
            
            # Configure DI container with all implementations
            configure()
            print("✓ Dependency injection container configured")
            
            # Create backend bridge
            self.backend = BackendBridge()
            print("✓ Backend bridge created")
            
            # Expose backend to QML
            self.engine.rootContext().setContextProperty("Backend", self.backend)
            print("✓ Backend exposed to QML context")
            
        except Exception as e:
            print(f"Warning: Backend initialization failed: {e}")
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
            # Check admin rights
            try:
                if not psutil.Process().username().lower().endswith('administrator'):
                    print("⚠ Warning: Not running with administrative privileges")
                    print("  Some security features may be limited")
            except:
                print("⚠ Warning: Could not check administrative privileges")
            
            # Create QML engine and load UI
            self._create_qml_engine()
            print("✓ QML UI loaded successfully")
            print("\n=== Sentinel Desktop Security Suite ===")
            print("Application ready. Entering event loop...\n")
            
            # Start event loop
            exit_code = self.app.exec()
            print(f"\nEvent loop exited with code: {exit_code}")
            return exit_code
            
        except Exception as e:
            print(f"✗ Error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1


def run():
    """Application entry point."""
    return DesktopSecurityApplication().run()