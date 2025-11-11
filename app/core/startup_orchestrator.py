"""
Startup Orchestrator - Manages deferred initialization and background loading
Prevents UI blocking during app launch by scheduling non-critical tasks
"""

import logging
import time
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

logger = logging.getLogger(__name__)


class StartupTask(QRunnable):
    """Runnable task for background initialization"""

    class Signals(QObject):
        completed = Signal(str)  # task_name
        failed = Signal(str, str)  # task_name, error

    def __init__(self, name: str, func: Callable, *args, **kwargs):
        super().__init__()
        self.name = name
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.signals = StartupTask.Signals()
        self.setAutoDelete(True)

    def run(self):
        start_time = time.time()
        try:
            logger.info(f"[StartupTask] Running: {self.name}")
            self.func(*self.args, **self.kwargs)
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"[StartupTask] Completed: {self.name} ({elapsed:.0f}ms)")
            self.signals.completed.emit(self.name)
        except Exception as e:
            logger.exception(f"[StartupTask] Failed {self.name}: {e}")
            self.signals.failed.emit(self.name, str(e))


class StartupOrchestrator(QObject):
    """
    Orchestrates application startup to optimize load time
    - Critical tasks: Run immediately (QML engine, main window)
    - Important tasks: Delay 100ms (backend services)
    - Background tasks: Delay 300ms+ (GPU monitoring, scanners, analytics)
    """

    startupComplete = Signal()
    taskCompleted = Signal(str)  # task name
    taskFailed = Signal(str, str)  # task name, error

    def __init__(self, parent=None):
        super().__init__(parent)
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(4)
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._total_tasks = 0
        self._task_names: list[str] = []

    def schedule_immediate(self, name: str, func: Callable, *args, **kwargs):
        """Execute immediately on current thread"""
        start_time = time.time()
        try:
            logger.info(f"[Immediate] {name}")
            func(*args, **kwargs)
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"[Immediate] Completed {name} ({elapsed:.0f}ms)")
            self.taskCompleted.emit(name)
        except Exception as e:
            logger.exception(f"[Immediate] Failed {name}: {e}")
            self.taskFailed.emit(name, str(e))

    def schedule_deferred(
        self, delay_ms: int, name: str, func: Callable, *args, **kwargs
    ):
        """Schedule to run after delay on UI thread"""
        self._task_names.append(name)

        def execute():
            start_time = time.time()
            try:
                logger.info(f"[Deferred {delay_ms}ms] {name}")
                func(*args, **kwargs)
                elapsed = (time.time() - start_time) * 1000
                logger.info(f"[Deferred] Completed {name} ({elapsed:.0f}ms)")
                self.taskCompleted.emit(name)
            except Exception as e:
                logger.exception(f"[Deferred] Failed {name}: {e}")
                self.taskFailed.emit(name, str(e))

        QTimer.singleShot(delay_ms, execute)

    def schedule_background(
        self, delay_ms: int, name: str, func: Callable, *args, **kwargs
    ):
        """Schedule to run in background thread pool"""
        self._total_tasks += 1
        self._task_names.append(name)

        def execute():
            task = StartupTask(name, func, *args, **kwargs)
            task.signals.completed.connect(self._on_task_completed)
            task.signals.failed.connect(self._on_task_failed)
            self.thread_pool.start(task)

        QTimer.singleShot(delay_ms, execute)

    def _on_task_completed(self, name: str):
        """Handle background task completion"""
        self._tasks_completed += 1
        self.taskCompleted.emit(name)
        self._check_completion()

    def _on_task_failed(self, name: str, error: str):
        """Handle background task failure"""
        self._tasks_failed += 1
        self.taskFailed.emit(name, error)
        self._check_completion()

    def _check_completion(self):
        """Check if all tasks are done"""
        total = self._tasks_completed + self._tasks_failed
        if total >= self._total_tasks and self._total_tasks > 0:
            logger.info(
                f"[Startup] All tasks completed ({self._tasks_completed} succeeded, {self._tasks_failed} failed)"
            )
            self.startupComplete.emit()

    def wait_for_completion(self, timeout_ms: int = 30000) -> bool:
        """
        Block until all background tasks complete (for testing).

        Args:
            timeout_ms: Maximum wait time

        Returns:
            True if completed, False if timeout
        """
        return self.thread_pool.waitForDone(timeout_ms)
