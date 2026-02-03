"""
Local AI Provider - Offline-only knowledge-based responses.

This provider uses:
- EventRulesEngine for deterministic event explanations
- Knowledge base for security facts
- No network calls, instant responses

This is the SOURCE OF TRUTH - online providers can only enhance,
never override what local provides.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from .base import AIProvider, AIResponse, ProviderConfig

logger = logging.getLogger(__name__)


class LocalProvider(AIProvider):
    """
    Local/offline AI provider using knowledge base and rules.
    
    Features:
    - Instant responses (no network latency)
    - Always available (works offline)
    - Deterministic (same input = same output)
    - Source of truth for facts
    """
    
    def __init__(self, config: Optional[ProviderConfig] = None):
        super().__init__(config)
        self._rules_engine = None
        self._event_id_knowledge = None
    
    @property
    def name(self) -> str:
        return "local"
    
    @property
    def is_available(self) -> bool:
        return True  # Local is always available
    
    def _get_rules_engine(self):
        """Lazy-load the rules engine."""
        if self._rules_engine is None:
            try:
                from ..event_rules_engine import get_event_rules_engine
                self._rules_engine = get_event_rules_engine()
            except ImportError as e:
                logger.warning(f"Rules engine not available: {e}")
        return self._rules_engine
    
    def _get_event_knowledge(self):
        """Lazy-load event ID knowledge."""
        if self._event_id_knowledge is None:
            try:
                from ..event_id_knowledge import EVENT_KB
                self._event_id_knowledge = EVENT_KB
            except ImportError:
                self._event_id_knowledge = {}
        return self._event_id_knowledge
    
    async def generate(
        self,
        query: str,
        context: dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> AIResponse:
        """
        Generate a local response for general queries.
        
        For now, this provides template-based responses.
        A future version could use a local LLM.
        """
        start = time.monotonic()
        
        # Extract key info from query
        query_lower = query.lower()
        
        # Try to detect query type and provide appropriate response
        if "firewall" in query_lower:
            response = self._handle_firewall_query(context)
        elif "defender" in query_lower or "antivirus" in query_lower:
            response = self._handle_defender_query(context)
        elif "update" in query_lower:
            response = self._handle_update_query(context)
        elif "event" in query_lower:
            response = self._handle_event_query(query, context)
        else:
            response = self._handle_general_query(query, context)
        
        response.latency_ms = int((time.monotonic() - start) * 1000)
        return response
    
    async def explain_event(
        self,
        event: dict[str, Any],
        kb_explanation: Optional[dict] = None,
    ) -> AIResponse:
        """
        Explain a security event using the knowledge base.
        
        This is the primary function - provides instant, accurate explanations.
        """
        start = time.monotonic()
        
        # Extract event details
        provider = event.get("provider", event.get("source", ""))
        event_id = event.get("event_id", event.get("eventId", 0))
        level = event.get("level", "Information")
        message = event.get("message", "")
        
        # Use rules engine for lookup
        rules_engine = self._get_rules_engine()
        
        if rules_engine:
            det = rules_engine.lookup(
                provider=provider,
                event_id=int(event_id) if event_id else 0,
                level=level,
                raw_message=message,
            )
            
            response = AIResponse(
                answer=det.impact or det.title,
                why_it_happened=det.causes,
                what_it_affects=[det.impact] if det.impact else [],
                what_to_do_now=det.actions,
                technical_details={
                    "source": "local",
                    "confidence": "high" if det.matched else "medium",
                    "evidence": [{
                        "type": "knowledge_base",
                        "matched": det.matched,
                        "provider": provider,
                        "event_id": event_id,
                    }],
                    "extracted_entities": det.extracted_entities,
                },
                follow_up_suggestions=self._generate_follow_ups(event_id, provider),
                source="local",
                confidence="high" if det.matched else "medium",
            )
        else:
            # Fallback if rules engine not available
            response = AIResponse(
                answer=f"Event {event_id} from {provider}",
                why_it_happened=["Event details are being analyzed"],
                what_it_affects=["Impact assessment pending"],
                what_to_do_now=["Review event details manually"],
                source="local",
                confidence="low",
            )
        
        response.latency_ms = int((time.monotonic() - start) * 1000)
        return response
    
    def _handle_firewall_query(self, context: dict) -> AIResponse:
        """Handle firewall-related queries."""
        firewall = context.get("firewall", {})
        
        all_enabled = (
            firewall.get("domain", True) and
            firewall.get("private", True) and
            firewall.get("public", True)
        )
        
        if all_enabled:
            return AIResponse(
                answer="Your Windows Firewall is properly configured and enabled for all network profiles.",
                why_it_happened=[
                    "Windows Firewall is the first line of defense against network attacks",
                    "All three profiles (Domain, Private, Public) are active"
                ],
                what_it_affects=[
                    "Inbound and outbound network traffic is being filtered",
                    "Unauthorized connections are blocked"
                ],
                what_to_do_now=[
                    "No action needed - firewall is properly configured",
                    "Review firewall rules periodically for unnecessary exceptions"
                ],
                follow_up_suggestions=[
                    "Show me recent blocked connections",
                    "Are there any risky firewall rules?",
                ],
                source="local",
                confidence="high",
            )
        else:
            disabled = []
            if not firewall.get("domain", True):
                disabled.append("Domain")
            if not firewall.get("private", True):
                disabled.append("Private")
            if not firewall.get("public", True):
                disabled.append("Public")
            
            return AIResponse(
                answer=f"⚠️ Warning: Firewall is disabled for {', '.join(disabled)} profile(s).",
                why_it_happened=[
                    "One or more firewall profiles have been disabled",
                    "This may have been done manually or by software"
                ],
                what_it_affects=[
                    "Your system is vulnerable to network-based attacks",
                    f"Connections on {', '.join(disabled)} networks are not filtered"
                ],
                what_to_do_now=[
                    "Enable Windows Firewall for all profiles immediately",
                    "Run: netsh advfirewall set allprofiles state on",
                    "Check for malware that may have disabled the firewall"
                ],
                follow_up_suggestions=[
                    "How do I enable the firewall?",
                    "Check for security threats",
                ],
                source="local",
                confidence="high",
            )
    
    def _handle_defender_query(self, context: dict) -> AIResponse:
        """Handle Defender/antivirus queries."""
        defender = context.get("defender", {})
        
        is_healthy = (
            defender.get("realtime_protection", True) and
            defender.get("antivirus_enabled", True)
        )
        
        if is_healthy:
            last_scan = defender.get("last_scan", "Unknown")
            return AIResponse(
                answer="Windows Defender is active and protecting your system.",
                why_it_happened=[
                    "Real-time protection is enabled",
                    "Antivirus engine is running",
                    f"Last scan: {last_scan}"
                ],
                what_it_affects=[
                    "Files are scanned in real-time when accessed",
                    "Downloads and email attachments are checked",
                    "Malicious scripts are blocked"
                ],
                what_to_do_now=[
                    "No action needed - protection is active",
                    "Consider running a full scan weekly"
                ],
                follow_up_suggestions=[
                    "When was the last full scan?",
                    "Show me recent threat detections",
                ],
                source="local",
                confidence="high",
            )
        else:
            issues = []
            if not defender.get("realtime_protection", True):
                issues.append("Real-time protection is disabled")
            if not defender.get("antivirus_enabled", True):
                issues.append("Antivirus engine is disabled")
            
            return AIResponse(
                answer="🔴 Critical: Windows Defender protection is compromised!",
                why_it_happened=issues,
                what_it_affects=[
                    "Your system is vulnerable to malware",
                    "Files are not being scanned in real-time",
                    "New threats may not be detected"
                ],
                what_to_do_now=[
                    "Open Windows Security immediately",
                    "Enable Virus & threat protection",
                    "Run a full system scan",
                    "Check for malware that disabled Defender"
                ],
                follow_up_suggestions=[
                    "How do I enable Defender?",
                    "Scan my system for threats",
                ],
                source="local",
                confidence="high",
            )
    
    def _handle_update_query(self, context: dict) -> AIResponse:
        """Handle Windows Update queries."""
        updates = context.get("updates", {})
        
        pending = updates.get("pending_count", 0)
        pending_reboot = updates.get("pending_reboot", False)
        last_update = updates.get("last_update", "Unknown")
        
        if pending_reboot:
            return AIResponse(
                answer="⚠️ Your system needs to restart to complete pending updates.",
                why_it_happened=[
                    "Security updates have been installed",
                    "A restart is required to apply all changes"
                ],
                what_it_affects=[
                    "Some security patches are not yet active",
                    "System may be vulnerable until restart"
                ],
                what_to_do_now=[
                    "Save your work and restart soon",
                    "Schedule a restart if now isn't convenient"
                ],
                follow_up_suggestions=[
                    "What updates are pending?",
                    "Is it safe to postpone the restart?",
                ],
                source="local",
                confidence="high",
            )
        elif pending > 0:
            return AIResponse(
                answer=f"There are {pending} updates available for installation.",
                why_it_happened=[
                    f"{pending} updates are waiting to be installed",
                    "These may include security patches"
                ],
                what_it_affects=[
                    "Security vulnerabilities may remain unpatched",
                    "New features and fixes are available"
                ],
                what_to_do_now=[
                    "Install updates when convenient",
                    "Review updates in Settings > Windows Update"
                ],
                follow_up_suggestions=[
                    "Are any updates critical?",
                    "Show me the update history",
                ],
                source="local",
                confidence="high",
            )
        else:
            return AIResponse(
                answer="Your system is up to date.",
                why_it_happened=[
                    "All available updates have been installed",
                    f"Last update check: {last_update}"
                ],
                what_it_affects=[
                    "Your system has the latest security patches",
                    "Known vulnerabilities are addressed"
                ],
                what_to_do_now=[
                    "No action needed",
                    "Updates are checked automatically"
                ],
                follow_up_suggestions=[
                    "Check for updates now",
                    "Show me the update history",
                ],
                source="local",
                confidence="high",
            )
    
    def _handle_event_query(self, query: str, context: dict) -> AIResponse:
        """Handle event-related queries."""
        events = context.get("events", [])
        
        # Try to extract event ID from query
        import re
        event_ids = re.findall(r'\b(\d{4})\b', query)
        
        if event_ids:
            event_id = int(event_ids[0])
            knowledge = self._get_event_knowledge()
            
            # EVENT_KB uses (source, event_id) tuple keys
            # Try generic lookup with "*" source first
            info = knowledge.get(("*", event_id)) or knowledge.get(("Security", event_id))
            
            if info:
                # info is an EventKnowledge dataclass
                return AIResponse(
                    answer=info.title,
                    why_it_happened=[info.what_happened],
                    what_it_affects=[info.tech_notes] if info.tech_notes else [],
                    what_to_do_now=[info.what_you_can_do],
                    source="local",
                    confidence="high",
                )
        
        # General event summary
        if events:
            error_count = sum(1 for e in events if e.get("level") in ["Error", "Critical"])
            return AIResponse(
                answer=f"Found {len(events)} recent events, including {error_count} errors/critical.",
                why_it_happened=["Summary of recent system activity"],
                what_it_affects=["Various system components"],
                what_to_do_now=[
                    "Review errors and critical events first",
                    "Click on specific events for details"
                ],
                source="local",
                confidence="medium",
            )
        
        return AIResponse(
            answer="No events found matching your query.",
            why_it_happened=["No matching events in the current log"],
            source="local",
            confidence="medium",
        )
    
    def _handle_general_query(self, query: str, context: dict) -> AIResponse:
        """Handle general security queries."""
        return AIResponse(
            answer="I can help you with security questions. Try asking about:",
            why_it_happened=[],
            what_it_affects=[],
            what_to_do_now=[
                "Ask about specific events (e.g., 'Explain event 4625')",
                "Check security status (e.g., 'Is my firewall enabled?')",
                "Review system health (e.g., 'Any security concerns?')"
            ],
            follow_up_suggestions=[
                "Check my security status",
                "Show me recent security events",
                "Are there any threats?",
            ],
            source="local",
            confidence="medium",
        )
    
    def _generate_follow_ups(self, event_id: int, provider: str) -> list[str]:
        """Generate relevant follow-up suggestions based on event type."""
        follow_ups = []
        
        # Event-specific follow-ups
        event_follow_ups = {
            4625: [
                "Show me successful logins from this account",
                "Is this a brute force attack?",
                "Block this IP address",
            ],
            4624: [
                "Is this login expected?",
                "Show me other activity from this account",
            ],
            7045: [
                "Is this service legitimate?",
                "Show me the service executable path",
                "Check for similar service installations",
            ],
            4688: [
                "Is this process expected?",
                "Show me the parent process",
            ],
            1116: [
                "What threat was detected?",
                "Was the threat removed?",
                "Scan the system for more threats",
            ],
        }
        
        follow_ups = event_follow_ups.get(event_id, [
            "Show me similar events",
            "Is this normal?",
        ])
        
        return follow_ups[:3]  # Limit to 3


# Singleton
_local_provider: Optional[LocalProvider] = None

def get_local_provider() -> LocalProvider:
    """Get the singleton local provider."""
    global _local_provider
    if _local_provider is None:
        _local_provider = LocalProvider()
    return _local_provider
