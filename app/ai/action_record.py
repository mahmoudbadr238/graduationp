"""
Action Record - Audit logging for AI resolution actions.

This module provides:
- ActionRecord dataclass for logging AI actions
- ActionLog class for managing action history
- Resolution session tracking
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Types of actions the AI can perform."""
    EXPLAIN = "explain"
    SCAN = "scan"
    CHECK_STATUS = "check_status"
    ANALYZE = "analyze"
    RECOMMEND = "recommend"
    RESOLVE = "resolve"
    INFO = "info"


class ActionOutcome(str, Enum):
    """Outcome of an action."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"


@dataclass
class ActionRecord:
    """
    Record of a single AI action during a resolution session.
    
    Attributes:
        action_id: Unique identifier for this action
        session_id: Resolution session this action belongs to
        action_type: Type of action performed
        description: Human-readable description
        input_data: Input parameters for the action
        output_data: Output/result of the action
        outcome: Success/failure status
        timestamp: When the action was performed
        duration_ms: How long the action took
        error: Error message if failed
    """
    action_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    session_id: str = ""
    action_type: ActionType = ActionType.INFO
    description: str = ""
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    outcome: ActionOutcome = ActionOutcome.PENDING
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_ms: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "action_id": self.action_id,
            "session_id": self.session_id,
            "action_type": self.action_type.value if isinstance(self.action_type, ActionType) else self.action_type,
            "description": self.description,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "outcome": self.outcome.value if isinstance(self.outcome, ActionOutcome) else self.outcome,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionRecord:
        """Create from dictionary."""
        return cls(
            action_id=data.get("action_id", str(uuid.uuid4())[:8]),
            session_id=data.get("session_id", ""),
            action_type=ActionType(data.get("action_type", "info")),
            description=data.get("description", ""),
            input_data=data.get("input_data", {}),
            output_data=data.get("output_data", {}),
            outcome=ActionOutcome(data.get("outcome", "pending")),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            duration_ms=data.get("duration_ms", 0),
            error=data.get("error"),
        )


@dataclass
class ResolutionSession:
    """
    A resolution session containing multiple actions.
    
    Attributes:
        session_id: Unique session identifier
        event_id: Event being resolved (if applicable)
        event_source: Source of the event
        started_at: When the session started
        ended_at: When the session ended (None if ongoing)
        status: Current status of the session
        actions: List of actions performed
        summary: Summary of what was done
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    event_id: int | None = None
    event_source: str | None = None
    event_summary: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ended_at: str | None = None
    status: str = "in_progress"
    actions: list[ActionRecord] = field(default_factory=list)
    summary: str = ""

    def add_action(self, action: ActionRecord) -> None:
        """Add an action to this session."""
        action.session_id = self.session_id
        self.actions.append(action)

    def complete(self, summary: str = "") -> None:
        """Mark session as completed."""
        self.ended_at = datetime.now().isoformat()
        self.status = "completed"
        self.summary = summary or self._generate_summary()

    def _generate_summary(self) -> str:
        """Generate a summary of actions performed."""
        if not self.actions:
            return "No actions performed."

        success_count = sum(1 for a in self.actions if a.outcome == ActionOutcome.SUCCESS)
        total = len(self.actions)

        return f"Performed {total} actions ({success_count} successful)"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "event_id": self.event_id,
            "event_source": self.event_source,
            "event_summary": self.event_summary,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "status": self.status,
            "actions": [a.to_dict() for a in self.actions],
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResolutionSession:
        """Create from dictionary."""
        session = cls(
            session_id=data.get("session_id", str(uuid.uuid4())[:12]),
            event_id=data.get("event_id"),
            event_source=data.get("event_source"),
            event_summary=data.get("event_summary"),
            started_at=data.get("started_at", datetime.now().isoformat()),
            ended_at=data.get("ended_at"),
            status=data.get("status", "in_progress"),
            summary=data.get("summary", ""),
        )
        session.actions = [ActionRecord.from_dict(a) for a in data.get("actions", [])]
        return session


class ActionLog:
    """
    Manages action records and resolution sessions.
    
    Thread-safe logging of AI actions during resolution.
    """

    MAX_SESSIONS = 50  # Keep last 50 sessions

    def __init__(self):
        self._sessions: list[ResolutionSession] = []
        self._current_session: ResolutionSession | None = None
        self._lock = threading.Lock()

    def start_session(
        self,
        event_id: int | None = None,
        event_source: str | None = None,
        event_summary: str | None = None,
    ) -> ResolutionSession:
        """Start a new resolution session."""
        with self._lock:
            # End any current session first
            if self._current_session:
                self._current_session.complete()

            session = ResolutionSession(
                event_id=event_id,
                event_source=event_source,
                event_summary=event_summary,
            )
            self._current_session = session
            logger.info(f"Started resolution session: {session.session_id}")
            return session

    def end_session(self, summary: str = "") -> ResolutionSession | None:
        """End the current session and save it."""
        with self._lock:
            if not self._current_session:
                return None

            session = self._current_session
            session.complete(summary)

            # Add to history
            self._sessions.append(session)

            # Trim to max size
            if len(self._sessions) > self.MAX_SESSIONS:
                self._sessions = self._sessions[-self.MAX_SESSIONS:]

            self._current_session = None
            logger.info(f"Ended resolution session: {session.session_id}")
            return session

    def log_action(
        self,
        action_type: ActionType,
        description: str,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        outcome: ActionOutcome = ActionOutcome.SUCCESS,
        duration_ms: int = 0,
        error: str | None = None,
    ) -> ActionRecord | None:
        """Log an action to the current session."""
        with self._lock:
            if not self._current_session:
                # Auto-start a session if none exists
                self._current_session = ResolutionSession()

            action = ActionRecord(
                action_type=action_type,
                description=description,
                input_data=input_data or {},
                output_data=output_data or {},
                outcome=outcome,
                duration_ms=duration_ms,
                error=error,
            )

            self._current_session.add_action(action)
            logger.debug(f"Logged action: {action.action_type.value} - {description}")
            return action

    def get_current_session(self) -> ResolutionSession | None:
        """Get the current active session."""
        with self._lock:
            return self._current_session

    def get_all_sessions(self) -> list[ResolutionSession]:
        """Get all saved sessions."""
        with self._lock:
            return list(self._sessions)

    def get_session(self, session_id: str) -> ResolutionSession | None:
        """Get a specific session by ID."""
        with self._lock:
            for session in self._sessions:
                if session.session_id == session_id:
                    return session
            return None

    def clear(self) -> None:
        """Clear all sessions."""
        with self._lock:
            self._sessions.clear()
            self._current_session = None


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_action_log: ActionLog | None = None
_log_lock = threading.Lock()


def get_action_log() -> ActionLog:
    """Get singleton action log instance."""
    global _action_log
    with _log_lock:
        if _action_log is None:
            _action_log = ActionLog()
        return _action_log
