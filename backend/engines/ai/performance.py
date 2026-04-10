"""
Performance Utilities: Debouncing helper.

Reduces UI lag and API overload by delaying until calls stop (for search, typing).
"""

from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal, Slot


class Debouncer(QObject):
    """
    Debounce function calls to reduce redundant processing.

    Use for: search input, event selection, filter changes.
    Waits until calls stop for `delay_ms` before executing.

    Example:
        debouncer = Debouncer(300)  # 300ms delay
        debouncer.triggered.connect(do_search)

        # In input handler:
        debouncer.call(search_text)
    """

    triggered = Signal(object)  # Emits the latest args

    def __init__(self, delay_ms: int = 300, parent: QObject = None):
        """
        Initialize debouncer.

        Args:
            delay_ms: Delay in milliseconds before triggering
            parent: Qt parent object
        """
        super().__init__(parent)
        self._delay_ms = delay_ms
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._pending_args: Any = None

    @Slot(object)
    def call(self, args: Any = None) -> None:
        """
        Schedule a debounced call.

        Args:
            args: Arguments to pass when triggered
        """
        self._pending_args = args
        self._timer.stop()
        self._timer.start(self._delay_ms)

    def _on_timeout(self) -> None:
        """Handle timeout - emit the signal."""
        self.triggered.emit(self._pending_args)
        self._pending_args = None

    def cancel(self) -> None:
        """Cancel any pending call."""
        self._timer.stop()
        self._pending_args = None

    @property
    def is_pending(self) -> bool:
        """Check if a call is pending."""
        return self._timer.isActive()
