"""
Performance Utilities: Debouncing, throttling, and lazy loading helpers.

These utilities help reduce UI lag and API overload by:
    - Debouncing: Delay until calls stop (for search, typing)
    - Throttling: Limit call frequency (for scroll, resize)
    - Lazy loading: Defer expensive operations until needed
"""

from __future__ import annotations

import functools
import threading
import time
from typing import Any, Callable, TypeVar

from PySide6.QtCore import QObject, QTimer, Signal, Slot

T = TypeVar("T")


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


class Throttler(QObject):
    """
    Throttle function calls to limit frequency.
    
    Use for: scroll handlers, resize events, live updates.
    Executes immediately, then ignores calls until `interval_ms` passes.
    
    Example:
        throttler = Throttler(100)  # Max 10 calls/second
        throttler.triggered.connect(update_ui)
        
        # In scroll handler:
        throttler.call(scroll_position)
    """
    
    triggered = Signal(object)
    
    def __init__(self, interval_ms: int = 100, parent: QObject = None):
        """
        Initialize throttler.
        
        Args:
            interval_ms: Minimum interval between calls
            parent: Qt parent object
        """
        super().__init__(parent)
        self._interval_ms = interval_ms
        self._last_call: float = 0
        self._pending_args: Any = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
    
    @Slot(object)
    def call(self, args: Any = None) -> None:
        """
        Make a throttled call.
        
        Args:
            args: Arguments to pass when triggered
        """
        now = time.time() * 1000  # ms
        elapsed = now - self._last_call
        
        if elapsed >= self._interval_ms:
            # Enough time passed, execute immediately
            self._last_call = now
            self.triggered.emit(args)
        else:
            # Too soon, schedule for later
            self._pending_args = args
            if not self._timer.isActive():
                remaining = self._interval_ms - elapsed
                self._timer.start(int(remaining))
    
    def _on_timeout(self) -> None:
        """Handle timeout - emit pending args."""
        self._last_call = time.time() * 1000
        self.triggered.emit(self._pending_args)
        self._pending_args = None


class LazyLoader:
    """
    Lazy loading helper for expensive objects.
    
    Defers initialization until first access.
    
    Example:
        ai_engine = LazyLoader(lambda: LocalLLMEngine())
        
        # Later, when needed:
        engine = ai_engine.get()  # Now it initializes
    """
    
    def __init__(self, factory: Callable[[], T]):
        """
        Initialize lazy loader.
        
        Args:
            factory: Function that creates the object
        """
        self._factory = factory
        self._instance: T | None = None
        self._lock = threading.Lock()
        self._initialized = False
    
    def get(self) -> T:
        """
        Get the instance, initializing if needed.
        
        Returns:
            The lazily-loaded instance
        """
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._instance = self._factory()
                    self._initialized = True
        return self._instance
    
    def is_initialized(self) -> bool:
        """Check if the instance has been initialized."""
        return self._initialized
    
    def reset(self) -> None:
        """Reset the loader, forcing reinitialization on next get()."""
        with self._lock:
            self._instance = None
            self._initialized = False


def debounce(delay_ms: int = 300):
    """
    Decorator to debounce a function.
    
    Args:
        delay_ms: Delay in milliseconds
    
    Example:
        @debounce(300)
        def on_search_changed(text):
            # This won't be called until 300ms after last invocation
            perform_search(text)
    """
    def decorator(func: Callable) -> Callable:
        timer: QTimer = None
        pending_args = None
        pending_kwargs = None
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal timer, pending_args, pending_kwargs
            
            pending_args = args
            pending_kwargs = kwargs
            
            if timer is None:
                timer = QTimer()
                timer.setSingleShot(True)
                
                def on_timeout():
                    func(*pending_args, **pending_kwargs)
                
                timer.timeout.connect(on_timeout)
            
            timer.stop()
            timer.start(delay_ms)
        
        return wrapper
    return decorator


