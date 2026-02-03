"""
Response Critic Agent
=====================
Validates and improves the final response.

This agent ensures the response is:
1. Complete (all required fields present)
2. Consistent (matches KB analysis)
3. Relevant (answers the user's question)
4. Well-formatted (proper JSON schema)

RESPONSIBILITIES:
1. Validate schema compliance
2. Check intent-response alignment
3. Ensure KB consistency
4. Add follow-up suggestions
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .schema import (
    IntentType,
    AssistantState,
    AssistantResponse,
    TechnicalDetails,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Validation Result
# =============================================================================

@dataclass
class ValidationResult:
    """Result of a validation check."""
    is_valid: bool
    issues: List[str]
    fixes_applied: List[str]


# =============================================================================
# Response Validator
# =============================================================================

class ResponseValidator:
    """Validates response against schema and intent."""
    
    def validate_schema(self, response: AssistantResponse) -> ValidationResult:
        """Validate the response matches the required schema."""
        issues = []
        fixes = []
        
        # Check required fields
        if not response.answer or len(response.answer) < 5:
            issues.append("Answer is too short or empty")
        
        if not response.why_it_happened:
            issues.append("Missing why_it_happened")
            response.why_it_happened = ["The system processed your request."]
            fixes.append("Added default why_it_happened")
        
        if not response.what_it_affects:
            issues.append("Missing what_it_affects")
            response.what_it_affects = ["System security and operation."]
            fixes.append("Added default what_it_affects")
        
        if not response.what_to_do_now:
            issues.append("Missing what_to_do_now")
            response.what_to_do_now = ["No specific action required."]
            fixes.append("Added default what_to_do_now")
        
        # Validate technical_details has confidence
        if response.technical_details:
            confidence = response.technical_details.confidence
            if confidence not in ("low", "medium", "high"):
                issues.append(f"Invalid confidence: {confidence}")
                response.technical_details.confidence = "medium"
                fixes.append("Fixed confidence to valid value")
        else:
            response.technical_details = TechnicalDetails(
                source="mixed",
                confidence="medium",
                evidence=[],
            )
            fixes.append("Added default technical_details")
        
        return ValidationResult(
            is_valid=len(issues) == 0 or len(fixes) == len(issues),
            issues=issues,
            fixes_applied=fixes,
        )
    
    def validate_intent_match(
        self,
        response: AssistantResponse,
        intent_type: IntentType,
        entities: Any
    ) -> ValidationResult:
        """Validate the response matches the user's intent."""
        issues = []
        fixes = []
        
        # For event explanation, ensure we mention the event ID
        if intent_type == IntentType.EVENT_EXPLAIN:
            if entities and entities.event_ids:
                event_id = entities.event_ids[0]
                if str(event_id) not in response.answer:
                    issues.append(f"Response doesn't mention requested event {event_id}")
                    # Don't auto-fix - just flag it
        
        # For security check, ensure we mention key components
        if intent_type == IntentType.SECURITY_CHECK:
            key_terms = ['firewall', 'defender', 'protection', 'security']
            if not any(term in response.answer.lower() for term in key_terms):
                issues.append("Security check response doesn't mention security components")
        
        # For scans, ensure we give a clear safe/unsafe verdict
        if intent_type in (IntentType.FILE_SCAN, IntentType.URL_SCAN):
            verdict_terms = ['safe', 'unsafe', 'risk', 'clean', 'suspicious', 'malicious']
            if not any(term in response.answer.lower() for term in verdict_terms):
                issues.append("Scan response doesn't include clear verdict")
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            fixes_applied=fixes,
        )
    
    def validate_consistency(
        self,
        response: AssistantResponse,
        kb_analysis: Optional[Dict[str, Any]]
    ) -> ValidationResult:
        """Validate response is consistent with KB analysis."""
        issues = []
        fixes = []
        
        if not kb_analysis:
            return ValidationResult(is_valid=True, issues=[], fixes_applied=[])
        
        # Check severity level consistency
        kb_severity = kb_analysis.get("max_severity", "info")
        
        # If KB says high severity but answer sounds casual, flag it
        if kb_severity in ("high", "critical"):
            casual_terms = ["don't worry", "nothing to worry", "perfectly normal"]
            if any(term in response.answer.lower() for term in casual_terms):
                issues.append(f"KB indicates {kb_severity} severity but response is too casual")
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            fixes_applied=fixes,
        )


# =============================================================================
# Response Critic Agent
# =============================================================================

