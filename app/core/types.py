"""Core domain types for Sentinel."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime


class ScanType(str, Enum):
    """Types of scans supported by the system."""
    NETWORK = "network"
    FILE = "file"
    URL = "url"


@dataclass
class EventItem:
    """Represents a system security event."""
    timestamp: str
    level: str
    source: str
    message: str


@dataclass
class ScanRecord:
    """Represents a completed security scan."""
    id: Optional[int]
    started_at: str
    finished_at: str
    type: ScanType
    target: str
    status: str
    findings: int
    meta: Dict[str, Any] = field(default_factory=dict)
