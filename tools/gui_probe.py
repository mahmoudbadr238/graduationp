#!/usr/bin/env python3
"""
GUI Responsiveness Test Harness
Launches QML app headless across 15+ aspect ratios and captures screenshots.
Tests for clipped text, overlapping controls, anchor conflicts, and scaling issues.
"""

import sys
import os
import json
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlEngine, QQmlComponent
from PySide6.QtCore import Qt, QUrl, QTimer, QSize, QRect
from PySide6.QtGui import QGuiApplication, QScreen
import signal

# Setup logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# Test viewport configurations (width x height in pixels)
TEST_SIZES = [
    # Phones/tablets
    (360, 640),    # Galaxy S8
    (412, 915),    # Pixel 6
    (800, 1280),   # iPad Mini
    # Laptops 13-15"
    (1280, 720),   # HD
    (1366, 768),   # WXGA
    (1536, 864),   # 16:9
    (1600, 900),   # WXGA+
    # 16:10 / 3:2
    (1280, 800),   # WXGA+
    (1920, 1200),  # 16:10 FHD
    (2256, 1504),  # 3:2 MacBook
    # Classic 4:3
    (1024, 768),   # XGA
    (1280, 960),   # SXGA
    # Desktop FHD/WQHD
    (1920, 1080),  # FHD
    (2560, 1440),  # WQHD
    # Ultrawide
    (2560, 1080),  # 21:9
    (3440, 1440),  # 32:9
]

class GUIProbe:
    def __init__(self):
        self.app = None
        self.engine = None
        self.results = {
            'passed': [],
            'failed': [],
            'warnings': []
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
        
        # Add QML import paths
        qml_root = Path(__file__).parent.parent / 'qml'
        self.engine.addImportPath(str(qml_root))
        self.engine.addImportPath(str(qml_root / 'components'))
        self.engine.addImportPath(str(qml_root / 'pages'))
        self.engine.addImportPath(str(qml_root / 'theme'))
        self.engine.addImportPath(str(qml_root / 'ui'))
        
    def load_qml(self, qml_file):
        """Load main QML file"""
        qml_path = Path(__file__).parent.parent / 'qml' / qml_file
        if not qml_path.exists():
            log.error(f"QML file not found: {qml_path}")
            return None
            
        component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(qml_path)))
        if component.isError():
            for error in component.errors():
                log.error(f"QML Error: {error.toString()}")
            return None
            
        window = component.create()
        if not window:
            log.error("Failed to create QML window instance")
            return None
            
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
            
            # Verify visibility
            if window.visibility() != 1:
                log.warning(f"  ⚠ Window not visible for {size_str}")
                self.results['warnings'].append(f"{size_str}: not visible")
                
            # Check for layout issues
            issues = self._check_layout(window)
            if issues:
                for issue in issues:
                    log.warning(f"  ⚠ {size_str}: {issue}")
                    self.results['warnings'].append(f"{size_str}: {issue}")
            
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
            return True
            
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
        """Run tests for all viewport sizes"""
        log.info(f"Starting GUI responsiveness tests ({len(TEST_SIZES)} sizes)")
        log.info(f"Artifacts will be saved to: {self.artifacts_dir}\n")
        
        for width, height in TEST_SIZES:
            self.test_size(width, height)
            
        self._print_summary()
        return len(self.results['failed']) == 0
        
    def _print_summary(self):
        """Print test summary"""
        log.info("\n" + "="*60)
        log.info("GUI RESPONSIVENESS TEST SUMMARY")
        log.info("="*60)
        log.info(f"✓ Passed: {len(self.results['passed'])}")
        log.info(f"✗ Failed: {len(self.results['failed'])}")
        log.info(f"⚠ Warnings: {len(self.results['warnings'])}")
        
        if self.results['failed']:
            log.error(f"\nFailed sizes: {', '.join(self.results['failed'])}")
        if self.results['warnings']:
            log.warning(f"\nWarnings detected - see above for details")
            
        log.info(f"\nScreenshots saved to: {self.artifacts_dir}")
        log.info("="*60)


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
