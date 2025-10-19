"""Minimal dependency injection container."""
from typing import Callable, Dict, Type, Any


class Container:
    """Simple DI container for managing dependencies."""
    
    def __init__(self):
        self._registry: Dict[Any, Callable] = {}
    
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
    from ..infra.system_monitor_psutil import PsutilSystemMonitor
    from ..infra.events_windows import WindowsEventReader
    from ..infra.nmap_cli import NmapCli
    from ..infra.vt_client import VirusTotalClient
    from ..infra.file_scanner import LocalFileScanner
    from ..infra.url_scanner import UrlScanner
    from ..infra.sqlite_repo import SqliteRepo
    from .interfaces import (
        ISystemMonitor, IEventReader, IScanRepository,
        IEventRepository, INetworkScanner, IFileScanner, IUrlScanner
    )
    from .errors import IntegrationDisabled
    
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
        print(f"⚠ VirusTotal integration disabled: {error_msg}")
        # Register dummy factories that raise IntegrationDisabled when resolved
        def _raise_disabled():
            raise IntegrationDisabled(error_msg)
        DI.register(IFileScanner, _raise_disabled)
        DI.register(IUrlScanner, _raise_disabled)
    
    DI.register(INetworkScanner, lambda: NmapCli())
