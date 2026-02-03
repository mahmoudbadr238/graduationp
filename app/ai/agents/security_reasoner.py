"""
Security Reasoner Agent
=======================
Correlates signals and provides security analysis.

This agent ONLY activates after KB rules have been applied.
It generates natural language explanations based on evidence.

CRITICAL RULES:
1. KB analysis is AUTHORITATIVE - use KB data as primary source
2. Do NOT guess if something is normal - use KB data
3. Keep explanations concise and actionable
"""

import logging
from typing import Dict, List, Optional, Any

from .schema import (
    IntentType,
    AssistantState,
    TechnicalDetails,
    AssistantResponse,
    EventEvidence,
    StatusEvidence,
    ScanEvidence,
)

logger = logging.getLogger(__name__)


class SecurityReasonerAgent:
    """
    Correlates signals and provides security analysis.
    
    This agent generates natural language responses based on
    KB analysis and evidence collected by previous agents.
    """
    
    def __init__(self, llm_client: Optional[Any] = None):
        """
        Initialize the reasoner.
        
        Args:
            llm_client: Optional LLM client for advanced reasoning.
                       If None, uses rule-based reasoning only.
        """
        self.llm_client = llm_client
        logger.info(f"SecurityReasonerAgent initialized (LLM: {llm_client is not None})")
    
    def _get_confidence(self, kb_matched: bool) -> str:
        """Get confidence level based on KB match."""
        return "high" if kb_matched else "medium"
    
    def _reason_about_event(self, state: AssistantState) -> AssistantResponse:
        """Generate response for event explanation."""
        if not state.evidence or not state.evidence.events:
            return self._build_no_data_response("No event data found.")
        
        event = state.evidence.events[0]
        kb = state.kb_analysis
        
        # Get KB info for this event
        kb_event = None
        if kb and kb.get("events"):
            for e in kb["events"]:
                if e.get("event_id") == event.event_id:
                    kb_event = e
                    break
        
        if kb_event and kb_event.get("kb_matched", True):
            return self._build_kb_based_response(event, kb_event)
        else:
            return self._build_generic_event_response(event)
    
    def _build_kb_based_response(
        self,
        event: EventEvidence,
        kb_event: Dict[str, Any]
    ) -> AssistantResponse:
        """Build response using KB data."""
        is_normal = kb_event.get("is_normal", True)
        
        # Build answer - include the specific event ID and message snippet
        answer = f"**Event {event.event_id}**: {kb_event.get('kb_title', 'Windows Event')}"
        
        # Add event message snippet if available (shows actual event data)
        if event.message and len(event.message) > 10:
            # Take first meaningful sentence (up to 200 chars)
            msg_snippet = event.message[:200].split('\n')[0].strip()
            if msg_snippet:
                answer += f"\n\n*Event details*: {msg_snippet}"
        
        if kb_event.get("kb_impact"):
            answer += f"\n\n{kb_event['kb_impact']}"
        
        if is_normal:
            answer += "\n\nThis is normal system behavior."
        else:
            severity = kb_event.get("kb_severity", "medium")
            if severity in ("high", "critical"):
                answer += "\n\n⚠️ This requires your attention."
            else:
                answer += "\n\nThis should be reviewed."
        
        return AssistantResponse.build(
            answer=answer,
            why_it_happened=kb_event.get("kb_causes", ["System activity triggered this event"]),
            what_it_affects=kb_event.get("kb_impact", "System operation"),
            what_to_do_now=kb_event.get("kb_actions", [
                "No action needed" if is_normal else "Review the event details"
            ]),
            source="rules" if kb_event.get("kb_matched") else "mixed",
            confidence="high" if kb_event.get("kb_matched") else "medium",
            follow_up_suggestions=[
                "Would you like to see related events?",
                "Should I check for security concerns?",
            ] if not is_normal else [
                "What else would you like to know?",
            ],
            evidence=[event.to_dict()],
        )
    
    def _build_generic_event_response(self, event: EventEvidence) -> AssistantResponse:
        """Build response for event without KB entry."""
        is_normal = event.level in ('Information', 'Verbose')
        
        # Include actual event ID, provider, and message
        answer = f"**Event {event.event_id}** from `{event.provider}`"
        
        # Add event message if available
        if event.message and len(event.message) > 10:
            msg_snippet = event.message[:300].split('\n')[0].strip()
            answer += f"\n\n*Event message*: {msg_snippet}"
        
        if is_normal:
            answer += f"\n\nThis is a {event.level.lower()}-level event which appears informational."
        else:
            answer += f"\n\nThis is a **{event.level}**-level event that may need attention."
        
        return AssistantResponse.build(
            answer=answer,
            why_it_happened=[f"This event was logged by {event.provider}"],
            what_it_affects=["System logging and monitoring"],
            what_to_do_now=["No specific action needed"] if is_normal else ["Review the event in Event Viewer for full details"],
            source="live_snapshot",
            confidence="low",
            follow_up_suggestions=[
                f"Would you like me to search for more events from {event.provider}?"
            ],
            evidence=[event.to_dict()],
        )
    
    def _reason_about_security_status(self, state: AssistantState) -> AssistantResponse:
        """Generate response for security status check."""
        if not state.evidence:
            return self._build_no_data_response("Could not retrieve security status.")
        
        concerns = []
        all_healthy = True
        
        for status in state.evidence.statuses:
            if not status.is_healthy:
                all_healthy = False
            concerns.extend(status.issues)
        
        # Check events for issues
        for event in state.evidence.events:
            if event.level.lower() in ('error', 'critical', 'warning'):
                if event.kb_title:
                    concerns.append(f"Event: {event.kb_title}")
                else:
                    concerns.append(f"Event {event.event_id}: {event.level} level")
        
        if not concerns:
            answer = (
                "Your security looks good! Firewall is enabled, Windows Defender is active, "
                "and no concerning events were detected."
            )
            what_to_do = "No action needed - continue with regular security practices."
        else:
            answer = f"I found {len(concerns)} item(s) that need attention: " + "; ".join(concerns[:3])
            if len(concerns) > 3:
                answer += f" and {len(concerns) - 3} more."
            what_to_do = concerns[0] if concerns else "Review the security concerns listed."
        
        return AssistantResponse.build(
            answer=answer,
            why_it_happened="Security status was checked across firewall, antivirus, and recent events.",
            what_it_affects="Overall system security posture.",
            what_to_do_now=what_to_do,
            source="live_snapshot",
            confidence="high" if not concerns else "medium",
            follow_up_suggestions=[
                "Would you like details on any specific concern?",
                "Should I explain how to fix any of these issues?",
            ] if concerns else [
                "Would you like to see recent security events?",
            ],
        )
    
    def _reason_about_scan(self, state: AssistantState) -> AssistantResponse:
        """Generate response for file/URL scan."""
        if not state.evidence or not state.evidence.scans:
            return self._build_no_data_response("No scan results available.")
        
        scan = state.evidence.scans[0]
        
        if scan.verdict in ("clean", "safe"):
            answer = f"The {scan.scan_type} '{scan.target}' appears to be safe."
            what_to_do = "You can proceed with using this resource."
        else:
            answer = (
                f"⚠️ The {scan.scan_type} '{scan.target}' may be {scan.verdict} "
                f"(risk score: {scan.score}/100)."
            )
            if scan.signals:
                answer += f" Findings: {'; '.join(scan.signals)}"
            what_to_do = "Avoid using this resource until further investigation."
        
        return AssistantResponse.build(
            answer=answer,
            why_it_happened=f"You requested a safety scan of this {scan.scan_type}.",
            what_it_affects="Your system's security if you interact with this resource.",
            what_to_do_now=what_to_do,
            source="scan_result",
            confidence="high" if scan.score < 30 or scan.score > 70 else "medium",
            follow_up_suggestions=["Would you like to scan another file or URL?"],
            evidence=[scan.to_dict()],
        )
    
    def _reason_about_events_list(self, state: AssistantState) -> AssistantResponse:
        """Generate response for events list/search."""
        if not state.evidence or not state.evidence.events:
            return AssistantResponse.build(
                answer="No events found matching your criteria.",
                why_it_happened="The search or filter didn't match any events.",
                what_it_affects="No events to analyze.",
                what_to_do_now="Try broadening your search criteria.",
                source="live_snapshot",
                confidence="high",
            )
        
        events = state.evidence.events
        count = len(events)
        
        # Summarize by level
        levels = {}
        for e in events:
            levels[e.level] = levels.get(e.level, 0) + 1
        
        level_summary = ", ".join(f"{c} {level}" for level, c in levels.items())
        answer = f"Found {count} events: {level_summary}."
        
        # Check for concerning events
        has_issues = state.evidence.has_issues()
        if has_issues:
            answer += " Some events may require attention."
        
        event_list = [
            f"• Event {e.event_id} [{e.level}]: {e.message[:50]}..." 
            for e in events[:5]
        ]
        
        return AssistantResponse.build(
            answer=answer,
            why_it_happened="You requested recent events or searched for specific events.",
            what_it_affects="System activity and security monitoring.",
            what_to_do_now="Review any error or warning events." if has_issues else "These events look normal.",
            source="live_snapshot",
            confidence="high",
            follow_up_suggestions=[
                f"Explain event {events[0].event_id}" if events else "Search for specific events",
            ],
            evidence=[{"events_summary": "\n".join(event_list)}],
        )
    
    def _reason_about_single_status(self, state: AssistantState, status_name: str) -> AssistantResponse:
        """Generate response for single status check."""
        if not state.evidence:
            return self._build_no_data_response(f"Could not retrieve {status_name} status.")
        
        status = None
        for s in state.evidence.statuses:
            if s.name == status_name:
                status = s
                break
        
        if not status:
            return self._build_no_data_response(f"Could not retrieve {status_name} status.")
        
        if status.is_healthy:
            answer = f"Your {status_name} is properly configured and active."
            if status.issues:
                answer += f" Note: {'; '.join(status.issues)}"
        else:
            answer = f"⚠️ Your {status_name} has issues: {'; '.join(status.issues)}"
        
        return AssistantResponse.build(
            answer=answer,
            why_it_happened=f"You asked about your {status_name} status.",
            what_it_affects="System security and protection.",
            what_to_do_now=status.issues[0] if status.issues else "No action needed - looks good!",
            source="live_snapshot",
            confidence="high",
            evidence=[status.to_dict()],
        )
    
    def _build_greeting_response(self) -> AssistantResponse:
        """Build a greeting response."""
        return AssistantResponse.build(
            answer=(
                "Hello! I'm Sentinel, your security assistant. "
                "I can help you understand security events, check your system's protection status, "
                "analyze files and URLs, and answer security questions. How can I help you today?"
            ),
            why_it_happened="You greeted me.",
            what_it_affects="Nothing - this is just a friendly hello!",
            what_to_do_now="Ask me anything about your system's security.",
            source="mixed",
            confidence="high",
            follow_up_suggestions=[
                "Check my security status",
                "Explain recent events",
                "Scan a file or URL",
            ],
        )
    
    def _build_help_response(self) -> AssistantResponse:
        """Build an app help response."""
        return AssistantResponse.build(
            answer=(
                "I can help you with:\n"
                "• **Security Events** - Explain Windows event logs\n"
                "• **Security Status** - Check firewall, antivirus, and updates\n"
                "• **File Scanning** - Analyze files for malware\n"
                "• **URL Analysis** - Check if links are safe\n\n"
                "Just ask me in natural language!"
            ),
            why_it_happened="You asked for help using the app.",
            what_it_affects="Your understanding of Sentinel's capabilities.",
            what_to_do_now="Try one of the suggestions below!",
            source="mixed",
            confidence="high",
            follow_up_suggestions=[
                "Any security concerns?",
                "Show recent events",
                "Explain event 4624",
            ],
        )
    
    def _build_clarification_response(self) -> AssistantResponse:
        """Build a clarification request response."""
        return AssistantResponse.clarification_response(
            "I'm not sure what you're asking about. Could you please clarify?",
            "For example, you can ask me to explain a specific event, check your security status, or analyze a file."
        )
    
    def _build_no_data_response(self, reason: str) -> AssistantResponse:
        """Build a response when no data is available."""
        return AssistantResponse.build(
            answer=f"I couldn't complete your request. {reason}",
            why_it_happened="The requested data was not available.",
            what_it_affects="Unable to provide analysis.",
            what_to_do_now="Please try rephrasing your question or provide more details.",
            source="mixed",
            confidence="low",
            follow_up_suggestions=["What would you like to know about?"],
        )
    
    def run(self, state: AssistantState) -> AssistantState:
        """
        Run the security reasoner on the current state.
        
        Updates state with:
        - response: AssistantResponse with the final answer
        """
        intent_type = state.intent.intent_type if state.intent else IntentType.UNKNOWN
        
        # Route to appropriate reasoning method
        if intent_type == IntentType.GREETING:
            response = self._build_greeting_response()
        
        elif intent_type == IntentType.APP_HELP:
            response = self._build_help_response()
        
        elif intent_type == IntentType.UNKNOWN:
            response = self._build_clarification_response()
        
        elif intent_type == IntentType.EVENT_EXPLAIN:
            response = self._reason_about_event(state)
        
        elif intent_type == IntentType.SECURITY_CHECK:
            response = self._reason_about_security_status(state)
        
        elif intent_type in (IntentType.FILE_SCAN, IntentType.URL_SCAN):
            response = self._reason_about_scan(state)
        
        elif intent_type in (IntentType.EVENT_SUMMARY, IntentType.EVENT_SEARCH):
            response = self._reason_about_events_list(state)
        
        elif intent_type == IntentType.FIREWALL_STATUS:
            response = self._reason_about_single_status(state, "firewall")
        
        elif intent_type == IntentType.DEFENDER_STATUS:
            response = self._reason_about_single_status(state, "defender")
        
        elif intent_type == IntentType.UPDATE_STATUS:
            response = self._reason_about_single_status(state, "updates")
        
        elif intent_type == IntentType.FOLLOWUP:
            # Handle follow-up by re-examining evidence
            if state.evidence and state.evidence.events:
                response = self._reason_about_event(state)
            else:
                response = self._build_clarification_response()
        
        else:
            response = self._build_clarification_response()
        
        state.response = response
        
        logger.info(f"Generated response for intent: {intent_type.value}")
        
        return state


def create_security_reasoner(llm_client: Optional[Any] = None) -> SecurityReasonerAgent:
    """Create a SecurityReasonerAgent instance."""
    return SecurityReasonerAgent(llm_client)
