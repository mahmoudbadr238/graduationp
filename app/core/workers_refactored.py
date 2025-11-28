"""
Thread-safe worker infrastructure with timeouts, cancellation, and watchdog monitoring.

Features:
  - CancellableWorker: Base for background tasks with timeout/cancel support
  - WorkerWatchdog: Monitors worker health via heartbeats
  - ThrottledWorker: Debounces rapid requests
  - All signals are thread-safe (emitted from worker thread)

Architecture:
  Worker threads emit signals that are automatically queued to main thread.
  Mutex-protected state prevents race conditions.
  Watchdog monitors for stalled workers (no heartbeat for 15s).
"""

import logging
import threading
import traceback
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QMutex, QMutexLocker, QObject, QRunnable, QTimer, Signal

logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    """
    Thread-safe signals emitted by workers.
    
    These signals are automatically queued to the main thread by Qt's signal system
    when emitted from worker threads.
    """

    started = Signal(str)  # worker_id
    progress = Signal(str, int)  # worker_id, percent (0-100)
    finished = Signal(str, object)  # worker_id, result
    error = Signal(str, str)  # worker_id, error_message
    cancelled = Signal(str)  # worker_id
    heartbeat = Signal(str)  # worker_id (for watchdog)
    statusChanged = Signal(str, str)  # worker_id, status (running, paused, etc)


