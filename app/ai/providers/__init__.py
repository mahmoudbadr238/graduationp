"""
AI Providers Module - Simplified Groq-only Architecture
========================================================

Sentinel uses Groq Cloud AI as the sole provider for:
- Event explanations (llama-3.3-70b-versatile)
- Chatbot responses (llama-3.1-8b-instant)

DESIGN PRINCIPLES:
1. Groq handles all AI requests (fast, free tier)
2. EventRulesEngine provides offline KB lookups (source of truth)
3. Sensitive data redacted before API calls
4. Persistent SQLite caching for repeated queries
"""

from .base import (
    AIMode,
    AIProvider,
    AIResponse,
    ProviderConfig,
)
from .groq import GroqProvider, get_groq_provider, is_groq_available
from .privacy import RedactionEngine, redact_sensitive

__all__ = [
    # Modes
    "AIMode",
    # Base
    "AIProvider",
    "AIResponse",
    "ProviderConfig",
    # Groq Provider (primary)
    "GroqProvider",
    "get_groq_provider",
    "is_groq_available",
    # Privacy
    "RedactionEngine",
    "redact_sensitive",
]
