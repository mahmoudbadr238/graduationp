"""
AI Router - Intelligent routing between offline and online providers.

Routes requests based on:
- AI mode (offline_only, hybrid, online_only)
- Provider availability
- Request type
- User preferences

CRITICAL FLOW:
1. Local provider ALWAYS runs first (source of truth)
2. Online provider enhances if available and mode allows
3. Results are merged (local facts + online explanation)
4. Caching prevents repeated calls
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from typing import Any, Optional

from .base import AIMode, AIProvider, AIResponse, ProviderConfig
from .local import LocalProvider, get_local_provider
from .online import ClaudeProvider, OpenAIProvider

logger = logging.getLogger(__name__)


@dataclass
class CachedResponse:
    """A cached AI response."""
    response: AIResponse
    timestamp: float
    ttl_seconds: float = 300  # 5 minutes default
    
    @property
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl_seconds


class AIRouter:
    """
    Routes AI requests to appropriate providers.
    
    Supports three modes:
    - offline_only: Only uses local provider (rules + KB)
    - hybrid: Local first, then online enhancement
    - online_only: Online with local fallback
    
    Features:
    - Response caching
    - Automatic fallback
    - Timeout handling
    - Parallel execution where possible
    """
    
    def __init__(
        self,
        mode: AIMode = AIMode.OFFLINE_ONLY,
        preferred_online: str = "claude",  # "claude" or "openai"
        online_timeout: float = 15.0,
        cache_ttl: float = 300.0,
        cache_size: int = 100,
    ):
        self.mode = mode
        self.preferred_online = preferred_online
        self.online_timeout = online_timeout
        self.cache_ttl = cache_ttl
        self.cache_size = cache_size
        
        # Providers
        self._local = get_local_provider()
        self._claude: Optional[ClaudeProvider] = None
        self._openai: Optional[OpenAIProvider] = None
        
        # Cache
        self._cache: OrderedDict[str, CachedResponse] = OrderedDict()
        self._cache_lock = Lock()
        
        # Stats
        self._stats = {
            "local_calls": 0,
            "online_calls": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "online_timeouts": 0,
            "online_errors": 0,
        }
    
    def set_mode(self, mode: AIMode) -> None:
        """Change the AI mode."""
        self.mode = mode
        logger.info(f"AI mode changed to: {mode.value}")
    
    def _get_online_provider(self) -> Optional[AIProvider]:
        """Get the preferred online provider if available."""
        if self.mode == AIMode.OFFLINE_ONLY:
            return None
        
        if self.preferred_online == "claude":
            if self._claude is None:
                self._claude = ClaudeProvider()
            if self._claude.is_available:
                return self._claude
            # Try OpenAI as fallback
            if self._openai is None:
                self._openai = OpenAIProvider()
            return self._openai if self._openai.is_available else None
        else:
            if self._openai is None:
                self._openai = OpenAIProvider()
            if self._openai.is_available:
                return self._openai
            # Try Claude as fallback
            if self._claude is None:
                self._claude = ClaudeProvider()
            return self._claude if self._claude.is_available else None
    
    def _make_cache_key(self, request_type: str, data: dict) -> str:
        """Create a cache key for the request."""
        # Include mode in key since responses differ
        key_data = f"{self.mode.value}:{request_type}:{str(sorted(data.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_cached(self, key: str) -> Optional[AIResponse]:
        """Get a cached response if available and not expired."""
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry is None:
                self._stats["cache_misses"] += 1
                return None
            
            if entry.is_expired:
                del self._cache[key]
                self._stats["cache_misses"] += 1
                return None
            
            # Move to end (LRU)
            self._cache.move_to_end(key)
            self._stats["cache_hits"] += 1
            
            # Return a copy with cached flag set
            response = entry.response
            response.cached = True
            return response
    
    def _set_cached(self, key: str, response: AIResponse) -> None:
        """Cache a response."""
        with self._cache_lock:
            # Evict oldest if at capacity
            while len(self._cache) >= self.cache_size:
                self._cache.popitem(last=False)
            
            self._cache[key] = CachedResponse(
                response=response,
                timestamp=time.time(),
                ttl_seconds=self.cache_ttl,
            )
    
    async def explain_event(
        self,
        event: dict[str, Any],
        skip_cache: bool = False,
    ) -> AIResponse:
        """
        Explain a security event.
        
        This is the main entry point for event explanations.
        
        Args:
            event: Event data dict
            skip_cache: Force fresh response
        
        Returns:
            AIResponse with explanation
        """
        start = time.monotonic()
        
        # Check cache
        cache_key = self._make_cache_key("explain_event", {
            "event_id": event.get("event_id", event.get("eventId")),
            "provider": event.get("provider", event.get("source")),
            "message_hash": hashlib.md5(
                str(event.get("message", "")).encode()
            ).hexdigest()[:8],
        })
        
        if not skip_cache:
            cached = self._get_cached(cache_key)
            if cached:
                return cached
        
        # Always run local first - it's instant and provides ground truth
        self._stats["local_calls"] += 1
        local_response = await self._local.explain_event(event)
        
        # If offline-only mode, return local response
        if self.mode == AIMode.OFFLINE_ONLY:
            self._set_cached(cache_key, local_response)
            return local_response
        
        # Try online enhancement
        online_provider = self._get_online_provider()
        
        if online_provider:
            try:
                self._stats["online_calls"] += 1
                
                # Run online with timeout
                online_response = await asyncio.wait_for(
                    online_provider.explain_event(
                        event,
                        kb_explanation=local_response.to_dict(),
                    ),
                    timeout=self.online_timeout,
                )
                
                if online_response._is_valid:
                    # Merge responses
                    if self.mode == AIMode.HYBRID:
                        final_response = local_response.merge_with(online_response)
                    else:
                        # Online-only mode - use online response but keep local as fallback
                        final_response = online_response
                    
                    final_response.latency_ms = int((time.monotonic() - start) * 1000)
                    self._set_cached(cache_key, final_response)
                    return final_response
                
            except asyncio.TimeoutError:
                self._stats["online_timeouts"] += 1
                logger.warning(f"Online provider timed out after {self.online_timeout}s")
            
            except Exception as e:
                self._stats["online_errors"] += 1
                logger.error(f"Online provider error: {e}")
        
        # Fall back to local response
        local_response.latency_ms = int((time.monotonic() - start) * 1000)
        self._set_cached(cache_key, local_response)
        return local_response
    
    async def generate(
        self,
        query: str,
        context: dict[str, Any],
        skip_cache: bool = False,
    ) -> AIResponse:
        """
        Generate a response for a general query.
        
        Args:
            query: User's question
            context: System context (defender status, firewall, etc.)
            skip_cache: Force fresh response
        
        Returns:
            AIResponse with answer
        """
        start = time.monotonic()
        
        # Check cache
        cache_key = self._make_cache_key("generate", {
            "query": query.lower().strip(),
        })
        
        if not skip_cache:
            cached = self._get_cached(cache_key)
            if cached:
                return cached
        
        # Local first
        self._stats["local_calls"] += 1
        local_response = await self._local.generate(query, context)
        
        if self.mode == AIMode.OFFLINE_ONLY:
            self._set_cached(cache_key, local_response)
            return local_response
        
        # Try online
        online_provider = self._get_online_provider()
        
        if online_provider:
            try:
                self._stats["online_calls"] += 1
                
                online_response = await asyncio.wait_for(
                    online_provider.generate(query, context),
                    timeout=self.online_timeout,
                )
                
                if online_response._is_valid:
                    if self.mode == AIMode.HYBRID:
                        final_response = local_response.merge_with(online_response)
                    else:
                        final_response = online_response
                    
                    final_response.latency_ms = int((time.monotonic() - start) * 1000)
                    self._set_cached(cache_key, final_response)
                    return final_response
                
            except asyncio.TimeoutError:
                self._stats["online_timeouts"] += 1
                logger.warning("Online generate timed out")
            
            except Exception as e:
                self._stats["online_errors"] += 1
                logger.error(f"Online generate error: {e}")
        
        local_response.latency_ms = int((time.monotonic() - start) * 1000)
        self._set_cached(cache_key, local_response)
        return local_response
    
    def get_stats(self) -> dict:
        """Get router statistics."""
        return {
            **self._stats,
            "mode": self.mode.value,
            "cache_size": len(self._cache),
            "cache_hit_rate": (
                self._stats["cache_hits"] / 
                max(1, self._stats["cache_hits"] + self._stats["cache_misses"])
            ),
        }
    
    def clear_cache(self) -> None:
        """Clear the response cache."""
        with self._cache_lock:
            self._cache.clear()
        logger.info("AI response cache cleared")


# Singleton
_router: Optional[AIRouter] = None

def get_ai_router(
    mode: Optional[AIMode] = None,
    preferred_online: Optional[str] = None,
) -> AIRouter:
    """
    Get the singleton AI router.
    
    Args:
        mode: Override default mode
        preferred_online: Preferred online provider ("claude" or "openai")
    
    Returns:
        The singleton AIRouter instance
    """
    global _router
    
    if _router is None:
        _router = AIRouter(
            mode=mode or AIMode.OFFLINE_ONLY,
            preferred_online=preferred_online or "claude",
        )
    elif mode is not None:
        _router.set_mode(mode)
    
    return _router
