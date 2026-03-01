"""
Sandbox Session Manager - Live event capture and persistence.

Manages sandbox execution sessions:
- Unified event schema for all sandbox events
- Real-time event streaming via callbacks
- Persistent JSONL logging for crash recovery
- Session lifecycle management

100% Offline - No network required.
"""

import json
import logging
import os
import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of sandbox events."""
    PROCESS_START = "process_start"
    PROCESS_END = "process_end"
    FILE_CREATE = "file_create"
    FILE_MODIFY = "file_modify"
    FILE_DELETE = "file_delete"
    REGISTRY_MODIFY = "registry_modify"
    REGISTRY_CREATE = "registry_create"
    NETWORK_CONNECT = "network_connect"
    NETWORK_BLOCKED = "network_blocked"
    PERSISTENCE_ATTEMPT = "persistence_attempt"
    SUSPICIOUS_BEHAVIOR = "suspicious_behavior"
    STATUS_UPDATE = "status_update"
    ERROR = "error"


@dataclass
class SandboxEvent:
    """
    A single event captured during sandbox execution.
    
    Unified schema for all event types.
    """
    event_type: str  # EventType value
    timestamp: str  # ISO format

    # Process events
    pid: int | None = None
    parent_pid: int | None = None
    process_name: str | None = None
    command_line: str | None = None
    exit_code: int | None = None

    # File events
    file_path: str | None = None
    file_size: int | None = None
    file_hash: str | None = None

    # Registry events
    registry_key: str | None = None
    registry_value: str | None = None
    registry_data: str | None = None

    # Network events
    remote_address: str | None = None
    remote_port: int | None = None
    protocol: str | None = None
    blocked: bool = False

    # Behavior analysis
    behavior_category: str | None = None
    severity: str | None = None  # low, medium, high, critical
    description: str | None = None
    indicators: list[str] = field(default_factory=list)

    # Metadata
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None and v != [] and v != ""}

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class SessionStats:
    """Live statistics for the sandbox session."""
    running_time_seconds: float = 0.0
    processes_spawned: int = 0
    files_touched: int = 0
    registry_changes: int = 0
    network_attempts: int = 0
    suspicious_behaviors: int = 0
    current_action: str = "Initializing"
    is_running: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SandboxSession:
    """
    Manages a single sandbox execution session.
    
    Features:
    - Live event streaming via callbacks
    - Batched event delivery for UI performance
    - Persistent JSONL logging
    - Session summary generation
    """

    def __init__(
        self,
        session_id: str | None = None,
        workspace: Path | None = None,
        event_callback: Callable[[list[SandboxEvent]], None] | None = None,
        stats_callback: Callable[[SessionStats], None] | None = None,
        batch_interval_ms: int = 300,
    ):
        """
        Initialize a sandbox session.
        
        Args:
            session_id: Unique session identifier (auto-generated if not provided)
            workspace: Directory for session files
            event_callback: Called with batched events for UI
            stats_callback: Called with updated stats for UI
            batch_interval_ms: How often to flush events to callback (default 300ms)
        """
        self.session_id = session_id or f"sandbox_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.workspace = workspace or self._get_default_workspace()
        self.event_callback = event_callback
        self.stats_callback = stats_callback
        self.batch_interval_ms = batch_interval_ms

        # Session state
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None
        self.sample_path: str | None = None
        self.sample_hash: str | None = None
        self.is_running = False
        self.was_cancelled = False

        # Event storage
        self.events: list[SandboxEvent] = []
        self._event_queue: Queue = Queue()
        self._lock = threading.Lock()

        # Stats
        self.stats = SessionStats()

        # Background thread for batching
        self._batch_thread: threading.Thread | None = None
        self._stop_batching = threading.Event()

        # File handles
        self._jsonl_file = None

        # Ensure workspace exists
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _get_default_workspace(self) -> Path:
        """Get default session workspace."""
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        else:
            base = Path.home() / ".config"

        return base / "Sentinel" / "sandbox_sessions" / self.session_id

    def start(self, sample_path: str, sample_hash: str | None = None) -> None:
        """
        Start the session.
        
        Args:
            sample_path: Path to the sample being analyzed
            sample_hash: SHA256 hash of the sample (optional)
        """
        self.start_time = datetime.now()
        self.sample_path = sample_path
        self.sample_hash = sample_hash
        self.is_running = True
        self.stats.is_running = True
        self.stats.current_action = "Launching sample"

        # Create session directory
        self.workspace.mkdir(parents=True, exist_ok=True)

        # Open JSONL file for persistent logging
        jsonl_path = self.workspace / "sandbox_session.jsonl"
        self._jsonl_file = open(jsonl_path, "w", encoding="utf-8")

        # Write session header
        header = {
            "type": "session_start",
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "sample_path": sample_path,
            "sample_hash": sample_hash,
        }
        self._jsonl_file.write(json.dumps(header) + "\n")
        self._jsonl_file.flush()

        # Start batching thread
        self._stop_batching.clear()
        self._batch_thread = threading.Thread(target=self._batch_loop, daemon=True)
        self._batch_thread.start()

        logger.info(f"Sandbox session started: {self.session_id}")

        # Emit initial stats
        if self.stats_callback:
            self.stats_callback(self.stats)

    def add_event(self, event: SandboxEvent) -> None:
        """
        Add an event to the session (thread-safe).
        
        Args:
            event: The sandbox event to add
        """
        if not self.is_running:
            return

        # Add to queue for batching
        self._event_queue.put(event)

        # Write to JSONL immediately for crash recovery
        if self._jsonl_file:
            try:
                self._jsonl_file.write(event.to_json() + "\n")
                self._jsonl_file.flush()
            except Exception as e:
                logger.warning(f"Failed to write event to JSONL: {e}")

        # Update stats
        with self._lock:
            self.events.append(event)
            self._update_stats(event)

    def _update_stats(self, event: SandboxEvent) -> None:
        """Update session statistics based on event type."""
        if self.start_time:
            self.stats.running_time_seconds = (datetime.now() - self.start_time).total_seconds()

        event_type = event.event_type

        if event_type == EventType.PROCESS_START:
            self.stats.processes_spawned += 1
        elif event_type in (EventType.FILE_CREATE, EventType.FILE_MODIFY, EventType.FILE_DELETE):
            self.stats.files_touched += 1
        elif event_type in (EventType.REGISTRY_CREATE, EventType.REGISTRY_MODIFY):
            self.stats.registry_changes += 1
        elif event_type in (EventType.NETWORK_CONNECT, EventType.NETWORK_BLOCKED):
            self.stats.network_attempts += 1
        elif event_type in (EventType.SUSPICIOUS_BEHAVIOR, EventType.PERSISTENCE_ATTEMPT):
            self.stats.suspicious_behaviors += 1

    def _batch_loop(self) -> None:
        """Background loop to batch events for UI delivery."""
        batch_interval = self.batch_interval_ms / 1000.0

        while not self._stop_batching.is_set():
            batch: list[SandboxEvent] = []

            # Collect events from queue
            try:
                while True:
                    event = self._event_queue.get_nowait()
                    batch.append(event)
            except Empty:
                pass

            # Deliver batch
            if batch and self.event_callback:
                try:
                    self.event_callback(batch)
                except Exception as e:
                    logger.warning(f"Event callback error: {e}")

            # Deliver stats update
            if self.stats_callback:
                try:
                    with self._lock:
                        if self.start_time:
                            self.stats.running_time_seconds = (datetime.now() - self.start_time).total_seconds()
                    self.stats_callback(self.stats)
                except Exception as e:
                    logger.warning(f"Stats callback error: {e}")

            # Wait for next batch interval
            self._stop_batching.wait(timeout=batch_interval)

    def update_action(self, action: str) -> None:
        """Update the current action status."""
        self.stats.current_action = action

        # Add status event
        event = SandboxEvent(
            event_type=EventType.STATUS_UPDATE,
            timestamp=datetime.now().isoformat(),
            description=action,
        )
        self.add_event(event)

    def stop(self, cancelled: bool = False) -> None:
        """
        Stop the session.
        
        Args:
            cancelled: Whether the session was cancelled by user
        """
        self.end_time = datetime.now()
        self.is_running = False
        self.was_cancelled = cancelled
        self.stats.is_running = False
        self.stats.current_action = "Cancelled" if cancelled else "Completed"

        # Stop batching thread
        self._stop_batching.set()
        if self._batch_thread:
            self._batch_thread.join(timeout=2)

        # Flush remaining events
        remaining: list[SandboxEvent] = []
        try:
            while True:
                remaining.append(self._event_queue.get_nowait())
        except Empty:
            pass

        if remaining and self.event_callback:
            try:
                self.event_callback(remaining)
            except Exception as e:
                logger.warning(f"Final event batch callback error: {e}")

        # Close JSONL file
        if self._jsonl_file:
            try:
                # Write session footer
                footer = {
                    "type": "session_end",
                    "session_id": self.session_id,
                    "end_time": self.end_time.isoformat(),
                    "cancelled": cancelled,
                    "total_events": len(self.events),
                    "stats": self.stats.to_dict(),
                }
                self._jsonl_file.write(json.dumps(footer) + "\n")
                self._jsonl_file.close()
            except Exception as e:
                logger.warning(f"Failed to close JSONL file: {e}")

        # Write summary JSON
        self._write_summary()

        # Final stats update
        if self.stats_callback:
            try:
                self.stats_callback(self.stats)
            except Exception:
                pass

        logger.info(f"Sandbox session stopped: {self.session_id} (cancelled={cancelled})")

    def _write_summary(self) -> None:
        """Write session summary JSON file."""
        try:
            summary = {
                "session_id": self.session_id,
                "sample_path": self.sample_path,
                "sample_hash": self.sample_hash,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "duration_seconds": self.stats.running_time_seconds,
                "cancelled": self.was_cancelled,
                "stats": self.stats.to_dict(),
                "events_by_type": self._group_events_by_type(),
                "suspicious_behaviors": self._get_suspicious_behaviors(),
                "narrative": self._generate_narrative(),
            }

            summary_path = self.workspace / "summary.json"
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)

        except Exception as e:
            logger.warning(f"Failed to write session summary: {e}")

    def _group_events_by_type(self) -> dict[str, list[dict]]:
        """Group events by type for report generation."""
        groups: dict[str, list[dict]] = {}

        with self._lock:
            for event in self.events:
                event_type = event.event_type
                if event_type not in groups:
                    groups[event_type] = []
                groups[event_type].append(event.to_dict())

        return groups

    def _get_suspicious_behaviors(self) -> list[dict]:
        """Get all suspicious behavior events."""
        suspicious = []

        with self._lock:
            for event in self.events:
                if event.event_type in (EventType.SUSPICIOUS_BEHAVIOR, EventType.PERSISTENCE_ATTEMPT):
                    suspicious.append(event.to_dict())

        return suspicious

    def _generate_narrative(self) -> str:
        """Generate a human-readable narrative of what happened."""
        if not self.events:
            return "No significant activity was observed during sandbox execution."

        parts = []

        # Process activity
        process_starts = [e for e in self.events if e.event_type == EventType.PROCESS_START]
        if process_starts:
            if len(process_starts) == 1:
                parts.append(f"The sample launched as a single process (PID: {process_starts[0].pid}).")
            else:
                parts.append(f"The sample spawned {len(process_starts)} processes during execution.")

        # File activity
        file_creates = [e for e in self.events if e.event_type == EventType.FILE_CREATE]
        file_mods = [e for e in self.events if e.event_type == EventType.FILE_MODIFY]
        if file_creates or file_mods:
            total_files = len(file_creates) + len(file_mods)
            parts.append(f"It created or modified {total_files} file(s) on the system.")

        # Registry activity
        reg_mods = [e for e in self.events if e.event_type in (EventType.REGISTRY_CREATE, EventType.REGISTRY_MODIFY)]
        if reg_mods:
            parts.append(f"Made {len(reg_mods)} registry modification(s).")

        # Network activity
        net_events = [e for e in self.events if e.event_type == EventType.NETWORK_CONNECT]
        blocked_events = [e for e in self.events if e.event_type == EventType.NETWORK_BLOCKED]
        if net_events:
            parts.append(f"Attempted {len(net_events)} network connection(s).")
        if blocked_events:
            parts.append(f"Blocked {len(blocked_events)} outbound network attempt(s).")

        # Suspicious behaviors
        suspicious = [e for e in self.events if e.event_type in (EventType.SUSPICIOUS_BEHAVIOR, EventType.PERSISTENCE_ATTEMPT)]
        if suspicious:
            parts.append(f"Detected {len(suspicious)} suspicious behavior(s):")
            for s in suspicious[:5]:  # Limit to first 5
                if s.description:
                    parts.append(f"  • {s.description}")

        if not parts:
            return "The sample executed without significant observable behavior."

        return " ".join(parts)

    def get_summary(self) -> dict[str, Any]:
        """Get session summary for report generation."""
        with self._lock:
            return {
                "session_id": self.session_id,
                "sample_path": self.sample_path,
                "sample_hash": self.sample_hash,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "duration_seconds": self.stats.running_time_seconds,
                "cancelled": self.was_cancelled,
                "stats": self.stats.to_dict(),
                "events_by_type": self._group_events_by_type(),
                "suspicious_behaviors": self._get_suspicious_behaviors(),
                "narrative": self._generate_narrative(),
                "workspace": str(self.workspace),
            }


def load_session(session_path: Path) -> SandboxSession | None:
    """
    Load a session from disk (for crash recovery or review).
    
    Args:
        session_path: Path to session workspace directory
        
    Returns:
        Loaded SandboxSession or None if failed
    """
    try:
        jsonl_path = session_path / "sandbox_session.jsonl"
        if not jsonl_path.exists():
            return None

        session = SandboxSession(workspace=session_path)

        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                data = json.loads(line)

                if data.get("type") == "session_start":
                    session.session_id = data.get("session_id", session.session_id)
                    session.sample_path = data.get("sample_path")
                    session.sample_hash = data.get("sample_hash")
                    if data.get("start_time"):
                        session.start_time = datetime.fromisoformat(data["start_time"])

                elif data.get("type") == "session_end":
                    if data.get("end_time"):
                        session.end_time = datetime.fromisoformat(data["end_time"])
                    session.was_cancelled = data.get("cancelled", False)

                elif data.get("event_type"):
                    # Regular event
                    event = SandboxEvent(
                        event_type=data["event_type"],
                        timestamp=data.get("timestamp", ""),
                        pid=data.get("pid"),
                        parent_pid=data.get("parent_pid"),
                        process_name=data.get("process_name"),
                        command_line=data.get("command_line"),
                        exit_code=data.get("exit_code"),
                        file_path=data.get("file_path"),
                        file_size=data.get("file_size"),
                        file_hash=data.get("file_hash"),
                        registry_key=data.get("registry_key"),
                        registry_value=data.get("registry_value"),
                        registry_data=data.get("registry_data"),
                        remote_address=data.get("remote_address"),
                        remote_port=data.get("remote_port"),
                        protocol=data.get("protocol"),
                        blocked=data.get("blocked", False),
                        behavior_category=data.get("behavior_category"),
                        severity=data.get("severity"),
                        description=data.get("description"),
                        indicators=data.get("indicators", []),
                    )
                    session.events.append(event)

        # Update stats from events
        for event in session.events:
            session._update_stats(event)

        return session

    except Exception as e:
        logger.error(f"Failed to load session from {session_path}: {e}")
        return None
