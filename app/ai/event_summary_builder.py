"""
SimpleSummaryBuilder: Deterministic event summaries without AI.

This module provides instant, reliable summaries for Windows events
using pattern matching and a comprehensive knowledge base. No LLM required.

Output Structure:
    - title: Short human-readable title
    - what_happened: One sentence explanation
    - impact: How this might affect the user
    - likely_causes: List of probable reasons
    - recommended_actions: What the user can do
    - confidence: How confident we are (high/medium/low)
    - tags: Classification tags for filtering
    - severity: Safe/Minor/Warning/Critical
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Load event rules knowledge base
_KNOWLEDGE_PATH = Path(__file__).parent / "knowledge" / "event_rules.json"
_EVENT_RULES: dict[str, Any] = {}


def _load_event_rules() -> dict[str, Any]:
    """Load event rules from JSON file."""
    global _EVENT_RULES
    if _EVENT_RULES:
        return _EVENT_RULES
    
    try:
        if _KNOWLEDGE_PATH.exists():
            with open(_KNOWLEDGE_PATH, "r", encoding="utf-8") as f:
                _EVENT_RULES = json.load(f)
    except Exception:
        _EVENT_RULES = {"providers": {}, "templates": {}}
    
    return _EVENT_RULES


@dataclass
class EventSummary:
    """Structured summary of a Windows event."""
    
    title: str
    what_happened: str
    impact: str
    likely_causes: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    confidence: str = "medium"  # high, medium, low
    tags: list[str] = field(default_factory=list)
    severity: str = "Minor"  # Safe, Minor, Warning, Critical
    source_matched: bool = False  # True if we found a specific rule
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "what_happened": self.what_happened,
            "impact": self.impact,
            "likely_causes": self.likely_causes,
            "recommended_actions": self.recommended_actions,
            "confidence": self.confidence,
            "tags": self.tags,
            "severity": self.severity,
            "source_matched": self.source_matched,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventSummary":
        """Create from dictionary."""
        return cls(
            title=data.get("title", "Unknown Event"),
            what_happened=data.get("what_happened", ""),
            impact=data.get("impact", ""),
            likely_causes=data.get("likely_causes", []),
            recommended_actions=data.get("recommended_actions", []),
            confidence=data.get("confidence", "low"),
            tags=data.get("tags", []),
            severity=data.get("severity", "Minor"),
            source_matched=data.get("source_matched", False),
        )


class SimpleSummaryBuilder:
    """
    Builds deterministic event summaries without AI.
    
    Uses pattern matching and a knowledge base to provide instant,
    reliable summaries for Windows events.
    """
    
    def __init__(self):
        """Initialize the summary builder."""
        self._rules = _load_event_rules()
        self._providers = self._rules.get("providers", {})
        self._templates = self._rules.get("templates", {})
    
    def build_summary(
        self,
        event_id: int | str,
        provider: str,
        level: str,
        message: str,
        time_created: str | None = None,
        task_category: str | None = None,
        keywords: list[str] | None = None,
    ) -> EventSummary:
        """
        Build a summary for the given event.
        
        Args:
            event_id: Windows event ID
            provider: Event provider/source name
            level: Event level (Information, Warning, Error, Critical)
            message: Event message text
            time_created: ISO timestamp of event
            task_category: Task category from event
            keywords: Event keywords list
        
        Returns:
            EventSummary with all fields populated
        """
        event_id_str = str(event_id)
        
        # Try to find exact match in knowledge base
        summary = self._lookup_known_event(provider, event_id_str)
        
        if summary:
            # Enhance with message-specific details
            summary = self._enhance_with_message(summary, message, provider, level)
            return summary
        
        # Fall back to pattern-based analysis
        return self._analyze_unknown_event(
            event_id_str, provider, level, message, task_category, keywords
        )
    
    def _lookup_known_event(
        self, provider: str, event_id: str
    ) -> EventSummary | None:
        """Look up a known event in the knowledge base."""
        # Normalize provider name for lookup
        provider_key = self._normalize_provider(provider)
        
        provider_info = self._providers.get(provider_key)
        if not provider_info:
            return None
        
        events = provider_info.get("common_events", {})
        event_info = events.get(event_id)
        
        if not event_info:
            return None
        
        return EventSummary(
            title=event_info.get("title", f"Event {event_id}"),
            what_happened=event_info.get("title", ""),
            impact=event_info.get("impact", ""),
            likely_causes=list(event_info.get("causes", [])),
            recommended_actions=list(event_info.get("actions", [])),
            confidence="high",
            tags=self._generate_tags(provider_key, event_id, event_info),
            severity=event_info.get("severity", "Minor"),
            source_matched=True,
        )
    
    def _normalize_provider(self, provider: str) -> str:
        """Normalize provider name for lookup."""
        if not provider:
            return ""
        
        # Direct match first
        if provider in self._providers:
            return provider
        
        # Try common variations
        provider_lower = provider.lower()
        
        for key in self._providers:
            if key.lower() == provider_lower:
                return key
        
        # Handle common aliases
        aliases = {
            "scm": "Service Control Manager",
            "security": "Microsoft-Windows-Security-Auditing",
            "kernel-power": "Microsoft-Windows-Kernel-Power",
            "windows update": "Microsoft-Windows-WindowsUpdateClient",
            "wuauclt": "Microsoft-Windows-WindowsUpdateClient",
        }
        
        return aliases.get(provider_lower, provider)
    
    def _enhance_with_message(
        self,
        summary: EventSummary,
        message: str,
        provider: str,
        level: str,
    ) -> EventSummary:
        """Enhance summary with details from the message."""
        # Extract specific names from message
        service_name = self._extract_service_name(message)
        if service_name:
            summary.what_happened = f"{summary.title}: {service_name}"
            summary.tags.append(f"service:{service_name}")
        
        app_name = self._extract_app_name(message)
        if app_name:
            summary.what_happened = f"{summary.title}: {app_name}"
            summary.tags.append(f"app:{app_name}")
        
        # Add level-based tag
        level_lower = (level or "").lower()
        if level_lower:
            summary.tags.append(f"level:{level_lower}")
        
        return summary
    
    def _analyze_unknown_event(
        self,
        event_id: str,
        provider: str,
        level: str,
        message: str,
        task_category: str | None,
        keywords: list[str] | None,
    ) -> EventSummary:
        """Analyze an unknown event using patterns."""
        level_lower = (level or "information").lower()
        
        # Select appropriate template based on level
        if level_lower in ("critical",):
            template = self._templates.get("unknown_critical", {})
            severity = "Critical"
        elif level_lower in ("error", "warning"):
            template = self._templates.get("unknown_warning", {})
            severity = "Warning"
        else:
            template = self._templates.get("unknown_information", {})
            severity = "Safe"
        
        # Extract useful info from message
        what_happened = self._summarize_message(message, provider, event_id)
        
        # Build tags
        tags = self._generate_tags_from_message(message, provider, level, keywords)
        
        return EventSummary(
            title=template.get("title", f"Event {event_id}"),
            what_happened=what_happened,
            impact=template.get("impact", ""),
            likely_causes=list(template.get("causes", [])),
            recommended_actions=list(template.get("actions", [])),
            confidence="low",
            tags=tags,
            severity=severity,
            source_matched=False,
        )
    
    def _summarize_message(
        self, message: str, provider: str, event_id: str
    ) -> str:
        """Create a short summary from the message."""
        if not message:
            return f"Event {event_id} from {provider}"
        
        # Clean up the message
        message = message.strip()
        
        # Take first sentence or line
        first_line = message.split("\n")[0].strip()
        first_sentence = first_line.split(". ")[0].strip()
        
        # Truncate if too long
        if len(first_sentence) > 150:
            first_sentence = first_sentence[:147] + "..."
        
        return first_sentence or f"Event {event_id} from {provider}"
    
    def _extract_service_name(self, message: str) -> str | None:
        """Extract service name from message."""
        patterns = [
            r"The (\w+(?:\s+\w+)*) service",
            r"service[:\s]+([A-Za-z0-9_\-\.]+)",
            r"'([A-Za-z0-9_\-\.]+)' service",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Skip generic words
                if name.lower() not in ("the", "a", "this", "that"):
                    return name
        
        return None
    
    def _extract_app_name(self, message: str) -> str | None:
        """Extract application name from message."""
        patterns = [
            r"Faulting application name:\s*([^\s,]+)",
            r"Application:\s*([^\s,]+\.exe)",
            r"process[:\s]+([A-Za-z0-9_\-\.]+\.exe)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _generate_tags(
        self,
        provider: str,
        event_id: str,
        event_info: dict[str, Any],
    ) -> list[str]:
        """Generate classification tags for an event."""
        tags = [f"id:{event_id}"]
        
        # Add provider category
        provider_info = self._providers.get(provider, {})
        category = provider_info.get("category", "system")
        tags.append(f"category:{category}")
        
        # Add severity
        severity = event_info.get("severity", "Minor").lower()
        tags.append(f"severity:{severity}")
        
        return tags
    
    def _generate_tags_from_message(
        self,
        message: str,
        provider: str,
        level: str,
        keywords: list[str] | None,
    ) -> list[str]:
        """Generate tags from message analysis."""
        tags = []
        
        # Add level
        if level:
            tags.append(f"level:{level.lower()}")
        
        # Detect categories from message content
        message_lower = (message or "").lower()
        
        if any(w in message_lower for w in ("login", "logon", "logoff", "authentication")):
            tags.append("category:security")
        elif any(w in message_lower for w in ("service", "started", "stopped")):
            tags.append("category:service")
        elif any(w in message_lower for w in ("disk", "storage", "drive")):
            tags.append("category:hardware")
        elif any(w in message_lower for w in ("network", "tcp", "ip", "connection")):
            tags.append("category:network")
        elif any(w in message_lower for w in ("update", "install", "patch")):
            tags.append("category:update")
        else:
            tags.append("category:system")
        
        # Add from keywords
        if keywords:
            for kw in keywords[:3]:  # Limit keywords
                if kw and len(kw) < 30:
                    tags.append(f"keyword:{kw.lower()}")
        
        return tags
    
    def get_provider_info(self, provider: str) -> dict[str, Any] | None:
        """Get information about a provider."""
        normalized = self._normalize_provider(provider)
        return self._providers.get(normalized)
    
    def is_known_event(self, provider: str, event_id: int | str) -> bool:
        """Check if an event is in the knowledge base."""
        normalized = self._normalize_provider(provider)
        provider_info = self._providers.get(normalized)
        
        if not provider_info:
            return False
        
        events = provider_info.get("common_events", {})
        return str(event_id) in events


# Singleton instance for convenience
_builder_instance: SimpleSummaryBuilder | None = None


def get_summary_builder() -> SimpleSummaryBuilder:
    """Get the singleton SimpleSummaryBuilder instance."""
    global _builder_instance
    if _builder_instance is None:
        _builder_instance = SimpleSummaryBuilder()
    return _builder_instance


def build_event_summary(
    event_id: int | str,
    provider: str,
    level: str,
    message: str,
    **kwargs,
) -> EventSummary:
    """
    Convenience function to build an event summary.
    
    Args:
        event_id: Windows event ID
        provider: Event provider/source name
        level: Event level (Information, Warning, Error, Critical)
        message: Event message text
        **kwargs: Additional fields (time_created, task_category, keywords)
    
    Returns:
        EventSummary with all fields populated
    """
    builder = get_summary_builder()
    return builder.build_summary(event_id, provider, level, message, **kwargs)


def get_quick_title(
    event_id: int | str,
    provider: str,
    level: str = "Information",
) -> str:
    """
    Get a quick title for an event without full analysis.
    
    Args:
        event_id: Windows event ID
        provider: Event provider/source name
        level: Event level
    
    Returns:
        Short title string
    """
    builder = get_summary_builder()
    provider_key = builder._normalize_provider(provider)
    provider_info = builder._providers.get(provider_key, {})
    events = provider_info.get("common_events", {})
    event_info = events.get(str(event_id))
    
    if event_info:
        return event_info.get("title", f"Event {event_id}")
    
    # Generate generic title based on level
    level_lower = (level or "").lower()
    if level_lower == "critical":
        return f"Critical: Event {event_id}"
    elif level_lower == "error":
        return f"Error: Event {event_id}"
    elif level_lower == "warning":
        return f"Warning: Event {event_id}"
    else:
        return f"Event {event_id}"
