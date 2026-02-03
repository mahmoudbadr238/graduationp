"""
Intent Detector Agent
=====================
Classifies user intent and extracts entities from user queries.

This is the FIRST agent in the pipeline. It must:
1. Classify the user's intent (event_explain, security_check, file_scan, etc.)
2. Extract relevant entities (event IDs, file paths, URLs, time ranges)
3. Detect follow-up queries that refer to previous context
4. Identify confusion or clarification requests
"""

import re
import logging
from typing import Optional, List, Tuple

from .schema import (
    IntentType,
    ExtractedEntities,
    UserIntent,
    AssistantState,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Intent Classification Patterns
# =============================================================================

INTENT_PATTERNS: List[Tuple[IntentType, List[str]]] = [
    # Specific Event Explanation - HIGHEST PRIORITY
    (IntentType.EVENT_EXPLAIN, [
        r"\b(?:explain|what\s+is|what\s+does|tell\s+me\s+about|describe)\b.*\b(?:event\s*(?:id)?\s*\d+|\d+)\b",
        r"\bevent\s*(?:id)?\s*(\d+)\b",
        r"\b(?:what|why).*\bevent\s*\d+\b",
        r"\bid\s*(\d+)\b.*\b(?:mean|about|explain)\b",
    ]),
    
    # Security Status Check
    (IntentType.SECURITY_CHECK, [
        r"\b(?:any|are\s+there)\s+(?:security\s+)?(?:concerns?|issues?|problems?|threats?)\b",
        r"\b(?:am\s+i|is\s+my\s+(?:system|computer|pc))\s+(?:safe|secure|protected)\b",
        r"\b(?:security|protection)\s+(?:status|check|overview)\b",
        r"\b(?:what|how).*(?:security|protection)\b.*\?",
        r"\bcheck\s+(?:my\s+)?security\b",
    ]),
    
    # Recent Events Summary
    (IntentType.EVENT_SUMMARY, [
        r"\b(?:recent|latest|last|new)\s+(?:\d+\s+)?(?:events?|logs?|activity|activities)\b",
        r"\b(?:what|show|list|get).*(?:recent|latest|happened|occurring)\b",
        r"\bwhat\s+(?:is\s+)?happening\b",
        r"\b(?:events?|logs?)\s+(?:from\s+)?(?:today|yesterday|this\s+week|last\s+\d+\s+(?:hours?|minutes?|days?))\b",
    ]),
    
    # Event Search
    (IntentType.EVENT_SEARCH, [
        r"\b(?:search|find|look\s+for|filter)\b.*\b(?:events?|logs?)\b",
        r"\b(?:events?|logs?)\b.*\b(?:with|containing|matching|where|that)\b",
        r"\b(?:show|find)\s+(?:all\s+)?(?:error|warning|critical|info)\s+(?:events?|logs?)\b",
    ]),
    
    # Firewall Status
    (IntentType.FIREWALL_STATUS, [
        r"\bfirewall\b.*\b(?:status|enabled|disabled|on|off|check|rules?)\b",
        r"\b(?:is|check)\s+(?:my\s+)?firewall\b",
        r"\bfirewall\s+(?:settings?|config(?:uration)?)\b",
    ]),
    
    # Defender Status
    (IntentType.DEFENDER_STATUS, [
        r"\b(?:windows\s+)?defender\b.*\b(?:status|enabled|disabled|on|off|check)\b",
        r"\bantivirus\b.*\b(?:status|running|active)\b",
        r"\b(?:is|check)\s+(?:my\s+)?(?:defender|antivirus)\b",
        r"\b(?:real[\s-]?time\s+)?protection\s+(?:status|enabled|on)\b",
    ]),
    
    # Update Status
    (IntentType.UPDATE_STATUS, [
        r"\b(?:windows\s+)?update[s]?\b.*\b(?:status|pending|available|check)\b",
        r"\b(?:system|security)\s+updates?\b",
        r"\b(?:is|am\s+i)\s+(?:up[\s-]?to[\s-]?date|updated)\b",
    ]),
    
    # File Scan
    (IntentType.FILE_SCAN, [
        r"\b(?:scan|check|analyze|inspect)\b.*\b(?:file|path|executable|\.exe|\.dll)\b",
        r"\b(?:is\s+(?:this|the)\s+)?file\b.*\b(?:safe|malicious|suspicious|clean)\b",
        r"[a-zA-Z]:\\[^\s]+",  # Windows path pattern
    ]),
    
    # URL Analysis
    (IntentType.URL_SCAN, [
        r"\b(?:check|analyze|scan|is)\b.*\b(?:url|link|website|domain)\b",
        r"\b(?:url|link|website|domain)\b.*\b(?:safe|malicious|phishing|suspicious)\b",
        r"https?://[^\s]+",  # URL pattern
    ]),
    
    # Follow-up (references previous context)
    (IntentType.FOLLOWUP, [
        r"^(?:and|also|what\s+about|how\s+about)\b",
        r"\b(?:that|this|it|those|these)\b.*\b(?:mean|safe|normal|bad|concern)\b",
        r"\bwhy\s+(?:is\s+)?(?:that|this|it)\b",
        r"\bmore\s+(?:details?|info(?:rmation)?)\b",
        r"\bwhat\s+(?:should|can)\s+i\s+do\b",
        r"^(?:ok|okay|got\s+it|thanks?)[\s,]*(?:but|and|so|now)\b",
    ]),
    
    # App Help
    (IntentType.APP_HELP, [
        r"\b(?:how\s+(?:do\s+i|to|can\s+i))\b.*\b(?:use|navigate|find|access)\b",
        r"\bwhere\s+(?:is|can\s+i\s+find)\b",
        r"\b(?:help|guide|tutorial)\b",
        r"\bwhat\s+can\s+(?:you|this\s+app)\s+do\b",
        r"\b(?:features?|capabilities|functions?)\b",
    ]),
    
    # Greeting
    (IntentType.GREETING, [
        r"^(?:hi|hello|hey|good\s+(?:morning|afternoon|evening)|greetings)\b",
        r"^(?:what's\s+up|howdy|yo)\b",
    ]),
]


# =============================================================================
# Entity Extraction Functions
# =============================================================================

def extract_event_ids(text: str) -> List[int]:
    """Extract event IDs from text."""
    patterns = [
        r"\bevent\s*(?:id)?\s*[:#]?\s*(\d+)\b",
        r"\bid\s*[:#]?\s*(\d+)\b",
        r"\b(\d{4,5})\b",  # Common Windows event IDs are 4-5 digits
    ]
    
    event_ids = set()
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            event_id = int(m)
            # Filter to valid Windows event ID range
            if 1 <= event_id <= 65535:
                event_ids.add(event_id)
    
    return sorted(event_ids)


def extract_file_paths(text: str) -> List[str]:
    """Extract file paths from text."""
    # Windows paths
    win_pattern = r'[A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*'
    paths = re.findall(win_pattern, text)
    
    # Also check for quoted paths
    quoted_pattern = r'"([^"]+)"'
    for match in re.findall(quoted_pattern, text):
        if '\\' in match or '/' in match:
            paths.append(match)
    
    return list(set(paths))


def extract_urls(text: str) -> List[str]:
    """Extract URLs from text."""
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, text, re.IGNORECASE)
    
    # Also extract domain-only mentions
    domain_pattern = r'\b(?:www\.)?([a-zA-Z0-9-]+(?:\.[a-zA-Z]{2,})+)\b'
    domains = re.findall(domain_pattern, text)
    
    return list(set(urls + [f"http://{d}" for d in domains if d not in str(urls)]))


