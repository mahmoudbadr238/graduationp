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


def summarize_event_for_table(event) -> str:
    """
    Generate a short, human-readable summary for the event table.
    
    This provides context even before opening the AI panel.
    Uses event level and source to create a meaningful one-liner.
    
    Args:
        event: Event object or dict with 'level', 'source', and optionally 'message'
        
    Returns:
        A short, user-friendly summary string
    """
    # Handle both dict and object access
    if hasattr(event, 'level'):
        level = (event.level or "").upper()
        src = event.source or event.provider or "System"
        message = getattr(event, 'message', '') or ''
    else:
        level = (event.get("level", "") or "").upper()
        src = event.get("source") or event.get("provider") or "System"
        message = event.get("message", "") or ""
    
    # Truncate source for display
    src_display = src[:25] + "..." if len(src) > 25 else src
    
    # Generate context-aware summary based on level
    if level == "ERROR":
        if "timeout" in message.lower():
            return f"{src_display} reported a timeout - an operation took too long."
        if "access" in message.lower() or "denied" in message.lower():
            return f"{src_display} was denied access to something it needed."
        if "connection" in message.lower() or "network" in message.lower():
            return f"{src_display} had a network or connection problem."
        return f"{src_display} reported a problem that may have interrupted something."
    
    if level == "WARNING":
        if "disk" in message.lower() or "space" in message.lower():
            return f"{src_display} noticed a disk or storage concern."
        if "memory" in message.lower():
            return f"{src_display} noticed a memory-related concern."
        return f"{src_display} noticed something unusual that might need attention."
    
    if level in ("SUCCESS", "INFORMATION", "INFO"):
        if "start" in message.lower():
            return f"{src_display} started successfully."
        if "stop" in message.lower() or "end" in message.lower():
            return f"{src_display} stopped or completed."
        if "update" in message.lower():
            return f"{src_display} recorded an update activity."
        return f"{src_display} recorded normal activity or a status update."
    
    if level in ("CRITICAL", "FAILURE"):
        return f"{src_display} reported a critical issue requiring attention."
    
    return f"{src_display} logged an event."


def build_friendly_message(source: str, event_id: int, raw_message: str) -> str:
    """
    Create a short, user-friendly summary for the event list.
    
    This is non-AI and should be fast. Uses the knowledge base for known events,
    and intelligently rephrases unknown events based on message content.
    
    Args:
        source: Event source (e.g., "System", "Application")
        event_id: Windows Event ID
        raw_message: Original event message text
        
    Returns:
        A short, friendly message suitable for display in the event list.
    """
    # Import here to avoid circular imports
    try:
        from ..ai.event_id_knowledge import get_friendly_title
        friendly = get_friendly_title(source, event_id)
        if friendly:
            return friendly
    except ImportError:
        pass
    
    # Rephrase unknown events based on message content
    return _rephrase_event_message(source, event_id, raw_message)


