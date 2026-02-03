"""Local AI modules for Sentinel - 100% offline, no external API calls.

NOTE: All AI modules are lazy-loaded for faster startup.
The ONNX model is loaded on first use, not at import time.

V4 Architecture (2025):
    - EventExplainerV4: Advanced prompts with structured output
    - Agent-based SmartAssistant in app/ai/agents/ with orchestrator

V3 Architecture (2025):
    - EventExplainerV3: Strict JSON I/O with self-check validation
    - SecurityChatbotV3: Grounded responses with evidence citations
    - AIDebugger: Debug logging for AI calls (%APPDATA%/Sentinel/ai_debug/)

V1 (Legacy fallback):
    - EventExplainer: Original event explanation
    - SecurityChatbot: Original chatbot

NOTE: V2 modules have been archived (unused) - see archive_unused/
"""

# Lazy loading for AI modules (heavy dependencies)
_local_llm_engine = None
_event_explainer = None
_security_chatbot = None

# V3 components
_event_explainer_v3 = None
_security_chatbot_v3 = None
_ai_debugger = None

# Context builders (still used)
_summary_builder = None
_context_builder = None
_cache_manager = None


def get_local_llm_engine():
    """Lazy-load LocalLLMEngine class."""
    global _local_llm_engine
    if _local_llm_engine is None:
        from .local_llm_engine import LocalLLMEngine
        _local_llm_engine = LocalLLMEngine
    return _local_llm_engine


def get_event_explainer():
    """Lazy-load EventExplainer class (V1 for backwards compatibility)."""
    global _event_explainer
    if _event_explainer is None:
        from .event_explainer import EventExplainer
        _event_explainer = EventExplainer
    return _event_explainer


def get_security_chatbot():
    """Lazy-load SecurityChatbot class (V1 for backwards compatibility)."""
    global _security_chatbot
    if _security_chatbot is None:
        from .security_chatbot import SecurityChatbot
        _security_chatbot = SecurityChatbot
    return _security_chatbot


def get_summary_builder():
    """Get SimpleSummaryBuilder singleton instance."""
    global _summary_builder
    if _summary_builder is None:
        from .event_summary_builder import get_summary_builder as _get_builder
        _summary_builder = _get_builder
    return _summary_builder


def get_context_builder():
    """Get ChatContextBuilder singleton instance."""
    global _context_builder
    if _context_builder is None:
        from .chat_context_builder import get_context_builder as _get_builder
        _context_builder = _get_builder
    return _context_builder


def get_cache_manager():
    """Get CacheManager singleton instance."""
    global _cache_manager
    if _cache_manager is None:
        from .cache import get_cache_manager as _get_manager
        _cache_manager = _get_manager
    return _cache_manager


# For backwards compatibility
def __getattr__(name):
    """Lazy attribute access for backwards compatibility."""
    if name == "LocalLLMEngine":
        return get_local_llm_engine()
    elif name == "EventExplainer":
        return get_event_explainer()
    elif name == "SecurityChatbot":
        return get_security_chatbot()
    elif name == "EventExplainerV3":
        from .event_explainer_v3 import EventExplainerV3
        return EventExplainerV3
    elif name == "SecurityChatbotV3":
        from .security_chatbot_v3 import SecurityChatbotV3
        return SecurityChatbotV3
    elif name == "SimpleSummaryBuilder":
        from .event_summary_builder import SimpleSummaryBuilder
        return SimpleSummaryBuilder
    elif name == "ChatContextBuilder":
        from .chat_context_builder import ChatContextBuilder
        return ChatContextBuilder
    elif name == "AIResponseCache":
        from .cache import AIResponseCache
        return AIResponseCache
    elif name == "AIDebugger":
        from .debug import AIDebugger
        return AIDebugger
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# V3 Component Getters
def get_event_explainer_v3():
    """Get EventExplainerV3 singleton instance."""
    global _event_explainer_v3
    if _event_explainer_v3 is None:
        from .event_explainer_v3 import get_event_explainer_v3 as _get_v3
        _event_explainer_v3 = _get_v3
    return _event_explainer_v3


def get_security_chatbot_v3():
    """Get SecurityChatbotV3 singleton instance."""
    global _security_chatbot_v3
    if _security_chatbot_v3 is None:
        from .security_chatbot_v3 import get_security_chatbot_v3 as _get_v3
        _security_chatbot_v3 = _get_v3
    return _security_chatbot_v3


def get_ai_debugger():
    """Get AIDebugger singleton instance."""
    global _ai_debugger
    if _ai_debugger is None:
        from .debug import get_ai_debugger as _get_debugger
        _ai_debugger = _get_debugger
    return _ai_debugger


__all__ = [
    # V1 (backwards compatibility/fallback)
    "LocalLLMEngine",
    "EventExplainer", 
    "SecurityChatbot",
    "get_local_llm_engine",
    "get_event_explainer",
    "get_security_chatbot",
    # Utilities (still used)
    "SimpleSummaryBuilder",
    "ChatContextBuilder",
    "AIResponseCache",
    "get_summary_builder",
    "get_context_builder",
    "get_cache_manager",
    # V3 (strict JSON, grounded, debug)
    "EventExplainerV3",
    "SecurityChatbotV3",
    "AIDebugger",
    "get_event_explainer_v3",
    "get_security_chatbot_v3",
    "get_ai_debugger",
]
