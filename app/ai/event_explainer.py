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

# Maximum line length for any output
MAX_LINE_LENGTH = 200
# Maximum number of recommended actions
MAX_ACTIONS = 3


class EventExplainer(QObject):
    """
    Explains Windows events using local AI in SIMPLE language.

    Output format:
    {
        "short_summary": str,           # One simple sentence
        "what_it_means": str,           # Is this a problem? (one sentence)
        "recommended_actions": [str],   # Up to 3 simple actions
        "severity_score": int,          # 0-10
        "severity_label": str           # Info/Low/Medium/High/Critical
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
        logger.info("EventExplainer initialized (model loads on first use)")

    def _make_cache_key(self, event: dict) -> str:
        """Create a cache key for an event."""
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

    def _truncate(self, text: str, max_len: int = MAX_LINE_LENGTH) -> str:
        """Truncate text to max length."""
        if not text:
            return text
        text = text.strip()
        if len(text) > max_len:
            return text[: max_len - 3] + "..."
        return text

    def explain_event(self, event: dict) -> dict[str, Any]:
        """
        Explain a Windows event in SIMPLE, human-readable terms.

        Returns:
            Structured explanation dict with simple language.
        """
        # Check cache first
        cache_key = self._make_cache_key(event)
        if cache_key in self._cache:
            logger.debug(f"Event explanation cache hit: {cache_key[:30]}...")
            return self._cache[cache_key]

        # Build prompt
        prompt = self._build_simple_prompt(event)

        # Generate explanation
        try:
            response = self._llm.generate_single_turn(prompt, max_tokens=300)
            result = self._parse_simple_response(response, event)
        except Exception as e:
            logger.error(f"Event explanation failed: {e}")
            result = self._default_explanation(event)

        # Cache result
        self._cache[cache_key] = result
        return result

    def _build_simple_prompt(self, event: dict) -> str:
        """Build a prompt that asks for SIMPLE, non-technical language."""
        log_name = event.get("log_name", "Unknown")
        provider = event.get("provider", event.get("source", "Unknown"))
        event_id = event.get("event_id", "Unknown")
        level = event.get("level", "Information")
        message = event.get("message", "No message available")

        # Truncate message if too long
        if len(message) > 400:
            message = message[:400] + "..."

        return f"""You are explaining a computer message to someone who is NOT a computer expert.
Use SIMPLE words. Imagine you're talking to a 14-year-old.

RULES:
- NO technical words like "heap", "RPC", "exception", "registry", "thread"
- If you must use a technical word, explain it in simple words
- Keep sentences SHORT
- Be reassuring - don't scare the user

Windows event information:
- Log: {log_name}
- Source: {provider}
- Event ID: {event_id}
- Level: {level}
- Message: {message}

Answer in EXACTLY this format:

SUMMARY:
<Write ONE simple sentence explaining what happened>

IS_IT_A_PROBLEM:
<Write ONE sentence like: "No, this is normal." or "Yes, this may cause problems.">

ACTIONS:
- <First action, or "No action needed.">
- <Second action if needed>
- <Third action if needed>

SEVERITY:
<A number from 0 to 10, where 0 is "totally fine" and 10 is "very serious">"""

    def _parse_simple_response(self, response: str, event: dict) -> dict[str, Any]:
        """Parse the LLM response into the simplified format."""
        result = {
            "short_summary": "",
            "what_it_means": "",
            "recommended_actions": [],
            "severity_score": 0,
            "severity_label": "Info",
        }

        try:
            lines = response.strip().split("\n")
            current_section = None
            actions_buffer = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                line_upper = line.upper()

                # Detect section headers
                if line_upper.startswith("SUMMARY:"):
                    content = line.split(":", 1)[-1].strip()
                    result["short_summary"] = self._truncate(content)
                    current_section = "summary"
                elif line_upper.startswith("IS_IT_A_PROBLEM:") or line_upper.startswith(
                    "IS IT A PROBLEM:"
                ):
                    content = line.split(":", 1)[-1].strip()
                    result["what_it_means"] = self._truncate(content)
                    current_section = "problem"
                elif line_upper.startswith("ACTIONS:"):
                    current_section = "actions"
                elif line_upper.startswith("SEVERITY:"):
                    # Extract number
                    numbers = re.findall(r"\d+", line)
                    if numbers:
                        score = int(numbers[0])
                        result["severity_score"] = min(10, max(0, score))
                    current_section = "severity"
                elif line.startswith("-") or line.startswith("•"):
                    # Action item
                    action = line.lstrip("-•").strip()
                    if action and len(actions_buffer) < MAX_ACTIONS:
                        actions_buffer.append(self._truncate(action))
                elif current_section == "summary" and not result["short_summary"]:
                    result["short_summary"] = self._truncate(line)
                elif current_section == "problem" and not result["what_it_means"]:
                    result["what_it_means"] = self._truncate(line)
                elif current_section == "actions" and len(actions_buffer) < MAX_ACTIONS:
                    # Non-bulleted action line
                    if line and not line.upper().startswith("SEVERITY"):
                        actions_buffer.append(self._truncate(line))

            # Set actions (limit to MAX_ACTIONS)
            if actions_buffer:
                result["recommended_actions"] = actions_buffer[:MAX_ACTIONS]

            # Set severity label based on score (new simpler thresholds)
            result["severity_label"] = self._score_to_label(result["severity_score"])

            # Fallback: use event level to infer severity if not extracted
            if result["severity_score"] == 0 and not result["short_summary"]:
                return self._default_explanation(event)

            # If severity is 0 but we got a summary, keep it but check level
            if result["severity_score"] == 0:
                level = event.get("level", "").upper()
                if level in ("CRITICAL", "ERROR"):
                    result["severity_score"] = 7
                    result["severity_label"] = "High"
                elif level == "WARNING":
                    result["severity_score"] = 4
                    result["severity_label"] = "Low"
                else:
                    result["severity_score"] = 1
                    result["severity_label"] = "Info"

            # Ensure we have content
            if not result["short_summary"]:
                result["short_summary"] = "Windows recorded a system message."

            if not result["what_it_means"]:
                result["what_it_means"] = (
                    "This is probably fine unless it happens a lot."
                )

            if not result["recommended_actions"]:
                if result["severity_score"] >= 5:
                    result["recommended_actions"] = [
                        "If this keeps happening, restart your computer.",
                        "If the problem continues, ask someone for help.",
                    ]
                else:
                    result["recommended_actions"] = ["No action needed."]

        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return self._default_explanation(event)

        return result

    def _score_to_label(self, score: int) -> str:
        """Convert severity score to simple label using new thresholds."""
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

    def _default_explanation(self, event: dict) -> dict[str, Any]:
        """Provide a simple default explanation when AI fails."""
        level = event.get("level", "Information").upper()
        source = event.get("provider", event.get("source", "Windows"))

        # Make source user-friendly
        if source and len(source) > 30:
            source = source[:27] + "..."

        if level in ("CRITICAL",):
            return {
                "short_summary": f"Something serious happened with {source}.",
                "what_it_means": "Yes, this needs attention. Your computer might have a problem.",
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
                "recommended_actions": [
                    "No action needed right now.",
                    "If you see this message many times, restart your PC.",
                ],
                "severity_score": 3,
                "severity_label": "Low",
            }
        else:
            return {
                "short_summary": f"Windows recorded a normal message from {source}.",
                "what_it_means": "No, this is just a normal system message.",
                "recommended_actions": ["No action needed."],
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