def _rephrase_event_message(source: str, event_id: int, raw_message: str) -> str:
    """
    Intelligently rephrase an event message into simple, user-friendly language.
    
    Uses keyword detection and pattern matching to generate human-readable summaries.
    """
    if not raw_message:
        return f"{source} activity logged (Event {event_id})"
    
    text = raw_message.lower().strip()
    original = (raw_message or "").strip().replace("\r\n", " ").replace("\n", " ")
    
    # =========================================================================
    # SUCCESS / COMPLETION PATTERNS
    # =========================================================================
    if any(w in text for w in ["successfully completed", "completed successfully", "success"]):
        if "install" in text:
            return "Software installed successfully"
        if "update" in text:
            return "Update completed successfully"
        if "start" in text:
            return "Service or program started successfully"
        if "stop" in text:
            return "Service or program stopped successfully"
        if "connect" in text:
            return "Connection established successfully"
        if "logon" in text or "login" in text or "sign" in text:
            return "User logged in successfully"
        if "backup" in text:
            return "Backup completed successfully"
        if "sync" in text:
            return "Synchronization completed"
        return "Operation completed successfully"
    
    # =========================================================================
    # FAILURE / ERROR PATTERNS
    # =========================================================================
    if any(w in text for w in ["failed", "failure", "error", "cannot", "unable", "denied"]):
        if "install" in text:
            return "Software installation failed"
        if "update" in text:
            return "Update failed to install"
        if "start" in text:
            return "Service or program failed to start"
        if "connect" in text:
            return "Connection failed"
        if "logon" in text or "login" in text:
            return "Login attempt failed"
        if "access" in text or "permission" in text:
            return "Access was denied"
        if "timeout" in text:
            return "Operation timed out"
        if "network" in text:
            return "Network error occurred"
        if "disk" in text or "drive" in text:
            return "Disk error detected"
        return "An error occurred"
    
    # =========================================================================
    # START / STOP PATTERNS
    # =========================================================================
    if any(w in text for w in ["started", "starting", "began", "initiated", "launched"]):
        if "service" in text:
            return "A Windows service started"
        if "driver" in text:
            return "A device driver loaded"
        if "session" in text:
            return "User session started"
        if "download" in text:
            return "Download started"
        if "scan" in text:
            return "Scan started"
        return "An operation started"
    
    if any(w in text for w in ["stopped", "stopping", "ended", "terminated", "exited", "closed"]):
        if "service" in text:
            return "A Windows service stopped"
        if "unexpected" in text or "crash" in text:
            return "Program closed unexpectedly"
        if "session" in text:
            return "User session ended"
        return "An operation ended"
    
    # =========================================================================
    # NETWORK PATTERNS
    # =========================================================================
    if any(w in text for w in ["network", "internet", "wifi", "wi-fi", "ethernet", "connection"]):
        if "connect" in text:
            return "Network connected"
        if "disconnect" in text:
            return "Network disconnected"
        if "ip address" in text or "dhcp" in text:
            return "Network address assigned"
        return "Network activity logged"
    
    # =========================================================================
    # SECURITY PATTERNS
    # =========================================================================
    if any(w in text for w in ["security", "audit", "policy", "credential", "password"]):
        if "logon" in text or "login" in text:
            return "User authentication logged"
        if "policy" in text:
            return "Security policy applied"
        if "password" in text:
            return "Password-related activity"
        return "Security event logged"
    
    # =========================================================================
    # UPDATE / INSTALL PATTERNS
    # =========================================================================
    if any(w in text for w in ["update", "upgrade", "patch"]):
        if "download" in text:
            return "Update downloaded"
        if "install" in text:
            return "Update installed"
        if "available" in text:
            return "Updates are available"
        if "check" in text:
            return "Checking for updates"
        return "Update activity logged"
    
    if any(w in text for w in ["install", "uninstall", "setup"]):
        if "uninstall" in text or "remov" in text:
            return "Software was uninstalled"
        return "Software installation activity"
    
    # =========================================================================
    # POWER / HARDWARE PATTERNS
    # =========================================================================
    if any(w in text for w in ["power", "sleep", "hibernate", "wake", "shutdown", "restart", "reboot"]):
        if "sleep" in text or "hibernate" in text:
            return "System entered low-power mode"
        if "wake" in text or "resume" in text:
            return "System woke from sleep"
        if "shutdown" in text:
            return "System shutdown logged"
        if "restart" in text or "reboot" in text:
            return "System restart logged"
        return "Power state changed"
    
    if any(w in text for w in ["driver", "device", "hardware", "usb", "bluetooth"]):
        if "load" in text or "start" in text:
            return "Device driver loaded"
        if "error" in text or "fail" in text:
            return "Device driver issue detected"
        if "usb" in text:
            return "USB device activity"
        if "bluetooth" in text:
            return "Bluetooth activity"
        return "Hardware activity logged"
    
    # =========================================================================
    # DISK / STORAGE PATTERNS  
    # =========================================================================
    if any(w in text for w in ["disk", "storage", "volume", "partition", "filesystem", "ntfs"]):
        if "error" in text:
            return "Disk error detected"
        if "check" in text or "scan" in text:
            return "Disk check performed"
        if "mount" in text:
            return "Volume mounted"
        return "Disk activity logged"
    
    # =========================================================================
    # BACKUP / RESTORE PATTERNS
    # =========================================================================
    if any(w in text for w in ["backup", "restore", "recovery", "snapshot"]):
        if "start" in text:
            return "Backup/restore started"
        if "complet" in text:
            return "Backup/restore completed"
        if "fail" in text:
            return "Backup/restore failed"
        return "Backup activity logged"
    
    # =========================================================================
    # SCHEDULE / TASK PATTERNS
    # =========================================================================
    if any(w in text for w in ["scheduled", "task", "trigger", "schedule"]):
        if "start" in text or "launch" in text:
            return "Scheduled task started"
        if "complet" in text:
            return "Scheduled task completed"
        return "Scheduled task activity"
    
    # =========================================================================
    # WINDOWS DEFENDER / ANTIVIRUS
    # =========================================================================
    if any(w in text for w in ["defender", "antivirus", "malware", "threat", "virus", "scan"]):
        if "detect" in text or "found" in text:
            return "Security threat detected"
        if "clean" in text or "remov" in text:
            return "Threat was removed"
        if "scan" in text:
            return "Security scan performed"
        if "update" in text:
            return "Security definitions updated"
        return "Security scan activity"
    
    # =========================================================================
    # PRINT PATTERNS
    # =========================================================================
    if any(w in text for w in ["print", "printer", "spooler"]):
        if "job" in text:
            return "Print job processed"
        return "Printer activity logged"
    
    # =========================================================================
    # APPLICATION PATTERNS
    # =========================================================================
    if any(w in text for w in ["crash", "hang", "not responding", "stopped working"]):
        return "Application stopped responding"
    
    if any(w in text for w in ["exception", "fault", "access violation"]):
        return "Application encountered an error"
    
    # =========================================================================
    # GENERIC FALLBACK - Extract key info from first sentence
    # =========================================================================
    # Take first sentence or first 100 chars
    first_sentence = original.split(".")[0].strip() if "." in original else original
    
    if len(first_sentence) > 80:
        # Find a good breaking point
        words = first_sentence[:80].split()
        first_sentence = " ".join(words[:-1]) + "..." if len(words) > 1 else first_sentence[:77] + "..."
    
    # If we have something meaningful, return it slightly cleaned
    if first_sentence and len(first_sentence) > 5:
        return first_sentence
    
    # Last resort
    return f"{source} activity (Event ID {event_id})"


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
                            
                            # Extract event ID (mask to get actual ID)
                            event_id = event.EventID & 0xFFFF

                            # Get user-friendly message (encoding-safe)
                            raw_message = self._simplify_message(event, source)
                            
                            # Build friendly message using knowledge base or heuristics
                            friendly = build_friendly_message(source, event_id, raw_message)

                            events.append(
                                EventItem(
                                    timestamp=timestamp,
                                    level=level,
                                    source=source,
                                    message=raw_message,
                                    event_id=event_id,
                                    friendly_message=friendly,
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
                        logger.warning(
                            f"Read {batch_count} batches from {source}, stopping"
                        )
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
                            safe_s = s.encode("ascii", errors="replace").decode("ascii")
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
