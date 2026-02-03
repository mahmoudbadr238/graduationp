"""
EventRulesEngine - Deterministic event lookup using knowledge base.

This is the FIRST layer in the explanation pipeline:
1. Lookup by (provider, event_id) → instant match
2. Fallback to templates based on level → still instant
3. Special case handling (1314 privilege error)

NO AI is used here. This runs on UI thread and must be fast.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DeterministicExplanation:
    """Result from deterministic lookup - instant, no AI."""
    
    # Core fields from knowledge base
    title: str = "System event recorded"
    severity: str = "Minor"  # Safe, Minor, Warning, Critical
    impact: str = ""
    causes: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    
    # Metadata
    provider: str = ""
    event_id: int = 0
    level: str = "Information"
    raw_message: str = ""
    matched: bool = False  # True if found in knowledge base
    template_used: str = ""  # Which template was used if fallback
    
    # Extracted entities (from raw message parsing)
    extracted_entities: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "severity": self.severity,
            "impact": self.impact,
            "causes": self.causes,
            "actions": self.actions,
            "provider": self.provider,
            "event_id": self.event_id,
            "level": self.level,
            "raw_message": self.raw_message,
            "matched": self.matched,
            "template_used": self.template_used,
            "extracted_entities": self.extracted_entities,
        }
    
    def cache_key(self) -> str:
        """Generate cache key for this explanation."""
        msg_hash = hashlib.md5(self.raw_message.encode()).hexdigest()[:12]
        return f"{self.provider}:{self.event_id}:{msg_hash}"


class EventRulesEngine:
    """
    Deterministic event lookup engine.
    
    Loads the knowledge base JSON and provides instant lookups.
    This class is designed to be fast and run on the UI thread.
    """
    
    _instance: "EventRulesEngine | None" = None
    
    def __new__(cls) -> "EventRulesEngine":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._rules: dict[str, Any] = {}
        self._templates: dict[str, Any] = {}
        self._load_knowledge_base()
        self._initialized = True
    
    def _load_knowledge_base(self) -> None:
        """Load the event rules JSON file."""
        # Find the knowledge base file
        possible_paths = [
            Path(__file__).parent / "knowledge" / "event_rules.json",
            Path(__file__).parent.parent.parent / "app" / "ai" / "knowledge" / "event_rules.json",
        ]
        
        kb_path = None
        for path in possible_paths:
            if path.exists():
                kb_path = path
                break
        
        if kb_path is None:
            logger.error("Event rules knowledge base not found!")
            return
        
        try:
            with open(kb_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._rules = data.get("providers", {})
            self._templates = data.get("templates", {})
            
            # Count events for logging
            event_count = sum(
                len(provider.get("common_events", {}))
                for provider in self._rules.values()
            )
            logger.info(f"EventRulesEngine loaded: {len(self._rules)} providers, {event_count} events")
            
        except Exception as e:
            logger.error(f"Failed to load event rules: {e}")
    
    def lookup(
        self,
        provider: str,
        event_id: int,
        level: str = "Information",
        raw_message: str = "",
    ) -> DeterministicExplanation:
        """
        Look up an event in the knowledge base.
        
        This is INSTANT - no network, no AI, no async.
        
        Args:
            provider: Event provider/source name
            event_id: Event ID number
            level: Event level (Information, Warning, Error, Critical)
            raw_message: Raw event message text
        
        Returns:
            DeterministicExplanation with matched or fallback data
        """
        result = DeterministicExplanation(
            provider=provider,
            event_id=event_id,
            level=level,
            raw_message=raw_message,
        )
        
        # Special case: 1314 privilege error
        if event_id == 1314 or "privilege" in raw_message.lower():
            return self._handle_privilege_error(result)
        
        # Try exact provider match first
        provider_data = self._find_provider(provider)
        
        if provider_data:
            event_data = provider_data.get("common_events", {}).get(str(event_id))
            
            if event_data:
                # Found exact match!
                result.title = event_data.get("title", result.title)
                result.severity = event_data.get("severity", "Minor")
                result.impact = event_data.get("impact", "")
                result.causes = event_data.get("causes", [])
                result.actions = event_data.get("actions", [])
                result.matched = True
                logger.debug(f"Exact match: {provider}:{event_id}")
            else:
                # Provider found but event not in list - use level-based template
                result = self._apply_fallback_template(result)
        else:
            # Provider not found - use level-based template
            result = self._apply_fallback_template(result)
        
        # Extract entities from raw message
        result.extracted_entities = self._extract_entities(raw_message)
        
        # Customize actions based on extracted entities
        result.actions = self._customize_actions(result.actions, result.extracted_entities)
        
        return result
    
    def _find_provider(self, provider: str) -> dict[str, Any] | None:
        """Find provider data, trying various name formats."""
        if not provider:
            return None
        
        # Try exact match first
        if provider in self._rules:
            return self._rules[provider]
        
        # Try case-insensitive match
        provider_lower = provider.lower()
        for name, data in self._rules.items():
            if name.lower() == provider_lower:
                return data
        
        # Try partial match (e.g., "Microsoft-Windows-Security-Auditing" matches "Security-Auditing")
        for name, data in self._rules.items():
            if provider_lower in name.lower() or name.lower() in provider_lower:
                return data
        
        return None
    
    def _apply_fallback_template(self, result: DeterministicExplanation) -> DeterministicExplanation:
        """Apply a fallback template based on event level."""
        level_lower = result.level.lower()
        
        if "critical" in level_lower:
            template_key = "unknown_critical"
        elif "error" in level_lower:
            template_key = "unknown_error"
        elif "warning" in level_lower:
            template_key = "unknown_warning"
        else:
            template_key = "unknown_information"
        
        template = self._templates.get(template_key, {})
        
        result.title = template.get("title", f"{result.level} event from {result.provider}")
        result.severity = template.get("severity", "Minor")
        result.impact = template.get("impact", "")
        result.causes = template.get("causes", [])
        result.actions = template.get("actions", [])
        result.matched = False
        result.template_used = template_key
        
        return result
    
    def _handle_privilege_error(self, result: DeterministicExplanation) -> DeterministicExplanation:
        """Handle the special 1314 privilege error case."""
        template = self._templates.get("security_1314", {})
        
        result.title = template.get("title", "Security log access denied")
        result.severity = template.get("severity", "Minor")
        result.impact = template.get("impact", "Cannot read Security event log without admin privileges.")
        result.causes = template.get("causes", ["Application running without admin rights"])
        result.actions = template.get("actions", [
            "Run Sentinel as Administrator",
            "Right-click Sentinel and select 'Run as administrator'"
        ])
        result.matched = True
        result.template_used = "security_1314"
        
        return result
    
    def _extract_entities(self, raw_message: str) -> dict[str, Any]:
        """
        Extract useful entities from the raw event message.
        
        This is regex-based, fast, deterministic.
        """
        entities: dict[str, Any] = {}
        
        if not raw_message:
            return entities
        
        # Service name patterns
        service_patterns = [
            r"service\s+['\"]?([^'\"]+)['\"]?\s+(?:was|is|has|entered|changed)",
            r"The\s+([A-Za-z0-9\s]+)\s+service",
            r"Service:\s+([^\r\n]+)",
            r"ServiceName:\s*([^\r\n]+)",
        ]
        for pattern in service_patterns:
            match = re.search(pattern, raw_message, re.IGNORECASE)
            if match:
                entities["service_name"] = match.group(1).strip()
                break
        
        # Application/process name
        app_patterns = [
            r"Application:\s*([^\r\n]+)",
            r"Process Name:\s*([^\r\n]+)",
            r"Faulting application name:\s*([^\r\n,]+)",
            r"([A-Za-z0-9_]+\.exe)",
        ]
        for pattern in app_patterns:
            match = re.search(pattern, raw_message, re.IGNORECASE)
            if match:
                entities["application"] = match.group(1).strip()
                break
        
        # File paths
        path_pattern = r"([A-Z]:\\[^\r\n:*?\"<>|]+)"
        paths = re.findall(path_pattern, raw_message)
        if paths:
            entities["file_paths"] = list(set(paths))[:3]  # Max 3 paths
        
        # IP addresses
        ip_pattern = r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b"
        ips = re.findall(ip_pattern, raw_message)
        if ips:
            entities["ip_addresses"] = list(set(ips))
        
        # Usernames
        user_patterns = [
            r"User:\s*([^\r\n]+)",
            r"Account Name:\s*([^\r\n]+)",
            r"Logon Account:\s*([^\r\n]+)",
            r"(?:user|username)[:\s]+([A-Za-z0-9_\-\.]+)",
        ]
        for pattern in user_patterns:
            match = re.search(pattern, raw_message, re.IGNORECASE)
            if match:
                entities["username"] = match.group(1).strip()
                break
        
        # Domain
        domain_patterns = [
            r"Domain:\s*([^\r\n]+)",
            r"Account Domain:\s*([^\r\n]+)",
        ]
        for pattern in domain_patterns:
            match = re.search(pattern, raw_message, re.IGNORECASE)
            if match:
                entities["domain"] = match.group(1).strip()
                break
        
        # Port numbers
        port_pattern = r"[Pp]ort[:\s]+(\d+)"
        ports = re.findall(port_pattern, raw_message)
        if ports:
            entities["ports"] = list(set(ports))
        
        # Error codes
        error_patterns = [
            r"Error [Cc]ode:\s*(\d+|0x[0-9A-Fa-f]+)",
            r"error\s+(\d+|0x[0-9A-Fa-f]+)",
            r"HRESULT:\s*(0x[0-9A-Fa-f]+)",
        ]
        for pattern in error_patterns:
            match = re.search(pattern, raw_message, re.IGNORECASE)
            if match:
                entities["error_code"] = match.group(1)
                break
        
        return entities
    
    def _customize_actions(
        self,
        actions: list[str],
        entities: dict[str, Any],
    ) -> list[str]:
        """
        Customize action recommendations based on extracted entities.
        
        E.g., if service_name is found, make actions more specific.
        """
        if not entities:
            return actions
        
        customized = []
        
        for action in actions:
            new_action = action
            
            # Customize for service name
            if "service" in action.lower() and "service_name" in entities:
                service = entities["service_name"]
                if "services.msc" in action.lower():
                    new_action = f"Open services.msc and find '{service}'"
                elif "check" in action.lower():
                    new_action = f"Check the '{service}' service status"
            
            # Customize for application
            if "application" in entities:
                app = entities["application"]
                if "reinstall" in action.lower():
                    new_action = f"Try reinstalling {app}"
                elif "update" in action.lower():
                    new_action = f"Update {app} to the latest version"
            
            customized.append(new_action)
        
        # Add entity-specific actions
        if "service_name" in entities and not any("service" in a.lower() for a in customized):
            customized.append(f"Check if '{entities['service_name']}' service is running")
        
        if "file_paths" in entities and not any("file" in a.lower() for a in customized):
            customized.append(f"Verify the file exists: {entities['file_paths'][0]}")
        
        return customized


# Module-level singleton accessor
_engine: EventRulesEngine | None = None


def get_event_rules_engine() -> EventRulesEngine:
    """Get the singleton EventRulesEngine instance."""
    global _engine
    if _engine is None:
        _engine = EventRulesEngine()
    return _engine
