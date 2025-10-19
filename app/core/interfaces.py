"""Service and repository interfaces (abstract base classes)."""
from abc import ABC, abstractmethod
from typing import Iterable, Dict, Any, Optional
from .types import EventItem, ScanRecord, ScanType


class ISystemMonitor(ABC):
    """Interface for system monitoring service."""
    
    @abstractmethod
    def snapshot(self) -> Dict[str, Any]:
        """Get current system snapshot (CPU, memory, GPU, network, disk)."""
        pass


class IEventReader(ABC):
    """Interface for reading system events."""
    
    @abstractmethod
    def tail(self, limit: int = 50) -> Iterable[EventItem]:
        """Get recent system events."""
        pass


class INetworkScanner(ABC):
    """Interface for network scanning service."""
    
    @abstractmethod
    def scan(self, target: str, fast: bool = True) -> Dict[str, Any]:
        """Scan network target."""
        pass


class IFileScanner(ABC):
    """Interface for file scanning service."""
    
    @abstractmethod
    def scan_file(self, path: str) -> Dict[str, Any]:
        """Scan a file for threats."""
        pass


class IUrlScanner(ABC):
    """Interface for URL scanning service."""
    
    @abstractmethod
    def scan_url(self, url: str) -> Dict[str, Any]:
        """Scan a URL for threats."""
        pass


class IScanRepository(ABC):
    """Interface for scan records repository."""
    
    @abstractmethod
    def init(self) -> None:
        """Initialize the repository (create tables, etc)."""
        pass
    
    @abstractmethod
    def add(self, rec: ScanRecord) -> int:
        """Add a scan record and return its ID."""
        pass
    
    @abstractmethod
    def all(self) -> Iterable[ScanRecord]:
        """Get all scan records."""
        pass


class IEventRepository(ABC):
    """Interface for events repository."""
    
    @abstractmethod
    def add_many(self, items: Iterable[EventItem]) -> None:
        """Add multiple event items."""
        pass
    
    @abstractmethod
    def recent(self, limit: int = 100) -> Iterable[EventItem]:
        """Get recent events."""
        pass
