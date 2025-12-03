"""
Event Explainer - AI-powered Windows event explanation.

Uses LocalLLMEngine to provide human-readable explanations
of Windows event log entries. 100% local, no network calls.

OUTPUT FORMAT (JSON):
{
    "severity": "Safe" | "Minor" | "Warning" | "Critical",
    "short_title": "<max 80 chars, clear title>",
    "what_happened": "<3-6 sentences explaining what occurred>",
    "why_it_happens": "<2-4 sentences on common causes>",
    "what_to_do": "<bullet list with actions + when to worry>",
    "tech_notes": "<1-3 sentences for advanced users with Event ID>"
}
"""

import hashlib
import json
import logging
import os
import re
from typing import Any, Optional

from PySide6.QtCore import QObject

from .local_llm_engine import LocalLLMEngine

logger = logging.getLogger(__name__)

# Maximum lengths for output fields
MAX_TITLE_LENGTH = 80
MAX_SECTION_LENGTH = 500
MAX_WHAT_TO_DO_LENGTH = 700
MAX_TECH_NOTES_LENGTH = 350
MAX_MESSAGE_INPUT_LENGTH = 700

# Improved system prompt - clear, detailed, non-scary
SENTINEL_EVENT_SYSTEM_PROMPT = """
You are the on-device Event Explainer for Sentinel – Endpoint Security Suite.

Your job:
- Read a single Windows Event Log entry.
- Use the event ID, level, source, and message to infer what really happened.
- Explain it in **clear, everyday English** for a normal user.
- Still give enough detail that a power user understands the situation.

Style rules:
- Write as if you are a helpful IT technician talking to a non-expert user.
- No scary language unless the situation is truly serious.
- Avoid raw jargon like 'DCOM', 'RPC', '0x80070005' unless you **briefly explain** what it means in simple terms.
- Never just restate the original log message – always transform it into a clear explanation.
- Be honest when something is not critical or is very common.

Structure your answer in **5 sections**:

1) **Title** – a short human-readable name for this event (e.g., "Application stopped responding", "Minor permissions issue during startup").

2) **What happened** – 3–6 sentences explaining what actually happened, using the event ID and any useful parts of the message.

3) **Why this happens** – 2–4 sentences describing the most common causes, in normal English.

4) **What you should do** – bullet list with clear actions. Include:
   - what to do **now** (often "nothing" or "just keep an eye on it")
   - when the user should start worrying (e.g., "if this happens many times a day…").

5) **Technical notes (optional)** – 1–3 short sentences for advanced users, using the event ID and source (you may mention DCOM, RPC, etc. here).

Tone:
- Calm, reassuring, and practical.
- Aim for roughly **150–250 words** when there is enough information.
- Make sure the user understands *what, why, and what next*.
"""

# Legacy alias for backward compatibility
EVENT_EXPLAINER_SYSTEM_PROMPT = SENTINEL_EVENT_SYSTEM_PROMPT

# Prompt template that includes event knowledge
EVENT_PROMPT_TEMPLATE = """
You are explaining this single Windows event log entry:

- Event ID: {event_id}
- Level: {level}
- Source: {source}
- Log: {log_name}
- Time: {timestamp}
- Computer: {computer_name}

Original message:
\"\"\"{message}\"\"\"

Known information for this Event ID (if available):
\"\"\"{event_knowledge}\"\"\"

Important:
- Base your explanation primarily on the **Event ID + Source + Level**.
- Use the message text to add useful detail, but rewrite it in clear English.
- If this looks like a very common harmless event (for example: routine DCOM permission warnings, normal application status logs, successful security operations), make that clear in your explanation.
- If the event suggests a crash, repeated failure, or security problem, clearly explain what risk it may pose and what concrete steps the user should take.

Now generate the explanation in the exact structure described in the system prompt.

Return your response as valid JSON with these exact keys:
{{
  "severity": "Safe | Minor | Warning | Critical",
  "short_title": "<clear 1-line title>",
  "what_happened": "<3-6 sentences>",
  "why_it_happens": "<2-4 sentences>",
  "what_to_do": "<bullet list with actions + when to worry>",
  "tech_notes": "<1-3 sentences for advanced users>"
}}
"""


