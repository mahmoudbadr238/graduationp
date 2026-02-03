"""
Agent Workflow Graph
====================
LangGraph-style workflow connecting all agents.

This module defines the complete agent pipeline:

    User Query
        │
        ▼
    ┌─────────────────┐
    │ Intent Detector │  ← Classify intent, extract entities
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │    Planner      │  ← Decide which tools to call
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │  Data Fetcher   │  ← Execute tool calls
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │  Rules Engine   │  ← Apply offline KB rules (CRITICAL)
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │Security Reasoner│  ← Correlate and explain
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │Response Critic  │  ← Validate and improve
    └────────┬────────┘
             │
             ▼
        Final Response
"""

import logging
from typing import Dict, Optional, Any, Callable, List
from dataclasses import dataclass, field
from enum import Enum

from .schema import AssistantState, ConversationState, AssistantResponse
from .intent_detector import IntentDetectorAgent, create_intent_detector
from .planner import PlannerAgent, create_planner
from .data_fetcher import DataFetchAgent, create_data_fetcher
from .rules_engine import RulesEngineAgent, create_rules_engine
from .security_reasoner import SecurityReasonerAgent, create_security_reasoner
from .response_critic import ResponseCriticAgent, create_response_critic
from .tools import ToolRegistry

logger = logging.getLogger(__name__)


# =============================================================================
# Graph Node Types
# =============================================================================

class NodeType(Enum):
    """Types of nodes in the graph."""
    INTENT_DETECTOR = "intent_detector"
    PLANNER = "planner"
    DATA_FETCHER = "data_fetcher"
    RULES_ENGINE = "rules_engine"
    SECURITY_REASONER = "security_reasoner"
    RESPONSE_CRITIC = "response_critic"
    END = "end"


@dataclass
class GraphNode:
    """A node in the agent graph."""
    name: str
    node_type: NodeType
    agent: Optional[Any] = None
    run_func: Optional[Callable[[AssistantState], AssistantState]] = None
    next_node: Optional[str] = None
    conditional_edges: Dict[str, str] = field(default_factory=dict)


# =============================================================================
# Agent Graph
# =============================================================================

class AgentGraph:
    """
    A graph of agents that process user queries.
    
    This is a simplified LangGraph-style implementation that:
    1. Defines nodes (agents)
    2. Defines edges (flow between agents)
    3. Executes the graph on a state
    
    The graph is linear by default but supports conditional edges.
    """
    
    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        self.nodes: Dict[str, GraphNode] = {}
        self.entry_point: Optional[str] = None
        self.tool_registry = tool_registry or ToolRegistry()
        
        # Build the default graph
        self._build_default_graph()
        
        logger.info("AgentGraph initialized with default workflow")
    
    def _build_default_graph(self):
        """Build the default agent pipeline."""
        
        # Create agents
        intent_detector = create_intent_detector()
        planner = create_planner()
        data_fetcher = create_data_fetcher(self.tool_registry)
        rules_engine = create_rules_engine()
        security_reasoner = create_security_reasoner()
        response_critic = create_response_critic()
        
        # Define nodes
        self.add_node(GraphNode(
            name="intent_detector",
            node_type=NodeType.INTENT_DETECTOR,
            agent=intent_detector,
            run_func=intent_detector.run,
            next_node="planner",
        ))
        
        self.add_node(GraphNode(
            name="planner",
            node_type=NodeType.PLANNER,
            agent=planner,
            run_func=planner.run,
            next_node="data_fetcher",
        ))
        
        self.add_node(GraphNode(
            name="data_fetcher",
            node_type=NodeType.DATA_FETCHER,
            agent=data_fetcher,
            run_func=data_fetcher.run,
            next_node="rules_engine",
        ))
        
        self.add_node(GraphNode(
            name="rules_engine",
            node_type=NodeType.RULES_ENGINE,
            agent=rules_engine,
            run_func=rules_engine.run,
            next_node="security_reasoner",
        ))
        
        self.add_node(GraphNode(
            name="security_reasoner",
            node_type=NodeType.SECURITY_REASONER,
            agent=security_reasoner,
            run_func=security_reasoner.run,
            next_node="response_critic",
        ))
        
        self.add_node(GraphNode(
            name="response_critic",
            node_type=NodeType.RESPONSE_CRITIC,
            agent=response_critic,
            run_func=response_critic.run,
            next_node="end",
        ))
        
        self.add_node(GraphNode(
            name="end",
            node_type=NodeType.END,
        ))
        
        # Set entry point
        self.entry_point = "intent_detector"
    
    def add_node(self, node: GraphNode):
        """Add a node to the graph."""
        self.nodes[node.name] = node
    
    def get_next_node(self, current_node: str, state: AssistantState) -> Optional[str]:
        """Get the next node to execute."""
        node = self.nodes.get(current_node)
        if not node:
            return None
        
        # Check conditional edges first
        if node.conditional_edges:
            for condition, next_node in node.conditional_edges.items():
                if self._evaluate_condition(condition, state):
                    return next_node
        
        # Return default next node
        return node.next_node
    
    def _evaluate_condition(self, condition: str, state: AssistantState) -> bool:
        """Evaluate a condition for conditional edges."""
        # Simple condition evaluation - can be extended
        if condition == "needs_clarification":
            return state.should_clarify
        if condition == "has_error":
            return bool(state.errors)
        return False
    
    def run(
        self,
        query: str,
        conversation_state: Optional[ConversationState] = None
    ) -> AssistantState:
        """
        Run the graph on a user query.
        
        Args:
            query: The user's query
            conversation_state: Optional conversation context
        
        Returns:
            The final AssistantState with response
        """
        # Initialize state
        state = AssistantState(
            user_message=query,
            conversation=conversation_state or ConversationState(),
        )
        
        logger.info(f"Starting graph execution for query: {query[:50]}...")
        
        # Execute nodes in sequence
        current_node = self.entry_point
        visited_nodes: List[str] = []
        max_iterations = 10  # Safety limit
        
        while current_node and current_node != "end" and len(visited_nodes) < max_iterations:
            node = self.nodes.get(current_node)
            if not node:
                logger.error(f"Node not found: {current_node}")
                break
            
            visited_nodes.append(current_node)
            
            # Execute the node
            if node.run_func:
                logger.debug(f"Executing node: {current_node}")
                try:
                    state = node.run_func(state)
                except Exception as e:
                    logger.error(f"Error in node {current_node}: {e}", exc_info=True)
                    # Continue to next node - don't fail completely
            
            # Get next node
            current_node = self.get_next_node(current_node, state)
        
        logger.info(f"Graph execution complete. Visited: {' -> '.join(visited_nodes)}")
        
        return state


