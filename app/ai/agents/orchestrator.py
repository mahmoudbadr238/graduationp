"""
Smart Security Assistant Orchestrator
======================================
Main entry point for the agent-based Smart Security Assistant.

This orchestrator provides a simple interface to the agent pipeline:
1. Receives user queries
2. Runs the agent graph
3. Returns structured responses

Production Features:
- Response caching with TTL (5 minutes default)
- Request throttling (prevent CPU overload)
- Timeout protection (10 second max)
- Thread-safe conversation state
- Qt signal integration

Usage:
    from app.ai.agents.orchestrator import SmartAssistant
    
    assistant = SmartAssistant()
    response = assistant.ask("Explain event 4625")
    print(response["answer"])
"""

import hashlib
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Callable, Tuple
from pathlib import Path

from .schema import (
    AssistantState,
    AssistantResponse,
    ConversationState,
    TechnicalDetails,
    IntentType,
    ToolName,
)
from .graph import create_simple_runner, SimpleGraphRunner
from .tools import ToolRegistry

logger = logging.getLogger(__name__)


# =============================================================================
# Response Cache
# =============================================================================

@dataclass
class CacheEntry:
    """A cached response entry."""
    response: Dict[str, Any]
    timestamp: float
    state_hash: str
    hit_count: int = 0


class ResponseCache:
    """
    Thread-safe LRU response cache with TTL.
    
    Caches responses based on intent type, query hash, and system state.
    This prevents redundant processing for repeated or similar queries.
    """
    
    DEFAULT_TTL = 300  # 5 minutes
    MAX_ENTRIES = 100
    
    def __init__(self, ttl: int = DEFAULT_TTL, max_entries: int = MAX_ENTRIES):
        self.ttl = ttl
        self.max_entries = max_entries
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
    
    def _make_key(self, intent: IntentType, query: str, state_hash: str = "") -> str:
        """Create cache key from intent, query, and state."""
        normalized = query.lower().strip()
        data = f"{intent.value}:{normalized}:{state_hash}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def get(self, intent: IntentType, query: str, state_hash: str = "") -> Optional[Dict]:
        """Get cached response if valid."""
        key = self._make_key(intent, query, state_hash)
        
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            
            # Check TTL
            age = time.time() - entry.timestamp
            if age > self.ttl:
                del self._cache[key]
                self._misses += 1
                return None
            
            # LRU: move to end
            self._cache.move_to_end(key)
            entry.hit_count += 1
            self._hits += 1
            logger.debug(f"Cache hit (age={age:.0f}s)")
            return entry.response
    
    def set(self, intent: IntentType, query: str, response: Dict, state_hash: str = "") -> None:
        """Store response in cache."""
        key = self._make_key(intent, query, state_hash)
        
        with self._lock:
            # Evict oldest if at capacity
            while len(self._cache) >= self.max_entries:
                self._cache.popitem(last=False)
            
            self._cache[key] = CacheEntry(
                response=response.copy(),
                timestamp=time.time(),
                state_hash=state_hash,
            )
    
    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            rate = (self._hits / total * 100) if total > 0 else 0
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{rate:.1f}%",
                "entries": len(self._cache),
            }


# =============================================================================
# Request Throttler
# =============================================================================

class RequestThrottler:
    """
    Request rate limiter to prevent CPU overload.
    
    Limits:
    - Max requests per second (default: 2)
    - Max concurrent requests (default: 2)
    - Minimum interval between same queries (default: 1s)
    """
    
    def __init__(
        self,
        max_rps: float = 2.0,
        max_concurrent: int = 2,
        same_query_interval: float = 1.0,
    ):
        self.max_rps = max_rps
        self.max_concurrent = max_concurrent
        self.same_query_interval = same_query_interval
        
        self._last_request = 0.0
        self._concurrent = 0
        self._query_times: Dict[str, float] = {}
        self._lock = threading.Lock()
    
    def acquire(self, query: str) -> Tuple[bool, str]:
        """Try to acquire permission to process a request."""
        with self._lock:
            now = time.time()
            
            # Concurrent limit
            if self._concurrent >= self.max_concurrent:
                return False, "Too many concurrent requests"
            
            # Rate limit
            min_interval = 1.0 / self.max_rps
            if now - self._last_request < min_interval:
                return False, "Rate limited"
            
            # Same-query limit
            key = query.lower().strip()[:100]
            if now - self._query_times.get(key, 0) < self.same_query_interval:
                return False, "Same query too soon"
            
            # Acquire
            self._concurrent += 1
            self._last_request = now
            self._query_times[key] = now
            
            # Cleanup old entries
            cutoff = now - 60
            self._query_times = {k: v for k, v in self._query_times.items() if v > cutoff}
            
            return True, "OK"
    
    def release(self) -> None:
        """Release a request slot."""
        with self._lock:
            self._concurrent = max(0, self._concurrent - 1)


