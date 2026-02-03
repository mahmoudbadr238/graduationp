"""
Schema definitions for the Smart Security Assistant.

Defines all data structures used throughout the agent pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import json


# =============================================================================
# USER INTENT CLASSIFICATION
# =============================================================================

class IntentType(Enum):
    """Classification of user intent."""
    EVENT_SUMMARY = "event_summary"        # "Show me recent events"
    EVENT_EXPLAIN = "event_explain"        # "Explain event 7000" (SPECIFIC)
    EVENT_SEARCH = "event_search"          # "Find login failures"
    FIREWALL_STATUS = "firewall_status"    # "Is my firewall enabled?"
    DEFENDER_STATUS = "defender_status"    # "Is Defender running?"
    UPDATE_STATUS = "update_status"        # "Do I have pending updates?"
    SECURITY_CHECK = "security_check"      # "Any security concerns?" (COMPREHENSIVE)
    FILE_SCAN = "file_scan"                # "Scan this file..."
    URL_SCAN = "url_scan"                  # "Check this URL..."
    APP_HELP = "app_help"                  # "How do I use Event Viewer?"
    SECURITY_ADVICE = "security_advice"    # "How do I protect against ransomware?"
    FOLLOWUP = "followup"                  # Follow-up to previous message
    GREETING = "greeting"                  # "Hello"
    UNKNOWN = "unknown"                    # Cannot classify


@dataclass
class ExtractedEntities:
    """Entities extracted from user message."""
    event_ids: list[int] = field(default_factory=list)
    record_ids: list[int] = field(default_factory=list)
    providers: list[str] = field(default_factory=list)
    file_paths: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    log_names: list[str] = field(default_factory=list)  # System, Security, Application
    timeframe: Optional[str] = None  # "last hour", "today", "last 24h"
    feature_name: Optional[str] = None  # App feature mentioned
    severity_filter: Optional[str] = None  # "errors", "warnings", "critical"
    
    def to_dict(self) -> dict:
        return {
            "event_ids": self.event_ids,
            "record_ids": self.record_ids,
            "providers": self.providers,
            "file_paths": self.file_paths,
            "urls": self.urls,
            "log_names": self.log_names,
            "timeframe": self.timeframe,
            "feature_name": self.feature_name,
            "severity_filter": self.severity_filter,
        }


@dataclass
class UserIntent:
    """Classified user intent with extracted entities."""
    intent_type: IntentType
    confidence: float  # 0.0 to 1.0
    entities: ExtractedEntities
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    original_message: str = ""
    resolved_message: str = ""  # After applying context
    
    def to_dict(self) -> dict:
        return {
            "intent_type": self.intent_type.value,
            "confidence": self.confidence,
            "entities": self.entities.to_dict(),
            "needs_clarification": self.needs_clarification,
            "clarification_question": self.clarification_question,
        }


# =============================================================================
# TOOL PLANNING
# =============================================================================

class ToolName(Enum):
    """Available tools."""
    GET_RECENT_EVENTS = "get_recent_events"
    GET_EVENT_DETAILS = "get_event_details"
    SEARCH_EVENTS = "search_events"
    GET_FIREWALL_STATUS = "get_firewall_status"
    GET_DEFENDER_STATUS = "get_defender_status"
    GET_UPDATE_STATUS = "get_update_status"
    SCAN_FILE = "scan_file"
    ANALYZE_URL_OFFLINE = "analyze_url_offline"
    ANALYZE_URL_ONLINE = "analyze_url_online"
    LOOKUP_KB_RULES = "lookup_kb_rules"
    GET_APP_HELP = "get_app_help"


@dataclass
class ToolCall:
    """A planned or executed tool call."""
    tool: ToolName
    args: dict = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
    executed: bool = False
    
    def to_dict(self) -> dict:
        return {
            "tool": self.tool.value,
            "args": self.args,
            "result": self.result if self.executed else None,
            "error": self.error,
            "executed": self.executed,
        }


@dataclass
class ToolPlan:
    """Plan for tool execution."""
    calls: list[ToolCall] = field(default_factory=list)
    use_online: bool = False
    reason: str = ""
    
    def to_dict(self) -> dict:
        return {
            "calls": [c.to_dict() for c in self.calls],
            "use_online": self.use_online,
            "reason": self.reason,
        }


# =============================================================================
# EVIDENCE AND ANALYSIS
# =============================================================================

@dataclass
class EventEvidence:
    """Evidence from an event."""
    record_id: int
    log_name: str
    provider: str
    event_id: int
    level: str
    time_created: str
    message: str
    fields: dict = field(default_factory=dict)
    # From KB lookup
    kb_title: Optional[str] = None
    kb_severity: Optional[str] = None
    kb_impact: Optional[str] = None
    kb_causes: list[str] = field(default_factory=list)
    kb_actions: list[str] = field(default_factory=list)
    kb_matched: bool = False
    
    def to_dict(self) -> dict:
        return {
            "type": "event",
            "record_id": self.record_id,
            "provider": self.provider,
            "event_id": self.event_id,
            "level": self.level,
            "time": self.time_created,
            "key_fields": self.fields,
            "kb_matched": self.kb_matched,
            "kb_title": self.kb_title,
            "kb_severity": self.kb_severity,
        }


@dataclass
class StatusEvidence:
    """Evidence from status check."""
    name: str  # "firewall", "defender", "updates"
    value: dict = field(default_factory=dict)
    is_healthy: bool = True
    issues: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "type": "status",
            "name": self.name,
            "value": self.value,
            "is_healthy": self.is_healthy,
            "issues": self.issues,
        }


@dataclass
class ScanEvidence:
    """Evidence from file/URL scan."""
    scan_type: str  # "file" or "url"
    target: str  # file path or URL
    verdict: str  # "clean", "suspicious", "malicious", "unknown"
    score: int  # 0-100
    signals: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "type": "scan",
            "scan_type": self.scan_type,
            "target": self.target,
            "verdict": self.verdict,
            "score": self.score,
            "signals": self.signals,
        }


@dataclass
class KBRuleEvidence:
    """Evidence from knowledge base rule lookup."""
    event_ids: list[int] = field(default_factory=list)
    rules: dict = field(default_factory=dict)  # event_id -> rule data
    
    def to_dict(self) -> dict:
        return {
            "type": "kb_rules",
            "event_ids": self.event_ids,
            "rules": self.rules,
        }


@dataclass
class Evidence:
    """All gathered evidence."""
    events: list[EventEvidence] = field(default_factory=list)
    statuses: list[StatusEvidence] = field(default_factory=list)
    scans: list[ScanEvidence] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    
    def to_evidence_list(self) -> list[dict]:
        """Convert to list for schema output."""
        result = []
        for e in self.events:
            result.append(e.to_dict())
        for s in self.statuses:
            result.append(s.to_dict())
        for sc in self.scans:
            result.append(sc.to_dict())
        return result
    
    def has_issues(self) -> bool:
        """Check if any evidence indicates issues."""
        for e in self.events:
            if e.level.lower() in ("error", "critical", "warning"):
                return True
        for s in self.statuses:
            if not s.is_healthy:
                return True
        for sc in self.scans:
            if sc.verdict in ("suspicious", "malicious"):
                return True
        return False


# =============================================================================
# ANALYSIS RESULTS
# =============================================================================

@dataclass
class SecurityAnalysis:
    """Security analysis from reasoner agent."""
    risk_level: str  # "none", "low", "medium", "high", "critical"
    risk_score: int  # 0-100
    summary: str
    correlations: list[str] = field(default_factory=list)
    why_it_happened: list[str] = field(default_factory=list)
    what_it_affects: list[str] = field(default_factory=list)
    what_to_do: list[str] = field(default_factory=list)


# =============================================================================
# RESPONSE SCHEMA (STRICT OUTPUT FORMAT)
# =============================================================================

@dataclass
class TechnicalDetails:
    """Technical details section of response."""
    source: str  # "rules", "live_snapshot", "scan_result", "web", "mixed"
    confidence: str  # "low", "medium", "high"
    evidence: list[dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


@dataclass
class AssistantResponse:
    """
    The final response following the STRICT schema.
    
    This is what gets returned to the UI.
    """
    answer: str  # Short direct answer (2-6 lines)
    why_it_happened: list[str]  # Bullet points
    what_it_affects: list[str]  # Bullet points
    what_to_do_now: list[str]  # Bullet points
    technical_details: TechnicalDetails
    follow_up_suggestions: list[str]  # Clickable follow-up questions
    
    # Internal flags (not in output)
    _is_valid: bool = True
    _validation_errors: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to the strict JSON schema."""
        return {
            "answer": self.answer,
            "why_it_happened": self.why_it_happened,
            "what_it_affects": self.what_it_affects,
            "what_to_do_now": self.what_to_do_now,
            "technical_details": self.technical_details.to_dict(),
            "follow_up_suggestions": self.follow_up_suggestions,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def error_response(cls, error_message: str) -> "AssistantResponse":
        """Create an error response."""
        return cls(
            answer=f"I encountered an issue: {error_message}. Please try again or rephrase your question.",
            why_it_happened=["An internal error occurred during processing"],
            what_it_affects=["The response may be incomplete"],
            what_to_do_now=["Try rephrasing your question", "Check the Event Viewer directly"],
            technical_details=TechnicalDetails(
                source="mixed",
                confidence="low",
                evidence=[],
            ),
            follow_up_suggestions=[
                "Show my recent events",
                "Check my security status",
            ],
            _is_valid=False,
            _validation_errors=[error_message],
        )
    
    @classmethod
    def clarification_response(cls, question: str, context: str = "") -> "AssistantResponse":
        """Create a clarification request response."""
        answer = question
        if context:
            answer = f"{context}\n\n{question}"
        
        return cls(
            answer=answer,
            why_it_happened=["I need more information to provide an accurate answer"],
            what_it_affects=["Cannot proceed without clarification"],
            what_to_do_now=["Please answer the question above"],
            technical_details=TechnicalDetails(
                source="mixed",
                confidence="low",
                evidence=[],
            ),
            follow_up_suggestions=[],
        )
    
    @classmethod
    def build(
        cls,
        answer: str,
        why_it_happened: str | list[str],
        what_it_affects: str | list[str],
        what_to_do_now: str | list[str],
        source: str = "mixed",
        confidence: str = "medium",
        follow_up_suggestions: Optional[list[str]] = None,
        evidence: Optional[list[dict]] = None,
    ) -> "AssistantResponse":
        """
        Builder method for creating responses with simpler inputs.
        
        Accepts strings or lists for bullet point fields,
        automatically converting strings to single-item lists.
        """
        def to_list(val) -> list[str]:
            if isinstance(val, str):
                return [val] if val else []
            return val if val else []
        
        return cls(
            answer=answer,
            why_it_happened=to_list(why_it_happened),
            what_it_affects=to_list(what_it_affects),
            what_to_do_now=to_list(what_to_do_now),
            technical_details=TechnicalDetails(
                source=source,
                confidence=confidence,
                evidence=evidence or [],
            ),
            follow_up_suggestions=follow_up_suggestions or [],
        )


# =============================================================================
# CONVERSATION MEMORY
# =============================================================================

@dataclass
class ConversationTurn:
    """A single turn in conversation."""
    role: str  # "user" or "assistant"
    content: str
    intent: Optional[IntentType] = None
    entities: Optional[ExtractedEntities] = None
    timestamp: str = ""


@dataclass
class ConversationState:
    """State tracking for conversation memory."""
    turns: list[ConversationTurn] = field(default_factory=list)
    last_explained_event: Optional[EventEvidence] = None
    last_intent: Optional[IntentType] = None
    last_entities: Optional[ExtractedEntities] = None
    summary_shown: bool = False
    security_check_done: bool = False
    
    def add_user_turn(self, message: str, intent: Optional[IntentType] = None, entities: Optional[ExtractedEntities] = None):
        """Add a user message to history."""
        self.turns.append(ConversationTurn(
            role="user",
            content=message,
            intent=intent,
            entities=entities,
        ))
        # Keep only last 10 turns
        if len(self.turns) > 20:
            self.turns = self.turns[-20:]
    
    def add_assistant_turn(self, response: AssistantResponse):
        """Add assistant response to history."""
        self.turns.append(ConversationTurn(
            role="assistant",
            content=response.answer,
        ))
    
    def get_recent_context(self, n: int = 6) -> str:
        """Get recent conversation for context."""
        recent = self.turns[-n:] if len(self.turns) >= n else self.turns
        lines = []
        for turn in recent:
            role = "User" if turn.role == "user" else "Assistant"
            content = turn.content[:200] + "..." if len(turn.content) > 200 else turn.content
            lines.append(f"{role}: {content}")
        return "\n".join(lines)


# =============================================================================
# MAIN ASSISTANT STATE (Passed through the graph)
# =============================================================================

@dataclass
class AssistantState:
    """
    The main state object passed through the LangGraph workflow.
    
    Each agent reads from and writes to this state.
    """
    # Input
    user_message: str = ""
    conversation: ConversationState = field(default_factory=ConversationState)
    online_enabled: bool = False
    
    # After Intent Detection
    intent: Optional[UserIntent] = None
    
    # After Planning
    plan: Optional[ToolPlan] = None
    
    # After Data Fetching
    evidence: Optional[Evidence] = None
    
    # After Rules Engine
    kb_analysis: dict = field(default_factory=dict)
    
    # After Security Reasoner
    security_analysis: Optional[SecurityAnalysis] = None
    
    # After Response Generation
    response: Optional[AssistantResponse] = None
    
    # Control flow
    should_clarify: bool = False
    revision_count: int = 0
    max_revisions: int = 1
    errors: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Serialize state for debugging."""
        return {
            "user_message": self.user_message,
            "intent": self.intent.to_dict() if self.intent else None,
            "plan": self.plan.to_dict() if self.plan else None,
            "evidence_count": len(self.evidence.events) if self.evidence else 0,
            "has_response": self.response is not None,
            "errors": self.errors,
        }
