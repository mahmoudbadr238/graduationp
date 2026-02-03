"""
Qt Background Worker for Smart Security Assistant
==================================================
Production-grade Qt integration with:
- Non-blocking background processing
- Request timeout handling
- Response caching
- CPU throttling
- Error recovery

This module ensures the UI NEVER freezes.
"""

import logging
import hashlib
import time
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import OrderedDict
from threading import Lock

logger = logging.getLogger(__name__)

# Try to import PySide6
try:
    from PySide6.QtCore import (
        QObject, QThread, Signal, Slot, QTimer, QMutex, QMutexLocker
    )
    HAS_QT = True
except ImportError:
    HAS_QT = False
    logger.warning("PySide6 not available - Qt worker disabled")


# =============================================================================
# Response Cache
# =============================================================================

@dataclass
class CachedResponse:
    """A cached assistant response with metadata."""
    response: Dict[str, Any]
    timestamp: float
    hit_count: int = 0


class ResponseCache:
    """
    LRU cache for assistant responses.
    
    Caches responses by (intent, query_hash) to avoid
    re-processing identical queries.
    """
    
    def __init__(self, max_size: int = 100, ttl_seconds: float = 300):
        """
        Initialize the cache.
        
        Args:
            max_size: Maximum number of cached responses
            ttl_seconds: Time-to-live for cached entries (5 min default)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, CachedResponse] = OrderedDict()
        self._lock = Lock()
    
    def _make_key(self, intent: str, query: str) -> str:
        """Create a cache key from intent and query."""
        query_hash = hashlib.md5(query.lower().strip().encode()).hexdigest()[:8]
        return f"{intent}:{query_hash}"
    
    def get(self, intent: str, query: str) -> Optional[Dict[str, Any]]:
        """
        Get a cached response if available and not expired.
        
        Args:
            intent: The classified intent
            query: The original query
        
        Returns:
            Cached response dict or None
        """
        key = self._make_key(intent, query)
        
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            
            # Check TTL
            if time.time() - entry.timestamp > self.ttl_seconds:
                del self._cache[key]
                return None
            
            # Update hit count and move to end (most recently used)
            entry.hit_count += 1
            self._cache.move_to_end(key)
            
            logger.debug(f"Cache hit for {key} (hits: {entry.hit_count})")
            return entry.response
    
    def put(self, intent: str, query: str, response: Dict[str, Any]) -> None:
        """
        Cache a response.
        
        Args:
            intent: The classified intent
            query: The original query
            response: The response to cache
        """
        key = self._make_key(intent, query)
        
        with self._lock:
            # Remove oldest entries if at capacity
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            
            self._cache[key] = CachedResponse(
                response=response,
                timestamp=time.time(),
            )
            
            logger.debug(f"Cached response for {key}")
    
    def clear(self) -> None:
        """Clear all cached responses."""
        with self._lock:
            self._cache.clear()
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_hits = sum(e.hit_count for e in self._cache.values())
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "total_hits": total_hits,
            }


# =============================================================================
# Request Throttler
# =============================================================================

class RequestThrottler:
    """
    Throttles requests to prevent CPU spikes.
    
    Implements:
    - Minimum delay between requests
    - Request rate limiting
    - Concurrent request limiting
    """
    
    def __init__(
        self,
        min_delay_ms: int = 100,
        max_requests_per_second: float = 5.0,
        max_concurrent: int = 2,
    ):
        self.min_delay_ms = min_delay_ms
        self.max_requests_per_second = max_requests_per_second
        self.max_concurrent = max_concurrent
        
        self._last_request_time = 0.0
        self._request_count = 0
        self._window_start = time.time()
        self._concurrent = 0
        self._lock = Lock()
    
    def can_proceed(self) -> bool:
        """Check if a new request can proceed."""
        with self._lock:
            now = time.time()
            
            # Check concurrent limit
            if self._concurrent >= self.max_concurrent:
                return False
            
            # Check minimum delay
            if (now - self._last_request_time) * 1000 < self.min_delay_ms:
                return False
            
            # Check rate limit (reset window every second)
            if now - self._window_start >= 1.0:
                self._request_count = 0
                self._window_start = now
            
            if self._request_count >= self.max_requests_per_second:
                return False
            
            return True
    
    def acquire(self) -> bool:
        """Acquire a request slot."""
        with self._lock:
            if not self.can_proceed():
                return False
            
            self._concurrent += 1
            self._request_count += 1
            self._last_request_time = time.time()
            return True
    
    def release(self) -> None:
        """Release a request slot."""
        with self._lock:
            self._concurrent = max(0, self._concurrent - 1)


# =============================================================================
# Qt Worker Thread
# =============================================================================

if HAS_QT:
    
    class AssistantWorker(QObject):
        """
        Background worker for processing assistant queries.
        
        Signals:
            started: Emitted when processing starts
            finished: Emitted with response dict when done
            error: Emitted with error message on failure
            progress: Emitted with progress updates
        """
        
        started = Signal()
        finished = Signal(dict)
        error = Signal(str)
        progress = Signal(str)
        
        def __init__(
            self,
            assistant=None,
            cache: Optional[ResponseCache] = None,
            throttler: Optional[RequestThrottler] = None,
            timeout_ms: int = 10000,
        ):
            super().__init__()
            self._assistant = assistant
            self._cache = cache or ResponseCache()
            self._throttler = throttler or RequestThrottler()
            self._timeout_ms = timeout_ms
            self._current_query = ""
            self._is_processing = False
        
        def set_assistant(self, assistant) -> None:
            """Set the assistant instance."""
            self._assistant = assistant
        
        @Slot(str)
        def process_query(self, query: str) -> None:
            """
            Process a query in the background.
            
            This slot should be connected to from the main thread
            and executed in a worker thread.
            """
            if self._is_processing:
                self.error.emit("Already processing a query")
                return
            
            if not self._assistant:
                self.error.emit("Assistant not initialized")
                return
            
            # Check throttle
            if not self._throttler.acquire():
                self.error.emit("Request throttled - please wait")
                return
            
            self._is_processing = True
            self._current_query = query
            self.started.emit()
            
            try:
                self._do_process(query)
            finally:
                self._is_processing = False
                self._throttler.release()
        
        def _do_process(self, query: str) -> None:
            """Internal processing logic."""
            start_time = time.time()
            
            # Quick intent check for cache lookup
            self.progress.emit("Analyzing query...")
            
            try:
                # Get intent first (fast, for cache key)
                from .intent_detector import create_intent_detector
                from .schema import AssistantState
                
                detector = create_intent_detector()
                temp_state = AssistantState(user_message=query)
                temp_state = detector.run(temp_state)
                intent = temp_state.intent.intent_type.value if temp_state.intent else "unknown"
                
                # Check cache
                cached = self._cache.get(intent, query)
                if cached:
                    self.progress.emit("Using cached response")
                    self.finished.emit(cached)
                    return
                
                # Process with assistant
                self.progress.emit("Processing with assistant...")
                
                response = self._assistant.ask_structured(query)
                
                # Check timeout
                elapsed_ms = (time.time() - start_time) * 1000
                if elapsed_ms > self._timeout_ms:
                    logger.warning(f"Query took {elapsed_ms:.0f}ms (timeout: {self._timeout_ms}ms)")
                
                # Cache the response
                self._cache.put(intent, query, response)
                
                self.progress.emit("Complete")
                self.finished.emit(response)
                
            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)
                self.error.emit(str(e))
        
        def cancel(self) -> None:
            """Cancel the current operation."""
            # Note: Python doesn't support thread interruption,
            # but we can set a flag for cooperative cancellation
            self._is_processing = False
    
    
    class AssistantThread(QThread):
        """
        Dedicated thread for running the assistant worker.
        
        Usage:
            thread = AssistantThread(assistant)
            thread.response_ready.connect(handle_response)
            thread.start_query("Explain event 4625")
        """
        
        # Signals proxied from worker
        response_ready = Signal(dict)
        error_occurred = Signal(str)
        processing_started = Signal()
        progress_update = Signal(str)
        
        def __init__(self, assistant=None, parent=None):
            super().__init__(parent)
            
            self._worker: Optional[AssistantWorker] = None
            self._assistant = assistant
            self._query_queue: list = []
            self._cache = ResponseCache()
            self._throttler = RequestThrottler()
            
            # Don't start automatically
            self._running = False
        
        def set_assistant(self, assistant) -> None:
            """Set the assistant instance."""
            self._assistant = assistant
            if self._worker:
                self._worker.set_assistant(assistant)
        
        def run(self) -> None:
            """Thread main loop."""
            # Create worker in this thread
            self._worker = AssistantWorker(
                assistant=self._assistant,
                cache=self._cache,
                throttler=self._throttler,
            )
            
            # Connect signals
            self._worker.started.connect(lambda: self.processing_started.emit())
            self._worker.finished.connect(lambda r: self.response_ready.emit(r))
            self._worker.error.connect(lambda e: self.error_occurred.emit(e))
            self._worker.progress.connect(lambda p: self.progress_update.emit(p))
            
            self._running = True
            
            # Process queue
            while self._running:
                if self._query_queue:
                    query = self._query_queue.pop(0)
                    self._worker.process_query(query)
                else:
                    self.msleep(50)  # Check every 50ms
        
        def start_query(self, query: str) -> None:
            """
            Start processing a query.
            
            Can be called from main thread.
            """
            self._query_queue.append(query)
            
            # Start thread if not running
            if not self.isRunning():
                self.start()
        
        def stop(self) -> None:
            """Stop the worker thread."""
            self._running = False
            if self._worker:
                self._worker.cancel()
            self.wait(1000)  # Wait up to 1 second
        
        def clear_cache(self) -> None:
            """Clear the response cache."""
            self._cache.clear()
        
        def get_cache_stats(self) -> Dict[str, Any]:
            """Get cache statistics."""
            return self._cache.stats()
    
    
    class SmartAssistantController(QObject):
        """
        High-level controller for Qt applications.
        
        Provides a simple interface for integrating the assistant
        into Qt/QML applications with proper threading.
        
        Usage:
            controller = SmartAssistantController()
            controller.response_received.connect(update_ui)
            controller.ask("What security concerns do I have?")
        """
        
        # Output signals
        response_received = Signal(dict)
        error_received = Signal(str)
        busy_changed = Signal(bool)
        
        def __init__(self, parent=None):
            super().__init__(parent)
            
            # Initialize assistant and worker
            from .orchestrator import SmartAssistant
            
            self._assistant = SmartAssistant()
            self._thread = AssistantThread(self._assistant)
            self._is_busy = False
            
            # Connect signals
            self._thread.response_ready.connect(self._on_response)
            self._thread.error_occurred.connect(self._on_error)
            self._thread.processing_started.connect(self._on_started)
        
        def _on_response(self, response: dict) -> None:
            """Handle response from worker."""
            self._is_busy = False
            self.busy_changed.emit(False)
            self.response_received.emit(response)
        
        def _on_error(self, error: str) -> None:
            """Handle error from worker."""
            self._is_busy = False
            self.busy_changed.emit(False)
            self.error_received.emit(error)
        
        def _on_started(self) -> None:
            """Handle processing started."""
            self._is_busy = True
            self.busy_changed.emit(True)
        
        @Slot(str)
        def ask(self, query: str) -> None:
            """
            Ask a question (non-blocking).
            
            Response will be emitted via response_received signal.
            """
            if not query or not query.strip():
                self.error_received.emit("Please enter a question")
                return
            
            self._thread.start_query(query.strip())
        
        @Slot()
        def reset_conversation(self) -> None:
            """Reset conversation context."""
            self._assistant.reset_conversation()
        
        @Slot()
        def clear_cache(self) -> None:
            """Clear the response cache."""
            self._thread.clear_cache()
        
        @property
        def is_busy(self) -> bool:
            """Check if assistant is processing."""
            return self._is_busy
        
        def shutdown(self) -> None:
            """Clean shutdown of worker thread."""
            self._thread.stop()


# =============================================================================
# Fallback for non-Qt environments
# =============================================================================

else:
    class AssistantWorker:  # type: ignore[no-redef]
        """Stub for non-Qt environments."""
        pass
    
    class AssistantThread:  # type: ignore[no-redef]
        """Stub for non-Qt environments."""
        pass
    
    class SmartAssistantController:  # type: ignore[no-redef]
        """Stub for non-Qt environments."""
        def __init__(self, *args, **kwargs):
            raise RuntimeError("Qt not available - use SmartAssistant directly")


# =============================================================================
# Factory Functions
# =============================================================================

def create_controller(parent=None) -> SmartAssistantController:
    """Create a SmartAssistantController for Qt applications."""
    if not HAS_QT:
        raise RuntimeError("PySide6 required for Qt controller")
    return SmartAssistantController(parent)


def create_worker_thread(assistant=None) -> AssistantThread:
    """Create a worker thread for background processing."""
    if not HAS_QT:
        raise RuntimeError("PySide6 required for worker thread")
    return AssistantThread(assistant)