class CancellableWorker(QRunnable):
    """
    Base class for cancellable background workers with timeout and heartbeat support.

    Features:
      - Timeout enforcement (raises TimeoutError if exceeded)
      - Cooperative cancellation (task must check is_cancelled())
      - Heartbeat signaling for watchdog monitoring
      - Exception handling with full traceback logging
      - Execution timing and metrics

    Usage:
        def my_task(worker: CancellableWorker, **kwargs):
            for i in range(100):
                if worker.is_cancelled():
                    return None
                # Do work...
                worker.emit_heartbeat()
            return "result"

        worker = CancellableWorker(
            "my-task",
            my_task,
            timeout_ms=30000,
            arg1="value"
        )
        worker.signals.finished.connect(on_complete)
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
        """
        Initialize cancellable worker.

        Args:
            worker_id: Unique worker identifier
            task_func: Callable that performs work
            timeout_ms: Timeout in milliseconds (0 = no timeout)
            *args, **kwargs: Arguments passed to task_func
        """
        super().__init__()
        self.worker_id = worker_id
        self.task_func = task_func
        self.args = args
        self.kwargs = kwargs
        self.timeout_ms = timeout_ms
        self.signals = WorkerSignals()

        # State management
        self._cancelled = False
        self._paused = False
        self._status = "idle"
        self._mutex = QMutex()

        # Metrics
        self._start_time: Optional[datetime] = None
        self._last_heartbeat: Optional[datetime] = None

        self.setAutoDelete(True)

    def cancel(self) -> None:
        """Request graceful cancellation (non-blocking)."""
        with QMutexLocker(self._mutex):
            if not self._cancelled:
                self._cancelled = True
                logger.info(f"Worker '{self.worker_id}' cancellation requested")
                self.signals.statusChanged.emit(self.worker_id, "cancelling")

    def is_cancelled(self) -> bool:
        """Check if cancellation was requested (thread-safe)."""
        with QMutexLocker(self._mutex):
            return self._cancelled

    def pause(self) -> None:
        """Request pause (cooperative - task must respond to is_paused())."""
        with QMutexLocker(self._mutex):
            if not self._paused:
                self._paused = True
                logger.debug(f"Worker '{self.worker_id}' paused")
                self.signals.statusChanged.emit(self.worker_id, "paused")

    def resume(self) -> None:
        """Resume after pause."""
        with QMutexLocker(self._mutex):
            if self._paused:
                self._paused = False
                logger.debug(f"Worker '{self.worker_id}' resumed")
                self.signals.statusChanged.emit(self.worker_id, "running")

    def is_paused(self) -> bool:
        """Check if pause was requested."""
        with QMutexLocker(self._mutex):
            return self._paused

    def emit_heartbeat(self) -> None:
        """Emit heartbeat signal (called by task to indicate it's alive)."""
        self._last_heartbeat = datetime.now()
        self.signals.heartbeat.emit(self.worker_id)

    def emit_progress(self, percent: int) -> None:
        """Emit progress update (0-100)."""
        self.signals.progress.emit(self.worker_id, max(0, min(100, percent)))

    def get_elapsed_ms(self) -> float:
        """Get elapsed time since start in milliseconds."""
        if self._start_time is None:
            return 0.0
        return (datetime.now() - self._start_time).total_seconds() * 1000

    def run(self) -> None:
        """Execute task with timeout and error handling (QRunnable interface)."""
        self._start_time = datetime.now()
        self._last_heartbeat = self._start_time

        try:
            # Update status
            with QMutexLocker(self._mutex):
                self._status = "running"
            self.signals.started.emit(self.worker_id)
            logger.info(f"Worker '{self.worker_id}' started")

            # Execute task with self passed as worker parameter
            result = self.task_func(worker=self, *self.args, **self.kwargs)

            # Check timeout
            elapsed_ms = self.get_elapsed_ms()
            if self.timeout_ms > 0 and elapsed_ms > self.timeout_ms:
                raise TimeoutError(f"Task exceeded {self.timeout_ms}ms timeout "
                                  f"(actual: {elapsed_ms:.0f}ms)")

            # Check cancellation
            if self.is_cancelled():
                self.signals.cancelled.emit(self.worker_id)
                logger.info(f"Worker '{self.worker_id}' cancelled after {elapsed_ms:.0f}ms")
                return

            # Success
            with QMutexLocker(self._mutex):
                self._status = "completed"
            self.signals.finished.emit(self.worker_id, result)
            logger.info(f"Worker '{self.worker_id}' completed in {elapsed_ms:.0f}ms")

        except Exception as e:
            elapsed_ms = self.get_elapsed_ms()
            error_msg = f"{type(e).__name__}: {e!s}"
            logger.exception(f"Worker '{self.worker_id}' failed after {elapsed_ms:.0f}ms: "
                           f"{error_msg}\n{traceback.format_exc()}")

            with QMutexLocker(self._mutex):
                self._status = "failed"
            self.signals.error.emit(self.worker_id, error_msg)


class WorkerWatchdog(QObject):
    """
    Monitors worker health via heartbeat signals.

    Detects stalled workers (no heartbeat for N seconds) and emits workerStalled signal.
    Can be connected to auto-restart or cancel logic.

    Signals:
      - workerStalled(worker_id: str, elapsed_sec: float)
      - workerUnregistered(worker_id: str)

    Usage:
        watchdog = WorkerWatchdog(check_interval_ms=5000, stale_threshold_sec=15)
        watchdog.workerStalled.connect(on_worker_stalled)
        
        worker = CancellableWorker(...)
        worker.signals.heartbeat.connect(watchdog.heartbeat)
        watchdog.register_worker("task-1")
        QThreadPool.globalInstance().start(worker)
    """

    workerStalled = Signal(str, float)  # worker_id, elapsed_sec
    workerUnregistered = Signal(str)  # worker_id

    def __init__(
        self,
        check_interval_ms: int = 5000,
        stale_threshold_sec: float = 15.0,
        parent: Optional[QObject] = None,
    ):
        """
        Initialize worker watchdog.

        Args:
            check_interval_ms: How often to check for stalled workers
            stale_threshold_sec: Seconds without heartbeat before stalled
            parent: Qt parent object
        """
        super().__init__(parent)
        self._workers: dict[str, datetime] = {}
        self._mutex = QMutex()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_workers)
        self._check_interval_ms = check_interval_ms
        self._stale_threshold_sec = stale_threshold_sec
        self._timer.start(check_interval_ms)

        logger.debug(f"WorkerWatchdog initialized (check={check_interval_ms}ms, "
                    f"stale={stale_threshold_sec}s)")

    def register_worker(self, worker_id: str) -> None:
        """Register a worker for heartbeat monitoring.

        Args:
            worker_id: Unique worker identifier
        """
        with QMutexLocker(self._mutex):
            self._workers[worker_id] = datetime.now()
            logger.debug(f"Watchdog: registered '{worker_id}'")

    def heartbeat(self, worker_id: str) -> None:
        """
        Receive heartbeat from worker (thread-safe).

        Called by worker to indicate it's still alive.

        Args:
            worker_id: Worker that sent heartbeat
        """
        with QMutexLocker(self._mutex):
            if worker_id in self._workers:
                self._workers[worker_id] = datetime.now()
                # Don't log every heartbeat - too noisy

    def unregister_worker(self, worker_id: str) -> None:
        """
        Stop monitoring a worker (task completed/failed).

        Args:
            worker_id: Worker to unregister
        """
        with QMutexLocker(self._mutex):
            if worker_id in self._workers:
                del self._workers[worker_id]
                logger.debug(f"Watchdog: unregistered '{worker_id}'")
                self.workerUnregistered.emit(worker_id)

    def _check_workers(self) -> None:
        """Check for stalled workers (called periodically by timer)."""
        now = datetime.now()
        stalled_workers = []

        with QMutexLocker(self._mutex):
            for worker_id, last_heartbeat in list(self._workers.items()):
                elapsed = (now - last_heartbeat).total_seconds()

                if elapsed > self._stale_threshold_sec:
                    stalled_workers.append((worker_id, elapsed))

        # Emit signals outside lock
        for worker_id, elapsed in stalled_workers:
            logger.warning(f"Watchdog: '{worker_id}' stalled "
                          f"({elapsed:.1f}s since last heartbeat)")
            self.workerStalled.emit(worker_id, elapsed)

            # Auto-unregister to prevent repeated alerts
            self.unregister_worker(worker_id)

    def stop(self) -> None:
        """Stop watchdog monitoring."""
        self._timer.stop()
        with QMutexLocker(self._mutex):
            self._workers.clear()


