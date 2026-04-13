"""Action Memory & Retry Guard — tracks recent actions and suppresses loops.

Maintains a sliding window of recent actions and prevents the agent from
repeating the same failed action more than a configurable number of times.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

from .models import ActionDecision, ActionRecord

log = logging.getLogger("sentinel_agent")

# Maximum times to retry the same (action, target) before suppressing
MAX_RETRIES = 2

# How long (seconds) to remember a failed action
MEMORY_WINDOW = 120.0

# Maximum number of total actions to keep in history
MAX_HISTORY = 200


class ActionMemory:
    """Tracks action history and enforces retry limits."""

    def __init__(self) -> None:
        self._history: list[ActionRecord] = []
        # (action, target_lower) → [timestamps of consecutive failures]
        self._failure_counts: dict[tuple[str, str], list[float]] = defaultdict(list)

    @property
    def history(self) -> list[ActionRecord]:
        return list(self._history)

    @property
    def total_actions(self) -> int:
        return len(self._history)

    @property
    def total_effective(self) -> int:
        return sum(1 for r in self._history if r.state_changed)

    def record(self, record: ActionRecord) -> None:
        """Record an action and update failure tracking."""
        self._history.append(record)
        if len(self._history) > MAX_HISTORY:
            self._history = self._history[-MAX_HISTORY:]

        key = (record.decision.action.value, record.decision.target.lower())

        if record.executed and not record.state_changed:
            # Action was executed but had no effect → count as failure
            self._failure_counts[key].append(record.timestamp)
            count = len(self._prune_old(key))
            log.info(
                "Ineffective action recorded: %s '%s' (%d/%d retries)",
                key[0], key[1], count, MAX_RETRIES,
            )
        elif record.state_changed:
            # Success — clear failure history for this action
            self._failure_counts.pop(key, None)

    def is_suppressed(self, action: str, target: str) -> bool:
        """Check whether this (action, target) pair has been suppressed."""
        key = (action.lower(), target.lower())
        failures = self._prune_old(key)
        if len(failures) >= MAX_RETRIES:
            log.info(
                "SUPPRESSED: %s '%s' — failed %d times in window",
                action, target, len(failures),
            )
            return True
        return False

    def consecutive_waits(self) -> int:
        """Count how many consecutive wait actions are at the end of history."""
        count = 0
        for record in reversed(self._history):
            if record.decision.action.value == "wait":
                count += 1
            else:
                break
        return count

    def detect_loop(self, window: int = 6) -> bool:
        """Detect if the last N actions form a repeating pattern."""
        if len(self._history) < window:
            return False

        recent = self._history[-window:]
        keys = [(r.decision.action.value, r.decision.target.lower()) for r in recent]

        # Check for all-same
        if len(set(keys)) == 1:
            return True

        # Check for A-B-A-B pattern
        if window >= 4:
            half = window // 2
            if keys[:half] == keys[half:half * 2]:
                return True

        return False

    def _prune_old(self, key: tuple[str, str]) -> list[float]:
        """Remove entries older than MEMORY_WINDOW and return remaining."""
        cutoff = time.monotonic() - MEMORY_WINDOW
        self._failure_counts[key] = [
            t for t in self._failure_counts[key] if t > cutoff
        ]
        return self._failure_counts[key]

    def get_summary(self) -> dict:
        """Return a summary dict for telemetry/reporting."""
        return {
            "total_actions": self.total_actions,
            "effective_actions": self.total_effective,
            "suppressed_pairs": len([
                k for k, v in self._failure_counts.items()
                if len(v) >= MAX_RETRIES
            ]),
        }
