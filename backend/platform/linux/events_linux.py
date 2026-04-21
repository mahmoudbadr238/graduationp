"""
Linux Event Log Reader — journalctl-based.

Replaces backend/infra/events_windows.py on Linux.
Reads system logs from systemd journal instead of Windows Event Log.
Implements the same IEventReader interface.
"""

import json
import logging
import subprocess
from collections.abc import Iterable
from datetime import datetime

from backend.core.interfaces import IEventReader
from backend.core.types import EventItem

logger = logging.getLogger(__name__)


# Priority mapping: journald numeric priority -> human label
_PRIORITY_MAP = {
    "0": "Emergency",
    "1": "Alert",
    "2": "Critical",
    "3": "Error",
    "4": "Warning",
    "5": "Notice",
    "6": "Info",
    "7": "Debug",
}

# Map journald priority to Windows-compatible level strings
_LEVEL_MAP = {
    "0": "Critical",
    "1": "Critical",
    "2": "Critical",
    "3": "Error",
    "4": "Warning",
    "5": "Information",
    "6": "Information",
    "7": "Information",
}


def build_friendly_message(source: str, event_id: int, raw_message: str) -> str:
    """Create a short, user-friendly summary for the event list."""
    if not raw_message:
        return f"Event from {source}"
    # Truncate long messages
    first_line = str(raw_message).split("\n")[0].strip()
    if len(first_line) > 120:
        return first_line[:117] + "..."
    return first_line


def _safe_message(raw) -> str:
    """Safely extract a string message from journalctl JSON.

    journalctl can return MESSAGE as:
      - a plain string
      - a list of ints (byte array for binary/non-UTF-8 data)
      - None / missing
    """
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        try:
            return bytes(raw).decode("utf-8", errors="replace")
        except (TypeError, ValueError):
            return str(raw)
    return str(raw)


class LinuxEventReader(IEventReader):
    """Read events from systemd journal via journalctl."""

    def read_events(
        self,
        sources: list[str] | None = None,
        max_events: int = 200,
        level_filter: str | None = None,
    ) -> Iterable[EventItem]:
        """Read events from the systemd journal."""
        cmd = [
            "journalctl",
            "--output=json",
            "--no-pager",
            f"--lines={max_events}",
            "--reverse",
        ]

        # Map level filter to journald priority
        if level_filter:
            priority_map = {
                "Critical": "0..2",
                "Error": "3",
                "Warning": "4",
                "Information": "5..6",
            }
            p = priority_map.get(level_filter)
            if p:
                cmd.append(f"--priority={p}")

        # Filter by specific units
        if sources:
            for src in sources:
                cmd.extend(["--unit", src])

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except FileNotFoundError:
            logger.warning("journalctl not found -- event viewer disabled")
            return []
        except subprocess.TimeoutExpired:
            logger.warning("journalctl timed out")
            return []

        events: list[EventItem] = []
        for line in (proc.stdout or "").strip().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Extract fields
            timestamp_us = entry.get("__REALTIME_TIMESTAMP", "")
            try:
                ts = datetime.fromtimestamp(int(timestamp_us) / 1_000_000)
            except (ValueError, TypeError, OSError):
                ts = datetime.now()

            priority = str(entry.get("PRIORITY", "6"))
            level = _LEVEL_MAP.get(priority, "Information")
            source = entry.get("SYSLOG_IDENTIFIER", "") or entry.get("_COMM", "unknown")
            message = _safe_message(entry.get("MESSAGE"))
            pid = entry.get("_PID", "")

            # Use PID as a pseudo event-ID
            try:
                event_id = int(pid) if pid else 0
            except (ValueError, TypeError):
                event_id = 0

            friendly = build_friendly_message(source, event_id, message)

            events.append(EventItem(
                timestamp=ts,
                level=level,
                source=source,
                event_id=event_id,
                message=message,
                friendly_message=friendly,
            ))

            if len(events) >= max_events:
                break

        return events

    def tail(self, limit: int = 50) -> Iterable[EventItem]:
        """Get recent system events (IEventReader interface)."""
        return self.read_events(max_events=limit)
