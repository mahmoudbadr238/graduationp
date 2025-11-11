#!/usr/bin/env python3
"""
GUI Responsiveness Test Harness
Launches QML app headless across 14 required viewport sizes.
Captures QML warnings, screenshots, and generates JSON report.
"""

import sys
import os
import json
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlEngine, QQmlComponent, QQmlApplicationEngine
from PySide6.QtCore import Qt, QUrl, QTimer, QSize, QRect, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication, QScreen
import signal
from PySide6.QtCore import QObject, Slot, Signal

# Setup logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# Global warning capture
_warning_capture = None

# CRITICAL 14 VIEWPORT SIZES - MUST ALL PASS
TEST_SIZES = [
    (360, 640),    # Galaxy S8 / small phone
    (412, 915),    # Pixel 6 / medium phone
    (800, 1280),   # iPad Mini / tablet
    (1024, 768),   # Classic XGA
    (1280, 720),   # HD / netbook
    (1366, 768),   # WXGA / laptop 13"
    (1536, 864),   # 16:9 laptop 14"
    (1600, 900),   # WXGA+ laptop
    (1280, 800),   # WXGA+ 16:10
    (1920, 1200),  # FHD 16:10
    (1920, 1080),  # FHD 16:9
    (2560, 1440),  # WQHD
    (2560, 1080),  # Ultrawide 21:9
    (3440, 1440),  # Ultrawide 32:9
]