# =============================================================================
# Smart Security Assistant
# =============================================================================

class SmartAssistant:
    """
    The main interface to the Smart Security Assistant.
    
    This class provides a simple API for:
    - Processing user queries
    - Managing conversation state
    - Returning structured responses
    
    Production features:
    - Response caching (5 min TTL)
    - Request throttling
    - Timeout protection (10s max)
    - Thread-safe operations
    
    Example:
        assistant = SmartAssistant()
        
        # Simple query
        response = assistant.ask("Are there any security concerns?")
        print(response["answer"])
        
        # Follow-up query (uses conversation context)
        response = assistant.ask("Tell me more about that")
        
        # Get full structured response
        full_response = assistant.ask_structured("Explain event 4625")
        print(full_response["why_it_happened"])
        print(full_response["what_to_do_now"])
    """
    
    DEFAULT_TIMEOUT = 10.0  # seconds
    
    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        kb_path: Optional[Path] = None,
        tool_callbacks: Optional[Dict[str, Callable]] = None,
        cache_ttl: int = 300,
        enable_cache: bool = True,
        enable_throttle: bool = True,
    ):
        """
        Initialize the Smart Assistant.
        
        Args:
            tool_registry: Optional custom tool registry
            kb_path: Optional path to knowledge base JSON
            tool_callbacks: Dict of callbacks for live system data
            cache_ttl: Cache TTL in seconds (default 5 min)
            enable_cache: Enable response caching
            enable_throttle: Enable request throttling
        """
        self.tool_registry = tool_registry or ToolRegistry()
        
        # Register tool callbacks if provided
        if tool_callbacks:
            self._register_callbacks(tool_callbacks)
        
        self.runner = create_simple_runner(self.tool_registry)
        self.conversation_state = ConversationState()
        self._lock = threading.Lock()
        self._selected_event = None  # For backward compatibility
        
        # Caching and throttling
        self.cache = ResponseCache(ttl=cache_ttl) if enable_cache else None
        self.throttler = RequestThrottler() if enable_throttle else None
        
        logger.info("SmartAssistant initialized (cache=%s, throttle=%s)",
                    enable_cache, enable_throttle)
    
    def _register_callbacks(self, callbacks: Dict[str, Callable]) -> None:
        """Register tool callbacks for live system data."""
        callback_map = {
            "get_defender_status": ToolName.GET_DEFENDER_STATUS,
            "get_firewall_status": ToolName.GET_FIREWALL_STATUS,
            "get_update_status": ToolName.GET_UPDATE_STATUS,
            "get_recent_events": ToolName.GET_RECENT_EVENTS,
            "get_event_details": ToolName.GET_EVENT_DETAILS,
            "scan_file": ToolName.SCAN_FILE,
            "analyze_url_offline": ToolName.ANALYZE_URL_OFFLINE,
            "analyze_url_online": ToolName.ANALYZE_URL_ONLINE,
        }
        for name, tool_name in callback_map.items():
            if name in callbacks:
                self.tool_registry.register_callback(tool_name, callbacks[name])
    
    def ask(self, query: str, timeout: float = DEFAULT_TIMEOUT) -> str:
        """
        Ask a simple question and get a text answer.
        
        Args:
            query: The user's question
            timeout: Maximum processing time in seconds
        
        Returns:
            The assistant's answer as a string
        """
        response = self.ask_structured(query, timeout=timeout)
        return response.get("answer", "I couldn't process your request.")
    
    def ask_structured(
        self,
        query: str,
        timeout: float = DEFAULT_TIMEOUT,
        skip_cache: bool = False,
    ) -> Dict[str, Any]:
        """
        Ask a question and get a fully structured response.
        
        Args:
            query: The user's question
            timeout: Maximum processing time in seconds
            skip_cache: Force fresh response (bypass cache)
        
        Returns:
            A dictionary with the complete response schema
        """
        logger.info(f"[TRACE] ask_structured START query='{query[:50]}...'")
        
        if not query or not query.strip():
            logger.info("[TRACE] ask_structured END (empty query)")
            return self._error_response("Empty query")
        
        query = query.strip()
        
        # Throttle check
        if self.throttler:
            allowed, reason = self.throttler.acquire(query)
            if not allowed:
                logger.warning(f"Throttled: {reason}")
                logger.info("[TRACE] ask_structured END (throttled)")
                return self._error_response(f"Please wait: {reason}")
        
        try:
            result = self._process_with_timeout(query, timeout, skip_cache)
            logger.info(f"[TRACE] ask_structured END (success)")
            return result
        finally:
            if self.throttler:
                self.throttler.release()
                logger.info("[TRACE] throttler released")
    
    def _process_with_timeout(
        self,
        query: str,
        timeout: float,
        skip_cache: bool,
    ) -> Dict[str, Any]:
        """Process query with timeout protection."""
        result: list[Any] = [None]
        error: list[Any] = [None]
        
        def run():
            try:
                result[0] = self._process_internal(query, skip_cache)
            except Exception as e:
                error[0] = str(e)
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join(timeout=timeout)
        
        if thread.is_alive():
            logger.error(f"Query timed out after {timeout}s")
            return self._error_response("Request timed out. Try a simpler question.")
        
        if error[0]:
            logger.error(f"Query error: {error[0]}")
            return self._error_response(error[0])
        
        return result[0] or self._error_response("No response generated")
    
    def _process_internal(self, query: str, skip_cache: bool) -> Dict[str, Any]:
        """Internal processing with caching."""
        
        # Run intent detection for cache key
        with self._lock:
            state = AssistantState(
                user_message=query,
                conversation=self.conversation_state,
            )
        
        state = self.runner.intent_detector.run(state)
        
        # Get intent type (state.intent is UserIntent, need .intent_type)
        intent_type = state.intent.intent_type if state.intent else IntentType.UNKNOWN
        
        # Cache lookup
        if self.cache and not skip_cache and intent_type not in (
            IntentType.GREETING, IntentType.UNKNOWN
        ):
            state_hash = self._get_state_hash(intent_type)
            cached = self.cache.get(intent_type, query, state_hash)
            if cached:
                logger.debug("Using cached response")
                return cached
        
        # Run full pipeline
        state = self.runner.planner.run(state)
        state = self.runner.data_fetcher.run(state)
        state = self.runner.rules_engine.run(state)
        state = self.runner.security_reasoner.run(state)
        state = self.runner.response_critic.run(state)
        
        # Get response
        if state.response is None:
            return self._error_response("Failed to generate response")
        
        response_dict = state.response.to_dict()
        
        # Update conversation state
        with self._lock:
            if state.conversation:
                self.conversation_state = state.conversation
        
        # Cache response
        if self.cache and intent_type not in (
            IntentType.GREETING, IntentType.UNKNOWN, IntentType.FOLLOWUP
        ):
            state_hash = self._get_state_hash(intent_type)
            self.cache.set(intent_type, query, response_dict, state_hash)
        
        return response_dict
    
    def _get_state_hash(self, intent: IntentType) -> str:
        """Get state hash for status queries."""
        if intent in (
            IntentType.FIREWALL_STATUS,
            IntentType.DEFENDER_STATUS,
            IntentType.UPDATE_STATUS,
            IntentType.SECURITY_CHECK,
        ):
            # 5-minute buckets for status queries
            bucket = int(time.time() // 300)
            return f"status-{bucket}"
        return ""
    
    def _error_response(self, error: str) -> Dict[str, Any]:
        """Create error response dict."""
        return {
            "answer": f"I couldn't complete your request. {error}",
            "why_it_happened": ["An error occurred during processing."],
            "what_it_affects": ["Unable to provide complete analysis."],
            "what_to_do_now": ["Please try rephrasing your question."],
            "technical_details": {
                "source": "error",
                "confidence": "low",
                "evidence": [],
            },
            "follow_up_suggestions": ["What would you like to know about?"],
        }
    
    def reset_conversation(self):
        """Reset the conversation state (start fresh)."""
        with self._lock:
            self.conversation_state = ConversationState()
        logger.info("Conversation state reset")
    
    # Alias for backward compatibility
    def clear_conversation(self):
        """Alias for reset_conversation() for backward compatibility."""
        self.reset_conversation()
    
    def clear_cache(self):
        """Clear the response cache."""
        if self.cache:
            self.cache.clear()
            logger.info("Response cache cleared")
    
    @property
    def cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if self.cache:
            return self.cache.stats
        return {"enabled": False}
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics (alias for cache_stats property)."""
        return self.cache_stats
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        stats: Dict[str, Any] = {
            "throttle_enabled": self.throttler is not None,
            "cache_enabled": self.cache is not None,
        }
        if self.cache:
            stats["cache"] = self.cache.stats
        return stats
    
    def set_selected_event(self, event: Dict) -> None:
        """Set selected event for context (stored in conversation state)."""
        with self._lock:
            # Store in conversation state for context
            self._selected_event = event
        logger.debug(f"Selected event set: {event.get('event_id', 'unknown')}")
    
    def clear_selected_event(self) -> None:
        """Clear selected event context."""
        with self._lock:
            self._selected_event = None
        logger.debug("Selected event cleared")
    
    def get_conversation_context(self) -> Dict[str, Any]:
        """Get the current conversation context."""
        return {
            "turn_count": len(self.conversation_state.turns),
            "last_explained_event": self.conversation_state.last_explained_event.event_id if self.conversation_state.last_explained_event else None,
            "last_intent": self.conversation_state.last_intent.value if self.conversation_state.last_intent else None,
            "summary_shown": self.conversation_state.summary_shown,
        }
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get a summary of the conversation (alias for get_conversation_context)."""
        return self.get_conversation_context()
    
    def get_follow_up_suggestions(self) -> List[str]:
        """Get suggested follow-up questions."""
        # These would come from the last response
        return [
            "Check my security status",
            "Show recent events",
            "Explain a specific event",
        ]


# =============================================================================
# Async Version
# =============================================================================

class AsyncSmartAssistant:
    """
    Async version of the Smart Assistant for use with async frameworks.
    
    Note: The current implementation is synchronous internally,
    but this wrapper allows integration with async code.
    """
    
    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self._sync_assistant = SmartAssistant(tool_registry)
    
    async def ask(self, query: str) -> str:
        """Async wrapper for ask()."""
        # TODO: Make truly async with async tool calls
        return self._sync_assistant.ask(query)
    
    async def ask_structured(self, query: str) -> Dict[str, Any]:
        """Async wrapper for ask_structured()."""
        return self._sync_assistant.ask_structured(query)
    
    def reset_conversation(self):
        """Reset conversation state."""
        self._sync_assistant.reset_conversation()


# =============================================================================
# Qt Integration
# =============================================================================

class QtSmartAssistant(SmartAssistant):
    """
    Smart Assistant with Qt signal integration.
    
    This version is designed for use with PySide6/PyQt applications.
    It can emit signals for async processing in the Qt event loop.
    """
    
    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        parent: Optional[Any] = None,
    ):
        super().__init__(tool_registry)
        self.parent = parent
        
        # Try to set up Qt signals if available
        try:
            from PySide6.QtCore import QObject, Signal
            
            class SignalEmitter(QObject):
                response_ready = Signal(dict)
                error_occurred = Signal(str)
            
            self.signals = SignalEmitter(parent)
        except ImportError:
            self.signals = None
            logger.warning("PySide6 not available - Qt signals disabled")
    
    def ask_async(self, query: str):
        """
        Process query and emit signal when done.
        
        This is meant to be called from a worker thread.
        """
        try:
            response = self.ask_structured(query)
            if self.signals:
                self.signals.response_ready.emit(response)
        except Exception as e:
            logger.error(f"Async ask error: {e}")
            if self.signals:
                self.signals.error_occurred.emit(str(e))


