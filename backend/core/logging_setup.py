"""Logging and crash handling for Sentinel.

Structured logging with rotating file handler, global exception hooks,
and optional Sentry crash reporting.
"""

import contextlib
import logging
import logging.handlers
import os
import sys

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from .config import get_config
from backend.platform.paths import get_app_paths

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
            # Last-resort crash reporting when the Qt dialog stack is unavailable.
            sys.stderr.write(f"[CRASH] {title}: {message}\n")


def setup_logging(app_name: str = "Sentinel") -> None:
    """Configure structured logging with rotating file handler and optional Sentry.

    Args:
        app_name: Application name for logging prefix.
    """
    config = get_config()
    logs_dir = config.logs_dir
    paths = get_app_paths()

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        with contextlib.suppress(Exception):
            handler.close()

    # Formatter
    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s [%(levelname)s] pid=%(process)d "
            "thread=%(threadName)s %(name)s: %(message)s"
        ),
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
        logger.info("Logging initialized to %s", log_file)
        logger.info(
            "Runtime paths: config=%s data=%s cache=%s state=%s logs=%s",
            paths.config_dir,
            paths.data_dir,
            paths.cache_dir,
            paths.state_dir,
            paths.log_dir,
        )
    except OSError as e:
        logger.error("Failed to initialize file logging: %s", e)

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
            logger.warning("Sentry initialization failed: %s", e)
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
            "Unhandled exception: %s: %s",
            exc_type.__name__,
            exc_value,
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