# =============================================================================
# Simplified Graph Runner
# =============================================================================

class SimpleGraphRunner:
    """
    A simplified runner that executes agents in sequence.
    
    This is an alternative to the full graph for simpler use cases.
    """
    
    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        self.tool_registry = tool_registry or ToolRegistry()
        
        # Create agents
        self.intent_detector = create_intent_detector()
        self.planner = create_planner()
        self.data_fetcher = create_data_fetcher(self.tool_registry)
        self.rules_engine = create_rules_engine()
        self.security_reasoner = create_security_reasoner()
        self.response_critic = create_response_critic()
        
        logger.info("SimpleGraphRunner initialized")
    
    def run(
        self,
        query: str,
        conversation_state: Optional[ConversationState] = None
    ) -> AssistantState:
        """Run the agent pipeline on a query."""
        
        # Initialize state
        state = AssistantState(
            user_message=query,
            conversation=conversation_state or ConversationState(),
        )
        
        logger.info(f"Processing query: {query[:50]}...")
        
        try:
            # 1. Detect intent
            state = self.intent_detector.run(state)
            
            # 2. Plan tools
            state = self.planner.run(state)
            
            # 3. Fetch data
            state = self.data_fetcher.run(state)
            
            # 4. Apply KB rules
            state = self.rules_engine.run(state)
            
            # 5. Reason about security
            state = self.security_reasoner.run(state)
            
            # 6. Validate response
            state = self.response_critic.run(state)
            
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            # Create error response using the build helper
            state.response = AssistantResponse.build(
                answer=f"I encountered an error processing your request: {str(e)}",
                why_it_happened="An internal error occurred.",
                what_it_affects="Unable to complete the analysis.",
                what_to_do_now="Please try rephrasing your question or try again later.",
                source="mixed",
                confidence="low",
            )
        
        return state


# =============================================================================
# Factory Functions
# =============================================================================

def create_agent_graph(tool_registry: Optional[ToolRegistry] = None) -> AgentGraph:
    """Create an AgentGraph instance."""
    return AgentGraph(tool_registry)


def create_simple_runner(tool_registry: Optional[ToolRegistry] = None) -> SimpleGraphRunner:
    """Create a SimpleGraphRunner instance."""
    return SimpleGraphRunner(tool_registry)
