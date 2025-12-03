"""
Event Summarizer - Generates simple English summaries for Windows events.

Uses the local LLM engine to turn raw Windows event logs into simple,
non-technical summaries that normal users can understand.

All processing is 100% local with NO network calls.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from PySide6.QtCore import QObject

from .local_llm_engine import LocalLLMEngine

logger = logging.getLogger(__name__)

# Maximum lengths for output fields
MAX_TABLE_SUMMARY_LENGTH = 120
MAX_TITLE_LENGTH = 80
MAX_WHAT_HAPPENED_LENGTH = 500
MAX_WHAT_YOU_CAN_DO_LENGTH = 400
MAX_TECH_NOTES_LENGTH = 250


@dataclass
class EventSummary:
    """
    A human-friendly summary of a Windows event.
    
    Fields:
        table_summary: Short 1-2 sentence summary for the event list (accurate, not oversimplified)
        title: Full but clear title representing the event meaning
        severity_label: One of: Safe, Minor, Warning, Critical
        what_happened: Full explanation (4-7 sentences) with important details in plain English
        what_you_can_do: Practical advice (2-6 sentences) with specific steps
        tech_notes: Technical summary for advanced users
        event_id: Original event ID
        source: Original event source
    """
    table_summary: str
    title: str
    severity_label: str  # "Safe", "Minor", "Warning", "Critical"
    what_happened: str
    what_you_can_do: str
    tech_notes: str = ""
    event_id: Optional[int] = None
    source: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "table_summary": self.table_summary,
            "title": self.title,
            "severity_label": self.severity_label,
            "what_happened": self.what_happened,
            "what_you_can_do": self.what_you_can_do,
            "tech_notes": self.tech_notes,
            "event_id": self.event_id,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventSummary":
        """Create EventSummary from dictionary."""
        return cls(
            table_summary=data.get("table_summary", "System event"),
            title=data.get("title", "Event information"),
            severity_label=data.get("severity_label", "Minor"),
            what_happened=data.get("what_happened", ""),
            what_you_can_do=data.get("what_you_can_do", ""),
            tech_notes=data.get("tech_notes", ""),
            event_id=data.get("event_id"),
            source=data.get("source"),
        )


class EventSummarizer(QObject):
    """
    Uses the local LLM to turn raw Windows event logs
    into simple English summaries and explanations.
    
    This class provides:
    1. Short summaries for the event table (friendly_message)
    2. Detailed explanations for the side panel
    
    All processing is 100% local - no network calls.
    """

    def __init__(self, engine: LocalLLMEngine, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._memory_cache: dict[str, EventSummary] = {}
        logger.info("EventSummarizer initialized")

    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text to max length, preserving word boundaries if possible."""
        if not text:
            return ""
        text = text.strip()
        if len(text) <= max_len:
            return text
        # Try to cut at word boundary
        truncated = text[: max_len - 3]
        last_space = truncated.rfind(" ")
        if last_space > max_len // 2:
            truncated = truncated[:last_space]
        return truncated.rstrip() + "..."

    def compute_signature(self, event: dict) -> str:
        """
        Compute a signature for an event based on source, event_id, and message hash.
        
        This allows us to cache explanations for events with the same signature.
        """
        source = str(event.get("source", event.get("provider", "")))
        event_id = str(event.get("event_id", 0))
        message = str(event.get("message", ""))
        
        raw = f"{source}|{event_id}|{message}"
        return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]

    def summarize(self, event: dict) -> EventSummary:
        """
        Generate a human-friendly summary for a Windows event.
        
        Args:
            event: dict containing event_id, level, source, timestamp, message
            
        Returns:
            EventSummary with all fields populated
        """
        event_id = int(event.get("event_id") or 0)
        level = str(event.get("level") or "INFO").upper()
        source = str(event.get("source", event.get("provider", "")))
        timestamp = str(event.get("timestamp", event.get("time_created", "")))
        message = str(event.get("message") or "")
        
        # Check memory cache first
        cache_key = self.compute_signature(event)
        if cache_key in self._memory_cache:
            logger.debug(f"Memory cache hit for event signature: {cache_key[:8]}...")
            return self._memory_cache[cache_key]
        
        # Generate summary using smart rules (more reliable than LLM for this)
        summary = self._create_smart_summary(
            event_id=event_id,
            level=level,
            source=source,
            timestamp=timestamp,
            message=message,
        )
        
        # Cache in memory
        self._memory_cache[cache_key] = summary
        return summary

    def _create_smart_summary(
        self,
        event_id: int,
        level: str,
        source: str,
        timestamp: str,
        message: str,
    ) -> EventSummary:
        """
        Create a smart summary based on event level and content.
        
        Uses rule-based logic to provide accurate, helpful summaries
        without requiring LLM generation (faster and more reliable).
        """
        # Truncate source for display
        source_short = source[:25] + "..." if len(source) > 25 else source
        
        # Map Windows event levels to severity and generate appropriate content
        if level in ["CRITICAL", "FAILURE"]:
            severity_label = "Critical"
            table_summary = self._generate_table_summary_critical(source_short, message)
            title = self._generate_title("Critical", source, message)
            what_happened = self._generate_what_happened_critical(source, message, event_id)
            what_you_can_do = self._generate_what_you_can_do_critical(source, message)
            tech_notes = self._generate_tech_notes(event_id, source, level, message)
        elif level == "ERROR":
            severity_label = "Warning"
            table_summary = self._generate_table_summary_error(source_short, message)
            title = self._generate_title("Error", source, message)
            what_happened = self._generate_what_happened_error(source, message, event_id)
            what_you_can_do = self._generate_what_you_can_do_error(source, message)
            tech_notes = self._generate_tech_notes(event_id, source, level, message)
        elif level == "WARNING":
            severity_label = "Minor"
            table_summary = self._generate_table_summary_warning(source_short, message)
            title = self._generate_title("Warning", source, message)
            what_happened = self._generate_what_happened_warning(source, message, event_id)
            what_you_can_do = self._generate_what_you_can_do_warning(source, message)
            tech_notes = self._generate_tech_notes(event_id, source, level, message)
        elif level == "SUCCESS":
            severity_label = "Safe"
            table_summary = self._generate_table_summary_success(source_short, message)
            title = self._generate_title("Success", source, message)
            what_happened = self._generate_what_happened_success(source, message, event_id)
            what_you_can_do = "No action is needed. This event confirms that an operation completed successfully."
            tech_notes = self._generate_tech_notes(event_id, source, level, message)
        else:  # INFO, INFORMATION, or unknown
            severity_label = "Safe"
            table_summary = self._generate_table_summary_info(source_short, message)
            title = self._generate_title("Info", source, message)
            what_happened = self._generate_what_happened_info(source, message, event_id)
            what_you_can_do = "No action is needed. This is a routine informational event that Windows logs for record-keeping."
            tech_notes = self._generate_tech_notes(event_id, source, level, message)

        return EventSummary(
            table_summary=self._truncate(table_summary, MAX_TABLE_SUMMARY_LENGTH),
            title=self._truncate(title, MAX_TITLE_LENGTH),
            severity_label=severity_label,
            what_happened=self._truncate(what_happened, MAX_WHAT_HAPPENED_LENGTH),
            what_you_can_do=self._truncate(what_you_can_do, MAX_WHAT_YOU_CAN_DO_LENGTH),
            tech_notes=self._truncate(tech_notes, MAX_TECH_NOTES_LENGTH),
            event_id=event_id,
            source=source,
        )

    def _generate_table_summary_critical(self, source: str, message: str) -> str:
        """Generate a short table summary for critical events."""
        msg_lower = message.lower()
        
        if "crash" in msg_lower or "stopped" in msg_lower:
            return f"A program from {source} crashed or stopped unexpectedly"
        elif "failed" in msg_lower:
            return f"Something failed in {source}"
        elif "shutdown" in msg_lower or "restart" in msg_lower:
            return "Your computer shut down or restarted unexpectedly"
        elif "disk" in msg_lower or "drive" in msg_lower:
            return "A problem was detected with your disk or storage"
        elif "memory" in msg_lower:
            return "A memory problem was detected"
        else:
            return f"A critical issue occurred with {source}"

    def _generate_table_summary_error(self, source: str, message: str) -> str:
        """Generate a short table summary for error events."""
        msg_lower = message.lower()
        
        if "timeout" in msg_lower:
            return f"{source} took too long to respond"
        elif "denied" in msg_lower or "permission" in msg_lower:
            return f"{source} was denied access to something"
        elif "not found" in msg_lower or "missing" in msg_lower:
            return f"{source} couldn't find something it needed"
        elif "connection" in msg_lower or "network" in msg_lower:
            return "A network or connection error occurred"
        elif "failed" in msg_lower:
            return f"An operation in {source} didn't complete successfully"
        else:
            return f"An error was reported by {source}"

    def _generate_table_summary_warning(self, source: str, message: str) -> str:
        """Generate a short table summary for warning events."""
        msg_lower = message.lower()
        
        if "update" in msg_lower:
            return f"{source} has an update available or is updating"
        elif "low" in msg_lower and ("disk" in msg_lower or "memory" in msg_lower or "space" in msg_lower):
            return "Your computer is running low on disk space or memory"
        elif "slow" in msg_lower or "performance" in msg_lower:
            return "Something is running slower than expected"
        elif "backup" in msg_lower:
            return "Something related to backup needs attention"
        else:
            return f"{source} noticed something that might need attention"

    def _generate_table_summary_success(self, source: str, message: str) -> str:
        """Generate a short table summary for success events."""
        msg_lower = message.lower()
        
        if "update" in msg_lower or "install" in msg_lower:
            return f"{source} finished installing or updating successfully"
        elif "scan" in msg_lower:
            return f"{source} completed a scan successfully"
        elif "backup" in msg_lower:
            return "A backup completed successfully"
        else:
            return f"{source} completed an operation successfully"

    def _generate_table_summary_info(self, source: str, message: str) -> str:
        """Generate a short table summary for info events."""
        msg_lower = message.lower()
        
        if "start" in msg_lower:
            return f"{source} started running"
        elif "stop" in msg_lower or "end" in msg_lower:
            return f"{source} stopped normally"
        elif "login" in msg_lower or "logon" in msg_lower:
            return "Someone logged in to this computer"
        elif "logout" in msg_lower or "logoff" in msg_lower:
            return "Someone logged out of this computer"
        elif "connect" in msg_lower:
            return "A connection was established"
        elif "disconnect" in msg_lower:
            return "A connection ended"
        elif "update" in msg_lower:
            return f"{source} is checking for updates"
        elif "security" in msg_lower:
            return "A security-related event was logged"
        else:
            return f"Normal activity from {source}"

    def _generate_title(self, level: str, source: str, message: str) -> str:
        """Generate a clear, descriptive title based on the event."""
        msg_lower = message.lower()
        source_short = source[:30] + "..." if len(source) > 30 else source
        
        # Try to extract meaningful title from message content
        if "crash" in msg_lower or "stopped unexpectedly" in msg_lower:
            return "Application Crash Detected"
        elif "hang" in msg_lower or "not responding" in msg_lower:
            return "Application Stopped Responding"
        elif "login" in msg_lower or "logon" in msg_lower:
            if "failed" in msg_lower:
                return "Failed Login Attempt"
            return "User Login Event"
        elif "logout" in msg_lower or "logoff" in msg_lower:
            return "User Logout Event"
        elif "update" in msg_lower:
            if "installed" in msg_lower or "success" in msg_lower:
                return "Windows Update Installed"
            elif "failed" in msg_lower:
                return "Windows Update Failed"
            return "Windows Update Activity"
        elif "firewall" in msg_lower:
            if "blocked" in msg_lower:
                return "Firewall Blocked a Connection"
            return "Firewall Configuration Changed"
        elif "disk" in msg_lower or "drive" in msg_lower:
            if "error" in msg_lower or "bad" in msg_lower:
                return "Disk Error Detected"
            return "Disk Activity Event"
        elif "network" in msg_lower or "connection" in msg_lower:
            if "failed" in msg_lower or "error" in msg_lower:
                return "Network Connection Error"
            return "Network Activity Event"
        elif "service" in msg_lower:
            if "start" in msg_lower:
                return f"Service Started: {source_short}"
            elif "stop" in msg_lower:
                return f"Service Stopped: {source_short}"
            return f"Service Event: {source_short}"
        elif "security" in msg_lower:
            return "Security Event Logged"
        elif "permission" in msg_lower or "access" in msg_lower:
            if "denied" in msg_lower:
                return "Access Denied Event"
            return "Permission Change Event"
        else:
            # Fallback based on level
            level_titles = {
                "Critical": f"Critical System Event from {source_short}",
                "Error": f"Error Reported by {source_short}",
                "Warning": f"Warning from {source_short}",
                "Success": f"Successful Operation: {source_short}",
                "Info": f"System Activity: {source_short}",
            }
            return level_titles.get(level, f"Event from {source_short}")

    def _generate_tech_notes(self, event_id: int, source: str, level: str, message: str) -> str:
        """Generate technical notes summarizing raw event data for advanced users."""
        notes_parts = []
        
        if event_id:
            notes_parts.append(f"Event ID: {event_id}")
        notes_parts.append(f"Source: {source}")
        notes_parts.append(f"Level: {level}")
        
        # Extract key technical details from message
        msg_lower = message.lower()
        if "error code" in msg_lower or "0x" in message:
            # Try to find error codes
            import re
            hex_codes = re.findall(r'0x[0-9A-Fa-f]+', message)
            if hex_codes:
                notes_parts.append(f"Error codes: {', '.join(hex_codes[:3])}")
        
        return " | ".join(notes_parts)

    def _generate_what_happened_critical(self, source: str, message: str, event_id: int) -> str:
        """Generate a detailed explanation for critical events."""
        msg_lower = message.lower()
        
        if "crash" in msg_lower or "stopped" in msg_lower:
            return (
                f"A program or service called '{source}' crashed or stopped working unexpectedly. "
                f"This type of event (ID: {event_id}) indicates a serious failure where the software encountered "
                "a problem it could not recover from. The crash may have been caused by a bug in the software, "
                "a conflict with another program, insufficient system resources, or corrupted files. "
                "Depending on what crashed, some features of your computer may not work properly until the "
                "issue is resolved or your computer is restarted."
            )
        elif "disk" in msg_lower or "drive" in msg_lower:
            return (
                f"Windows detected a significant problem with your disk or storage drive. "
                f"This event (ID: {event_id}) from '{source}' indicates that the system encountered errors "
                "while reading or writing data to your storage device. This could be caused by physical damage "
                "to the drive, file system corruption, or a failing hard drive. If left unaddressed, this could "
                "potentially lead to data loss or system instability."
            )
        elif "memory" in msg_lower:
            return (
                f"A critical memory-related error was detected by '{source}'. "
                f"This event (ID: {event_id}) indicates that your computer's memory (RAM) encountered a problem. "
                "This could be caused by faulty RAM hardware, memory being overused by programs, or a driver issue. "
                "Memory errors can cause programs to crash, data corruption, or system instability."
            )
        else:
            return (
                f"A critical system event was logged by '{source}' (Event ID: {event_id}). "
                "This indicates a serious issue that may affect your computer's stability or functionality. "
                "Critical events are relatively rare and typically indicate something significant has gone wrong. "
                "The system may have automatically attempted to recover from this issue, but it's worth "
                "investigating if you notice any unusual behavior."
            )

    def _generate_what_happened_error(self, source: str, message: str, event_id: int) -> str:
        """Generate a detailed explanation for error events."""
        msg_lower = message.lower()
        
        if "timeout" in msg_lower:
            return (
                f"The '{source}' component was waiting for a response but didn't receive one in time. "
                f"This timeout event (ID: {event_id}) means that a process, service, or network connection "
                "took longer than expected and was terminated. This commonly happens when programs are "
                "overloaded, when there are network connectivity issues, or when system resources are limited. "
                "The operation may have been automatically retried by the system."
            )
        elif "denied" in msg_lower or "permission" in msg_lower:
            return (
                f"'{source}' attempted to perform an action but was denied access (Event ID: {event_id}). "
                "This means the program tried to access a file, folder, or system resource that it doesn't "
                "have permission to use. This is often a security protection working as intended, but it can "
                "also indicate a misconfigured permission or a program that needs to run with administrator rights. "
                "If this is affecting a program you're trying to use, you may need to adjust its permissions."
            )
        elif "not found" in msg_lower or "missing" in msg_lower:
            return (
                f"'{source}' reported that something it needed was missing or could not be found (Event ID: {event_id}). "
                "This could be a file, a system component, or a required dependency. This type of error often occurs "
                "after program updates, uninstallations, or when files are accidentally deleted or moved. "
                "The affected functionality may not work properly until the missing item is restored."
            )
        else:
            return (
                f"An error was recorded by '{source}' (Event ID: {event_id}). "
                "This means an operation did not complete successfully. Error events are more serious than warnings "
                "but less severe than critical events. Your computer will continue to function, but the specific "
                "operation that failed may need to be retried, or there may be some functionality that's temporarily "
                "affected. If this error occurs repeatedly, it may indicate an underlying issue worth investigating."
            )

    def _generate_what_happened_warning(self, source: str, message: str, event_id: int) -> str:
        """Generate a detailed explanation for warning events."""
        msg_lower = message.lower()
        
        if "low" in msg_lower and ("disk" in msg_lower or "space" in msg_lower):
            return (
                f"Windows is alerting you that your disk space is running low (Event ID: {event_id}). "
                f"This warning from '{source}' means your hard drive or storage device is filling up. "
                "When storage space gets too low, programs may not be able to save files, updates cannot install, "
                "and your computer may slow down. Windows typically shows this warning when available space "
                "drops below a certain threshold to give you time to free up space."
            )
        elif "performance" in msg_lower or "slow" in msg_lower:
            return (
                f"A performance warning was logged by '{source}' (Event ID: {event_id}). "
                "This indicates that some component of your system is operating slower than expected. "
                "This could be due to high CPU usage, limited memory, slow disk access, or resource-intensive "
                "programs running in the background. While not immediately critical, repeated performance "
                "warnings may indicate a need to upgrade hardware or optimize system settings."
            )
        else:
            return (
                f"'{source}' has logged a warning (Event ID: {event_id}) indicating something that may "
                "deserve attention but is not immediately critical. Warning events are Windows's way of "
                "flagging potential issues before they become serious problems. The system is still functioning "
                "normally, but monitoring this type of event can help prevent future issues."
            )

    def _generate_what_happened_success(self, source: str, message: str, event_id: int) -> str:
        """Generate a detailed explanation for success events."""
        msg_lower = message.lower()
        
        if "update" in msg_lower or "install" in msg_lower:
            return (
                f"'{source}' has successfully completed an installation or update operation (Event ID: {event_id}). "
                "This is a positive event confirming that new software or updates were installed correctly. "
                "Your system has been updated with the latest changes, which may include security patches, "
                "bug fixes, or new features."
            )
        else:
            return (
                f"'{source}' has recorded a successful operation (Event ID: {event_id}). "
                "This event confirms that a particular action or process completed without any errors. "
                "Success events are useful for tracking when important operations finish correctly."
            )

    def _generate_what_happened_info(self, source: str, message: str, event_id: int) -> str:
        """Generate a detailed explanation for info events."""
        msg_lower = message.lower()
        
        if "login" in msg_lower or "logon" in msg_lower:
            return (
                f"A user login event was recorded by '{source}' (Event ID: {event_id}). "
                "Windows logs all login events as part of its security auditing. This could be your own login, "
                "another user on a shared computer, or a system account logging in to perform background tasks. "
                "These events are normal and help track who has accessed the computer and when."
            )
        elif "start" in msg_lower:
            return (
                f"'{source}' has started running (Event ID: {event_id}). "
                "This informational event records the startup of a program, service, or system component. "
                "Services and programs start and stop regularly as part of normal Windows operation. "
                "This type of event is useful for troubleshooting if you need to know when something started."
            )
        elif "stop" in msg_lower or "shutdown" in msg_lower:
            return (
                f"'{source}' has stopped or shut down (Event ID: {event_id}). "
                "This informational event records that a service, program, or component has ended. "
                "If this was a planned shutdown, it's completely normal. Windows logs these events to help "
                "diagnose issues if something stops unexpectedly."
            )
        else:
            return (
                f"This is an informational log entry from '{source}' (Event ID: {event_id}). "
                "Windows and its applications constantly log routine activities for diagnostic and auditing purposes. "
                "Informational events record normal operations and don't indicate any problems. They're useful "
                "for understanding what your computer has been doing and for troubleshooting when needed."
            )

    def _generate_what_you_can_do_critical(self, source: str, message: str) -> str:
        """Generate practical advice for critical events."""
        msg_lower = message.lower()
        
        if "disk" in msg_lower or "drive" in msg_lower:
            return (
                "First, back up your important files immediately if you can. Run the built-in Windows disk check "
                "by opening Command Prompt as Administrator and typing 'chkdsk /f'. Consider running a full "
                "antivirus scan to rule out malware. If disk errors continue, your drive may be failing and "
                "should be replaced soon. Monitor the drive using tools like CrystalDiskInfo."
            )
        elif "memory" in msg_lower:
            return (
                "Try restarting your computer to clear the memory. Close unnecessary programs to free up RAM. "
                "If this happens frequently, you may need more memory (RAM) or there could be a faulty RAM module. "
                "Run Windows Memory Diagnostic (search for it in the Start menu) to check for hardware issues."
            )
        else:
            return (
                "First, save any work you have open and restart your computer. Check Windows Update for any "
                "pending updates that might fix the issue. If the problem involves a specific program, try "
                "reinstalling it. Check Event Viewer for related errors to get more context. If critical events "
                "continue to occur, consider contacting technical support or a technician."
            )

    def _generate_what_you_can_do_error(self, source: str, message: str) -> str:
        """Generate practical advice for error events."""
        msg_lower = message.lower()
        
        if "permission" in msg_lower or "denied" in msg_lower:
            return (
                "If this is blocking a program you need to use, try running it as Administrator (right-click and "
                "select 'Run as administrator'). Check that you have permission to access the files or folders "
                "involved. If this happens with a work program, contact your IT department as they may need to "
                "adjust your permissions."
            )
        elif "network" in msg_lower or "connection" in msg_lower:
            return (
                "Check your internet connection and try refreshing or reconnecting. Restart your router if needed. "
                "If using a VPN, try disconnecting and reconnecting. For persistent network errors, run the Windows "
                "Network Troubleshooter (Settings > Network & Internet > Network troubleshooter)."
            )
        else:
            return (
                "If this error is affecting a specific program, try closing and reopening it. Check if the program "
                "has updates available. Restarting your computer can often resolve temporary errors. If the error "
                "keeps occurring, search online for the specific Event ID to find targeted solutions."
            )

    def _generate_what_you_can_do_warning(self, source: str, message: str) -> str:
        """Generate practical advice for warning events."""
        msg_lower = message.lower()
        
        if "low" in msg_lower and ("disk" in msg_lower or "space" in msg_lower):
            return (
                "Free up disk space by emptying the Recycle Bin, running Disk Cleanup (search for it in the Start menu), "
                "or uninstalling programs you don't use. Consider moving large files like videos and photos to an "
                "external drive or cloud storage. Windows needs free space to function properly, so aim to keep at "
                "least 10-15% of your drive free."
            )
        else:
            return (
                "No immediate action is required for most warnings. However, if you see this warning repeatedly, it may "
                "indicate a developing issue worth investigating. Keep an eye on your system's behavior and check Windows "
                "Update for any available fixes. If warnings persist, searching for the specific Event ID online can "
                "provide more targeted guidance."
            )

    def clear_cache(self) -> None:
        """Clear the in-memory cache."""
        self._memory_cache.clear()
        logger.info("EventSummarizer memory cache cleared")

    def get_cache_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return {"memory_cached": len(self._memory_cache)}


# Singleton instance
_event_summarizer: Optional[EventSummarizer] = None


def get_event_summarizer(engine: LocalLLMEngine) -> EventSummarizer:
    """Get the singleton EventSummarizer instance."""
    global _event_summarizer
    if _event_summarizer is None:
        _event_summarizer = EventSummarizer(engine)
    return _event_summarizer
