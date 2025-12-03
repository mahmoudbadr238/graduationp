"""Minimal dependency injection container."""

from collections.abc import Callable
from typing import Any


class Container:
    """Simple DI container for managing dependencies."""

    def __init__(self):
        self._registry: dict[Any, Callable] = {}

    def register(self, key: Any, factory: Callable) -> None:
        """Register a factory function for a given key (usually an interface)."""
        self._registry[key] = factory

    def resolve(self, key: Any) -> Any:
        """Resolve a dependency by calling its factory."""
        if key not in self._registry:
            raise KeyError(f"No factory registered for {key}")
        return self._registry[key]()


# Global DI container instance
DI = Container()


def configure() -> None:
    """Configure all dependencies in the DI container."""
    from ..infra.events_windows import WindowsEventReader
    from ..infra.file_scanner import LocalFileScanner
    from ..infra.nmap_cli import NmapCli
    from ..infra.sqlite_repo import SqliteRepo
    from ..infra.system_monitor_psutil import PsutilSystemMonitor
    from ..infra.url_scanner import UrlScanner
    from ..infra.vt_client import VirusTotalClient
    from .errors import IntegrationDisabled
    from .interfaces import (
        IEventReader,
        IEventRepository,
        IFileScanner,
        INetworkScanner,
        IScanRepository,
        ISystemMonitor,
        IUrlScanner,
    )

    # Register implementations
    DI.register(ISystemMonitor, lambda: PsutilSystemMonitor())
    DI.register(IEventReader, lambda: WindowsEventReader())
    DI.register(IScanRepository, lambda: SqliteRepo())
    DI.register(IEventRepository, lambda: SqliteRepo())

    # Shared VirusTotal client (may be unavailable)
    try:
        vt = VirusTotalClient()
        DI.register(IFileScanner, lambda: LocalFileScanner(vt))
        DI.register(IUrlScanner, lambda: UrlScanner(vt))
    except IntegrationDisabled as e:
        error_msg = str(e)
        print(f"[SKIP] VirusTotal integration disabled: {error_msg}")

        # Register dummy factories that raise IntegrationDisabled when resolved
        def _raise_disabled():
            raise IntegrationDisabled(error_msg)

        DI.register(IFileScanner, _raise_disabled)
        DI.register(IUrlScanner, _raise_disabled)

    DI.register(INetworkScanner, lambda: NmapCli())

    # Register AI services (100% local, no network calls)
    try:
        from ..ai.local_llm_engine import LocalLLMEngine, get_llm_engine
        from ..ai.event_explainer import EventExplainer, get_event_explainer
        from ..ai.event_summarizer import EventSummarizer, get_event_summarizer
        from ..ai.security_chatbot import SecurityChatbot, get_security_chatbot

        # Register LLM engine singleton
        DI.register(LocalLLMEngine, get_llm_engine)

        # Register Event Explainer (uses LLM engine)
        DI.register(EventExplainer, lambda: get_event_explainer(get_llm_engine()))
        
        # Register Event Summarizer (uses LLM engine)
        DI.register(EventSummarizer, lambda: get_event_summarizer(get_llm_engine()))

        # Security Chatbot will be initialized with services in application.py
        # since it needs snapshot_service which isn't available at container config time
        DI.register(SecurityChatbot, lambda: None)  # Placeholder

        print("[OK] Local AI services registered (no network calls)")
    except Exception as e:
        print(f"[SKIP] AI services not available: {e}")
