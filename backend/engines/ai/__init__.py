"""AI modules for Sentinel - Cloud-powered architecture.

Architecture (2025):
    - Groq Cloud AI as primary provider (free tier, fast)
    - Offline EventRulesEngine for instant KB lookups
    - Persistent SQLite caching for explanations

V5 (Current - Online with KB fallback):
    - EventExplainerV5: Groq-powered with offline KB fallback
    - ChatbotBridge: QThread-based Groq chatbot with conversation memory
    - Providers: Groq (primary)

NOTE: All AI modules are lazy-loaded for faster startup.
"""

# V5 components (current - Groq-powered)
_event_explainer_v5 = None
_chatbot_bridge = None


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


def get_chatbot_bridge():
    """Get ChatbotBridge singleton instance (Groq API via QThread)."""
    global _chatbot_bridge
    if _chatbot_bridge is None:
        from .security_chatbot_v4 import get_chatbot_bridge as _get_bridge

        _chatbot_bridge = _get_bridge()
    return _chatbot_bridge


# For backwards compatibility
def __getattr__(name):
    """Lazy attribute access for backwards compatibility."""
    if name == "EventExplainerV5":
        from .event_explainer_v5 import EventExplainerV5

        return EventExplainerV5
    if name == "ChatbotBridge":
        from .security_chatbot_v4 import ChatbotBridge

        return ChatbotBridge
    if name == "GroqChatWorker":
        from .security_chatbot_v4 import GroqChatWorker

        return GroqChatWorker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # V5 (current - Groq-powered with KB fallback)
    "get_event_explainer_v5",
    "get_chatbot_bridge",
]