# =============================================================================
# Factory Functions
# =============================================================================

def create_assistant(
    tool_registry: Optional[ToolRegistry] = None,
) -> SmartAssistant:
    """Create a SmartAssistant instance."""
    return SmartAssistant(tool_registry)


def create_qt_assistant(
    tool_registry: Optional[ToolRegistry] = None,
    parent: Optional[Any] = None,
) -> QtSmartAssistant:
    """Create a Qt-integrated SmartAssistant instance."""
    return QtSmartAssistant(tool_registry, parent)


# =============================================================================
# Convenience Function
# =============================================================================

# Global assistant instance for simple usage
_global_assistant: Optional[SmartAssistant] = None


def get_assistant() -> SmartAssistant:
    """Get or create the global assistant instance."""
    global _global_assistant
    if _global_assistant is None:
        _global_assistant = SmartAssistant()
    return _global_assistant


def ask(query: str) -> str:
    """
    Simple convenience function to ask a question.
    
    Usage:
        from app.ai.agents.orchestrator import ask
        answer = ask("Are there any security concerns?")
    """
    return get_assistant().ask(query)


def ask_structured(query: str) -> Dict[str, Any]:
    """
    Convenience function to ask and get structured response.
    
    Usage:
        from app.ai.agents.orchestrator import ask_structured
        response = ask_structured("Explain event 4625")
        print(response["what_to_do_now"])
    """
    return get_assistant().ask_structured(query)
