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
    from ..scanning.url_scanner import UrlScanner
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

    # Register scanners (local-only, no external APIs)
    DI.register(IFileScanner, lambda: LocalFileScanner())
    DI.register(IUrlScanner, lambda: UrlScanner())

    DI.register(INetworkScanner, lambda: NmapCli())

    # Register AI services (cloud-based via Groq API)
    try:
        from ..ai.event_explainer_v5 import EventExplainerV5, get_event_explainer_v5
        from ..ai.event_summarizer import EventSummarizer, get_event_summarizer
        from ..ai.security_chatbot_v4 import SecurityChatbotV4

        # Register Event Explainer V5 (uses Groq cloud API)
        DI.register(EventExplainerV5, lambda: get_event_explainer_v5())

        # Register Event Summarizer (fallback for batch summaries)
        DI.register(EventSummarizer, lambda: get_event_summarizer(None))

        # Security Chatbot V4 will be initialized with services in application.py
        # since it needs snapshot_service which isn't available at container config time
        DI.register(SecurityChatbotV4, lambda: None)  # Placeholder

        print("[OK] Cloud AI services registered (Groq API)")
    except Exception as e:
        print(f"[SKIP] AI services not available: {e}")
