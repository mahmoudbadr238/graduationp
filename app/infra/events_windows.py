"""Windows event log reader implementation."""

from collections.abc import Iterable
from datetime import datetime

import win32con
import win32evtlog

from ..core.interfaces import IEventReader
from ..core.types import EventItem


class WindowsEventReader(IEventReader):
    """Read recent Windows event logs."""

    # Event log sources to monitor (prioritized order)
    SOURCES = ["Application", "System", "Security"]

    # Map Windows event types to severity levels
    EVENT_TYPE_MAP = {
        win32con.EVENTLOG_ERROR_TYPE: "ERROR",
        win32con.EVENTLOG_WARNING_TYPE: "WARNING",
        win32con.EVENTLOG_INFORMATION_TYPE: "INFO",
        win32con.EVENTLOG_AUDIT_SUCCESS: "SUCCESS",
        win32con.EVENTLOG_AUDIT_FAILURE: "FAILURE",
    }

    def tail(self, limit: int = 100) -> Iterable[EventItem]:
        """Return recent Windows event log entries."""
        events = []

        # Read more events per source to ensure we get the requested total
        # Even if Security log is inaccessible, we'll have enough from Application + System
        per_source_limit = limit // 2  # Divide by 2 instead of 3 for better coverage

        for source in self.SOURCES:
            try:
                # Try to read each source, but continue if access denied
                source_events = self._read_source(source, per_source_limit)
                events.extend(source_events)
                print(f"✓ Read {len(source_events)} events from {source}")
            except (OSError, PermissionError, ValueError) as e:
                # Gracefully handle permission errors and invalid sources
                error_msg = str(e)
                if "1314" in error_msg or "privilege" in error_msg.lower():
                    print(
                        f"⚠ {source} events require administrator privileges (skipped)"
                    )
                else:
                    print(f"⚠ Could not read {source} events: {e}")
                continue

        # Sort by timestamp descending and limit
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]

    def _read_source(self, source: str, limit: int) -> list[EventItem]:
        """Read events from a specific source."""
        events = []

        try:
            hand = win32evtlog.OpenEventLog(None, source)
            flags = (
                win32evtlog.EVENTLOG_BACKWARDS_READ
                | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            )

            while len(events) < limit:
                event_batch = win32evtlog.ReadEventLog(hand, flags, 0)
                if not event_batch:
                    break

                for event in event_batch:
                    if len(events) >= limit:
                        break

                    # Extract event information
                    level = self.EVENT_TYPE_MAP.get(event.EventType, "UNKNOWN")
                    timestamp = datetime.fromtimestamp(
                        int(event.TimeGenerated.timestamp())
                    )

                    # Get user-friendly message
                    message = self._simplify_message(event, source)

                    events.append(
                        EventItem(
                            timestamp=timestamp,
                            level=level,
                            source=source,
                            message=message,
                        )
                    )

            win32evtlog.CloseEventLog(hand)

        except Exception:
            # Re-raise to be handled by caller
            raise

        return events

    def _simplify_message(self, event, source: str) -> str:
        """
        Convert technical event messages into user-friendly descriptions.

        Args:
            event: Windows event object
            source: Event log source name

        Returns:
            str: Simplified, user-friendly message
        """
        event_id = event.EventID & 0xFFFF  # Mask to get actual ID

        # Try to get the original message
        raw_message = ""
        if event.StringInserts:
            raw_message = " ".join([s for s in event.StringInserts if s])

        # Common event ID translations for better UX
        EVENT_TRANSLATIONS = {
            # System Events
            1074: "System restart or shutdown",
            1076: "System shutdown was unexpected",
            6005: "Windows Event Log service started",
            6006: "Windows Event Log service stopped",
            6008: "System shutdown was unexpected (power loss or crash)",
            6009: "System started successfully",
            7000: "A service failed to start",
            7001: "A service depends on a service that failed to start",
            7034: "A service terminated unexpectedly",
            7036: "Service status changed",
            10016: "Application permission issue (DCOM)",
            # Application Events
            1000: "Application error or crash",
            1001: "Windows Error Reporting",
            1002: "Application hang detected",
            # Security Events (if accessible)
            4624: "User successfully logged in",
            4625: "User failed to log in",
            4634: "User logged out",
            4648: "Login attempt using explicit credentials",
            4672: "Special privileges assigned to new login",
            4688: "New process created",
            4689: "Process exited",
            4768: "Kerberos authentication ticket requested",
            5152: "Network packet blocked by firewall",
            5156: "Network connection allowed by firewall",
        }

        # Try to get friendly message
        friendly = EVENT_TRANSLATIONS.get(event_id)

        if friendly:
            # If we have a translation, use it with details if available
            if raw_message and len(raw_message) < 100:
                return f"{friendly}: {raw_message}"
            return friendly

        # For unknown events, try to make the message cleaner
        if raw_message:
            # Limit message length for readability
            if len(raw_message) > 150:
                return raw_message[:150] + "..."
            return raw_message

        # Fallback: just show event ID with source
        return f"{source} Event ID {event_id}"
