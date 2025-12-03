"""
Event Explainer - AI-powered Windows event explanation.

Uses LocalLLMEngine to provide human-readable explanations
of Windows event log entries. 100% local, no network calls.
"""

import hashlib
import json
import logging
import re
from typing import Any, Optional

from PySide6.QtCore import QObject

from .local_llm_engine import LocalLLMEngine

logger = logging.getLogger(__name__)


class EventExplainer(QObject):
    """
    Explains Windows events using local AI.

    Provides structured explanations including:
    - Summary
    - What it means
    - Likely causes
    - Impact assessment
    - Recommended actions
    - Severity score (0-10)
    """

    def __init__(
        self,
        llm_engine: LocalLLMEngine,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._llm = llm_engine
        self._cache: dict[str, dict[str, Any]] = {}
        logger.info(
            f"EventExplainer initialized (LLM mode: {'transformers' if llm_engine.is_available else 'fallback'})"
        )

    def _make_cache_key(self, event: dict) -> str:
        """Create a cache key for an event."""
        # Use relevant fields to create unique key
        key_parts = [
            event.get("log_name", ""),
            event.get("provider", event.get("source", "")),
            str(event.get("event_id", "")),
            event.get("level", ""),
        ]

        # Add message hash for uniqueness
        message = event.get("message", "")
        msg_hash = hashlib.md5(message.encode()).hexdigest()[:8]
        key_parts.append(msg_hash)

        return "|".join(key_parts)

    def explain_event(self, event: dict) -> dict[str, Any]:
        """
        Explain a Windows event in human-readable terms.

        Args:
            event: Event dictionary with fields like:
                - log_name, provider/source, event_id, level
                - message, time_created/timestamp

        Returns:
            Structured explanation dict with:
                - short_summary: 1-2 line summary
                - what_it_means: Explanation of the event
                - likely_cause: Probable cause
                - impact: System impact assessment
                - recommended_actions: List of action strings
                - severity_score: 0-10 integer
                - severity_label: Info/Low/Medium/High/Critical
        """
        # Check cache first
        cache_key = self._make_cache_key(event)
        if cache_key in self._cache:
            logger.debug(f"Event explanation cache hit: {cache_key[:30]}...")
            return self._cache[cache_key]

        # Build prompt
        prompt = self._build_prompt(event)

        # Generate explanation
        try:
            response = self._llm.generate_single_turn(prompt, max_tokens=300)
            result = self._parse_response(response, event)
        except Exception as e:
            logger.error(f"Event explanation failed: {e}")
            result = self._default_explanation(event)

        # Cache result
        self._cache[cache_key] = result
        return result

    def _build_prompt(self, event: dict) -> str:
        """Build the prompt for the LLM."""
        log_name = event.get("log_name", "Unknown")
        provider = event.get("provider", event.get("source", "Unknown"))
        event_id = event.get("event_id", "Unknown")
        level = event.get("level", "Information")
        time_created = event.get("time_created", event.get("timestamp", "Unknown"))
        message = event.get("message", "No message available")

        # Truncate message if too long
        if len(message) > 500:
            message = message[:500] + "..."

        return f"""You are a local security assistant. Explain this Windows event in simple terms for a non-expert user.

Event log: {log_name}
Source: {provider}
Event ID: {event_id}
Level: {level}
Time: {time_created}
Message:
{message}

Provide a clear explanation with:
- Short summary (1-2 lines)
- What it means
- Possible causes
- Impact on the system
- Recommended actions (as a list)
- Overall severity from 0 to 10

Keep the explanation concise and actionable."""

    def _parse_response(self, response: str, event: dict) -> dict[str, Any]:
        """Parse the LLM response into structured format."""
        result = {
            "short_summary": "",
            "what_it_means": "",
            "likely_cause": "",
            "impact": "",
            "recommended_actions": [],
            "severity_score": 0,
            "severity_label": "Info",
        }

        try:
            lines = response.strip().split("\n")

            # Try to extract structured data
            current_section = None
            actions_buffer = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                line_lower = line.lower()

                # Detect section headers
                if "summary" in line_lower and ":" in line:
                    result["short_summary"] = line.split(":", 1)[-1].strip()
                    current_section = "summary"
                elif "what it means" in line_lower or "meaning" in line_lower:
                    if ":" in line:
                        result["what_it_means"] = line.split(":", 1)[-1].strip()
                    current_section = "meaning"
                elif "cause" in line_lower:
                    if ":" in line:
                        result["likely_cause"] = line.split(":", 1)[-1].strip()
                    current_section = "cause"
                elif "impact" in line_lower:
                    if ":" in line:
                        result["impact"] = line.split(":", 1)[-1].strip()
                    current_section = "impact"
                elif "action" in line_lower or "recommend" in line_lower:
                    current_section = "actions"
                elif "severity" in line_lower:
                    # Try to extract severity score
                    numbers = re.findall(r"\d+", line)
                    if numbers:
                        score = int(numbers[0])
                        result["severity_score"] = min(10, max(0, score))
                    current_section = "severity"
                elif line.startswith("-") or line.startswith("•"):
                    # Action item
                    action = line.lstrip("-•").strip()
                    if action:
                        actions_buffer.append(action)
                elif current_section == "actions" and line:
                    actions_buffer.append(line)
                elif current_section == "meaning" and not result["what_it_means"]:
                    result["what_it_means"] = line
                elif current_section == "cause" and not result["likely_cause"]:
                    result["likely_cause"] = line
                elif current_section == "impact" and not result["impact"]:
                    result["impact"] = line

            # Set actions
            if actions_buffer:
                result["recommended_actions"] = actions_buffer[:5]  # Limit to 5

            # Set severity label based on score
            result["severity_label"] = self._score_to_label(result["severity_score"])

            # Fallback: use event level to infer severity if not extracted
            if result["severity_score"] == 0:
                level = event.get("level", "").upper()
                if level in ("CRITICAL", "ERROR"):
                    result["severity_score"] = 7
                    result["severity_label"] = "High"
                elif level == "WARNING":
                    result["severity_score"] = 4
                    result["severity_label"] = "Medium"
                else:
                    result["severity_score"] = 1
                    result["severity_label"] = "Info"

            # Ensure we have some content
            if not result["short_summary"]:
                result["short_summary"] = lines[0] if lines else "Event analyzed"

            if not result["recommended_actions"]:
                result["recommended_actions"] = [
                    "Review the event details in Event Viewer"
                ]

        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return self._default_explanation(event)

        return result

    def _score_to_label(self, score: int) -> str:
        """Convert severity score to label."""
        if score >= 9:
            return "Critical"
        elif score >= 7:
            return "High"
        elif score >= 4:
            return "Medium"
        elif score >= 2:
            return "Low"
        else:
            return "Info"

    def _default_explanation(self, event: dict) -> dict[str, Any]:
        """Provide a default explanation when AI fails."""
        level = event.get("level", "Information").upper()
        source = event.get("provider", event.get("source", "Windows"))

        # Determine severity from level
        if level in ("CRITICAL", "ERROR"):
            severity_score = 7
            severity_label = "High"
            summary = f"An error occurred in {source}"
            impact = "May affect system functionality"
            actions = [
                "Check for recurring errors",
                "Review detailed event message",
                "Consider restarting affected service",
            ]
        elif level == "WARNING":
            severity_score = 4
            severity_label = "Medium"
            summary = f"Warning from {source}"
            impact = "Potential issue that should be monitored"
            actions = ["Monitor for additional warnings", "Review event details"]
        else:
            severity_score = 1
            severity_label = "Info"
            summary = f"Informational event from {source}"
            impact = "Normal system operation"
            actions = ["No action required"]

        return {
            "short_summary": summary,
            "what_it_means": f"This event was logged by {source} to record system activity.",
            "likely_cause": "Standard system operation or routine activity.",
            "impact": impact,
            "recommended_actions": actions,
            "severity_score": severity_score,
            "severity_label": severity_label,
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
