"""AI modules for Sentinel - Cloud-powered architecture.

Architecture (2025):
    - Groq Cloud AI as primary provider (free tier, fast)
    - Offline EventRulesEngine for instant KB lookups
    - Persistent SQLite caching for explanations
    
V5 (Current - Online with KB fallback):
    - EventExplainerV5: Groq-powered with offline KB fallback
    - SecurityChatbotV4: Groq-powered with conversation memory
    - Providers: Groq (primary)

NOTE: All AI modules are lazy-loaded for faster startup.
"""

# V5 components (current - Groq-powered)
_event_explainer_v5 = None
_security_chatbot_v4 = None


# =============================================================================
# V5 (CURRENT - GROQ-POWERED)
# =============================================================================

def get_event_explainer_v5(db_repo=None):
    """Get EventExplainerV5 singleton instance (Groq-powered)."""
    global _event_explainer_v5
    if _event_explainer_v5 is None:
        from .event_explainer_v5 import get_event_explainer_v5 as _get_v5
        _event_explainer_v5 = _get_v5(db_repo)
    return _event_explainer_v5


def get_security_chatbot_v4():
    """Get SecurityChatbotV4 singleton instance (Groq-powered with memory)."""
    global _security_chatbot_v4
    if _security_chatbot_v4 is None:
        from .security_chatbot_v4 import get_security_chatbot_v4 as _get_v4
        _security_chatbot_v4 = _get_v4()
    return _security_chatbot_v4


# For backwards compatibility
def __getattr__(name):
    """Lazy attribute access for backwards compatibility."""
    if name == "EventExplainerV5":
        from .event_explainer_v5 import EventExplainerV5
        return EventExplainerV5
    if name == "SecurityChatbotV4":
        from .security_chatbot_v4 import SecurityChatbotV4
        return SecurityChatbotV4
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # V5 (current - Groq-powered with KB fallback)
    "get_event_explainer_v5",
    "get_security_chatbot_v4",
]
