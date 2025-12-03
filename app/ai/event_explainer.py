"""
Event Explainer - AI-powered Windows event explanation.

Uses LocalLLMEngine to provide human-readable explanations
of Windows event log entries. 100% local, no network calls.

OUTPUT FORMAT:
All explanations use SIMPLE language suitable for non-technical users.
No jargon, no hex codes, no acronyms without explanation.
"""

import hashlib
import logging
import re
from typing import Any, Optional

from PySide6.QtCore import QObject

from .local_llm_engine import LocalLLMEngine

logger = logging.getLogger(__name__)

# Maximum lengths for output fields
MAX_SUMMARY_LENGTH = 160
MAX_FIELD_LENGTH = 200
MAX_ACTIONS = 3


class EventExplainer(QObject):
    """
    Explains Windows events using local AI in SIMPLE language.

    Output format (ALWAYS returned):
    {
        "short_summary": str,           # One simple sentence (max 160 chars)
        "what_it_means": str,           # Is this a problem? (one sentence)
        "likely_cause": str,            # Possible cause (one sentence)
        "recommended_actions": [str],   # Up to 3 simple actions
        "severity_score": int,          # 0-10
        "severity_label": str           # Info/Low/Medium/High/Critical
    }
    """

    # Default fallback values
    DEFAULT_SUMMARY = "Windows recorded a system event."
    DEFAULT_MEANING = "This is not usually serious unless it keeps happening."
    DEFAULT_CAUSE = "Unknown."
    DEFAULT_ACTIONS = [
        "If this message appears many times, restart your PC or ask a technician."
    ]

    def __init__(
        self,
        llm_engine: LocalLLMEngine,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._llm = llm_engine
        self._cache: dict[str, dict[str, Any]] = {}
        logger.info("EventExplainer initialized (model loads on first use)")

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

    def _truncate(self, text: str, max_len: int = MAX_FIELD_LENGTH) -> str:
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

    def explain_event(self, event: dict) -> dict[str, Any]:
        """
        Explain a Windows event in SIMPLE, human-readable terms.

        Returns:
            Structured explanation dict with simple language.
            ALWAYS contains all required keys with valid values.
        """
        try:
            # Check cache first
            cache_key = self._make_cache_key(event)
            if cache_key in self._cache:
                logger.debug(f"Event explanation cache hit: {cache_key[:30]}...")
                return self._cache[cache_key]

            # Build prompt
            prompt = self._build_prompt(event)

            # Generate explanation
            response = self._llm.generate_single_turn(prompt, max_tokens=350)
            result = self._parse_response(response, event)

            # Cache result
            self._cache[cache_key] = result
            return result

        except Exception as e:
            logger.error(f"Event explanation failed: {e}")
            return self._create_fallback_explanation(event)

    def _build_prompt(self, event: dict) -> str:
        """
        Build a prompt that enforces simple, non-technical language.

        The prompt instructs the model to:
        - Use simple language (like explaining to a 14-year-old)
        - Base explanation on given fields only
        - Not guess or invent information
        - Not mention AI or model
        - Use the exact FIXED STRUCTURE
        """
        log_name = event.get("log_name", "Unknown")
        provider = event.get("provider", event.get("source", "Unknown"))
        event_id = event.get("event_id", "Unknown")
        level = event.get("level", "Information")
        message = event.get("message", "No message available")
        time_created = event.get("time_created", "Unknown")

        # Truncate message if too long
        if len(message) > 400:
            message = message[:400] + "..."

        return f"""You are explaining a Windows computer message to a HOME USER who is NOT a computer expert.

TARGET AUDIENCE: Non-technical person (like a 14-year-old).

STYLE RULES:
- Use VERY simple language
- Short sentences only
- NO low-level technical terms (no "heap", "registry", "thread", "RPC", "exception", "handle")
- If you must use a technical word, explain it briefly in brackets
- NEVER guess about the user's hardware, software, or actions
- NEVER mention "AI" or "model" in your answer
- Base your explanation ONLY on the information below
- If the cause is not clear, say "Unknown" - do NOT invent reasons

WINDOWS EVENT DATA:
- Log: {log_name}
- Source: {provider}
- Event ID: {event_id}
- Level: {level}
- Time: {time_created}
- Message: {message}

ANSWER IN EXACTLY THIS FORMAT (keep the labels exactly as shown):

SUMMARY:
<one sentence explaining what happened, max 120 characters>

IS_IT_A_PROBLEM:
<one sentence like: "No, this is normal." or "Yes, this may cause problems.">

CAUSE:
<one short sentence explaining why this happened, or "Unknown" if not clear>

ACTIONS:
- <first thing to do, or "No action needed.">
- <optional second action>
- <optional third action>

SEVERITY:
<integer from 0 to 10, where 0 = totally fine, 10 = very serious>"""

    def _parse_response(self, response: str, event: dict) -> dict[str, Any]:
        """
        Robustly parse the LLM response into the required structure.

        Always returns a valid dict with all required keys.
        Uses fallbacks for missing or invalid values.
        """
        result = {
            "short_summary": "",
            "what_it_means": "",
            "likely_cause": "",
            "recommended_actions": [],
            "severity_score": 0,
            "severity_label": "Info",
        }

        if not response or not response.strip():
            return self._create_fallback_explanation(event)

        try:
            lines = response.strip().split("\n")
            current_section = None
            actions_buffer = []

            for line in lines:
                line_stripped = line.strip()
                if not line_stripped:
                    continue

                line_upper = line_stripped.upper()

                # Detect section headers
                if line_upper.startswith("SUMMARY:"):
                    content = line_stripped.split(":", 1)[-1].strip()
                    result["short_summary"] = self._truncate(
                        content, MAX_SUMMARY_LENGTH
                    )
                    current_section = "summary"

                elif line_upper.startswith("IS_IT_A_PROBLEM:") or line_upper.startswith(
                    "IS IT A PROBLEM:"
                ):
                    content = line_stripped.split(":", 1)[-1].strip()
                    result["what_it_means"] = self._truncate(content, MAX_FIELD_LENGTH)
                    current_section = "problem"

                elif line_upper.startswith("CAUSE:"):
                    content = line_stripped.split(":", 1)[-1].strip()
                    result["likely_cause"] = self._truncate(content, MAX_FIELD_LENGTH)
                    current_section = "cause"

                elif line_upper.startswith("ACTIONS:"):
                    current_section = "actions"

                elif line_upper.startswith("SEVERITY:"):
                    # Extract integer
                    numbers = re.findall(r"\d+", line_stripped)
                    if numbers:
                        score = int(numbers[0])
                        result["severity_score"] = min(10, max(0, score))
                    current_section = "severity"

                elif line_stripped.startswith("-") or line_stripped.startswith("•"):
                    # Action item
                    action = line_stripped.lstrip("-•").strip()
                    if action and len(actions_buffer) < MAX_ACTIONS:
                        actions_buffer.append(self._truncate(action, MAX_FIELD_LENGTH))

                else:
                    # Continuation line for current section
                    if current_section == "summary" and not result["short_summary"]:
                        result["short_summary"] = self._truncate(
                            line_stripped, MAX_SUMMARY_LENGTH
                        )
                    elif current_section == "problem" and not result["what_it_means"]:
                        result["what_it_means"] = self._truncate(
                            line_stripped, MAX_FIELD_LENGTH
                        )
                    elif current_section == "cause" and not result["likely_cause"]:
                        result["likely_cause"] = self._truncate(
                            line_stripped, MAX_FIELD_LENGTH
                        )

            # Set actions
            if actions_buffer:
                result["recommended_actions"] = actions_buffer[:MAX_ACTIONS]

            # Apply severity label mapping
            result["severity_label"] = self._score_to_label(result["severity_score"])

            # Validate and apply fallbacks
            result = self._apply_fallbacks(result, event)

            return result

        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return self._create_fallback_explanation(event)

    def _score_to_label(self, score: int) -> str:
        """
        Convert severity score to label.

        Mapping:
        - 0-2 → Info
        - 3-4 → Low
        - 5-6 → Medium
        - 7-8 → High
        - 9-10 → Critical
        """
        if score >= 9:
            return "Critical"
        elif score >= 7:
            return "High"
        elif score >= 5:
            return "Medium"
        elif score >= 3:
            return "Low"
        else:
            return "Info"

    def _apply_fallbacks(self, result: dict, event: dict) -> dict:
        """
        Ensure all required fields have valid values.

        Uses event-level-based defaults when fields are missing.
        """
        level = event.get("level", "Information").upper()

        # Fallback for short_summary
        if not result["short_summary"]:
            source = event.get("provider", event.get("source", "Windows"))
            if len(source) > 25:
                source = source[:22] + "..."
            result["short_summary"] = f"Windows recorded a message from {source}."

        # Fallback for what_it_means
        if not result["what_it_means"]:
            result["what_it_means"] = self.DEFAULT_MEANING

        # Fallback for likely_cause
        if not result["likely_cause"]:
            result["likely_cause"] = self.DEFAULT_CAUSE

        # Fallback for recommended_actions
        if not result["recommended_actions"]:
            result["recommended_actions"] = list(self.DEFAULT_ACTIONS)

        # Adjust severity based on event level if score is 0 but we got a summary
        if result["severity_score"] == 0:
            if level in ("CRITICAL",):
                result["severity_score"] = 9
                result["severity_label"] = "Critical"
            elif level == "ERROR":
                result["severity_score"] = 6
                result["severity_label"] = "Medium"
            elif level == "WARNING":
                result["severity_score"] = 4
                result["severity_label"] = "Low"
            else:
                result["severity_score"] = 1
                result["severity_label"] = "Info"

        return result

    def _create_fallback_explanation(self, event: dict) -> dict[str, Any]:
        """
        Create a safe fallback explanation when AI fails or returns invalid data.

        Uses the event level to determine appropriate messaging.
        """
        level = event.get("level", "Information").upper()
        source = event.get("provider", event.get("source", "Windows"))

        # Truncate long source names
        if source and len(source) > 25:
            source = source[:22] + "..."

        if level == "CRITICAL":
            return {
                "short_summary": f"Something serious happened with {source}.",
                "what_it_means": "Yes, this needs attention. Your computer might have a problem.",
                "likely_cause": "Unknown.",
                "recommended_actions": [
                    "Restart your computer.",
                    "If this keeps happening, contact a technician.",
                ],
                "severity_score": 9,
                "severity_label": "Critical",
            }
        elif level == "ERROR":
            return {
                "short_summary": f"Something went wrong with {source}.",
                "what_it_means": "This might cause problems, but your PC should still work.",
                "likely_cause": "Unknown.",
                "recommended_actions": [
                    "If this keeps happening, restart your computer.",
                    "If the problem continues, ask someone for help.",
                ],
                "severity_score": 6,
                "severity_label": "Medium",
            }
        elif level == "WARNING":
            return {
                "short_summary": f"Windows noticed something unusual from {source}.",
                "what_it_means": "This is probably fine, but keep an eye on it.",
                "likely_cause": "Unknown.",
                "recommended_actions": [
                    "No action needed right now.",
                    "If you see this message many times, restart your PC.",
                ],
                "severity_score": 4,
                "severity_label": "Low",
            }
        else:
            return {
                "short_summary": self.DEFAULT_SUMMARY,
                "what_it_means": self.DEFAULT_MEANING,
                "likely_cause": self.DEFAULT_CAUSE,
                "recommended_actions": list(self.DEFAULT_ACTIONS),
                "severity_score": 1,
                "severity_label": "Info",
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