def extract_timeframe(text: str) -> Optional[str]:
    """Extract time range references from text."""
    patterns = [
        (r'\blast\s+(\d+)\s+(hour|minute|day|week)s?\b', lambda m: f"last_{m.group(1)}_{m.group(2)}s"),
        (r'\btoday\b', lambda m: "today"),
        (r'\byesterday\b', lambda m: "yesterday"),
        (r'\bthis\s+week\b', lambda m: "this_week"),
        (r'\bpast\s+(\d+)\s+(hour|minute|day|week)s?\b', lambda m: f"past_{m.group(1)}_{m.group(2)}s"),
    ]
    
    for pattern, formatter in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return formatter(match)
    
    return None


def extract_severity_filter(text: str) -> Optional[str]:
    """Extract event level/severity filter from text."""
    level_map = {
        r'\berror\b': 'Error',
        r'\bwarning\b': 'Warning',
        r'\bcritical\b': 'Critical',
        r'\binformation(?:al)?\b': 'Information',
        r'\binfo\b': 'Information',
    }
    
    for pattern, level in level_map.items():
        if re.search(pattern, text, re.IGNORECASE):
            return level
    
    return None


def extract_log_names(text: str) -> List[str]:
    """Extract Windows log names from text."""
    log_patterns = {
        r'\bsecurity\s*log\b': 'Security',
        r'\bsystem\s*log\b': 'System',
        r'\bapplication\s*log\b': 'Application',
        r'\bsecurity\b': 'Security',
    }
    
    logs = []
    for pattern, log_name in log_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            if log_name not in logs:
                logs.append(log_name)
    
    return logs


