"""
Planner Agent
=============
Decides which tools to call based on user intent.

The Planner receives the classified intent and entities, then creates
a ToolPlan specifying which tools to execute and in what order.

CRITICAL RULES:
1. SECURITY_CHECK intent MUST call: firewall + defender + update_status + recent_events
2. EVENT_EXPLAIN intent MUST call: get_event_details + lookup_kb_rules
3. Tool calls should be minimal - only fetch what's needed
4. KB rules lookup should ALWAYS be included for event-related queries
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from .schema import (
    IntentType,
    ToolName,
    ToolCall,
    ToolPlan,
    UserIntent,
    ExtractedEntities,
    AssistantState,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Tool Planning Rules
# =============================================================================

@dataclass
class PlanningRule:
    """A rule that maps intent to required tool calls."""
    intent: IntentType
    required_tools: List[ToolCall]
    optional_tools: List[ToolCall] = field(default_factory=list)
    description: str = ""


def create_tool_call(tool: ToolName, args: Optional[Dict[str, Any]] = None) -> ToolCall:
    """Helper to create a ToolCall matching schema structure."""
    return ToolCall(
        tool=tool,
        args=args or {},
    )


# Define the planning rules for each intent type
PLANNING_RULES: Dict[IntentType, PlanningRule] = {
    
    # EXPLAIN A SPECIFIC EVENT
    IntentType.EVENT_EXPLAIN: PlanningRule(
        intent=IntentType.EVENT_EXPLAIN,
        required_tools=[
            create_tool_call(ToolName.GET_EVENT_DETAILS),
            create_tool_call(ToolName.LOOKUP_KB_RULES),
        ],
        optional_tools=[],
        description="Get event details and KB rules for explanation",
    ),
    
    # OVERALL SECURITY CHECK
    IntentType.SECURITY_CHECK: PlanningRule(
        intent=IntentType.SECURITY_CHECK,
        required_tools=[
            create_tool_call(ToolName.GET_FIREWALL_STATUS),
            create_tool_call(ToolName.GET_DEFENDER_STATUS),
            create_tool_call(ToolName.GET_UPDATE_STATUS),
            create_tool_call(ToolName.GET_RECENT_EVENTS, {"limit": 10, "level": "Warning"}),
        ],
        optional_tools=[],
        description="Full security posture check",
    ),
    
    # RECENT EVENTS / EVENT SUMMARY
    IntentType.EVENT_SUMMARY: PlanningRule(
        intent=IntentType.EVENT_SUMMARY,
        required_tools=[
            create_tool_call(ToolName.GET_RECENT_EVENTS),
        ],
        optional_tools=[
            create_tool_call(ToolName.LOOKUP_KB_RULES),
        ],
        description="Fetch recent security events",
    ),
    
    # SEARCH EVENTS
    IntentType.EVENT_SEARCH: PlanningRule(
        intent=IntentType.EVENT_SEARCH,
        required_tools=[
            create_tool_call(ToolName.SEARCH_EVENTS),
        ],
        optional_tools=[
            create_tool_call(ToolName.LOOKUP_KB_RULES),
        ],
        description="Search events by criteria",
    ),
    
    # FIREWALL STATUS
    IntentType.FIREWALL_STATUS: PlanningRule(
        intent=IntentType.FIREWALL_STATUS,
        required_tools=[
            create_tool_call(ToolName.GET_FIREWALL_STATUS),
        ],
        optional_tools=[],
        description="Check firewall status only",
    ),
    
    # DEFENDER STATUS
    IntentType.DEFENDER_STATUS: PlanningRule(
        intent=IntentType.DEFENDER_STATUS,
        required_tools=[
            create_tool_call(ToolName.GET_DEFENDER_STATUS),
        ],
        optional_tools=[],
        description="Check Windows Defender status only",
    ),
    
    # UPDATE STATUS
    IntentType.UPDATE_STATUS: PlanningRule(
        intent=IntentType.UPDATE_STATUS,
        required_tools=[
            create_tool_call(ToolName.GET_UPDATE_STATUS),
        ],
        optional_tools=[],
        description="Check Windows Update status",
    ),
    
    # FILE SCAN
    IntentType.FILE_SCAN: PlanningRule(
        intent=IntentType.FILE_SCAN,
        required_tools=[
            create_tool_call(ToolName.SCAN_FILE),
        ],
        optional_tools=[],
        description="Scan a file for malware",
    ),
    
    # URL SCAN
    IntentType.URL_SCAN: PlanningRule(
        intent=IntentType.URL_SCAN,
        required_tools=[
            create_tool_call(ToolName.ANALYZE_URL_OFFLINE),
        ],
        optional_tools=[
            create_tool_call(ToolName.ANALYZE_URL_ONLINE),
        ],
        description="Analyze URL safety (offline first, then online)",
    ),
    
    # FOLLOW-UP QUERY
    IntentType.FOLLOWUP: PlanningRule(
        intent=IntentType.FOLLOWUP,
        required_tools=[],  # Will be determined based on context
        optional_tools=[],
        description="Follow-up query - tools based on context",
    ),
    
    # UNKNOWN / CLARIFICATION
    IntentType.UNKNOWN: PlanningRule(
        intent=IntentType.UNKNOWN,
        required_tools=[],  # No tools needed - use existing context
        optional_tools=[],
        description="Unknown intent - may need clarification",
    ),
    
    # APP HELP
    IntentType.APP_HELP: PlanningRule(
        intent=IntentType.APP_HELP,
        required_tools=[
            create_tool_call(ToolName.GET_APP_HELP),
        ],
        optional_tools=[],
        description="Get app usage help",
    ),
    
    # SECURITY ADVICE
    IntentType.SECURITY_ADVICE: PlanningRule(
        intent=IntentType.SECURITY_ADVICE,
        required_tools=[
            # Gather context for advice
            create_tool_call(ToolName.GET_DEFENDER_STATUS),
            create_tool_call(ToolName.GET_FIREWALL_STATUS),
        ],
        optional_tools=[],
        description="Provide general security advice based on system state",
    ),
    
    # GREETING
    IntentType.GREETING: PlanningRule(
        intent=IntentType.GREETING,
        required_tools=[],  # No tools needed for greeting
        optional_tools=[],
        description="Greeting - no tools needed",
    ),
}


# =============================================================================
# Planner Agent
# =============================================================================

class PlannerAgent:
    """
    Creates a tool execution plan based on user intent.
    
    This agent is purely rule-based and does NOT use LLM.
    It maps intents to required tool calls.
    """
    
    def __init__(self):
        self.planning_rules = PLANNING_RULES
        logger.info("PlannerAgent initialized")
    
    def _create_plan_for_intent(self, intent: UserIntent, online_enabled: bool = False) -> ToolPlan:
        """Create a tool plan for the given intent."""
        intent_type = intent.intent_type
        entities = intent.entities
        
        # Get the planning rule for this intent
        rule = self.planning_rules.get(intent_type)
        
        if not rule:
            logger.warning(f"No planning rule for intent: {intent_type}")
            return ToolPlan(calls=[], reason="Unknown intent - no tools planned")
        
        # Start with required tools (make copies to avoid mutating the originals)
        calls: List[ToolCall] = []
        
        for tool_call in rule.required_tools:
            # Create a copy with updated args based on entities
            updated_call = self._update_tool_args(tool_call, entities)
            calls.append(updated_call)
        
        # Add optional tools if we have the needed entities
        for tool_call in rule.optional_tools:
            if self._should_include_optional(tool_call, entities):
                updated_call = self._update_tool_args(tool_call, entities)
                calls.append(updated_call)
        
        return ToolPlan(
            calls=calls,
            use_online=online_enabled,
            reason=rule.description,
        )
    
    def _update_tool_args(self, tool_call: ToolCall, entities: ExtractedEntities) -> ToolCall:
        """Update tool args based on extracted entities."""
        args = dict(tool_call.args)
        
        # Update args based on tool type and available entities
        if tool_call.tool == ToolName.GET_EVENT_DETAILS:
            if entities.event_ids:
                args['event_id'] = entities.event_ids[0]
            if entities.record_ids:
                args['record_id'] = entities.record_ids[0]
        
        elif tool_call.tool == ToolName.GET_RECENT_EVENTS:
            if entities.timeframe:
                args['time_range'] = entities.timeframe
            if entities.severity_filter:
                args['level'] = entities.severity_filter
            if 'limit' not in args:
                args['limit'] = 10
            if entities.log_names:
                args['log_names'] = entities.log_names
        
        elif tool_call.tool == ToolName.SEARCH_EVENTS:
            if entities.severity_filter:
                args['level'] = entities.severity_filter
            if entities.timeframe:
                args['time_range'] = entities.timeframe
            if entities.event_ids:
                args['event_ids'] = entities.event_ids
            if entities.log_names:
                args['log_names'] = entities.log_names
            if entities.providers:
                args['providers'] = entities.providers
        
        elif tool_call.tool == ToolName.SCAN_FILE:
            if entities.file_paths:
                args['file_path'] = entities.file_paths[0]
        
        elif tool_call.tool in (ToolName.ANALYZE_URL_OFFLINE, ToolName.ANALYZE_URL_ONLINE):
            if entities.urls:
                args['url'] = entities.urls[0]
        
        elif tool_call.tool == ToolName.LOOKUP_KB_RULES:
            if entities.event_ids:
                args['event_ids'] = entities.event_ids
        
        elif tool_call.tool == ToolName.GET_APP_HELP:
            if entities.feature_name:
                args['topic'] = entities.feature_name
        
        return ToolCall(
            tool=tool_call.tool,
            args=args,
        )
    
    def _should_include_optional(self, tool_call: ToolCall, entities: ExtractedEntities) -> bool:
        """Determine if an optional tool should be included."""
        # KB rules lookup should always be included if we have event IDs
        if tool_call.tool == ToolName.LOOKUP_KB_RULES:
            return bool(entities.event_ids)
        
        # Online URL analysis only if we have a URL
        if tool_call.tool == ToolName.ANALYZE_URL_ONLINE:
            return bool(entities.urls)
        
        return False
    
    def _handle_follow_up(self, state: AssistantState) -> ToolPlan:
        """Create a plan for follow-up queries based on conversation context."""
        # If we have context about the last event, plan to explain that
        if state.conversation and state.conversation.last_explained_event:
            last_event = state.conversation.last_explained_event
            return ToolPlan(
                calls=[
                    ToolCall(
                        tool=ToolName.GET_EVENT_DETAILS,
                        args={'event_id': last_event.event_id, 'record_id': last_event.record_id},
                    ),
                    ToolCall(
                        tool=ToolName.LOOKUP_KB_RULES,
                        args={'event_ids': [last_event.event_id]},
                    ),
                ],
                use_online=state.online_enabled,
                reason="Follow-up on previous event discussion",
            )
        
        # If no context, we need clarification
        return ToolPlan(
            calls=[],
            use_online=False,
            reason="Follow-up without context - need clarification",
        )
    
    def run(self, state: AssistantState) -> AssistantState:
        """
        Run the planner on the current state.
        
        Updates state with:
        - plan: ToolPlan with calls to make
        """
        if not state.intent:
            logger.error("No intent in state - cannot plan")
            state.plan = ToolPlan(calls=[], reason="No intent detected")
            return state
        
        intent = state.intent
        
        # Handle follow-up queries specially
        if intent.intent_type == IntentType.FOLLOWUP:
            state.plan = self._handle_follow_up(state)
        else:
            state.plan = self._create_plan_for_intent(intent, state.online_enabled)
        
        logger.info(
            f"Created plan with {len(state.plan.calls)} tool calls: "
            f"{[c.tool.value for c in state.plan.calls]}"
        )
        
        return state


# =============================================================================
# Factory Function
# =============================================================================

def create_planner() -> PlannerAgent:
    """Create a PlannerAgent instance."""
    return PlannerAgent()
