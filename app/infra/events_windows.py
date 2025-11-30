"""Windows event log reader implementation."""

import platform
import sys
from collections.abc import Iterable
from datetime import datetime
import logging

from ..core.interfaces import IEventReader
from ..core.types import EventItem

logger = logging.getLogger(__name__)

# Only import win32 modules on Windows
_IS_WINDOWS = platform.system() == "Windows"

if _IS_WINDOWS:
    try:
        import win32con
        import win32evtlog
        _WIN32_AVAILABLE = True
    except ImportError:
        _WIN32_AVAILABLE = False
        logger.warning("win32 modules not available - event viewer disabled")
else:
    _WIN32_AVAILABLE = False


class WindowsEventReader(IEventReader):
    """Read recent Windows event logs."""

    # Event log sources to monitor (prioritized order)
    SOURCES = ["Application", "System", "Security"]

    # ASCII-safe icons for output (no encoding issues)
    SAFE_ICON_SUCCESS = "[OK]"
    SAFE_ICON_ERROR = "[!]"
    SAFE_ICON_WARNING = "[*]"

    # Map Windows event types to severity levels (only set if win32 available)
    EVENT_TYPE_MAP = {}
    
    def __init__(self):
        """Initialize the event reader."""
        if _WIN32_AVAILABLE:
            self.EVENT_TYPE_MAP = {
                win32con.EVENTLOG_ERROR_TYPE: "ERROR",
                win32con.EVENTLOG_WARNING_TYPE: "WARNING",
                win32con.EVENTLOG_INFORMATION_TYPE: "INFO",
                win32con.EVENTLOG_AUDIT_SUCCESS: "SUCCESS",
                win32con.EVENTLOG_AUDIT_FAILURE: "FAILURE",
            }

    def tail(self, limit: int = 100) -> Iterable[EventItem]:
        """Return recent Windows event log entries.
        
        Returns gracefully with available events if some sources are inaccessible.
        """
        # Return empty on non-Windows or if win32 modules unavailable
        if not _WIN32_AVAILABLE:
            logger.info("Event viewer not available on this platform")
            return []
        
        events = []
        per_source_limit = limit // 2

        for source in self.SOURCES:
            try:
                source_events = self._read_source(source, per_source_limit)
                events.extend(source_events)
                logger.debug(f"Read {len(source_events)} events from {source}")
            except PermissionError as e:
                logger.warning(f"{source} requires admin privileges: {e}")
                continue
            except (OSError, ValueError) as e:
                # Gracefully handle Event Viewer unavailable or encoding errors
                logger.warning(f"Could not read {source} events: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error reading {source}: {e}")
                continue

        # Sort by timestamp descending and limit
        events.sort(key=lambda e: e.timestamp, reverse=True)
        result = events[:limit]
        
        if not result:
            logger.warning("No events available from any source")
            # Return empty list gracefully instead of failing
        
        return result

    def _read_source(self, source: str, limit: int) -> list[EventItem]:
        """Read events from a specific source with encoding-safe handling.
        
        Args:
            source: Event log source name (Application, System, Security)
            limit: Maximum events to read per batch
            
        Returns:
            List of EventItem objects, may be empty if source unavailable
            
        Raises:
            PermissionError: If access denied (e.g., Security log without admin)
            OSError: If source doesn't exist or is inaccessible
        """
        events = []
        
        try:
            hand = win32evtlog.OpenEventLog(None, source)
        except Exception as e:
            # Gracefully handle Event Viewer unavailable or closed
            logger.error(f"Cannot open {source} event log: {e}")
            raise
            
        try:
            flags = (
                win32evtlog.EVENTLOG_BACKWARDS_READ
                | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            )

            batch_count = 0
            while len(events) < limit:
                try:
                    event_batch = win32evtlog.ReadEventLog(hand, flags, 0)
                    if not event_batch:
                        break

                    for event in event_batch:
                        if len(events) >= limit:
                            break

                        try:
                            # Extract event information with encoding safety
                            level = self.EVENT_TYPE_MAP.get(event.EventType, "UNKNOWN")
                            timestamp = datetime.fromtimestamp(
                                int(event.TimeGenerated.timestamp())
                            )

                            # Get user-friendly message (encoding-safe)
                            message = self._simplify_message(event, source)

                            events.append(
                                EventItem(
                                    timestamp=timestamp,
                                    level=level,
                                    source=source,
                                    message=message,
                                )
                            )
                        except UnicodeEncodeError as e:
                            logger.warning(f"Encoding error processing event: {e}")
                            # Skip this event, continue with next
                            continue
                        except Exception as e:
                            logger.warning(f"Error processing event: {e}")
                            continue
                    
                    batch_count += 1
                    if batch_count > 100:  # Prevent infinite loops
                        logger.warning(f"Read {batch_count} batches from {source}, stopping")
                        break
                        
                except OSError as e:
                    logger.error(f"Error reading batch from {source}: {e}")
                    break

        except Exception as e:
            logger.error(f"Unexpected error reading {source}: {e}")
            raise
        finally:
            try:
                win32evtlog.CloseEventLog(hand)
            except Exception as e:
                logger.warning(f"Error closing event log: {e}")

        return events

    def _simplify_message(self, event, source: str) -> str:
        """Convert technical event messages into user-friendly, encoding-safe descriptions.

        Args:
            event: Windows event object
            source: Event log source name

        Returns:
            str: Simplified, user-friendly, ASCII-safe message
        """
        try:
            event_id = event.EventID & 0xFFFF  # Mask to get actual ID
        except Exception as e:
            logger.warning(f"Could not extract event ID: {e}")
            return f"{source} Event (unknown ID)"

        # Try to get the original message safely
        raw_message = ""
        try:
            if event.StringInserts:
                # Filter out None/empty strings and encode safely
                inserts = []
                for s in event.StringInserts:
                    if s:
                        # Replace any non-ASCII characters with safe alternatives
                        try:
                            safe_s = s.encode('ascii', errors='replace').decode('ascii')
                            inserts.append(safe_s)
                        except Exception:
                            inserts.append("(text)")
                raw_message = " ".join(inserts)
        except Exception as e:
            logger.warning(f"Could not extract event details: {e}")

        # Common event ID translations for better UX (ASCII-safe)
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

        # For unknown events, try to make the message cleaner and ASCII-safe
        if raw_message:
            # Limit message length for readability and safety
            safe_msg = raw_message[:150]
            if len(raw_message) > 150:
                safe_msg += "..."
            return safe_msg

        # Fallback: just show event ID with source
        return f"{source} Event ID {event_id}"
