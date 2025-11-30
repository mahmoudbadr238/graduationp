"""
Enhanced logging and crash handling for Sentinel.

Features:
  - Structured logging with rotating file handler
  - Qt signal-based logging adapter for QML notifications
  - Performance metrics and timing decorators
  - Global exception hooks for unhandled errors
  - Optional Sentry crash reporting
  - Standardized log levels: [DEBUG], [INFO], [OK], [WARNING], [ERROR], [CRITICAL]

Log levels:
  - DEBUG: Detailed diagnostic information (default in dev, filtered in prod)
  - INFO: General informational messages
  - WARNING: Warning messages for potential issues
  - ERROR: Error messages for failures
  - CRITICAL: Critical errors that may crash the app
"""

import functools
import logging
import logging.handlers
import os
import sys
import time
from collections.abc import Callable
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from .config import get_config

logger = logging.getLogger(__name__)

# Optional Sentry (only if DSN is set)
try:
    import sentry_sdk

    SENTRY_AVAILABLE = True
except ImportError:
    sentry_sdk = None
    SENTRY_AVAILABLE = False


class QtLogSignalAdapter(logging.Handler):
    """
    Adapter that forwards log records to Qt signals.

    Allows QML to display log notifications (toasts, alerts) in real-time.
    Only forwards WARNING and above to avoid notification spam.
    """

    # Signals
    logEmitted = Signal(str, str, str)  # level, logger_name, message

    _instance: Optional["QtLogSignalAdapter"] = None

    def __init__(self):
        """Initialize Qt log adapter."""
        super().__init__()
        self.setLevel(logging.WARNING)  # Only forward warnings and above

    @classmethod
    def instance(cls) -> "QtLogSignalAdapter":
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = QtLogSignalAdapter()
        return cls._instance

    def emit(self, record: logging.LogRecord) -> None:
        """Emit log record as Qt signal."""
        try:
            level_name = record.levelname
            logger_name = record.name
            message = self.format(record)

            # Emit to Qt signal (automatically queued to main thread)
            self.logEmitted.emit(level_name, logger_name, message)
        except Exception:
            self.handleError(record)


class QtCrashHandler(QObject):
    """Handles Qt-specific crashes with non-blocking dialogs."""

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


class StructuredFormatter(logging.Formatter):
    """
    Structured logging formatter with standardized levels.

    Formats log records with color codes and consistent structure:
      [TIMESTAMP] [LEVEL] [LOGGER] message

    Example output:
      2024-01-15 10:30:45.123 [INFO] app.core.container: Container initialized
      2024-01-15 10:30:45.234 [WARNING] app.infra.nmap: Nmap not found in PATH
      2024-01-15 10:30:45.456 [ERROR] app.ui.backend: Failed to load events
    """

    # ANSI color codes
    COLORS = {
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[32m",  # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_color: bool = True):
        """
        Initialize formatter.

        Args:
            use_color: Whether to use ANSI colors (disabled for file logging)
        """
        super().__init__()
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        """Format log record."""
        # Timestamp
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")

        # Level with color
        level_name = record.levelname
        if self.use_color and record.levelno in self.COLORS:
            level_color = self.COLORS[record.levelno]
            level_str = f"{level_color}[{level_name:8}]{self.RESET}"
        else:
            level_str = f"[{level_name:8}]"

        # Logger name (shortened)
        logger_name = record.name
        if logger_name.startswith("app."):
            logger_name = logger_name[4:]  # Remove 'app.' prefix

        # Message
        message = record.getMessage()

        # Build final log line
        log_line = f"{timestamp} {level_str} {logger_name}: {message}"

        # Add exception info if present
        if record.exc_info:
            log_line += f"\n{self.formatException(record.exc_info)}"

        return log_line


def setup_logging(app_name: str = "Sentinel") -> None:
    """
    Configure structured logging with rotating file handler.

    Args:
        app_name: Application name for logging and file names
    """
    # Set console encoding to UTF-8 to handle Unicode characters
    if sys.platform == "win32":
        import io

        # On Windows, ensure stdout/stderr use UTF-8
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )

    config = get_config()
    logs_dir = config.logs_dir

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler (colored, INFO and above)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = StructuredFormatter(use_color=True)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler (no color, DEBUG and above, rotating)
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / f"{app_name.lower()}.log"

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=1024 * 1024,  # 1 MB per file
            backupCount=10,  # Keep 10 old files
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = StructuredFormatter(use_color=False)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        logger.info(f"File logging initialized: {log_file}")

    except OSError as e:
        logger.exception(f"Failed to initialize file logging: {e}")

    # Qt signal adapter (for QML notifications)
    try:
        qt_adapter = QtLogSignalAdapter.instance()
        qt_adapter.setFormatter(StructuredFormatter(use_color=False))
        root_logger.addHandler(qt_adapter)
        logger.debug("Qt signal adapter enabled")
    except Exception as e:
        logger.exception(f"Failed to initialize Qt adapter: {e}")

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

    logger.info(f"Logging setup complete for '{app_name}'")


def setup_crash_handlers(app_name: str = "Sentinel") -> None:
    """
    Setup global exception hooks for Python and Qt crashes.

    Args:
        app_name: Application name for error dialogs
    """
    qt_crash_handler = QtCrashHandler()
    original_excepthook = sys.excepthook

    def global_excepthook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: object,
    ) -> None:
        """Global exception hook for unhandled exceptions."""
        # Log the exception with full traceback
        logger.critical(
            f"Unhandled exception: {exc_type.__name__}: {exc_value}",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

        # Don't show dialog for keyboard interrupt
        if exc_type is KeyboardInterrupt:
            original_excepthook(exc_type, exc_value, exc_traceback)
            return

        # Try to show Qt message box (non-blocking)
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


def log_timing(func: Callable) -> Callable:
    """
    Decorator to log function execution time.

    Example:
        @log_timing
        def expensive_operation():
            time.sleep(1)
            return "done"

    Logs as:
        [DEBUG] expensive_operation completed in 1000.5ms
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start = time.time()
        func_name = func.__qualname__

        try:
            logger.debug(f"[{func_name}] starting...")
            result = func(*args, **kwargs)
            elapsed_ms = (time.time() - start) * 1000
            logger.debug(f"[{func_name}] completed in {elapsed_ms:.1f}ms")
            return result
        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            logger.exception(f"[{func_name}] failed after {elapsed_ms:.1f}ms: {e}")
            raise

    return wrapper


def get_log_adapter(name: str = __name__) -> logging.LoggerAdapter:
    """
    Get a logger adapter with custom filters/extras.

    Useful for adding context to all logs from a module.

    Example:
        log = get_log_adapter(__name__)
        log.info("Message", extra={"worker_id": "scan-1"})
    """
    return logging.LoggerAdapter(logging.getLogger(name), {})
