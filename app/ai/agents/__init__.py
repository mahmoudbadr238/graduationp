"""
Sentinel Smart Security Assistant - Agent-Based Architecture
=============================================================

This module implements a LangGraph-based multi-agent system for intelligent
security analysis and assistance.

Quick Start:
    from app.ai.agents import SmartAssistant
    
    assistant = SmartAssistant()
    response = assistant.ask("Are there any security concerns?")
    print(response)
    
    # Get structured response
    response = assistant.ask_structured("Explain event 4625")
    print(response["answer"])
    print(response["what_to_do_now"])

Architecture:
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER MESSAGE                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      INTENT DETECTOR AGENT                                  │
│  • Classify intent (event_explain, security_check, file_scan, etc.)         │
│  • Extract entities (event_id, file_path, url, provider)                    │
│  • Detect if clarification needed                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PLANNER AGENT                                       │
│  • Decide which tools to call                                               │
│  • Order of execution                                                       │
│  • Offline vs Online mode                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       DATA FETCH AGENT                                      │
│  • Execute tool calls                                                       │
│  • Gather structured evidence                                               │
│  • Handle errors gracefully                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RULES ENGINE AGENT                                       │
│  • Apply offline KB (provider + event_id → explanation)                     │
│  • Use templates for unknown events                                         │
│  • NEVER hallucinate event meanings                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SECURITY REASONER AGENT                                  │
│  • Correlate signals across events                                          │
│  • Assess risk level                                                        │
│  • Optional: enrich with online threat intel                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     RESPONSE CRITIC AGENT                                   │
│  • Check schema compliance                                                  │
│  • Detect repetition / missing fields                                       │
│  • Validate answer matches intent                                           │
│  • Revise once if needed                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      STRUCTURED RESPONSE                                    │
│  { answer, why_it_happened, what_it_affects, what_to_do_now,                │
│    is_normal, confidence, technical_details, follow_up_suggestions }        │
└─────────────────────────────────────────────────────────────────────────────┘

Key Design Principles:
1. Offline-First: KB rules are ALWAYS checked first
2. Intent-First: Specific queries get specific answers (no generic summaries)
3. Evidence-Based: All answers grounded in tool outputs
4. Schema-Strict: Every response follows the exact JSON schema
"""

# Schema types
from .schema import (
    IntentType,
    ExtractedEntities,
    UserIntent,
    ToolName,
    ToolCall,
    ToolPlan,
    EventEvidence,
    StatusEvidence,
    ScanEvidence,
    KBRuleEvidence,
    Evidence,
    SecurityAnalysis,
    TechnicalDetails,
    AssistantResponse,
    ConversationState,
    ConversationTurn,
    AssistantState,
)

# Tools
from .tools import ToolRegistry

# Agents
from .intent_detector import IntentDetectorAgent, create_intent_detector
from .planner import PlannerAgent, create_planner
from .data_fetcher import DataFetchAgent, create_data_fetcher
from .rules_engine import RulesEngineAgent, create_rules_engine
from .security_reasoner import SecurityReasonerAgent, create_security_reasoner
from .response_critic import ResponseCriticAgent, create_response_critic

# Graph and orchestration
from .graph import AgentGraph, SimpleGraphRunner, create_agent_graph, create_simple_runner
from .orchestrator import (
    SmartAssistant,
    AsyncSmartAssistant,
    QtSmartAssistant,
    create_assistant,
    create_qt_assistant,
    get_assistant,
    ask,
    ask_structured,
)

# Qt worker (production-grade background processing)
from .qt_worker import (
    ResponseCache,
    RequestThrottler,
    create_controller,
    create_worker_thread,
)

__all__ = [
    # Schema types
    "IntentType",
    "ExtractedEntities",
    "UserIntent",
    "ToolName",
    "ToolCall",
    "ToolPlan",
    "EventEvidence",
    "StatusEvidence",
    "ScanEvidence",
    "KBRuleEvidence",
    "Evidence",
    "SecurityAnalysis",
    "TechnicalDetails",
    "AssistantResponse",
    "ConversationState",
    "AssistantState",
    # Tools
    "ToolRegistry",
    # Agents
    "IntentDetectorAgent",
    "create_intent_detector",
    "PlannerAgent",
    "create_planner",
    "DataFetchAgent",
    "create_data_fetcher",
    "RulesEngineAgent",
    "create_rules_engine",
    "SecurityReasonerAgent",
    "create_security_reasoner",
    "ResponseCriticAgent",
    "create_response_critic",
    # Graph
    "AgentGraph",
    "SimpleGraphRunner",
    "create_agent_graph",
    "create_simple_runner",
    # Orchestrators
    "SmartAssistant",
    "AsyncSmartAssistant",
    "QtSmartAssistant",
    "create_assistant",
    "create_qt_assistant",
    "get_assistant",
    "ask",
    "ask_structured",
    # Qt Worker (production)
    "ResponseCache",
    "RequestThrottler",
    "create_controller",
    "create_worker_thread",
]