# =============================================================================
# Intent Detector Agent
# =============================================================================

class IntentDetectorAgent:
    """
    Classifies user intent and extracts entities.
    
    This agent is purely rule-based and does NOT use LLM.
    It uses pattern matching for fast, deterministic results.
    """
    
    def __init__(self):
        self.intent_patterns = INTENT_PATTERNS
        logger.info("IntentDetectorAgent initialized")
    
    def classify_intent(self, query: str) -> IntentType:
        """Classify the user's intent based on patterns."""
        query_lower = query.lower().strip()
        
        # Check each intent pattern in priority order
        for intent_type, patterns in self.intent_patterns:
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    logger.debug(f"Matched intent {intent_type.value} with pattern: {pattern}")
                    return intent_type
        
        # Default to event summary if mentions "events" without specific ID
        if 'event' in query_lower:
            return IntentType.EVENT_SUMMARY
        
        # If truly unknown
        return IntentType.UNKNOWN
    
    def extract_entities(self, query: str) -> ExtractedEntities:
        """Extract all relevant entities from the query."""
        return ExtractedEntities(
            event_ids=extract_event_ids(query),
            file_paths=extract_file_paths(query),
            urls=extract_urls(query),
            timeframe=extract_timeframe(query),
            severity_filter=extract_severity_filter(query),
            log_names=extract_log_names(query),
        )
    
    def detect_follow_up(self, query: str, conversation_state: Optional[dict] = None) -> bool:
        """Detect if this is a follow-up query referencing previous context."""
        follow_up_indicators = [
            r"^(?:and|also|but|so|then|now)\b",
            r"\b(?:that|this|it|those|these)\b(?!\s+(?:file|event|url))",
            r"^(?:why|what|how)\s+(?:about|is|does)\s+(?:that|this|it)\b",
            r"\bthe\s+(?:same|previous|last)\b",
            r"^(?:ok|okay|thanks?|got\s+it)[,.\s]",
        ]
        
        query_lower = query.lower().strip()
        
        for pattern in follow_up_indicators:
            if re.search(pattern, query_lower):
                return True
        
        # Short queries without explicit entities are often follow-ups
        if len(query.split()) <= 4 and not extract_event_ids(query):
            if conversation_state and conversation_state.get('last_explained_event'):
                return True
        
        return False
    
    def run(self, state: AssistantState) -> AssistantState:
        """
        Run the intent detector on the current state.
        
        Updates state with:
        - intent: UserIntent with type and entities
        """
        query = state.user_message
        
        # Classify intent
        intent_type = self.classify_intent(query)
        
        # Extract entities
        entities = self.extract_entities(query)
        
        # Special case: If we detected EVENT_EXPLAIN but found no event IDs,
        # and there's a last_explained_event in context, use that
        if intent_type == IntentType.EVENT_EXPLAIN and not entities.event_ids:
            if state.conversation and state.conversation.last_explained_event:
                entities.event_ids = [state.conversation.last_explained_event.event_id]
                logger.debug(f"Using last_explained_event from context: {entities.event_ids[0]}")
        
        # Detect follow-up
        is_follow_up = self.detect_follow_up(query)
        
        # Create UserIntent
        user_intent = UserIntent(
            intent_type=intent_type,
            confidence=0.9 if intent_type != IntentType.UNKNOWN else 0.5,
            entities=entities,
            needs_clarification=intent_type == IntentType.UNKNOWN,
            original_message=query,
        )
        
        # Update state
        state.intent = user_intent
        
        logger.info(
            f"Intent detected: {intent_type.value}, "
            f"entities: event_ids={entities.event_ids}, "
            f"follow_up: {is_follow_up}"
        )
        
        return state


def create_intent_detector() -> IntentDetectorAgent:
    """Create an IntentDetectorAgent instance."""
    return IntentDetectorAgent()
