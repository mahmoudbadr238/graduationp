"""
AI Providers Module
===================

Hybrid AI provider system supporting:
- Offline-only mode (rules + KB)
- Hybrid mode (offline facts + online explanation)
- Online-only mode (with safety guardrails)

CRITICAL DESIGN PRINCIPLES:
1. Offline logic runs FIRST and is source of truth
2. Online LLM enhances but never overrides facts
3. No raw logs sent to online APIs
4. Sensitive data redacted by default
5. Caching to avoid repeated calls
6. Circuit breaker for failing providers
"""

from .base import (
    AIMode,
    AIProvider,
    AIResponse,
    ProviderConfig,
)

from .local import LocalProvider, get_local_provider
from .online import OnlineProvider, ClaudeProvider, OpenAIProvider
from .router import AIRouter, get_ai_router
from .privacy import RedactionEngine, redact_sensitive

__all__ = [
    # Modes
    "AIMode",
    # Base
    "AIProvider",
    "AIResponse", 
    "ProviderConfig",
    # Providers
    "LocalProvider",
    "get_local_provider",
    "OnlineProvider",
    "ClaudeProvider",
    "OpenAIProvider",
    # Router
    "AIRouter",
    "get_ai_router",
    # Privacy
    "RedactionEngine",
    "redact_sensitive",
]