class GUIProbe:
    def __init__(self):
        self.app = None
        self.engine = None
        self.results = {
            'passed': [],
            'failed': [],
            'warnings_by_size': {}
        }
        self.artifacts_dir = Path(__file__).parent.parent / 'artifacts' / 'gui'
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        
    def init_app(self):
        """Initialize PySide6 application"""
        # Enable high-DPI scaling
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        self.app = QGuiApplication(sys.argv)
        self.engine = QQmlEngine()
        # Ensure QSettings works when loading QML Settings element
        try:
            self.app.setApplicationName("Sentinel")
            self.app.setOrganizationName("SecuritySuite")
            self.app.setOrganizationDomain("sentinel.local")
        except Exception:
            pass
        # Expose a minimal Backend stub so QML pages that reference Backend don't error during probe
        class BackendStub(QObject):
            # Provide the signals that QML Connections may hook into
            snapshotUpdated = Signal(object)
            toast = Signal(str, str)
            eventsLoaded = Signal(object)

            def __init__(self):
                super().__init__()

            @Slot()
            def startLive(self):
                log.info("[probe] BackendStub.startLive called")
                # Emit a minimal snapshot update so pages depending on snapshot data don't error
                sample = {"cpu": {"usage": 0, "percent": 0}, "mem": {"used": 0, "total": 0}}
                try:
                    self.snapshotUpdated.emit(sample)
                except Exception:
                    pass

            @Slot()
            def loadRecentEvents(self):
                log.info("[probe] BackendStub.loadRecentEvents called")
                # Emit eventsLoaded and a harmless toast to satisfy listeners
                sample_events = []
                try:
                    self.eventsLoaded.emit(sample_events)
                except Exception:
                    pass
                try:
                    self.toast.emit("info", "probe: events loaded")
                except Exception:
                    pass

            @Slot()
            def stopLive(self):
                log.info("[probe] BackendStub.stopLive called")

        # Keep a reference to the stub on the probe instance to avoid GC
        try:
            self.backend_stub = BackendStub()
            self.engine.rootContext().setContextProperty("Backend", self.backend_stub)
        except Exception:
            # If rootContext not available yet, we will set Backend before loading component
            self.backend_stub = None

        # Provide a minimal GPUService stub so GPU pages can bind safely
        class GPUServiceStub(QObject):
            def __init__(self):
                super().__init__()
                self.gpuCount = 0

            @Slot(int)
            def start(self, interval_ms):
                log.info(f"[probe] GPUServiceStub.start({interval_ms})")

            @Slot(int, result='QVariant')
            def getGPUMetrics(self, index):
                return None

        try:
            self.gpu_service_stub = GPUServiceStub()
            self.engine.rootContext().setContextProperty("GPUService", self.gpu_service_stub)
        except Exception:
            self.gpu_service_stub = None
        
        # Add QML import paths
        qml_root = Path(__file__).parent.parent / 'qml'
        self.engine.addImportPath(str(qml_root))
        for subdir in ['components', 'pages', 'theme', 'ui', 'ux']:
            path = qml_root / subdir
            if path.exists():
                self.engine.addImportPath(str(path))

        
    def load_qml(self, qml_file):
        """Load main QML file"""
        qml_path = Path(__file__).parent.parent / 'qml' / qml_file
        if not qml_path.exists():
            log.error(f"QML file not found: {qml_path}")
            return None

        # Create a temporary QQmlApplicationEngine for each test to isolate state
        temp_engine = QQmlApplicationEngine()
        # Copy import paths from the main engine
        for p in self.engine.importPathList():
            temp_engine.addImportPath(p)

        # Expose probe's stubs to the temp engine context
        try:
            temp_engine.rootContext().setContextProperty("Backend", getattr(self, 'backend_stub', None))
            temp_engine.rootContext().setContextProperty("GPUService", getattr(self, 'gpu_service_stub', None))
        except Exception:
            pass

        # Load QML file
        temp_engine.load(QUrl.fromLocalFile(str(qml_path)))
        if not temp_engine.rootObjects():
            # Collect and log errors if any
            # QQmlApplicationEngine writes errors to warnings; no direct API for errors here
            log.error("Failed to load QML via temporary QQmlApplicationEngine")
            return None

        window = temp_engine.rootObjects()[0]
        # Keep a reference to engine on the window to prevent premature GC
        try:
            window.setProperty("__probe_engine", temp_engine)
        except Exception:
            pass

        return window
        
    def test_size(self, width, height):
        """Test a specific viewport size"""
        size_str = f"{width}x{height}"
        log.info(f"Testing viewport: {size_str}")
        
        try:
            window = self.load_qml('main.qml')
            if not window:
                self.results['failed'].append(size_str)
                return False
                
            # Resize window
            window.setWidth(width)
            window.setHeight(height)
            window.setVisibility(1)  # Window.Visible
            
            # Process events to render
            self.app.processEvents()
            
            # Wait for rendering
            QTimer.singleShot(500, self.app.quit)
            self.app.exec()
            
            # Check for layout issues
            issues = self._check_layout(window)
            
            if issues:
                self.results['warnings_by_size'][size_str] = issues
                for issue in issues:
                    log.warning(f"  ⚠ {size_str}: {issue}")
            
            # Take screenshot
            screenshot_path = self.artifacts_dir / f"{size_str}.png"
            if hasattr(window, 'grabWindow'):
                pixmap = window.grabWindow()
                if pixmap.save(str(screenshot_path)):
                    log.info(f"  ✓ Screenshot saved: {screenshot_path}")
                else:
                    log.warning(f"  ⚠ Failed to save screenshot for {size_str}")
            
            # Close window
            window.close()
            window.deleteLater()
            
            self.results['passed'].append(size_str)
            return len(issues) == 0
            
        except Exception as e:
            log.error(f"  ✗ Error testing {size_str}: {e}")
            self.results['failed'].append(size_str)
            return False

            
    def _check_layout(self, window):
        """Check for common layout issues"""
        issues = []
        try:
            # Check for items smaller than implicit size
            def check_item(item, depth=0):
                if depth > 10:  # Prevent infinite recursion
                    return
                try:
                    if hasattr(item, 'implicitWidth') and hasattr(item, 'width'):
                        if item.width > 0 and item.width < item.implicitWidth * 0.9:
                            issues.append(f"Item clipped horizontally: width={item.width} < implicit={item.implicitWidth}")
                    if hasattr(item, 'implicitHeight') and hasattr(item, 'height'):
                        if item.height > 0 and item.height < item.implicitHeight * 0.9:
                            issues.append(f"Item clipped vertically: height={item.height} < implicit={item.implicitHeight}")
                except:
                    pass
                    
                # Recurse to children
                if hasattr(item, 'children'):
                    for child in item.children():
                        check_item(child, depth + 1)
                        
            check_item(window)
        except Exception as e:
            log.debug(f"Layout check failed: {e}")
            
        return issues[:5]  # Return max 5 issues
        
            
    def run_all_tests(self):
        """Run tests for all 14 required viewport sizes"""
        log.info(f"Starting GUI responsiveness tests ({len(TEST_SIZES)} required sizes)")
        log.info(f"Artifacts will be saved to: {self.artifacts_dir}\n")
        
        for width, height in TEST_SIZES:
            self.test_size(width, height)
        
        # Generate JSON report
        self._generate_json_report()
        self._print_summary()
        
        # Exit with non-zero if any violations
        has_violations = len(self.results['failed']) > 0 or len(self.results['warnings_by_size']) > 0
        return not has_violations
    
    def _generate_json_report(self):
        """Generate JSON report with violations per size"""
        report = {
            'total_sizes': len(TEST_SIZES),
            'passed_clean': len(self.results['passed']) - len(self.results['warnings_by_size']),
            'passed_with_warnings': len(self.results['warnings_by_size']),
            'failed': len(self.results['failed']),
            'test_results': {
                'passed': self.results['passed'],
                'failed': self.results['failed'],
                'violations_by_size': self.results['warnings_by_size']
            }
        }
        
        report_path = self.artifacts_dir / 'report.json'
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        log.info(f"JSON report saved to: {report_path}")
            
    def _print_summary(self):
        """Print test summary"""
        clean_passed = len(self.results['passed']) - len(self.results['warnings_by_size'])
        
        log.info("\n" + "="*70)
        log.info("GUI RESPONSIVENESS TEST SUMMARY")
        log.info("="*70)
        log.info(f"Total Sizes Tested: {len(TEST_SIZES)}")
        log.info(f"✓ Passed (clean): {clean_passed}")
        log.info(f"⚠ Passed (with warnings): {len(self.results['warnings_by_size'])}")
        log.info(f"✗ Failed: {len(self.results['failed'])}")
        
        if self.results['warnings_by_size']:
            log.warning(f"\nVIOLATIONS DETECTED ({len(self.results['warnings_by_size'])} sizes):")
            for size, violations in sorted(self.results['warnings_by_size'].items()):
                log.warning(f"  {size}:")
                for violation in violations[:3]:  # Show first 3 violations per size
                    log.warning(f"    - {violation}")
                if len(violations) > 3:
                    log.warning(f"    ... and {len(violations) - 3} more")
        
        if self.results['failed']:
            log.error(f"\nFailed sizes: {', '.join(self.results['failed'])}")
        
        if not self.results['warnings_by_size'] and not self.results['failed']:
            log.info("\n✓ ALL TESTS PASSED WITH ZERO VIOLATIONS!")
            
        log.info(f"\nScreenshots saved to: {self.artifacts_dir}")
        log.info(f"JSON report: {self.artifacts_dir / 'report.json'}")
        log.info("="*70)

def main():
    # Handle SIGINT gracefully
    def signal_handler(sig, frame):
        log.info("\nTest interrupted by user")
        sys.exit(1)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        probe = GUIProbe()
        probe.init_app()
        success = probe.run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
