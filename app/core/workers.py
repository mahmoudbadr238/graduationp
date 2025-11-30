"""
Thread-safe worker infrastructure with timeouts, cancellation, and watchdog monitoring.
Prevents UI freezes and deadlocks by moving blocking operations off the GUI thread.
"""

import logging
import traceback
from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QMutex, QMutexLocker, QObject, QRunnable, QTimer, Signal

logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    """
    Signals emitted by workers (must be QObject for cross-thread signaling)
    """

    started = Signal(str)  # worker_id
    progress = Signal(str, int)  # worker_id, percent
    finished = Signal(str, object)  # worker_id, result
    error = Signal(str, str)  # worker_id, error_message
    cancelled = Signal(str)  # worker_id
    heartbeat = Signal(str)  # worker_id (for watchdog)


class CancellableWorker(QRunnable):
    """
    Base class for cancellable background workers with timeout support.

    Usage:
        worker = CancellableWorker("scan-network", scan_function, target="192.168.1.0/24")
        worker.signals.finished.connect(on_scan_complete)
        worker.signals.error.connect(on_scan_error)
        QThreadPool.globalInstance().start(worker)
    """

    def __init__(
        self,
        worker_id: str,
        task_func: Callable,
        *args,
        timeout_ms: int = 30000,
        **kwargs,
    ):
        super().__init__()
        self.worker_id = worker_id
        self.task_func = task_func
        self.args = args
        self.kwargs = kwargs
        self.timeout_ms = timeout_ms
        self.signals = WorkerSignals()
        self._cancelled = False
        self._mutex = QMutex()
        self.setAutoDelete(True)

    def cancel(self):
        """Request cancellation (checked periodically by task)"""
        with QMutexLocker(self._mutex):
            self._cancelled = True
            logger.info(f"Worker '{self.worker_id}' cancellation requested")

    def is_cancelled(self) -> bool:
        """Check if cancellation was requested"""
        with QMutexLocker(self._mutex):
            return self._cancelled

    def run(self):
        """Execute task with timeout and error handling"""
        start_time = datetime.now()

        try:
            self.signals.started.emit(self.worker_id)
            logger.info(f"Worker '{self.worker_id}' started")

            # Pass self to task so it can check is_cancelled() and emit heartbeat
            result = self.task_func(*self.args, worker=self, **self.kwargs)

            # Check timeout
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            if elapsed > self.timeout_ms:
                raise TimeoutError(f"Task exceeded {self.timeout_ms}ms timeout")

            # Check cancellation
            if self.is_cancelled():
                self.signals.cancelled.emit(self.worker_id)
                logger.info(f"Worker '{self.worker_id}' cancelled")
                return

            self.signals.finished.emit(self.worker_id, result)
            logger.info(f"Worker '{self.worker_id}' completed in {elapsed:.0f}ms")

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e!s}"
            logger.exception(f"Worker '{self.worker_id}' failed: {error_msg}")
            logger.debug(traceback.format_exc())
            self.signals.error.emit(self.worker_id, error_msg)


class WorkerWatchdog(QObject):
    """
    Monitors worker health via heartbeat signals.
    If a worker misses expected heartbeats, it's considered stalled.
    """

    workerStalled = Signal(str)  # worker_id

    # Default threshold (can be overridden per-worker)
    DEFAULT_STALE_THRESHOLD_SEC = 15
    
    # Extended threshold for long-running operations (network scans, etc.)
    EXTENDED_STALE_THRESHOLD_SEC = 120

    def __init__(self, check_interval_ms: int = 5000, parent=None):
        super().__init__(parent)
        self._workers: dict[str, datetime] = {}
        self._worker_thresholds: dict[str, float] = {}  # Per-worker thresholds
        self._mutex = QMutex()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_workers)
        self._timer.start(check_interval_ms)

    def register_worker(self, worker_id: str, stale_threshold_sec: float | None = None):
        """Register a worker for monitoring with optional custom threshold"""
        with QMutexLocker(self._mutex):
            self._workers[worker_id] = datetime.now()
            # Use provided threshold, or default
            self._worker_thresholds[worker_id] = (
                stale_threshold_sec if stale_threshold_sec is not None 
                else self.DEFAULT_STALE_THRESHOLD_SEC
            )
            logger.debug(f"Watchdog: registered '{worker_id}' with {self._worker_thresholds[worker_id]}s threshold")

    def heartbeat(self, worker_id: str):
        """Worker sends heartbeat to indicate it's alive"""
        with QMutexLocker(self._mutex):
            if worker_id in self._workers:
                self._workers[worker_id] = datetime.now()

    def unregister_worker(self, worker_id: str):
        """Remove worker from monitoring (task completed)"""
        with QMutexLocker(self._mutex):
            if worker_id in self._workers:
                del self._workers[worker_id]
            if worker_id in self._worker_thresholds:
                del self._worker_thresholds[worker_id]
            logger.debug(f"Watchdog: unregistered '{worker_id}'")

    def _check_workers(self):
        """Check for stalled workers"""
        now = datetime.now()
        with QMutexLocker(self._mutex):
            stalled = []
            for worker_id, last_heartbeat in list(self._workers.items()):
                elapsed = (now - last_heartbeat).total_seconds()
                threshold = self._worker_thresholds.get(
                    worker_id, self.DEFAULT_STALE_THRESHOLD_SEC
                )
                if elapsed > threshold:
                    stalled.append(worker_id)
                    logger.warning(
                        f"Watchdog: '{worker_id}' stalled ({elapsed:.1f}s since last heartbeat, threshold={threshold}s)"
                    )

            # Emit signals outside lock
            for worker_id in stalled:
                self.workerStalled.emit(worker_id)
                # Auto-unregister stalled workers after notification
                if worker_id in self._workers:
                    del self._workers[worker_id]
                if worker_id in self._worker_thresholds:
                    del self._worker_thresholds[worker_id]


class ThrottledWorker(QObject):
    """
    Throttles/debounces rapid requests to avoid overwhelming resources.
    Only executes the most recent request after a delay period.

    Example: User types in search box → throttle requests to backend
    """

    executed = Signal(object)  # result

    def __init__(self, delay_ms: int, task_func: Callable, parent=None):
        super().__init__(parent)
        self.delay_ms = delay_ms
        self.task_func = task_func
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._execute)
        self._pending_args = None
        self._pending_kwargs = None

    def request(self, *args, **kwargs):
        """Request execution (restarts timer if already pending)"""
        self._pending_args = args
        self._pending_kwargs = kwargs
        self._timer.stop()
        self._timer.start(self.delay_ms)

    def _execute(self):
        """Execute the most recent request"""
        if self._pending_args is not None:
            try:
                result = self.task_func(*self._pending_args, **self._pending_kwargs)
                self.executed.emit(result)
            except Exception as e:
                logger.exception(f"ThrottledWorker error: {e}")
            finally:
                self._pending_args = None
                self._pending_kwargs = None

    def cancel(self):
        """Cancel pending execution"""
        self._timer.stop()
        self._pending_args = None
        self._pending_kwargs = None


# Global watchdog instance
_watchdog_instance: WorkerWatchdog | None = None


def get_watchdog() -> WorkerWatchdog:
    """Get or create global watchdog instance"""
    global _watchdog_instance
    if _watchdog_instance is None:
        _watchdog_instance = WorkerWatchdog()
    return _watchdog_instance
