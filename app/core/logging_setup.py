"""Logging and crash handling for Sentinel.

Structured logging with rotating file handler, global exception hooks,
and optional Sentry crash reporting.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from .config import get_config

logger = logging.getLogger(__name__)

# Optional Sentry (only if DSN is set)
try:
    import sentry_sdk

    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False


class QtCrashHandler(QObject):
    """Handles Qt-specific crashes non-blockingly."""

    crash_signal = Signal(str, str)  # title, message

    def __init__(self):
        """Initialize crash handler."""
        super().__init__()
        self.crash_signal.connect(self._show_crash_dialog)

    def _show_crash_dialog(self, title: str, message: str) -> None:
        """Show non-blocking crash message box."""
        try:
            QMessageBox.critical(None, title, message)
        except RuntimeError:
            # If even the message box fails, just print
            print(f"[CRASH] {title}: {message}")


def setup_logging(app_name: str = "Sentinel") -> None:
    """Configure structured logging with rotating file handler and optional Sentry.

    Args:
        app_name: Application name for logging prefix.
    """
    config = get_config()
    logs_dir = config.logs_dir

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (INFO and above)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Rotating file handler (DEBUG and above, 10 files x 1MB each)
    log_file = logs_dir / f"{app_name.lower()}.log"
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=1024 * 1024,  # 1 MB
            backupCount=10,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        logger.info(f"Logging initialized to {log_file}")
    except OSError as e:
        logger.exception(f"Failed to initialize file logging: {e}")

    # Optional Sentry
    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn and SENTRY_AVAILABLE:
        try:
            sentry_sdk.init(
                dsn=sentry_dsn,
                traces_sample_rate=0.1,
                environment="production" if os.getenv("PROD_ENV") else "development",
            )
            logger.info("Sentry crash reporting initialized")
        except ValueError as e:
            logger.warning(f"Sentry initialization failed: {e}")
    elif sentry_dsn and not SENTRY_AVAILABLE:
        logger.warning("SENTRY_DSN set but sentry_sdk not installed (optional)")


def setup_crash_handlers(app_name: str = "Sentinel") -> None:
    """Setup global exception hooks for Python and Qt crashes.

    Args:
        app_name: Application name for error messages.
    """
    qt_crash_handler = QtCrashHandler()
    original_excepthook = sys.excepthook

    def global_excepthook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: object,
    ) -> None:
        """Global exception hook for unhandled exceptions."""
        # Log the exception
        logger.critical(
            f"Unhandled exception: {exc_type.__name__}: {exc_value}",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

        # Try to show Qt message box (non-blocking)
        if exc_type is KeyboardInterrupt:
            # Don't show dialog for keyboard interrupt
            original_excepthook(exc_type, exc_value, exc_traceback)
            return

        try:
            error_msg = (
                f"An unexpected error occurred:\n\n{exc_value}\n\n"
                "Please check the logs for more details."
            )
            qt_crash_handler.crash_signal.emit(
                f"{app_name} - Error",
                error_msg,
            )
        except RuntimeError:
            # If Qt fails, use original hook
            original_excepthook(exc_type, exc_value, exc_traceback)

    sys.excepthook = global_excepthook
    logger.debug("Global exception hooks installed")
