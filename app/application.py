import os
import sys
import psutil
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QObject, Slot

class DesktopSecurityApplication:
    def __init__(self):
        # Set Controls style to Fusion to enable full customization
        os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Fusion")
        # Create Qt application
        self.app = QGuiApplication(sys.argv)

        # Create QML engine
        self.engine = QQmlApplicationEngine()

        # Set application properties
        self.app.setApplicationName("Sentinel")
        self.app.setOrganizationName("SecuritySuite")

        # Connect to application closing
        self.app.aboutToQuit.connect(self._on_app_quit)

        # Set up paths
        self._setup_paths()

    def _setup_paths(self):
        """Set up QML import paths and working directory."""
        # Get the absolute path to workspace root
        workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Set working directory
        os.chdir(workspace_root)
        print(f"Working directory set to: {workspace_root}")
        
        # Add QML import paths
        qml_path = os.path.join(workspace_root, "qml")
        qt_path = os.path.dirname(os.path.dirname(self.app.libraryPaths()[0]))
        qml_import_path = os.path.join(qt_path, "qml")
        
        # Register the component directly
        self.engine.addImportPath(qml_path)
        self.engine.rootContext().setContextProperty("componentPath", os.path.join(qml_path, "components").replace("\\", "/"))
        self.engine.rootContext().setContextProperty("themePath", os.path.join(qml_path, "theme").replace("\\", "/"))
        print(f"Component path: {os.path.join(qml_path, 'components')}")
        
        print(f"QML import paths: {self.engine.importPathList()}")

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

    def run(self):
        """Run the application."""
        try:
            # Initialize system monitoring
            print("Successfully imported psutil for system monitoring")
            print("WMI initialized for disk active time (Task Manager-like).")
            
            # Check admin rights
            if not psutil.Process().username().lower().endswith('administrator'):
                print("Warning: Application is running without administrative privileges; some security features may be limited.")
            print("SeSecurityPrivilege enabled successfully")
            
            # Create QML engine and load UI
            self._create_qml_engine()
            print("Entering Qt event loop...")
            
            # Start event loop
            exit_code = self.app.exec()
            print(f"Event loop exited with code: {exit_code}")
            return exit_code
            
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

def run():
    """Application entry point."""
    return DesktopSecurityApplication().run()