"""
Startup Orchestrator - Manages deferred initialization and background loading
Prevents UI blocking during app launch by scheduling non-critical tasks
"""

import logging
import time
from collections.abc import Callable
from typing import Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

logger = logging.getLogger(__name__)

# Phase timeouts: ensure startup completes even if a task hangs
PHASE_TIMEOUTS = {
    "critical": 5000,      # Critical initialization: max 5 seconds
    "important": 10000,    # Important services: max 10 seconds
    "background": 30000,   # Background tasks: max 30 seconds
}

# Phase definitions for tracking
STARTUP_PHASES = {
    "critical": "QML Engine + Main Window",
    "important": "Backend Services Initialization",
    "background": "GPU Monitoring + Scanners",
}


class StartupTask(QRunnable):
    """Runnable task for background initialization"""

    class Signals(QObject):
        completed = Signal(str)  # task_name
        failed = Signal(str, str)  # task_name, error
        timeout = Signal(str)  # task_name (timeout signal)

    def __init__(self, name: str, func: Callable, timeout_ms: int = 0, *args, **kwargs):
        super().__init__()
        self.name = name
        self.func = func
        self.timeout_ms = timeout_ms
        self.args = args
        self.kwargs = kwargs
        self.signals = StartupTask.Signals()
        self.setAutoDelete(True)
        self._timeout_timer: Optional[QTimer] = None

    def run(self):
        start_time = time.time()
        try:
            logger.info(f"[StartupTask] Running: {self.name}")
            
            # Set timeout if specified
            if self.timeout_ms > 0:
                self._timeout_timer = QTimer()
                self._timeout_timer.setSingleShot(True)
                self._timeout_timer.timeout.connect(self._on_timeout)
                self._timeout_timer.start(self.timeout_ms)
            
            self.func(*self.args, **self.kwargs)
            
            # Cancel timeout if task completed in time
            if self._timeout_timer:
                self._timeout_timer.stop()
            
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"[StartupTask] Completed: {self.name} ({elapsed:.0f}ms)")
            self.signals.completed.emit(self.name)
        except Exception as e:
            logger.exception(f"[StartupTask] Failed {self.name}: {e}")
            self.signals.failed.emit(self.name, str(e))
    
    def _on_timeout(self):
        """Handle task timeout"""
        logger.error(f"[StartupTask] Timeout: {self.name}")
        self.signals.timeout.emit(self.name)


