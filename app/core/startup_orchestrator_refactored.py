"""
Startup Orchestrator - Manages deferred initialization with robust error handling.

Architecture:
  - Critical tasks (logging, config): Immediate, on main thread
  - Important tasks (backend services): Deferred 100ms, main thread
  - Background tasks (GPU, scanners): Deferred 300ms+, thread pool
  
All tasks are logged with timestamps and execution time. Failures don't prevent
subsequent initialization. A final summary is emitted when complete.

Signals:
  - taskStarted(task_name: str, phase: str)
  - taskCompleted(task_name: str, elapsed_ms: float, phase: str)
  - taskFailed(task_name: str, error: str, phase: str)
  - startupComplete(successful: int, failed: int, total: int)
  - phaseChanged(phase: str)  # Critical, Important, Background
"""

import logging
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

logger = logging.getLogger(__name__)


class StartupPhase(Enum):
    """Task execution phases."""

    CRITICAL = "critical"  # Must succeed, run immediately
    IMPORTANT = "important"  # Should succeed, small delay
    BACKGROUND = "background"  # Nice to have, thread pool


@dataclass
class StartupTaskInfo:
    """Information about a scheduled task."""

    name: str
    phase: StartupPhase
    delay_ms: int
    func: Callable
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    attempt: int = 0  # For retry logic


class BackgroundTask(QRunnable):
    """
    QRunnable for thread pool execution with proper exception handling.
    
    Thread-safe: All signals emitted from worker thread are queued to main thread
    via Qt's thread-safe signal mechanism.
    """

    class Signals(QObject):
        """Signals emitted by background task."""

        started = Signal(str)  # task_name
        completed = Signal(str, float)  # task_name, elapsed_ms
        failed = Signal(str, str)  # task_name, error_message

    def __init__(self, task_info: StartupTaskInfo):
        """
        Initialize background task.

        Args:
            task_info: StartupTaskInfo with task details
        """
        super().__init__()
        self.task_info = task_info
        self.signals = BackgroundTask.Signals()
        self.setAutoDelete(True)

    def run(self):
        """Execute task in thread pool with timing and error handling."""
        start_time = time.time()
        task_name = self.task_info.name

        try:
            self.signals.started.emit(task_name)
            logger.debug(f"[{self.task_info.phase.value.upper()}] Task '{task_name}' started")

            # Execute the task
            self.task_info.func(*self.task_info.args, **self.task_info.kwargs)

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(f"[{self.task_info.phase.value.upper()}] Task '{task_name}' "
                       f"completed in {elapsed_ms:.0f}ms")
            self.signals.completed.emit(task_name, elapsed_ms)

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            error_msg = f"{type(e).__name__}: {e!s}"
            logger.exception(f"[{self.task_info.phase.value.upper()}] Task '{task_name}' "
                           f"failed after {elapsed_ms:.0f}ms: {error_msg}")
            self.signals.failed.emit(task_name, error_msg)


