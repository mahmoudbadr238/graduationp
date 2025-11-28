#!/usr/bin/env python3
"""Development entry point for Sentinel - includes crash handling and logging"""

import logging
import sys
from pathlib import Path

# Add parent directory to path to allow imports from root
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

# Set up logging before any other imports
log_dir = Path.home() / ".sentinel" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "app.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        # Check for diagnostic mode FIRST (before any heavy imports)
        if "--diagnose" in sys.argv:
            from app.utils.diagnostics import run_diagnostics

            raise SystemExit(run_diagnostics())

        logger.info("Starting Sentinel application...")

        # Import after logging is configured
        from app.__version__ import APP_FULL_NAME, __version__

        logger.info(f"{APP_FULL_NAME} v{__version__}")

        # Normal launch
        from app.application import run

        raise SystemExit(run())

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)

    except Exception as e:
        logger.exception(f"Fatal error: {e}")

        # Show error dialog if GUI available
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(
                None,
                "Sentinel Fatal Error",
                f"Application crashed:\n\n{e}\n\nCheck logs at:\n{log_file}",
            )
        except (ImportError, RuntimeError):
            pass  # GUI not available, already logged to file

        print(f"\n❌ FATAL ERROR: {e}")
        print(f"See logs at: {log_file}")
        sys.exit(1)