class StartupOrchestrator(QObject):
    """
    Orchestrates application startup to optimize load time with timeout protection
    - Critical phase: QML engine, main window (5s timeout)
    - Important phase: Backend services (10s timeout)
    - Background phase: GPU monitoring, scanners (30s timeout)
    """

    startupComplete = Signal()
    phaseStarted = Signal(str)  # phase_name
    phaseCompleted = Signal(str)  # phase_name
    phaseFailed = Signal(str, str)  # phase_name, error
    taskCompleted = Signal(str)  # task name
    taskFailed = Signal(str, str)  # task name, error

    def __init__(self, parent=None):
        super().__init__(parent)
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(4)
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._tasks_timeout = 0
        self._total_tasks = 0
        self._task_names: list[str] = []
        self._current_phase: Optional[str] = None
        self._phase_timers: dict[str, QTimer] = {}
        self._phase_success: dict[str, bool] = {}

    def schedule_immediate(self, name: str, func: Callable, *args, **kwargs):
        """Execute immediately on current thread (critical phase, no timeout)"""
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
            # Critical phase failure - propagate
            if self._current_phase == "critical":
                self.phaseFailed.emit("critical", str(e))

    def schedule_deferred(
        self, delay_ms: int, name: str, func: Callable, *args, **kwargs
    ):
        """Schedule to run after delay on UI thread (important phase)"""
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
                # Important phase failure - continue but log
                if self._current_phase == "important":
                    logger.warning(f"Important task failed, continuing: {name}")

        QTimer.singleShot(delay_ms, execute)

    def schedule_background(
        self, delay_ms: int, name: str, func: Callable, *args, **kwargs
    ):
        """Schedule to run in background thread pool (background phase, 30s timeout)"""
        self._total_tasks += 1
        self._task_names.append(name)

        def execute():
            task = StartupTask(
                name, func, 
                timeout_ms=PHASE_TIMEOUTS.get("background", 30000),
                *args, **kwargs
            )
            task.signals.completed.connect(self._on_task_completed)
            task.signals.failed.connect(self._on_task_failed)
            task.signals.timeout.connect(self._on_task_timeout)
            self.thread_pool.start(task)

        QTimer.singleShot(delay_ms, execute)

    def start_phase(self, phase: str):
        """Mark the start of a startup phase"""
        self._current_phase = phase
        self._phase_success[phase] = True
        logger.info(f"[Startup] Starting phase: {phase} ({STARTUP_PHASES.get(phase, 'unknown')})")
        self.phaseStarted.emit(phase)
        
        # Set phase timeout
        if phase in PHASE_TIMEOUTS:
            timeout_ms = PHASE_TIMEOUTS[phase]
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self._on_phase_timeout(phase))
            timer.start(timeout_ms)
            self._phase_timers[phase] = timer
            logger.info(f"[Startup] Phase timeout set: {phase} ({timeout_ms}ms)")

    def end_phase(self, phase: str, success: bool = True):
        """Mark the end of a startup phase"""
        self._phase_success[phase] = success
        status = "SUCCESS" if success else "FAILED"
        logger.info(f"[Startup] Ending phase: {phase} ({status})")
        
        # Cancel phase timeout
        if phase in self._phase_timers:
            self._phase_timers[phase].stop()
            del self._phase_timers[phase]
        
        if success:
            self.phaseCompleted.emit(phase)
        else:
            self.phaseFailed.emit(phase, "Phase failed")

    def _on_phase_timeout(self, phase: str):
        """Handle phase timeout"""
        logger.error(f"[Startup] Phase timeout: {phase}")
        self._phase_success[phase] = False
        self.phaseFailed.emit(phase, "Phase timeout exceeded")

    def _on_task_completed(self, name: str):
        """Handle background task completion"""
        self._tasks_completed += 1
        logger.info(f"[Task] Completed: {name}")
        self.taskCompleted.emit(name)
        self._check_completion()

    def _on_task_failed(self, name: str, error: str):
        """Handle background task failure"""
        self._tasks_failed += 1
        logger.warning(f"[Task] Failed: {name} - {error}")
        self.taskFailed.emit(name, error)
        self._check_completion()

    def _on_task_timeout(self, name: str):
        """Handle background task timeout"""
        self._tasks_timeout += 1
        logger.error(f"[Task] Timeout: {name}")
        self.taskFailed.emit(name, "Task timeout")
        self._check_completion()

    def _check_completion(self):
        """Check if all tasks are done"""
        total = self._tasks_completed + self._tasks_failed + self._tasks_timeout
        if total >= self._total_tasks and self._total_tasks > 0:
            logger.info(
                f"[Startup] All tasks completed "
                f"({self._tasks_completed} succeeded, "
                f"{self._tasks_failed} failed, "
                f"{self._tasks_timeout} timeout)"
            )
            self.startupComplete.emit()

    def wait_for_completion(self, timeout_ms: int = 60000) -> bool:
        """
        Block until all background tasks complete (for testing).
        Default timeout increased to 60s to account for phase timeouts.

        Args:
            timeout_ms: Maximum wait time

        Returns:
            True if completed, False if timeout
        """
        return self.thread_pool.waitForDone(timeout_ms)

    def get_phase_status(self) -> dict[str, bool]:
        """Get status of all phases"""
        return self._phase_success.copy()

    def is_phase_complete(self, phase: str) -> bool:
        """Check if a specific phase completed successfully"""
        return self._phase_success.get(phase, False)