class ThrottledWorker(QObject):
    """
    Throttles/debounces rapid requests to avoid overwhelming resources.

    Only executes the most recent request after a delay period.
    Useful for search boxes, sliders, or other rapid user interactions.

    Example:
        def search(query: str):
            return backend.search(query)

        throttle = ThrottledWorker(300, search)  # 300ms delay
        line_edit.textChanged.connect(throttle.request)
        throttle.executed.connect(on_search_results)

    Signals:
      - executed(result): Emitted when task executes
      - queued(): Emitted when request is queued
      - cancelled(): Emitted when pending request is cancelled
    """

    executed = Signal(object)  # result
    queued = Signal()  # Request added to queue
    cancelled = Signal()  # Request cancelled

    def __init__(
        self,
        delay_ms: int,
        task_func: Callable,
        parent: Optional[QObject] = None,
    ):
        """
        Initialize throttled worker.

        Args:
            delay_ms: Milliseconds to wait before executing
            task_func: Callable to execute
            parent: Qt parent object
        """
        super().__init__(parent)
        self.delay_ms = delay_ms
        self.task_func = task_func

        # Timer for delayed execution
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._execute)

        # Pending request storage
        self._pending_args: Optional[tuple] = None
        self._pending_kwargs: Optional[dict] = None
        self._mutex = QMutex()

    def request(self, *args, **kwargs) -> None:
        """
        Request execution (restarts timer if already pending).

        Args:
            *args, **kwargs: Arguments to pass to task_func
        """
        with QMutexLocker(self._mutex):
            self._pending_args = args
            self._pending_kwargs = kwargs

        # Restart timer (discards pending execution)
        self._timer.stop()
        self._timer.start(self.delay_ms)
        self.queued.emit()

    def _execute(self) -> None:
        """Execute the most recent request."""
        with QMutexLocker(self._mutex):
            args = self._pending_args
            kwargs = self._pending_kwargs
            self._pending_args = None
            self._pending_kwargs = None

        if args is not None:
            try:
                result = self.task_func(*args, **kwargs)
                self.executed.emit(result)
            except Exception as e:
                logger.exception(f"ThrottledWorker error: {e}")
                self.executed.emit({"error": str(e)})

    def cancel(self) -> None:
        """Cancel pending execution."""
        self._timer.stop()
        with QMutexLocker(self._mutex):
            self._pending_args = None
            self._pending_kwargs = None
        self.cancelled.emit()


# Global watchdog instance
_watchdog_instance: Optional[WorkerWatchdog] = None
_watchdog_lock = threading.Lock()


def get_watchdog() -> WorkerWatchdog:
    """Get or create global watchdog instance (thread-safe singleton)."""
    global _watchdog_instance
    if _watchdog_instance is None:
        with _watchdog_lock:
            if _watchdog_instance is None:
                _watchdog_instance = WorkerWatchdog()
                logger.debug("Global watchdog created")
    return _watchdog_instance


@contextmanager
def worker_context(
    worker_id: str,
    timeout_ms: int = 30000,
):
    """
    Context manager for registering/unregistering workers with watchdog.

    Usage:
        with worker_context("my-task", timeout_ms=10000):
            # Do work, emit heartbeats
            pass
    """
    watchdog = get_watchdog()
    watchdog.register_worker(worker_id)
    try:
        yield
    finally:
        watchdog.unregister_worker(worker_id)
