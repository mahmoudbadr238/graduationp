"""
FileFunctionBridge — QObject bridge exposing file-shred and file-recovery
workers to the QML frontend via Signals / Slots.

Registered as a context property ``FileFunctionService`` in application.py.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QObject,
    QThreadPool,
    Signal,
    Slot,
)

from .workers import SIGNATURES, CarverWorker, ShredderWorker

logger = logging.getLogger(__name__)


class FileFunctionBridge(QObject):
    """Bridge between QML UI and background shredder / carver workers."""

    # -- signals to QML -----------------------------------------------------
    shredProgress = Signal(int)    # 0-100
    shredStatus = Signal(str)      # phase label
    shredFinished = Signal(str)    # success message
    shredError = Signal(str)       # error message

    carveFound = Signal(str)       # one log-line per carved file
    carveStatus = Signal(str)      # current drive / offset
    carveFinished = Signal(str)    # completion summary
    carveError = Signal(str)       # error message

    busyChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._busy = False
        self._active_worker: ShredderWorker | CarverWorker | None = None

    # -- property -----------------------------------------------------------
    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    def _set_busy(self, value: bool) -> None:
        if self._busy != value:
            self._busy = value
            self.busyChanged.emit()

    # -- slots from QML -----------------------------------------------------
    @Slot(str)
    def start_shredding(self, file_path: str) -> None:
        """Validate *file_path* and launch the ShredderWorker."""
        if self._busy:
            self.shredError.emit("An operation is already running.")
            return

        p = Path(file_path)
        if not p.is_file():
            self.shredError.emit(f"File not found: {file_path}")
            return

        self._set_busy(True)

        worker = ShredderWorker(file_path)
        worker.signals.progress.connect(self.shredProgress)
        worker.signals.status.connect(self.shredStatus)
        worker.signals.finished.connect(self._on_shred_done)
        worker.signals.error.connect(self._on_shred_error)

        self._active_worker = worker
        QThreadPool.globalInstance().start(worker)

    @Slot(str)
    def start_recovery(self, file_type: str) -> None:
        """Launch the CarverWorker for *file_type*."""
        if self._busy:
            self.carveError.emit("An operation is already running.")
            return

        if file_type.upper() not in SIGNATURES:
            self.carveError.emit(f"Unsupported file type: {file_type}")
            return

        self._set_busy(True)

        worker = CarverWorker(file_type)
        worker.signals.found.connect(self.carveFound)
        worker.signals.status.connect(self.carveStatus)
        worker.signals.finished.connect(self._on_carve_done)
        worker.signals.error.connect(self._on_carve_error)

        self._active_worker = worker
        QThreadPool.globalInstance().start(worker)

    @Slot()
    def cancelOperation(self) -> None:
        """Request cancellation of the active worker."""
        if self._active_worker is not None:
            self._active_worker.cancel()

    @Slot(result=list)
    def supportedFileTypes(self) -> list[str]:
        """Return the list of file types the carver can recover."""
        return sorted(SIGNATURES.keys())

    # -- internal handlers --------------------------------------------------
    def _on_shred_done(self, msg: str) -> None:
        self._set_busy(False)
        self._active_worker = None
        self.shredFinished.emit(msg)

    def _on_shred_error(self, msg: str) -> None:
        self._set_busy(False)
        self._active_worker = None
        self.shredError.emit(msg)

    def _on_carve_done(self, msg: str) -> None:
        self._set_busy(False)
        self._active_worker = None
        self.carveFinished.emit(msg)

    def _on_carve_error(self, msg: str) -> None:
        self._set_busy(False)
        self._active_worker = None
        self.carveError.emit(msg)