class ResponseCriticAgent:
    """
    Validates and improves the final response.
    
    This agent ensures the response is:
    1. Complete (all required fields present)
    2. Consistent (matches KB analysis)
    3. Relevant (answers the user's question)
    4. Well-formatted (proper JSON schema)
    """
    
    def __init__(self):
        self.validator = ResponseValidator()
        logger.info("ResponseCriticAgent initialized")
    
    def _ensure_technical_details(self, state: AssistantState) -> TechnicalDetails:
        """Ensure technical details are present."""
        if state.response and state.response.technical_details:
            return state.response.technical_details
        
        # Build from evidence
        evidence_list = []
        source = "mixed"
        
        if state.evidence:
            if state.evidence.events:
                source = "live_snapshot"
                for event in state.evidence.events:
                    evidence_list.append(event.to_dict())
            
            if state.evidence.statuses:
                for status in state.evidence.statuses:
                    evidence_list.append(status.to_dict())
            
            if state.evidence.scans:
                source = "scan_result"
                for scan in state.evidence.scans:
                    evidence_list.append(scan.to_dict())
        
        # If KB was used, update source
        if state.kb_analysis and state.kb_analysis.get("has_kb_match"):
            source = "rules"
        
        return TechnicalDetails(
            source=source,
            confidence="high" if state.kb_analysis and state.kb_analysis.get("has_kb_match") else "medium",
            evidence=evidence_list,
        )
    
    def _ensure_follow_ups(
        self,
        response: AssistantResponse,
        intent_type: IntentType
    ) -> List[str]:
        """Ensure follow-up suggestions are present and relevant."""
        if response.follow_up_suggestions:
            return response.follow_up_suggestions
        
        # Generate default follow-ups based on intent
        follow_ups = {
            IntentType.EVENT_EXPLAIN: [
                "Would you like to see related events?",
                "Should I check for security concerns?",
            ],
            IntentType.SECURITY_CHECK: [
                "Would you like details on any specific issue?",
                "Should I explain how to fix these?",
            ],
            IntentType.EVENT_SUMMARY: [
                "Would you like me to explain any of these events?",
                "Should I filter by a specific type?",
            ],
            IntentType.FILE_SCAN: [
                "Would you like to scan another file?",
                "Should I check your overall security?",
            ],
            IntentType.URL_SCAN: [
                "Would you like to check another URL?",
                "Should I explain what makes a URL suspicious?",
            ],
            IntentType.FIREWALL_STATUS: [
                "Would you like to check Windows Defender too?",
                "Should I look at recent security events?",
            ],
            IntentType.DEFENDER_STATUS: [
                "Would you like to check your firewall status?",
                "Should I look for any detected threats?",
            ],
            IntentType.GREETING: [
                "How can I help you today?",
                "Would you like to check your system security?",
            ],
            IntentType.APP_HELP: [
                "Would you like to know about a specific feature?",
                "Should I check your security status?",
            ],
        }
        
        return follow_ups.get(intent_type, [
            "Is there anything else you'd like to know?",
        ])
    
    def _update_conversation_state(self, state: AssistantState) -> None:
        """Update conversation state with this interaction."""
        if not state.conversation:
            from .schema import ConversationState
            state.conversation = ConversationState()
        
        # Track last event if we explained one
        if state.evidence and state.evidence.events:
            state.conversation.last_explained_event = state.evidence.events[0]
        
        # Track last intent
        if state.intent:
            state.conversation.last_intent = state.intent.intent_type
            state.conversation.last_entities = state.intent.entities
            
            # Add to history
            state.conversation.add_user_turn(
                message=state.user_message,
                intent=state.intent.intent_type,
                entities=state.intent.entities,
            )
            
            if state.response:
                state.conversation.add_assistant_turn(state.response)
    
    def run(self, state: AssistantState) -> AssistantState:
        """
        Run the response critic on the current state.
        
        Updates state with:
        - Validated and improved response
        - Updated conversation state
        """
        if not state.response:
            logger.warning("No response to validate")
            return state
        
        response = state.response
        
        # 1. Validate schema
        schema_result = self.validator.validate_schema(response)
        if not schema_result.is_valid and not schema_result.fixes_applied:
            logger.warning(f"Schema validation issues: {schema_result.issues}")
        
        # 2. Validate intent match
        if state.intent:
            intent_result = self.validator.validate_intent_match(
                response,
                state.intent.intent_type,
                state.intent.entities,
            )
            if not intent_result.is_valid:
                logger.warning(f"Intent match issues: {intent_result.issues}")
        
        # 3. Validate KB consistency
        if state.kb_analysis:
            kb_result = self.validator.validate_consistency(
                response,
                state.kb_analysis,
            )
            if not kb_result.is_valid:
                logger.warning(f"KB consistency issues: {kb_result.issues}")
        
        # 4. Ensure technical details
        if not response.technical_details or not response.technical_details.evidence:
            response.technical_details = self._ensure_technical_details(state)
        
        # 5. Ensure follow-up suggestions
        if state.intent and not response.follow_up_suggestions:
            response.follow_up_suggestions = self._ensure_follow_ups(
                response,
                state.intent.intent_type,
            )
        
        # 6. Update conversation state
        self._update_conversation_state(state)
        
        logger.info("Response validation complete")
        
        return state


# =============================================================================
# Factory Function
# =============================================================================

def create_response_critic() -> ResponseCriticAgent:
    """Create a ResponseCriticAgent instance."""
    return ResponseCriticAgent()
