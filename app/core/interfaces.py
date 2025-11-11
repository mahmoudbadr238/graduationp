"""Service and repository interfaces (abstract base classes)."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any

from .types import EventItem, ScanRecord


class ISystemMonitor(ABC):
    """Interface for system monitoring service."""

    @abstractmethod
    def snapshot(self) -> dict[str, Any]:
        """Get current system snapshot (CPU, memory, GPU, network, disk)."""


class IEventReader(ABC):
    """Interface for reading system events."""

    @abstractmethod
    def tail(self, limit: int = 50) -> Iterable[EventItem]:
        """Get recent system events."""


class INetworkScanner(ABC):
    """Interface for network scanning service."""

    @abstractmethod
    def scan(self, target: str, fast: bool = True) -> dict[str, Any]:
        """Scan network target."""


class IFileScanner(ABC):
    """Interface for file scanning service."""

    @abstractmethod
    def scan_file(self, path: str) -> dict[str, Any]:
        """Scan a file for threats."""


class IUrlScanner(ABC):
    """Interface for URL scanning service."""

    @abstractmethod
    def scan_url(self, url: str) -> dict[str, Any]:
        """Scan a URL for threats."""


class IScanRepository(ABC):
    """Interface for scan records repository."""

    @abstractmethod
    def init(self) -> None:
        """Initialize the repository (create tables, etc)."""

    @abstractmethod
    def add(self, rec: ScanRecord) -> int:
        """Add a scan record and return its ID."""

    @abstractmethod
    def all(self) -> Iterable[ScanRecord]:
        """Get all scan records."""


class IEventRepository(ABC):
    """Interface for events repository."""

    @abstractmethod
    def add_many(self, items: Iterable[EventItem]) -> None:
        """Add multiple event items."""

    @abstractmethod
    def recent(self, limit: int = 100) -> Iterable[EventItem]:
        """Get recent events."""