def throttle(interval_ms: int = 100):
    """
    Decorator to throttle a function.
    
    Args:
        interval_ms: Minimum interval between calls
    
    Example:
        @throttle(100)
        def on_scroll(position):
            # Max 10 times per second
            update_view(position)
    """
    def decorator(func: Callable) -> Callable:
        last_call: list[float] = [0]
        lock = threading.Lock()
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time() * 1000
            with lock:
                elapsed = now - last_call[0]
                if elapsed >= interval_ms:
                    last_call[0] = now
                    return func(*args, **kwargs)
            return None
        
        return wrapper
    return decorator


class BatchProcessor:
    """
    Batch multiple items for processing together.
    
    Useful for reducing overhead when processing many items.
    
    Example:
        processor = BatchProcessor(
            process_func=save_to_db,
            batch_size=50,
            max_wait_ms=1000
        )
        
        for item in items:
            processor.add(item)  # Batches automatically
        
        processor.flush()  # Process remaining items
    """
    
    def __init__(
        self,
        process_func: Callable[[list], None],
        batch_size: int = 50,
        max_wait_ms: int = 1000,
    ):
        """
        Initialize batch processor.
        
        Args:
            process_func: Function to process a batch
            batch_size: Maximum items per batch
            max_wait_ms: Maximum time to wait before processing
        """
        self._process = process_func
        self._batch_size = batch_size
        self._max_wait_ms = max_wait_ms
        self._items: list = []
        self._lock = threading.Lock()
        self._timer: QTimer | None = None
        self._last_add: float = 0
    
    def add(self, item: Any) -> None:
        """Add an item to the batch."""
        with self._lock:
            self._items.append(item)
            self._last_add = time.time() * 1000
            
            if len(self._items) >= self._batch_size:
                self._process_batch()
            elif self._timer is None:
                self._start_timer()
    
    def flush(self) -> None:
        """Process any remaining items."""
        with self._lock:
            if self._items:
                self._process_batch()
    
    def _process_batch(self) -> None:
        """Process current batch."""
        if not self._items:
            return
        
        batch = self._items
        self._items = []
        
        if self._timer:
            self._timer.stop()
            self._timer = None
        
        try:
            self._process(batch)
        except Exception:
            pass  # Log error but don't stop
    
    def _start_timer(self) -> None:
        """Start the max-wait timer."""
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.flush)
        self._timer.start(self._max_wait_ms)


class RequestDeduplicator:
    """
    Deduplicate concurrent requests for the same resource.
    
    If multiple requests come in for the same key while one is
    in progress, they all share the same result.
    
    Example:
        dedup = RequestDeduplicator()
        
        async def get_explanation(event_id):
            async def fetch():
                return await ai.explain(event_id)
            
            return await dedup.request(event_id, fetch)
    """
    
    def __init__(self):
        """Initialize deduplicator."""
        self._pending: dict[str, threading.Event] = {}
        self._results: dict[str, Any] = {}
        self._lock = threading.Lock()
    
    def request(
        self,
        key: str,
        fetch_func: Callable[[], T],
    ) -> T:
        """
        Request a resource, deduplicating concurrent requests.
        
        Args:
            key: Unique key for the request
            fetch_func: Function to fetch the resource
        
        Returns:
            The fetched resource
        """
        with self._lock:
            if key in self._pending:
                # Wait for existing request
                event = self._pending[key]
            else:
                # Start new request
                event = threading.Event()
                self._pending[key] = event
                
                try:
                    result = fetch_func()
                    self._results[key] = result
                finally:
                    event.set()
                    del self._pending[key]
                
                return result
        
        # Wait for the result
        event.wait()
        return self._results.get(key)
    
    def clear(self, key: str | None = None) -> None:
        """Clear cached results."""
        with self._lock:
            if key:
                self._results.pop(key, None)
            else:
                self._results.clear()