class StartupOrchestrator(QObject):
    """
    Orchestrates multi-phase application startup.

    Phases:
      1. CRITICAL: Logging, config (immediate, must complete)
      2. IMPORTANT: Backend services (100ms delay, should complete)
      3. BACKGROUND: GPU, scanners (300ms+, nice to have)

    All phases overlap safely via QTimer scheduling.
    
    Usage:
        orchestrator = StartupOrchestrator()
        orchestrator.taskFailed.connect(on_task_failed)
        orchestrator.startupComplete.connect(on_startup_done)
        
        orchestrator.add_immediate("init_logging", setup_logging)
        orchestrator.add_deferred("init_backend", 100, setup_backend)
        orchestrator.add_background("init_gpu", 300, setup_gpu)
        
        orchestrator.execute()
    """

    # Signals with full task metadata
    taskStarted = Signal(str, str)  # task_name, phase
    taskCompleted = Signal(str, float, str)  # task_name, elapsed_ms, phase
    taskFailed = Signal(str, str, str)  # task_name, error_msg, phase
    startupComplete = Signal(int, int, int)  # successful, failed, total
    phaseChanged = Signal(str)  # phase_name

    def __init__(self, parent: Optional[QObject] = None):
        """Initialize startup orchestrator."""
        super().__init__(parent)

        # Task storage
        self._tasks: dict[StartupPhase, list[StartupTaskInfo]] = {
            StartupPhase.CRITICAL: [],
            StartupPhase.IMPORTANT: [],
            StartupPhase.BACKGROUND: [],
        }

        # Execution state
        self._thread_pool = QThreadPool.globalInstance()
        self._thread_pool.setMaxThreadCount(4)
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._total_tasks = 0
        self._is_running = False

        # Timers for deferred execution
        self._timers: dict[int, QTimer] = {}
        self._timer_counter = 0

        logger.debug("StartupOrchestrator initialized")

    def add_immediate(
        self,
        name: str,
        func: Callable,
        *args,
        **kwargs,
    ) -> None:
        """
        Add immediate task (runs on current thread, blocks if slow).

        Critical tasks: logging init, config loading, etc.
        
        Args:
            name: Task name (for logging/signals)
            func: Callable to execute
            *args, **kwargs: Arguments to pass to func
        """
        info = StartupTaskInfo(
            name=name,
            phase=StartupPhase.CRITICAL,
            delay_ms=0,
            func=func,
            args=args,
            kwargs=kwargs,
        )
        self._tasks[StartupPhase.CRITICAL].append(info)
        self._total_tasks += 1
        logger.debug(f"Added immediate task: '{name}'")

    def add_deferred(
        self,
        name: str,
        delay_ms: int,
        func: Callable,
        *args,
        **kwargs,
    ) -> None:
        """
        Add deferred task (runs on main thread after delay).

        Important tasks: backend service init, etc.
        Prevents blocking the UI thread during startup.
        
        Args:
            name: Task name
            delay_ms: Milliseconds to delay before execution
            func: Callable to execute
            *args, **kwargs: Arguments
        """
        info = StartupTaskInfo(
            name=name,
            phase=StartupPhase.IMPORTANT,
            delay_ms=delay_ms,
            func=func,
            args=args,
            kwargs=kwargs,
        )
        self._tasks[StartupPhase.IMPORTANT].append(info)
        self._total_tasks += 1
        logger.debug(f"Added deferred task: '{name}' (delay={delay_ms}ms)")

    def add_background(
        self,
        name: str,
        delay_ms: int,
        func: Callable,
        *args,
        **kwargs,
    ) -> None:
        """
        Add background task (runs in thread pool after delay).

        Background tasks: GPU monitoring, network scanning, etc.
        Non-blocking; failures don't affect main app functionality.
        
        Args:
            name: Task name
            delay_ms: Milliseconds to delay before execution
            func: Callable to execute
            *args, **kwargs: Arguments
        """
        info = StartupTaskInfo(
            name=name,
            phase=StartupPhase.BACKGROUND,
            delay_ms=delay_ms,
            func=func,
            args=args,
            kwargs=kwargs,
        )
        self._tasks[StartupPhase.BACKGROUND].append(info)
        self._total_tasks += 1
        logger.debug(f"Added background task: '{name}' (delay={delay_ms}ms)")

    def execute(self) -> None:
        """
        Execute all scheduled tasks in order.

        Phases execute sequentially: CRITICAL → IMPORTANT → BACKGROUND
        """
        if self._is_running:
            logger.warning("Orchestrator already running")
            return

        self._is_running = True
        self._tasks_completed = 0
        self._tasks_failed = 0

        logger.info("=" * 70)
        logger.info("STARTUP ORCHESTRATOR BEGIN")
        logger.info("=" * 70)

        # Execute phases in order
        self._execute_phase(StartupPhase.CRITICAL)

    def _execute_phase(self, phase: StartupPhase) -> None:
        """Execute all tasks in a phase."""
        phase_name = phase.value.upper()
        logger.info(f"[{phase_name}] Starting phase with {len(self._tasks[phase])} tasks")
        self.phaseChanged.emit(phase.value)

        if not self._tasks[phase]:
            # No tasks in this phase, move to next
            self._advance_to_next_phase(phase)
            return

        if phase == StartupPhase.CRITICAL:
            # Critical tasks: execute immediately on main thread
            self._execute_critical_tasks()
            # Move to next phase
            self._advance_to_next_phase(phase)

        elif phase == StartupPhase.IMPORTANT:
            # Important tasks: execute on main thread after delay
            self._execute_important_tasks()

        elif phase == StartupPhase.BACKGROUND:
            # Background tasks: execute in thread pool with delays
            self._execute_background_tasks()

    def _execute_critical_tasks(self) -> None:
        """Execute all CRITICAL phase tasks immediately."""
        for task_info in self._tasks[StartupPhase.CRITICAL]:
            self._execute_task_immediate(task_info)

    def _execute_task_immediate(self, task_info: StartupTaskInfo) -> None:
        """Execute a task immediately (blocking on main thread)."""
        start_time = time.time()
        task_name = task_info.name

        try:
            self.taskStarted.emit(task_name, task_info.phase.value)
            logger.debug(f"[CRITICAL] Executing '{task_name}'")

            # Execute synchronously
            task_info.func(*task_info.args, **task_info.kwargs)

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(f"[CRITICAL] OK '{task_name}' ({elapsed_ms:.0f}ms)")
            self.taskCompleted.emit(task_name, elapsed_ms, task_info.phase.value)
            self._tasks_completed += 1

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            error_msg = f"{type(e).__name__}: {e!s}"
            logger.exception(f"[CRITICAL] FAILED '{task_name}' failed after {elapsed_ms:.0f}ms")
            self.taskFailed.emit(task_name, error_msg, task_info.phase.value)
            self._tasks_failed += 1
            # Continue with next task even if this fails

    def _execute_important_tasks(self) -> None:
        """Schedule IMPORTANT phase tasks with delays."""
        if not self._tasks[StartupPhase.IMPORTANT]:
            self._advance_to_next_phase(StartupPhase.IMPORTANT)
            return

        for i, task_info in enumerate(self._tasks[StartupPhase.IMPORTANT]):
            # Stagger task execution to avoid UI blocking
            delay = task_info.delay_ms + (i * 50)  # Add stagger

            timer = QTimer(self)
            timer.setSingleShot(True)
            timer_id = self._timer_counter
            self._timer_counter += 1
            self._timers[timer_id] = timer

            def execute_task(info=task_info, tid=timer_id):
                self._execute_task_deferred(info)
                if tid in self._timers:
                    self._timers[tid].deleteLater()
                    del self._timers[tid]

                # Check if all IMPORTANT tasks are done
                if self._tasks_completed + self._tasks_failed >= len(
                    self._tasks[StartupPhase.IMPORTANT]
                ):
                    self._advance_to_next_phase(StartupPhase.IMPORTANT)

            timer.timeout.connect(execute_task)
            timer.start(delay)

    def _execute_task_deferred(self, task_info: StartupTaskInfo) -> None:
        """Execute a task on the main thread with delay."""
        start_time = time.time()
        task_name = task_info.name

        try:
            self.taskStarted.emit(task_name, task_info.phase.value)
            logger.debug(f"[IMPORTANT] Executing '{task_name}'")

            # Execute synchronously
            task_info.func(*task_info.args, **task_info.kwargs)

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(f"[IMPORTANT] OK '{task_name}' ({elapsed_ms:.0f}ms)")
            self.taskCompleted.emit(task_name, elapsed_ms, task_info.phase.value)
            self._tasks_completed += 1

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            error_msg = f"{type(e).__name__}: {e!s}"
            logger.exception(f"[IMPORTANT] FAILED '{task_name}' failed after {elapsed_ms:.0f}ms")
            self.taskFailed.emit(task_name, error_msg, task_info.phase.value)
            self._tasks_failed += 1

    def _execute_background_tasks(self) -> None:
        """Schedule BACKGROUND phase tasks in thread pool."""
        if not self._tasks[StartupPhase.BACKGROUND]:
            self._finish_startup()
            return

        # Track completion
        completed_count = [0]
        total = len(self._tasks[StartupPhase.BACKGROUND])

        for task_info in self._tasks[StartupPhase.BACKGROUND]:
            # Create background task
            bg_task = BackgroundTask(task_info)
            bg_task.signals.started.connect(
                lambda name, phase=task_info.phase.value: self.taskStarted.emit(name, phase)
            )
            bg_task.signals.completed.connect(
                lambda name, elapsed, phase=task_info.phase.value: (
                    self.taskCompleted.emit(name, elapsed, phase),
                    self._on_bg_task_done(name, elapsed, phase, completed_count, total),
                )
            )
            bg_task.signals.failed.connect(
                lambda name, error, phase=task_info.phase.value: (
                    self.taskFailed.emit(name, error, phase),
                    self._on_bg_task_done(name, error, phase, completed_count, total),
                )
            )

            # Schedule execution
            def start_task(task=bg_task, delay=task_info.delay_ms):
                def run():
                    self._thread_pool.start(task)

                QTimer.singleShot(delay, run)

            start_task()

    def _on_bg_task_done(
        self, name: str, info: Any, phase: str, completed: list[int], total: int
    ) -> None:
        """Handle background task completion or failure."""
        completed[0] += 1

        if isinstance(info, float):
            # Success case: info is elapsed_ms
            self._tasks_completed += 1
            logger.info(f"[BACKGROUND] OK '{name}' ({info:.0f}ms)")
        else:
            # Failure case: info is error_msg
            self._tasks_failed += 1
            logger.error(f"[BACKGROUND] FAILED '{name}': {info}")

        # Check if all background tasks are done
        if completed[0] >= total:
            self._finish_startup()

    def _advance_to_next_phase(self, current_phase: StartupPhase) -> None:
        """Advance to the next phase."""
        if current_phase == StartupPhase.CRITICAL:
            self._execute_phase(StartupPhase.IMPORTANT)
        elif current_phase == StartupPhase.IMPORTANT:
            self._execute_phase(StartupPhase.BACKGROUND)

    def _finish_startup(self) -> None:
        """Finalize startup and emit completion signal."""
        logger.info("=" * 70)
        logger.info(f"STARTUP COMPLETE: {self._tasks_completed} successful, "
                   f"{self._tasks_failed} failed, {self._total_tasks} total")
        logger.info("=" * 70)

        self.startupComplete.emit(self._tasks_completed, self._tasks_failed, self._total_tasks)
        self._is_running = False

    def wait_for_completion(self, timeout_ms: int = 30000) -> bool:
        """
        Block until all background tasks complete (for testing).

        Args:
            timeout_ms: Maximum wait time in milliseconds

        Returns:
            True if completed, False if timeout
        """
        return self._thread_pool.waitForDone(timeout_ms)

    def cleanup(self) -> None:
        """Clean up resources (call on app shutdown)."""
        logger.info("StartupOrchestrator cleanup")
        # Stop all pending timers
        for timer in self._timers.values():
            timer.stop()
        self._timers.clear()
