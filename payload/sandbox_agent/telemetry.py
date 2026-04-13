"""Agent telemetry helpers for cycle-by-cycle trace recording.

This module keeps trace shaping and summary math separate from the core
react loop so the agent logic remains easy to read and test.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class TraceEvent:
    """Normalized trace event for a single react-loop cycle."""

    cycle: int
    remaining_s: int
    observed_state: str
    state_confidence: float
    state_explanation: str
    chosen_action: str
    action_target: str
    action_confidence: float
    action_reason: str
    match_confidence: float
    match_method: str
    verification_result: str
    executed: bool
    active_window: str = ""
    window_count: int = 0
    refusal_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert event to JSON-friendly dictionary payload."""
        payload: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "cycle": self.cycle,
            "remaining_s": self.remaining_s,
            "observed_state": self.observed_state,
            "state_confidence": round(self.state_confidence, 3),
            "state_explanation": self.state_explanation,
            "chosen_action": self.chosen_action,
            "action_target": self.action_target,
            "action_confidence": round(self.action_confidence, 3),
            "action_reason": self.action_reason,
            "match_confidence": round(self.match_confidence, 3),
            "match_method": self.match_method,
            "verification_result": self.verification_result,
            "executed": self.executed,
            "active_window": self.active_window,
            "window_count": self.window_count,
        }
        if self.refusal_reason:
            payload["refusal_reason"] = self.refusal_reason
        return payload


class TraceRecorder:
    """In-memory collector for trace events and derived summary stats."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def record(self, event: TraceEvent) -> None:
        """Append one trace event."""
        self._events.append(event.to_dict())

    def to_list(self) -> list[dict[str, Any]]:
        """Return a copy of all trace events."""
        return list(self._events)

    def summary(self) -> dict[str, Any]:
        """Return aggregate metrics for monitoring/reporting."""
        total = len(self._events)
        if total == 0:
            return {
                "cycles": 0,
                "executed_actions": 0,
                "changed_cycles": 0,
                "unchanged_cycles": 0,
                "wait_cycles": 0,
                "refused_cycles": 0,
                "execution_rate": 0.0,
                "change_rate": 0.0,
            }

        executed = sum(1 for e in self._events if e.get("executed") is True)
        changed = sum(1 for e in self._events if e.get("verification_result") == "changed")
        unchanged = sum(1 for e in self._events if e.get("verification_result") == "unchanged")
        waits = sum(1 for e in self._events if e.get("chosen_action") == "wait")
        refused = sum(1 for e in self._events if bool(e.get("refusal_reason")))

        return {
            "cycles": total,
            "executed_actions": executed,
            "changed_cycles": changed,
            "unchanged_cycles": unchanged,
            "wait_cycles": waits,
            "refused_cycles": refused,
            "execution_rate": round(executed / total, 3),
            "change_rate": round(changed / total, 3),
        }