def _load_event_knowledge_json() -> dict:
    """Load event knowledge from JSON file."""
    try:
        json_path = os.path.join(os.path.dirname(__file__), "event_knowledge.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load event_knowledge.json: {e}")
    return {}


# Load knowledge base at module level
_EVENT_KNOWLEDGE_JSON = _load_event_knowledge_json()


class EventExplainer(QObject):
    """
    Explains Windows events using local AI in clear, detailed language.

    Output format (JSON, ALWAYS returned):
    {
        "severity": str,         # Safe | Minor | Warning | Critical
        "short_title": str,      # Clear title (max 80 chars)
        "what_happened": str,    # 3-6 sentences
        "why_it_happens": str,   # 2-4 sentences
        "what_to_do": str,       # Bullet list with actions + when to worry
        "tech_notes": str        # 1-3 sentences with Event ID
    }
    """

    def __init__(
        self,
        llm_engine: LocalLLMEngine,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._llm = llm_engine
        self._cache: dict[str, dict[str, Any]] = {}
        self._knowledge_base = _EVENT_KNOWLEDGE_JSON
        logger.info("EventExplainer initialized (model loads on first use)")

    def _get_event_knowledge(self, event_id: int | str) -> str:
        """Get knowledge text for a specific event ID."""
        event_id_str = str(event_id)
        if event_id_str in self._knowledge_base:
            kb = self._knowledge_base[event_id_str]
            name = kb.get("name", "")
            desc = kb.get("description", "")
            cause = kb.get("typical_cause", "")
            parts = []
            if name:
                parts.append(f"Event Name: {name}")
            if desc:
                parts.append(f"Description: {desc}")
            if cause:
                parts.append(f"Typical Cause: {cause}")
            return " ".join(parts)
        return "No extra documentation available."

    def _make_cache_key(self, event: dict) -> str:
        """Create a cache key for an event based on log_name, provider, event_id, level, hash(message)."""
        key_parts = [
            event.get("log_name", ""),
            event.get("provider", event.get("source", "")),
            str(event.get("event_id", "")),
            event.get("level", ""),
        ]
        message = event.get("message", "")
        msg_hash = hashlib.md5(message.encode()).hexdigest()[:8]
        key_parts.append(msg_hash)
        return "|".join(key_parts)

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

    def build_event_prompt(self, event: dict) -> str:
        """
        Build the event data portion of the prompt using the new template.

        Args:
            event: Event dict with id, source, level, time, message, computer_name

        Returns:
            Formatted event data string with knowledge base context
        """
        event_id = event.get("event_id", "Unknown")
        source = event.get("provider", event.get("source", "Unknown"))
        level = event.get("level", "Information")
        time = event.get("time_created", "Unknown")
        log_name = event.get("log_name", "Unknown")
        computer_name = event.get("computer_name", "This computer")
        message = event.get("message", "No message available")

        # Truncate message if too long to reduce lag
        if len(message) > MAX_MESSAGE_INPUT_LENGTH:
            message = message[:MAX_MESSAGE_INPUT_LENGTH] + "..."

        # Get knowledge base info for this event ID
        event_knowledge = self._get_event_knowledge(event_id)

        return EVENT_PROMPT_TEMPLATE.format(
            level=level,
            source=source,
            log_name=log_name,
            event_id=event_id,
            timestamp=time,
            computer_name=computer_name,
            message=message,
            event_knowledge=event_knowledge
        )

    def _build_full_prompt(self, event: dict) -> str:
        """
        Build the complete prompt with system instructions and event data.
        """
        event_data = self.build_event_prompt(event)
        return f"{SENTINEL_EVENT_SYSTEM_PROMPT}\n\n{event_data}"

    def explain_event(self, event: dict) -> dict[str, Any]:
        """
        Explain a Windows event in SIMPLE, human-readable terms.

        Returns:
            JSON-style dict with severity, short_title, explanation, recommendation.
            ALWAYS returns a valid dict with all required keys.
        """
        try:
            # Check cache first
            cache_key = self._make_cache_key(event)
            if cache_key in self._cache:
                logger.debug(f"Event explanation cache hit: {cache_key[:30]}...")
                return self._cache[cache_key]

            # Use rule-based explanation (more reliable than DialoGPT for structured output)
            # DialoGPT is a conversational model, not instruction-following
            result = self._create_smart_explanation(event)

            # Cache result
            self._cache[cache_key] = result
            return result

        except Exception as e:
            logger.error(f"Event explanation failed: {e}")
            return self._create_fallback_explanation(event)

    def _parse_json_response(self, response: str, event: dict) -> dict[str, Any]:
        """
        Parse the LLM response as JSON.

        Falls back to text parsing if JSON parsing fails.
        Always returns a valid dict with all required keys.
        """
        if not response or not response.strip():
            return self._create_fallback_explanation(event)

        # Try to extract JSON from response
        try:
            # Look for JSON object in response
            json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                parsed = json.loads(json_str)

                # Validate and sanitize
                result = self._validate_and_sanitize(parsed, event)
                return result

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed: {e}")

        # Fall back to text parsing
        return self._parse_text_response(response, event)

    def _validate_and_sanitize(self, parsed: dict, event: dict) -> dict[str, Any]:
        """
        Validate and sanitize the parsed JSON response.

        Ensures all required fields are present and properly formatted.
        Returns the simplified 5-section format.
        """
        # Valid severity values
        valid_severities = ["Safe", "Minor", "Warning", "Critical"]

        # Get severity with validation
        severity = parsed.get("severity", "")
        if severity not in valid_severities:
            # Try to match case-insensitively
            severity_lower = severity.lower()
            if "critical" in severity_lower:
                severity = "Critical"
            elif "warning" in severity_lower:
                severity = "Warning"
            elif "minor" in severity_lower:
                severity = "Minor"
            else:
                # Infer from event level
                severity = self._infer_severity_from_level(event)

        # Get and truncate short_title
        short_title = parsed.get("short_title", "")
        if not short_title:
            short_title = self._generate_default_title(event)
        short_title = self._truncate(short_title, MAX_TITLE_LENGTH)

        # Get the sections with fallbacks (5-section format)
        what_happened = parsed.get("what_happened", parsed.get("explanation", ""))
        if not what_happened:
            what_happened = self._generate_what_happened(event)
        what_happened = self._truncate(what_happened, MAX_SECTION_LENGTH)

        why_it_happens = parsed.get("why_it_happens", "")
        if not why_it_happens:
            why_it_happens = self._generate_why_it_happens(event)
        why_it_happens = self._truncate(why_it_happens, MAX_SECTION_LENGTH)

        # Combine what_to_do and when_to_worry into a single section
        what_to_do = parsed.get("what_to_do", parsed.get("recommendation", ""))
        when_to_worry = parsed.get("when_to_worry", "")
        if not what_to_do:
            what_to_do = self._generate_what_to_do(severity)
        # Append when_to_worry if it exists and isn't already in what_to_do
        if when_to_worry and when_to_worry.strip() not in what_to_do:
            what_to_do = what_to_do.rstrip() + "\n\n**When to worry:** " + when_to_worry
        what_to_do = self._truncate(what_to_do, MAX_WHAT_TO_DO_LENGTH)

        tech_notes = parsed.get("tech_notes", "")
        if not tech_notes:
            tech_notes = self._generate_tech_notes(event)
        tech_notes = self._truncate(tech_notes, MAX_TECH_NOTES_LENGTH)

        return {
            "severity": severity,
            "short_title": short_title,
            "what_happened": what_happened,
            "why_it_happens": why_it_happens,
            "what_to_do": what_to_do,
            "tech_notes": tech_notes,
            # Keep legacy fields for backward compatibility
            "explanation": what_happened,
            "recommendation": what_to_do,
        }

    def _parse_text_response(self, response: str, event: dict) -> dict[str, Any]:
        """
        Parse a non-JSON text response by looking for key patterns.

        Used as fallback when JSON parsing fails.
        """
        result = {
            "severity": "",
            "short_title": "",
            "what_happened": "",
            "why_it_happens": "",
            "what_to_do": "",
            "tech_notes": "",
        }

        lines = response.strip().split("\n")

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            line_lower = line_stripped.lower()

            # Look for field markers
            if "severity" in line_lower and ":" in line_stripped:
                value = line_stripped.split(":", 1)[-1].strip().strip('"\'')
                result["severity"] = value
            elif "short_title" in line_lower and ":" in line_stripped:
                value = line_stripped.split(":", 1)[-1].strip().strip('"\'')
                result["short_title"] = value
            elif "what_happened" in line_lower and ":" in line_stripped:
                value = line_stripped.split(":", 1)[-1].strip().strip('"\'')
                result["what_happened"] = value
            elif "why_it_happens" in line_lower and ":" in line_stripped:
                value = line_stripped.split(":", 1)[-1].strip().strip('"\'')
                result["why_it_happens"] = value
            elif "what_to_do" in line_lower and ":" in line_stripped:
                value = line_stripped.split(":", 1)[-1].strip().strip('"\'')
                result["what_to_do"] = value
            elif "tech_notes" in line_lower and ":" in line_stripped:
                value = line_stripped.split(":", 1)[-1].strip().strip('"\'')
                result["tech_notes"] = value
            # Legacy field support
            elif "explanation" in line_lower and ":" in line_stripped:
                value = line_stripped.split(":", 1)[-1].strip().strip('"\'')
                result["what_happened"] = value
            elif "recommendation" in line_lower and ":" in line_stripped:
                value = line_stripped.split(":", 1)[-1].strip().strip('"\'')
                result["what_to_do"] = value

        # Validate and apply fallbacks
        return self._validate_and_sanitize(result, event)

    def _create_smart_explanation(self, event: dict) -> dict[str, Any]:
        """
        Create a smart explanation based on event level and content.
        Uses the simplified 5-section format for detailed, user-friendly explanations.
        """
        level = event.get("level", "INFO").upper()
        source = event.get("provider", event.get("source", "Windows"))
        message = event.get("message", "")[:500]
        event_id = event.get("event_id", "Unknown")
        
        # Truncate source if too long
        source_display = source[:30] + "..." if len(source) > 30 else source
        
        # Generate meaningful title based on content
        short_title = self._generate_smart_title(level, source_display, message, event_id)
        
        # Get knowledge base info
        kb_info = self._get_event_knowledge(event_id)
        has_kb = kb_info != "No extra documentation available."
        
        # Map Windows event levels to severity and generate all sections
        if level in ["CRITICAL", "FAILURE"]:
            severity = "Critical"
            what_happened = (
                f"A critical event was logged by '{source}' (Event ID: {event_id}). "
                f"This indicates a significant system problem that may affect stability or functionality. "
                f"The event message reports: {message[:200]}{'...' if len(message) > 200 else ''}. "
                "Critical events are relatively rare and typically require attention. "
                "Your computer has detected something important enough to flag as critical."
            )
            why_it_happens = (
                "Critical events usually occur when a major system component fails unexpectedly. "
                "Common causes include hardware failures, driver crashes, severe software bugs, "
                "or critical system resources becoming unavailable. "
                "Sometimes they can be triggered by malware or severe configuration problems."
            )
            what_to_do = (
                "• Save any open work immediately to prevent data loss.\n"
                "• Restart your computer to clear any temporary issues.\n"
                "• Check if the problem affects specific programs or is system-wide.\n"
                "• Run Windows Update to ensure you have the latest fixes.\n"
                "• If the problem persists, check Event Viewer for related errors.\n"
                "• Consider contacting technical support if this keeps happening.\n\n"
                "**When to worry:** This type of event is always worth investigating. "
                "If it happens once and your computer works fine after a restart, you're probably okay. "
                "If it happens repeatedly, seek professional help."
            )
        elif level == "ERROR":
            severity = "Warning"
            what_happened = (
                f"An error was recorded by '{source}' (Event ID: {event_id}). "
                f"This means an operation did not complete successfully. "
                f"The issue involves: {message[:200]}{'...' if len(message) > 200 else ''}. "
                "While errors indicate something went wrong, your computer should continue functioning. "
                "The specific feature or program affected may not work correctly until the issue is resolved."
            )
            why_it_happens = (
                "Errors can happen for many reasons - a program couldn't access a file it needed, "
                "a service failed to start properly, a network connection timed out, "
                "or there was a conflict between software components. "
                "Often these are temporary issues that resolve themselves."
            )
            what_to_do = (
                "• Check if you notice any problems with specific programs or features.\n"
                "• If this error affects a program you're using, try restarting that program.\n"
                "• Make sure your software is up to date through Windows Update.\n"
                f"• Searching for 'Event ID {event_id}' online can help identify solutions.\n"
                "• Try restarting your computer if the problem continues.\n\n"
                "**When to worry:** An occasional error is normal and usually nothing to worry about. "
                "If you see this error repeatedly (several times a day) or if it's causing visible problems, "
                "investigate further or seek help."
            )
        elif level == "WARNING":
            severity = "Minor"
            what_happened = (
                f"A warning was logged by '{source}' (Event ID: {event_id}). "
                f"This indicates something that may need attention but is not immediately critical. "
                f"The warning relates to: {message[:200]}{'...' if len(message) > 200 else ''}. "
                "Your system is functioning normally, but Windows wanted to make a note of this. "
                "Warnings help you catch potential issues before they become serious problems."
            )
            why_it_happens = (
                "Warnings are like yellow traffic lights - they tell you to be aware. "
                "Common causes include a service taking longer than expected to start, "
                "a resource running low (like disk space), or a non-critical component having issues. "
                "Windows logs these to help identify potential problems before they become serious."
            )
            what_to_do = (
                "• No immediate action is typically required for warnings.\n"
                "• Keep an eye on your system's behavior over the next few hours.\n"
                "• Ensure Windows Update is current to get the latest fixes.\n"
                "• If you see this warning frequently, it may indicate a developing issue.\n"
                "• Reference this event if you need to seek help later.\n\n"
                "**When to worry:** Isolated warnings are usually safe to ignore. "
                "If you see the same warning repeatedly or notice performance issues, investigate further."
            )
        elif level == "SUCCESS":
            severity = "Safe"
            what_happened = (
                f"A successful operation was recorded by '{source}' (Event ID: {event_id}). "
                f"This positive event confirms: {message[:200]}{'...' if len(message) > 200 else ''}. "
                "Success events are logged to track when important operations complete correctly. "
                "This is Windows confirming that something worked as expected."
            )
            why_it_happens = (
                "Windows logs success events to provide a record of completed operations. "
                "This is useful for verifying that updates, installations, or system tasks finished properly. "
                "It's part of normal system operation and helps with troubleshooting if problems occur later."
            )
            what_to_do = (
                "• No action needed - this event confirms successful completion.\n"
                "• You can use this as confirmation that the operation worked.\n"
                "• These events are useful for troubleshooting if you need to verify when something happened.\n\n"
                "**When to worry:** You don't need to worry about success events. They're purely informational."
            )
        else:  # INFO, INFORMATION, or unknown
            severity = "Safe"
            what_happened = (
                f"An informational event was logged by '{source}' (Event ID: {event_id}). "
                f"This is a routine log entry recording normal system activity. "
                f"The event records: {message[:200]}{'...' if len(message) > 200 else ''}. "
                "Windows continuously logs these for diagnostic and auditing purposes. "
                "This is just your computer keeping notes about its operations."
            )
            why_it_happens = (
                "Windows logs thousands of informational events as part of normal operation. "
                "They track system activities like services starting, users logging in, "
                "or background tasks completing. "
                "These events help track system behavior and can be useful for troubleshooting."
            )
            what_to_do = (
                "• No action needed - this is normal system activity.\n"
                "• These events are logged for record-keeping and diagnostics.\n"
                "• You can safely ignore informational events unless troubleshooting.\n\n"
                "**When to worry:** You don't need to worry about informational events. "
                "They're part of normal Windows operation and don't indicate problems."
            )
        
        # Generate tech notes
        tech_notes = self._generate_tech_notes(event)
        
        return {
            "severity": severity,
            "short_title": self._truncate(short_title, MAX_TITLE_LENGTH),
            "what_happened": self._truncate(what_happened, MAX_SECTION_LENGTH),
            "why_it_happens": self._truncate(why_it_happens, MAX_SECTION_LENGTH),
            "what_to_do": self._truncate(what_to_do, MAX_WHAT_TO_DO_LENGTH),
            "tech_notes": self._truncate(tech_notes, MAX_TECH_NOTES_LENGTH),
            # Keep legacy fields for backward compatibility
            "explanation": self._truncate(what_happened, MAX_SECTION_LENGTH),
            "recommendation": self._truncate(what_to_do, MAX_WHAT_TO_DO_LENGTH),
        }

    def _generate_smart_title(self, level: str, source: str, message: str, event_id) -> str:
        """Generate a clear, descriptive title based on event content."""
        msg_lower = message.lower()
        
        if "crash" in msg_lower or "stopped unexpectedly" in msg_lower:
            return f"Application Crash Detected (ID: {event_id})"
        elif "hang" in msg_lower or "not responding" in msg_lower:
            return f"Application Stopped Responding (ID: {event_id})"
        elif "login" in msg_lower or "logon" in msg_lower:
            if "failed" in msg_lower:
                return f"Failed Login Attempt (ID: {event_id})"
            return f"User Login Event (ID: {event_id})"
        elif "logout" in msg_lower or "logoff" in msg_lower:
            return f"User Logout Event (ID: {event_id})"
        elif "update" in msg_lower:
            if "success" in msg_lower or "installed" in msg_lower:
                return f"Update Installed Successfully (ID: {event_id})"
            elif "failed" in msg_lower:
                return f"Update Failed (ID: {event_id})"
            return f"Windows Update Activity (ID: {event_id})"
        elif "firewall" in msg_lower:
            if "blocked" in msg_lower:
                return f"Firewall Blocked Connection (ID: {event_id})"
            return f"Firewall Event (ID: {event_id})"
        elif "disk" in msg_lower or "drive" in msg_lower:
            if "error" in msg_lower:
                return f"Disk Error Detected (ID: {event_id})"
            return f"Disk Activity Event (ID: {event_id})"
        elif "service" in msg_lower:
            if "start" in msg_lower:
                return f"Service Started: {source} (ID: {event_id})"
            elif "stop" in msg_lower:
                return f"Service Stopped: {source} (ID: {event_id})"
        
        # Fallback based on level
        level_titles = {
            "CRITICAL": f"Critical Event: {source} (ID: {event_id})",
            "FAILURE": f"Failure Event: {source} (ID: {event_id})",
            "ERROR": f"Error: {source} (ID: {event_id})",
            "WARNING": f"Warning: {source} (ID: {event_id})",
            "SUCCESS": f"Success: {source} (ID: {event_id})",
        }
        return level_titles.get(level, f"Event from {source} (ID: {event_id})")

    def _infer_severity_from_level(self, event: dict) -> str:
        """Infer severity from event level."""
        level = event.get("level", "Information").upper()
        if level in ["CRITICAL", "FAILURE"]:
            return "Critical"
        elif level == "ERROR":
            return "Warning"
        elif level == "WARNING":
            return "Minor"
        else:
            return "Safe"

    def _generate_default_title(self, event: dict) -> str:
        """Generate a default short title based on event."""
        level = event.get("level", "Information")
        source = event.get("provider", event.get("source", "Windows"))
        event_id = event.get("event_id", "Unknown")
        if len(source) > 20:
            source = source[:17] + "..."

        if level == "Critical":
            return f"Critical issue from {source} (ID: {event_id})"
        elif level == "Error":
            return f"Error from {source} (ID: {event_id})"
        elif level == "Warning":
            return f"Notice from {source} (ID: {event_id})"
        else:
            return f"System message from {source} (ID: {event_id})"

    def _generate_what_happened(self, event: dict) -> str:
        """Generate 'What happened' section (2-4 sentences)."""
        level = event.get("level", "Information")
        source = event.get("provider", event.get("source", "Windows"))
        event_id = event.get("event_id", "Unknown")
        message = event.get("message", "")[:150]

        if level == "Critical":
            return (
                f"A critical issue was recorded by {source} (Event ID: {event_id}). "
                f"This indicates something serious happened that may affect your computer's stability. "
                f"The event message: {message}{'...' if len(message) >= 150 else ''}."
            )
        elif level == "Error":
            return (
                f"An error was logged by {source} (Event ID: {event_id}). "
                f"This means an operation didn't complete as expected. "
                f"The event details: {message}{'...' if len(message) >= 150 else ''}."
            )
        elif level == "Warning":
            return (
                f"A warning was recorded by {source} (Event ID: {event_id}). "
                f"Windows noticed something unusual but not necessarily problematic. "
                f"Details: {message}{'...' if len(message) >= 150 else ''}."
            )
        else:
            return (
                f"An informational message was logged by {source} (Event ID: {event_id}). "
                f"This is routine system activity recorded for reference. "
                f"Details: {message}{'...' if len(message) >= 150 else ''}."
            )

    def _generate_why_it_happens(self, event: dict) -> str:
        """Generate 'Why this usually happens' section (2-4 sentences)."""
        level = event.get("level", "Information")
        event_id = event.get("event_id", "Unknown")
        
        # Check knowledge base first
        kb_info = self._get_event_knowledge(event_id)
        if "Typical Cause:" in kb_info:
            return kb_info.split("Typical Cause:")[-1].strip()

        if level == "Critical":
            return (
                "Critical events usually occur when a major system component fails unexpectedly. "
                "Common causes include hardware failures, driver crashes, or severe software bugs. "
                "Sometimes they can be triggered by malware or critical resource exhaustion."
            )
        elif level == "Error":
            return (
                "Errors can happen for many reasons - a program couldn't access a file, "
                "a service failed to start, or a network connection timed out. "
                "Often these are temporary issues that resolve themselves after a restart."
            )
        elif level == "Warning":
            return (
                "Warnings typically occur when Windows detects something that might become a problem. "
                "Common causes include low resources, slow responses from components, "
                "or minor configuration issues that Windows is handling automatically."
            )
        else:
            return (
                "Windows logs informational events as part of normal operation. "
                "They record system activities like services starting, configuration changes, "
                "or background tasks completing successfully."
            )

    def _generate_impact(self, event: dict, severity: str) -> str:
        """Generate 'Impact on the user' section (1-3 sentences)."""
        if severity == "Critical":
            return (
                "Your computer may become unstable or certain features may stop working. "
                "There's a possibility of data loss if you don't save your work. "
                "You should address this issue to prevent further problems."
            )
        elif severity == "Warning":
            return (
                "The specific operation that failed may not have completed successfully. "
                "You might notice a program not working correctly or a feature being unavailable. "
                "Your overall computer should still function normally."
            )
        elif severity == "Minor":
            return (
                "Typically, this has minimal immediate impact on your daily use. "
                "Your computer continues to work normally."
            )
        else:
            return "None - this is normal system activity that doesn't indicate any problems."

    def _generate_what_to_do(self, severity: str) -> str:
        """Generate 'What you should do' section (3-6 bullet points)."""
        if severity == "Critical":
            return (
                "• Save any open work immediately to prevent data loss.\n"
                "• Restart your computer to clear any temporary issues.\n"
                "• Check if the problem affects specific programs or is system-wide.\n"
                "• Run Windows Update to ensure you have the latest fixes.\n"
                "• If the problem persists, check Event Viewer for related errors.\n"
                "• Consider contacting technical support if this keeps happening."
            )
        elif severity == "Warning":
            return (
                "• Check if you notice any problems with specific programs or features.\n"
                "• If this affects a program you're using, try restarting that program.\n"
                "• Make sure your software is up to date through Windows Update.\n"
                "• Try restarting your computer if the problem continues.\n"
                "• Search online for the Event ID if you need more specific solutions."
            )
        elif severity == "Minor":
            return (
                "• No immediate action is typically required.\n"
                "• Keep an eye on your system's behavior over the next few hours.\n"
                "• Ensure Windows Update is current to get the latest fixes.\n"
                "• Reference this event if you need to seek help later."
            )
        else:
            return (
                "• No action needed - this is normal system activity.\n"
                "• These events are logged for record-keeping and diagnostics.\n"
                "• You can safely ignore informational events unless troubleshooting."
            )

    def _generate_when_to_worry(self, severity: str) -> str:
        """Generate 'When to worry and ask for help' section (1-3 sentences)."""
        if severity == "Critical":
            return (
                "This type of event is always worth investigating. "
                "If it happens once and your computer works fine after a restart, you may be okay. "
                "If it happens repeatedly, you should seek professional help."
            )
        elif severity == "Warning":
            return (
                "An occasional error is normal and usually nothing to worry about. "
                "If you see this repeatedly (several times a day) or if it's causing visible problems, "
                "you should investigate further or seek help."
            )
        elif severity == "Minor":
            return (
                "Isolated warnings are usually safe to ignore. "
                "If you see the same warning repeatedly or notice performance issues, "
                "it's worth investigating further."
            )
        else:
            return (
                "You don't need to worry about informational events. "
                "They're part of normal Windows operation and don't indicate problems."
            )

    def _generate_tech_notes(self, event: dict) -> str:
        """Generate 'Technical notes' section (1-3 sentences with Event ID)."""
        event_id = event.get("event_id", "Unknown")
        source = event.get("provider", event.get("source", "Windows"))
        level = event.get("level", "Information")
        log_name = event.get("log_name", "")
        
        # Check knowledge base for friendly name
        kb_info = self._get_event_knowledge(event_id)
        if kb_info != "No extra documentation available." and "Event Name:" in kb_info:
            event_name = kb_info.split("Event Name:")[-1].split("Description:")[0].strip()
            return (
                f"Event ID: {event_id} ({event_name}). "
                f"Source: {source}. Level: {level}. "
                f"Log: {log_name or 'Windows Event Log'}."
            )
        
        return (
            f"Event ID: {event_id}. Source: {source}. Level: {level}. "
            f"Log: {log_name or 'Windows Event Log'}. "
            "Search for this Event ID online for more specific information."
        )

    def _generate_default_recommendation(self, severity: str) -> str:
        """Generate a default recommendation based on severity (legacy support)."""
        return self._generate_what_to_do(severity)

    def _generate_default_explanation(self, event: dict) -> str:
        """Generate a default explanation based on event (legacy support)."""
        return self._generate_what_happened(event)

    def _create_fallback_explanation(self, event: dict) -> dict[str, Any]:
        """
        Create a safe fallback explanation when AI fails or returns invalid data.
        Uses the simplified 5-section format.
        """
        severity = self._infer_severity_from_level(event)
        what_happened = self._generate_what_happened(event)
        what_to_do = self._generate_what_to_do(severity)
        
        return {
            "severity": severity,
            "short_title": self._generate_default_title(event),
            "what_happened": what_happened,
            "why_it_happens": self._generate_why_it_happens(event),
            "what_to_do": what_to_do,
            "tech_notes": self._generate_tech_notes(event),
            # Legacy fields for backward compatibility
            "explanation": what_happened,
            "recommendation": what_to_do,
        }

    def clear_cache(self) -> None:
        """Clear the explanation cache."""
        self._cache.clear()
        logger.info("Event explanation cache cleared")

    def get_cache_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return {"cached_explanations": len(self._cache)}


# Singleton instance
_event_explainer: Optional[EventExplainer] = None


def get_event_explainer(llm_engine: LocalLLMEngine) -> EventExplainer:
    """Get the singleton EventExplainer instance."""
    global _event_explainer
    if _event_explainer is None:
        _event_explainer = EventExplainer(llm_engine)
    return _event_explainer
