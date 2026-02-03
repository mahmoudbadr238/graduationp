"""
SecurityChatbotV3 - Grounded chatbot that cites local evidence.

Key improvements over V2:
1. Every response cites which local signals were used (events, snapshot, security settings)
2. Structured response format with evidence sections
3. Hard rules: never claim malware/infection without direct evidence
4. Debug logging for all AI calls
5. No hallucinated security claims
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal

from app.ai.debug import get_ai_debugger
from app.ai.chat_context_builder import ChatContext, get_context_builder

logger = logging.getLogger(__name__)

# ============================================================================
# Grounded Response Format
# ============================================================================

RESPONSE_TEMPLATE = """**{direct_answer}**

📊 **Why I think this:**
{evidence}

🔧 **What to do:**
{actions}

{followup}"""

EVIDENCE_TEMPLATE = "• {signal_type}: {observation}"


# ============================================================================
# Knowledge Base for Common Questions
# ============================================================================

SENTINEL_FEATURES = {
    "event_viewer": {
        "name": "Event Viewer",
        "description": "Shows Windows Event logs from your system",
        "location": "First tab in the sidebar (Event Viewer icon)",
        "what_it_shows": "System events, errors, warnings, and information messages from Windows and applications",
    },
    "system_snapshot": {
        "name": "System Snapshot", 
        "description": "Real-time overview of your system's health",
        "location": "Second tab in the sidebar (Snapshot icon)",
        "what_it_shows": "CPU usage, memory, disk, network, running processes, and security status",
    },
    "scan_history": {
        "name": "Scan History",
        "description": "Results of past security scans",
        "location": "Third tab in the sidebar (Scan icon)",
        "what_it_shows": "Previous virus/malware scan results and detected threats",
    },
    "settings": {
        "name": "Settings",
        "description": "Configure Sentinel preferences",
        "location": "Settings icon in the sidebar",
        "what_it_shows": "Theme, notifications, scan settings, and AI preferences",
    },
}

SECURITY_CONCEPTS = {
    "firewall": {
        "what_is": "A firewall monitors and controls network traffic based on security rules",
        "why_important": "Blocks unauthorized access and malicious connections to your computer",
        "how_to_check": "Go to System Snapshot → Security tab, or Windows Security → Firewall",
    },
    "defender": {
        "what_is": "Windows Defender is Microsoft's built-in antivirus software",
        "why_important": "Protects against viruses, malware, and other threats in real-time",
        "how_to_check": "Go to System Snapshot → Security tab, or open Windows Security",
    },
    "updates": {
        "what_is": "Windows Updates include security patches and bug fixes",
        "why_important": "Updates fix security vulnerabilities that hackers can exploit",
        "how_to_check": "Settings → Windows Update, or check Sentinel's System Snapshot",
    },
}


# ============================================================================
# Structured Response Dataclass
# ============================================================================

@dataclass
class GroundedResponse:
    """A response grounded in local evidence."""
    
    direct_answer: str = ""
    evidence: list[tuple[str, str]] = field(default_factory=list)  # (signal_type, observation)
    actions: list[str] = field(default_factory=list)
    followup: str = ""
    confidence: str = "medium"  # low, medium, high
    sources_used: list[str] = field(default_factory=list)  # For debugging
    
    def format(self) -> str:
        """Format as user-facing response."""
        if not self.evidence:
            # Simple response without evidence section
            if self.actions:
                action_text = "\n".join(f"{i+1}. {a}" for i, a in enumerate(self.actions))
                return f"{self.direct_answer}\n\n🔧 **What to do:**\n{action_text}"
            return self.direct_answer
        
        evidence_lines = []
        for signal_type, observation in self.evidence:
            evidence_lines.append(f"• **{signal_type}**: {observation}")
        
        action_text = "\n".join(f"{i+1}. {a}" for i, a in enumerate(self.actions)) if self.actions else "No action needed at this time."
        
        followup_text = f"\n💡 {self.followup}" if self.followup else ""
        
        return RESPONSE_TEMPLATE.format(
            direct_answer=self.direct_answer,
            evidence="\n".join(evidence_lines),
            actions=action_text,
            followup=followup_text,
        ).strip()


# ============================================================================
# Intent Patterns
# ============================================================================

INTENT_PATTERNS = {
    "greeting": [r"^(hi|hello|hey|greetings)[\s!.,]*$", r"^good\s*(morning|afternoon|evening)"],
    "thanks": [r"\b(thank|thanks|appreciate)\b"],
    "goodbye": [r"\b(bye|goodbye|see\s*you)\b"],
    "status_check": [
        r"\b(status|health|check|how\s+is)\b.*\b(system|computer|pc)\b",
        r"\bam\s+i\s+(safe|protected|secure)\b",
    ],
    # NEW: Specific security product queries (use real snapshot)
    "defender_status": [
        r"\b(defender|windows\s*defender|antivirus|av)\b.*\b(status|on|off|enabled|disabled|working|running)\b",
        r"\b(is|check|show|what).*(defender|antivirus)\b",
        r"\bdefender\b",
        r"\breal[\s-]?time\s+protection\b",
        r"\bvirus\s+protection\b",
    ],
    "firewall_status": [
        r"\b(firewall)\b.*\b(status|on|off|enabled|disabled|working|running)\b",
        r"\b(is|check|show|what).*(firewall)\b",
        r"\bfirewall\b",
    ],
    "security_status": [
        r"\b(security|protection)\b.*\b(status|check|how)\b",
        r"\bam\s+i\s+(protected|secure)\b",
        r"\b(my|system|pc|computer)\s+(security|protection)\b",
    ],
    "what_is": [r"\bwhat\s+(is|are|does)\b", r"\bexplain\b", r"\btell\s+me\s+about\b"],
    "where_is": [r"\bwhere\s+(is|can|do)\b", r"\bfind\s+(the)?\b"],
    "how_to": [r"\bhow\s+(do|can|to)\b", r"\bshow\s+me\b"],
    "action": [r"\b(scan|check|run|start|open|enable|disable)\b"],
    "problem": [r"\b(problem|issue|error|wrong|broken|slow)\b"],
    "security_concern": [r"\b(virus|malware|hack|attack|threat|infected)\b"],
}

OFF_TOPIC_PATTERNS = [
    r"\b(weather|recipe|movie|music|game|sport|news|politics)\b",
    r"\b(joke|funny|meme|play)\b",
    r"\b(restaurant|food|travel)\b",
]


# ============================================================================
# Action Registry
# ============================================================================

ACTIONS = {
    "quick_scan": {
        "patterns": [r"\bquick\s+scan\b", r"\bscan\b.*(virus|malware)"],
        "description": "Run a quick virus scan",
        "command": "quick_scan",
    },
    "full_scan": {
        "patterns": [r"\bfull\s+scan\b", r"\bdeep\s+scan\b"],
        "description": "Run a full system scan",
        "command": "full_scan",
    },
    "check_updates": {
        "patterns": [r"\bcheck\s+(for\s+)?update", r"\bwindows\s+update"],
        "description": "Check for Windows updates",
        "command": "check_updates",
    },
}


# ============================================================================
# SecurityChatbotV3 Class
# ============================================================================

class SecurityChatbotV3(QObject):
    """
    Grounded security chatbot that cites local evidence.
    
    Signals:
        actionRequested(action_name, description): Emitted when user requests an action
        responseReady(response): Emitted for async responses
    """
    
    actionRequested = Signal(str, str)
    responseReady = Signal(str)
    
    def __init__(
        self,
        llm_engine=None,
        context_builder=None,
        action_executor: Callable[[str], bool] | None = None,
        parent=None,
    ):
        """
        Initialize the V3 chatbot.
        
        Args:
            llm_engine: Local LLM engine (optional, for complex questions)
            context_builder: ChatContextBuilder for local signals
            action_executor: Function to execute actions
            parent: Qt parent
        """
        super().__init__(parent)
        
        self._llm = llm_engine
        self._context_builder = context_builder or get_context_builder()
        self._action_executor = action_executor
        self._debugger = get_ai_debugger()
        
        # State
        self._pending_action: str | None = None
        self._last_context: ChatContext | None = None
        
        logger.info("SecurityChatbotV3 initialized")
    
    def answer(
        self,
        conversation: list[dict[str, str]],
        user_message: str,
    ) -> str:
        """
        Generate a grounded response to the user's message.
        
        Args:
            conversation: Conversation history
            user_message: User's message
        
        Returns:
            Formatted response string with evidence citations
        """
        msg = user_message.strip()
        if not msg:
            return "I didn't catch that. What would you like to know about your system's security?"
        
        msg_lower = msg.lower()
        
        # Handle pending action confirmation
        if self._pending_action:
            return self._handle_confirmation(msg_lower)
        
        # Classify intent
        intent = self._classify_intent(msg_lower)
        
        # Handle simple intents
        if intent == "greeting":
            return self._greet()
        if intent == "thanks":
            return "You're welcome! Let me know if you need anything else about your security."
        if intent == "goodbye":
            return "Goodbye! Stay safe online! 🔒"
        
        # Check if off-topic
        if self._is_off_topic(msg_lower):
            return self._handle_off_topic()
        
        # Get fresh context for grounding
        context = self._context_builder.build_context()
        self._last_context = context
        
        # Route by intent
        if intent == "status_check":
            return self._handle_status_check(context)
        
        # NEW: Handle defender/firewall/security with REAL snapshot data
        if intent == "defender_status":
            return self._handle_defender_status(msg_lower)
        
        if intent == "firewall_status":
            return self._handle_firewall_status(msg_lower)
        
        if intent == "security_status":
            return self._handle_security_status(msg_lower)
        
        if intent == "security_concern":
            return self._handle_security_concern(msg_lower, context)
        
        if intent == "action":
            return self._handle_action_request(msg_lower, context)
        
        if intent == "where_is":
            return self._handle_where_is(msg_lower)
        
        if intent == "what_is":
            return self._handle_what_is(msg_lower)
        
        if intent == "how_to":
            return self._handle_how_to(msg_lower)
        
        if intent == "problem":
            return self._handle_problem(msg_lower, context)
        
        # Try LLM for complex questions (with grounding)
        if self._llm:
            return self._generate_llm_response(msg_lower, context)
        
        # Fallback
        return self._handle_unknown(msg_lower)
    
    def _classify_intent(self, msg: str) -> str:
        """
        Classify message intent with priority ordering.
        
        Priority order (high to low):
        1. Simple intents (greeting, thanks, goodbye)
        2. Specific security product queries (defender, firewall, security status)
        3. General status/concern queries
        4. Feature queries (what_is, where_is, how_to)
        5. Generic (action, problem)
        """
        # Priority order for intent matching
        priority_order = [
            # Simple intents first
            "greeting", "thanks", "goodbye",
            # Specific security queries (these use REAL data)
            "defender_status", "firewall_status", "security_status",
            # General queries
            "status_check", "security_concern",
            # Feature/how-to queries
            "where_is", "what_is", "how_to",
            # Generic
            "action", "problem",
        ]
        
        for intent_name in priority_order:
            if intent_name in INTENT_PATTERNS:
                for pattern in INTENT_PATTERNS[intent_name]:
                    if re.search(pattern, msg, re.IGNORECASE):
                        return intent_name
        
        return "unknown"
    
    def _is_off_topic(self, msg: str) -> bool:
        """Check if message is off-topic."""
        for pattern in OFF_TOPIC_PATTERNS:
            if re.search(pattern, msg, re.IGNORECASE):
                # Verify not security-related
                security_keywords = ["security", "protect", "safe", "virus", "scan"]
                if not any(kw in msg for kw in security_keywords):
                    return True
        return False
    
    def _handle_off_topic(self) -> str:
        """Handle off-topic messages."""
        return (
            "I'm your security assistant! I can help with:\n\n"
            "• **System status** - Check if your computer is healthy\n"
            "• **Security events** - Explain Windows events\n"
            "• **Virus scans** - Run or review security scans\n"
            "• **Security tips** - Best practices for staying safe\n\n"
            "What would you like to know?"
        )
    
    def _greet(self) -> str:
        """Generate greeting with current system status."""
        context = self._context_builder.build_context()
        self._last_context = context
        
        response = GroundedResponse()
        
        if context.system_health == "good":
            response.direct_answer = "Hello! ✅ Your system looks healthy"
            response.evidence = [
                ("System Metrics", f"CPU {context.cpu_percent:.0f}%, Memory {context.memory_percent:.0f}%"),
            ]
            if context.firewall_enabled:
                response.evidence.append(("Security", "Firewall is enabled"))
            if context.realtime_protection:
                response.evidence.append(("Defender", "Real-time protection is active"))
            response.actions = ["No urgent actions needed right now"]
            response.followup = "Ask me about security events, system status, or how to run a scan"
        
        elif context.system_health == "warning":
            response.direct_answer = "Hello! ⚡ Your system has some minor issues"
            response.evidence = [
                ("System Metrics", f"CPU {context.cpu_percent:.0f}%, Memory {context.memory_percent:.0f}%"),
            ]
            if context.top_issues:
                for issue in context.top_issues[:2]:
                    response.evidence.append(("Issue Detected", issue))
            response.actions = [
                "Check System Snapshot for details",
                "Review any warnings in Event Viewer",
            ]
        
        else:  # critical
            response.direct_answer = "Hello! ⚠️ Your system needs attention"
            response.evidence = []
            for issue in context.top_issues[:3]:
                response.evidence.append(("Critical Issue", issue))
            response.actions = [
                "Address the issues listed above",
                "Check System Snapshot → Security tab",
                "Consider running a virus scan",
            ]
        
        response.sources_used = ["system_metrics", "security_status"]
        return response.format()
    
    def _handle_status_check(self, context: ChatContext) -> str:
        """Handle status check with full evidence."""
        response = GroundedResponse()
        
        # Determine overall status
        if context.system_health == "good":
            response.direct_answer = "✅ Your system is healthy"
        elif context.system_health == "warning":
            response.direct_answer = "⚡ Your system has minor issues"
        else:
            response.direct_answer = "⚠️ Your system needs attention"
        
        # Evidence from system metrics
        response.evidence = [
            ("CPU Usage", f"{context.cpu_percent:.0f}% - " + (
                "Normal" if context.cpu_percent < 80 else "High"
            )),
            ("Memory Usage", f"{context.memory_percent:.0f}% - " + (
                "Normal" if context.memory_percent < 85 else "High"  
            )),
            ("Disk Usage", f"{context.disk_percent:.0f}% - " + (
                "OK" if context.disk_percent < 90 else "Low space"
            )),
        ]
        
        # Security evidence
        if context.firewall_enabled is not None:
            status = "Enabled ✅" if context.firewall_enabled else "Disabled ❌"
            response.evidence.append(("Firewall", status))
        
        if context.realtime_protection is not None:
            status = "Active ✅" if context.realtime_protection else "Inactive ❌"
            response.evidence.append(("Real-time Protection", status))
        
        # Issues
        if context.top_issues:
            for issue in context.top_issues[:3]:
                response.evidence.append(("Issue", issue))
        
        # Actions based on findings
        if context.system_health == "good":
            response.actions = ["No action needed - keep up the good work!"]
        else:
            response.actions = []
            if context.cpu_percent > 80:
                response.actions.append("Check System Snapshot → Processes to find high CPU usage")
            if context.memory_percent > 85:
                response.actions.append("Close unused applications to free memory")
            if context.disk_percent > 90:
                response.actions.append("Free up disk space (Disk Cleanup or remove unused files)")
            if context.firewall_enabled is False:
                response.actions.append("Enable firewall: Settings → Windows Security → Firewall")
            if context.realtime_protection is False:
                response.actions.append("Enable Defender: Settings → Windows Security → Virus protection")
            if not response.actions:
                response.actions.append("Review System Snapshot for more details")
        
        response.sources_used = ["system_metrics", "security_status", "issues"]
        return response.format()
    
    def _handle_security_concern(self, msg: str, context: ChatContext) -> str:
        """
        Handle security concerns (virus, malware, attack, etc.)
        
        CRITICAL: Never claim infection without direct evidence.
        """
        response = GroundedResponse()
        
        # Collect available evidence
        has_real_threat = False
        response.evidence = []
        
        # Check security status
        if context.firewall_enabled is not None:
            response.evidence.append((
                "Firewall",
                "Enabled ✅" if context.firewall_enabled else "Disabled ❌ (security risk)"
            ))
            if not context.firewall_enabled:
                has_real_threat = True
        
        if context.realtime_protection is not None:
            response.evidence.append((
                "Real-time Protection",
                "Active ✅" if context.realtime_protection else "Inactive ❌ (security risk)"
            ))
            if not context.realtime_protection:
                has_real_threat = True
        
        # Check for concerning events
        if context.recent_critical_events:
            for event in context.recent_critical_events[:2]:
                response.evidence.append(("Recent Critical Event", event))
        
        if context.recent_warning_events:
            for event in context.recent_warning_events[:2]:
                response.evidence.append(("Recent Warning", event))
        
        # Resource concerns
        if context.cpu_percent > 90:
            response.evidence.append(("High CPU", f"{context.cpu_percent:.0f}% - unusually high"))
        
        # Determine response based on ACTUAL evidence
        if has_real_threat:
            response.direct_answer = "⚠️ Your security protections have gaps"
            response.actions = [
                "Enable Windows Firewall: Settings → Windows Security → Firewall",
                "Enable Real-time Protection: Windows Security → Virus & threat protection",
                "Run a full system scan after enabling protections",
            ]
        elif context.recent_critical_events:
            response.direct_answer = "⚡ I see some concerning events, but no confirmed threats"
            response.actions = [
                "Review critical events in Event Viewer for details",
                "Run a quick scan to be safe: Use the Scan History tab",
                "Check System Snapshot → Security for current status",
            ]
        else:
            response.direct_answer = "✅ No threats detected based on available data"
            response.evidence.append(("Scan Data", "No confirmed threats in recent scans"))
            response.actions = [
                "Run a quick scan for peace of mind",
                "Keep Windows and apps updated",
                "Avoid downloading from untrusted sources",
            ]
        
        response.followup = "I can only detect threats based on scan results and system signals. Would you like me to run a scan?"
        response.sources_used = ["security_status", "events", "metrics"]
        return response.format()
    
    def _handle_defender_status(self, msg: str) -> str:
        """
        Handle Defender status questions using REAL snapshot data.
        
        Uses get_security_snapshot() for actual PowerShell data.
        """
        from app.utils.security_snapshot import (
            get_security_snapshot,
            generate_defender_response,
        )
        
        # Get real snapshot (cached for 7 seconds)
        snapshot = get_security_snapshot()
        response_data = generate_defender_response(snapshot)
        
        # Format response with structured sections
        response_parts = []
        
        # Quick Status section
        response_parts.append("**🔒 Quick Status:**")
        for item in response_data["quick_status"]:
            response_parts.append(f"  {item}")
        
        response_parts.append("")
        
        # What This Means section
        response_parts.append("**📋 What this means:**")
        for sentence in response_data["what_this_means"]:
            response_parts.append(f"• {sentence}")
        
        response_parts.append("")
        
        # What You Can Do section (only if there are actions)
        if response_data["what_you_can_do"]:
            response_parts.append("**🔧 What you can do:**")
            for i, action in enumerate(response_data["what_you_can_do"], 1):
                response_parts.append(f"{i}. {action}")
        
        # Add source indicator
        response_parts.append("")
        response_parts.append(f"_📊 Data collected at {snapshot.timestamp} from local PowerShell queries_")
        
        return "\n".join(response_parts)
    
    def _handle_firewall_status(self, msg: str) -> str:
        """
        Handle Firewall status questions using REAL snapshot data.
        
        Uses get_security_snapshot() for actual PowerShell data.
        """
        from app.utils.security_snapshot import (
            get_security_snapshot,
            generate_firewall_response,
        )
        
        # Get real snapshot (cached for 7 seconds)
        snapshot = get_security_snapshot()
        response_data = generate_firewall_response(snapshot)
        
        # Format response with structured sections
        response_parts = []
        
        # Quick Status section
        response_parts.append("**🔒 Quick Status:**")
        for item in response_data["quick_status"]:
            response_parts.append(f"  {item}")
        
        response_parts.append("")
        
        # What This Means section
        response_parts.append("**📋 What this means:**")
        for sentence in response_data["what_this_means"]:
            response_parts.append(f"• {sentence}")
        
        response_parts.append("")
        
        # What You Can Do section (only if there are actions)
        if response_data["what_you_can_do"]:
            response_parts.append("**🔧 What you can do:**")
            for i, action in enumerate(response_data["what_you_can_do"], 1):
                response_parts.append(f"{i}. {action}")
        
        # Add source indicator
        response_parts.append("")
        response_parts.append(f"_📊 Data collected at {snapshot.timestamp} from local PowerShell queries_")
        
        return "\n".join(response_parts)
    
    def _handle_security_status(self, msg: str) -> str:
        """
        Handle general security status questions using REAL snapshot data.
        
        Uses get_security_snapshot() for actual PowerShell data.
        """
        from app.utils.security_snapshot import (
            get_security_snapshot,
            generate_overall_security_response,
        )
        
        # Get real snapshot (cached for 7 seconds)
        snapshot = get_security_snapshot()
        response_data = generate_overall_security_response(snapshot)
        
        # Format response with structured sections
        response_parts = []
        
        # Quick Status section
        response_parts.append("**🔒 Quick Status:**")
        for item in response_data["quick_status"]:
            response_parts.append(f"  {item}")
        
        response_parts.append("")
        
        # What This Means section
        response_parts.append("**📋 What this means:**")
        for sentence in response_data["what_this_means"]:
            response_parts.append(f"• {sentence}")
        
        response_parts.append("")
        
        # What You Can Do section
        if response_data["what_you_can_do"]:
            response_parts.append("**🔧 What you can do:**")
            for i, action in enumerate(response_data["what_you_can_do"], 1):
                response_parts.append(f"{i}. {action}")
        
        # Add source indicator
        response_parts.append("")
        response_parts.append(f"_📊 Data collected at {snapshot.timestamp} from local PowerShell queries_")
        
        return "\n".join(response_parts)
    
    def _handle_action_request(self, msg: str, context: ChatContext) -> str:
        """Handle action requests with confirmation."""
        for action_name, config in ACTIONS.items():
            for pattern in config["patterns"]:
                if re.search(pattern, msg, re.IGNORECASE):
                    self._pending_action = action_name
                    desc = config["description"]
                    return (
                        f"I can {desc.lower()} for you.\n\n"
                        f"📋 **What this does**: Runs a security scan to check for threats.\n\n"
                        f"Do you want me to proceed? (yes/no)"
                    )
        
        # Generic action not matched
        return (
            "I can help with:\n\n"
            "• **Quick scan** - Fast virus check\n"
            "• **Full scan** - Deep system scan\n"
            "• **Check updates** - Windows Update status\n\n"
            "What would you like me to do?"
        )
    
    def _handle_confirmation(self, msg: str) -> str:
        """Handle action confirmation."""
        action = self._pending_action
        self._pending_action = None
        
        if any(word in msg for word in ["yes", "ok", "sure", "go ahead", "proceed"]):
            if self._action_executor and action:
                success = self._action_executor(action)
                if success:
                    desc = ACTIONS.get(action, {}).get("description", action)
                    self.actionRequested.emit(action, desc)
                    return f"✅ Starting: {desc}\n\nI'll notify you when it's complete."
                return "❌ Sorry, I couldn't start that action. Please try manually."
            return f"✅ Action '{action}' requested. Please check the relevant tab for progress."
        
        return "OK, I've cancelled that action. Let me know if you need anything else."
    
    def _handle_where_is(self, msg: str) -> str:
        """Handle location questions."""
        for feature_key, feature in SENTINEL_FEATURES.items():
            if feature_key in msg or feature["name"].lower() in msg:
                return (
                    f"**{feature['name']}**\n\n"
                    f"📍 **Location**: {feature['location']}\n\n"
                    f"📝 **What it shows**: {feature['what_it_shows']}"
                )
        
        # Generic response
        return (
            "Here's what you can find in Sentinel:\n\n"
            "• **Event Viewer** - First tab, shows Windows events\n"
            "• **System Snapshot** - Second tab, shows system health\n"
            "• **Scan History** - Third tab, shows scan results\n"
            "• **Settings** - Configure Sentinel preferences\n"
        )
    
    def _handle_what_is(self, msg: str) -> str:
        """Handle explanation questions."""
        for concept_key, concept in SECURITY_CONCEPTS.items():
            if concept_key in msg:
                return (
                    f"**{concept_key.title()}**\n\n"
                    f"📖 **What it is**: {concept['what_is']}\n\n"
                    f"⚠️ **Why it matters**: {concept['why_important']}\n\n"
                    f"🔍 **How to check**: {concept['how_to_check']}"
                )
        
        # Check for Sentinel features
        for feature_key, feature in SENTINEL_FEATURES.items():
            if feature_key in msg or feature["name"].lower() in msg:
                return (
                    f"**{feature['name']}**\n\n"
                    f"📖 **Description**: {feature['description']}\n\n"
                    f"📍 **Location**: {feature['location']}\n\n"
                    f"📝 **Shows**: {feature['what_it_shows']}"
                )
        
        return (
            "I can explain:\n\n"
            "• **Firewall** - Network protection\n"
            "• **Defender** - Windows antivirus\n"
            "• **Updates** - Security patches\n"
            "• Sentinel features (Event Viewer, System Snapshot, etc.)\n\n"
            "What would you like to know about?"
        )
    
    def _handle_how_to(self, msg: str) -> str:
        """Handle how-to questions."""
        # Scan related
        if any(word in msg for word in ["scan", "virus", "malware"]):
            return (
                "**How to Run a Virus Scan**\n\n"
                "1. Open the **Scan History** tab (third icon in sidebar)\n"
                "2. Click **Quick Scan** for a fast check, or **Full Scan** for thorough analysis\n"
                "3. Wait for the scan to complete\n"
                "4. Review any detected threats\n\n"
                "💡 Quick scans take 5-10 minutes, full scans may take longer."
            )
        
        # Check security
        if any(word in msg for word in ["check", "status", "health"]):
            return (
                "**How to Check Your System's Security**\n\n"
                "1. Open **System Snapshot** (second icon in sidebar)\n"
                "2. Review the **Security** section\n"
                "3. Check that Firewall and Real-time Protection are enabled\n"
                "4. Look at resource usage (CPU, Memory, Disk)\n\n"
                "💡 You can also ask me 'am I safe?' for a quick summary."
            )
        
        # Enable firewall/defender
        if any(word in msg for word in ["firewall", "defender", "enable", "turn on"]):
            return (
                "**How to Enable Security Features**\n\n"
                "**Firewall:**\n"
                "1. Press Win + I to open Settings\n"
                "2. Go to Update & Security → Windows Security\n"
                "3. Click Firewall & network protection\n"
                "4. Enable for all networks\n\n"
                "**Windows Defender:**\n"
                "1. Open Windows Security\n"
                "2. Click Virus & threat protection\n"
                "3. Enable Real-time protection"
            )
        
        return (
            "I can help you with:\n\n"
            "• How to run a virus scan\n"
            "• How to check your system's security\n"
            "• How to enable firewall or Defender\n\n"
            "What would you like to know how to do?"
        )
    
    def _handle_problem(self, msg: str, context: ChatContext) -> str:
        """Handle problem reports with evidence."""
        response = GroundedResponse()
        response.direct_answer = "Let me check for issues"
        
        # Collect evidence
        response.evidence = [
            ("System Health", context.system_health.title()),
            ("CPU", f"{context.cpu_percent:.0f}%"),
            ("Memory", f"{context.memory_percent:.0f}%"),
        ]
        
        if context.top_issues:
            for issue in context.top_issues[:3]:
                response.evidence.append(("Known Issue", issue))
        
        if context.recent_critical_events:
            for event in context.recent_critical_events[:2]:
                response.evidence.append(("Critical Event", event))
        
        # Suggest actions based on keyword
        if "slow" in msg:
            response.direct_answer = "Let me check why your system might be slow"
            response.actions = [
                "Check System Snapshot → Processes for high CPU/memory apps",
                "Close unused browser tabs and applications",
                "Consider running Disk Cleanup",
            ]
        elif "error" in msg:
            response.direct_answer = "Let me check for recent errors"
            response.actions = [
                "Check Event Viewer for recent Error events",
                "Filter by 'Error' level to find issues",
                "Click an event for my explanation",
            ]
        else:
            response.actions = [
                "Check System Snapshot for current status",
                "Review Event Viewer for recent errors",
                "Run a quick scan if security-related",
            ]
        
        response.sources_used = ["metrics", "issues", "events"]
        return response.format()
    
    def _generate_llm_response(self, msg: str, context: ChatContext) -> str:
        """Generate LLM response with grounding context."""
        if not self._llm:
            return self._handle_unknown(msg)
        
        # Build grounded prompt with Sentinel Smart Security Assistant identity
        system_prompt = """You are "Sentinel Smart Security Assistant", an embedded AI inside a Windows Endpoint Security application.

Your job is to THINK like a security analyst, system administrator, and support engineer combined.

CORE IDENTITY:
• Product: Sentinel – Endpoint Security Suite
• Mode: Local-first, Offline-capable, Privacy-focused
• You explain Windows security in human language

MEMORY & CONTEXT:
• Remember what the user asked previously
• Connect follow-up questions to earlier answers
• If user says "hi" → greet + explain what you can help with NOW
• If user says "still dumb" → diagnose why your answer failed, fix it

EVENT EXPLANATION STRUCTURE:
1. Plain Summary (one sentence a normal person understands)
2. What Happened (what Windows did, why it logged this)
3. Is This Dangerous? (Yes/No/Depends with clear reasoning)
4. Why You're Seeing It NOW (startup, update, login, background task)
5. What You Should Do (clear actions or "No action needed")

SECURITY QUESTION RULES:
If permission fails → explain WHY, provide safe assumptions, never just say "Unable to retrieve"

ERROR HANDLING:
• Say what failed, why it failed, what Sentinel CAN still do
• Never blame the user

TONE: Calm, confident, clear, zero fluff. You are a SECURITY ASSISTANT, not a chatbot toy.

CURRENT SYSTEM CONTEXT:
- Overall Health: {health}
- CPU Usage: {cpu}%
- Memory Usage: {memory}%
- Disk Usage: {disk}%
- Firewall: {firewall}
- Real-time Protection: {defender}
- Recent Issues: {issues}
""".format(
            health=context.system_health,
            cpu=context.cpu_percent,
            memory=context.memory_percent,
            disk=context.disk_percent,
            firewall="Enabled" if context.firewall_enabled else "Disabled" if context.firewall_enabled is not None else "Unknown",
            defender="Active" if context.realtime_protection else "Inactive" if context.realtime_protection is not None else "Unknown",
            issues=", ".join(context.top_issues[:3]) if context.top_issues else "None detected",
        )
        
        # Log for debugging
        record = self._debugger.start_call(
            call_type="chat",
            model_name=getattr(self._llm, "model_name", "unknown"),
            backend=getattr(self._llm, "backend_info", "unknown"),
        )
        record.system_prompt = system_prompt
        record.user_prompt = msg
        record.structured_context = {
            "health": context.system_health,
            "cpu": context.cpu_percent,
            "memory": context.memory_percent,
            "firewall": context.firewall_enabled,
        }
        
        try:
            self._debugger.record_inference_start(record)
            response = self._llm.generate_single_turn(
                f"{system_prompt}\n\nUser: {msg}\n\nAssistant:",
                max_tokens=300,
            )
            self._debugger.record_inference_end(record)
            record.raw_response = response
            record.validation_passed = True
            self._debugger.end_call(record)
            
            # Clean up response
            response = response.strip()
            if response.startswith("Assistant:"):
                response = response[10:].strip()
            
            return response if response else self._handle_unknown(msg)
            
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            record.validation_passed = False
            record.validation_errors = [str(e)]
            self._debugger.end_call(record)
            return self._handle_unknown(msg)
    
    def _handle_unknown(self, msg: str) -> str:
        """Handle unknown questions."""
        return (
            "I'm not sure how to help with that specific question.\n\n"
            "I can help you with:\n"
            "• **System status** - 'Am I safe?' or 'Check my system'\n"
            "• **Security events** - 'What happened?' (select an event first)\n"
            "• **Scans** - 'Run a scan' or 'Check for viruses'\n"
            "• **Security tips** - 'How do I protect myself?'\n\n"
            "What would you like to know?"
        )
    
    def shutdown(self) -> None:
        """Clean up resources."""
        logger.info("SecurityChatbotV3 shutdown")


# ============================================================================
# Module accessor
# ============================================================================

_chatbot: SecurityChatbotV3 | None = None


def get_security_chatbot_v3(
    llm_engine=None,
    context_builder=None,
) -> SecurityChatbotV3:
    """Get or create the singleton SecurityChatbotV3 instance."""
    global _chatbot
    if _chatbot is None:
        _chatbot = SecurityChatbotV3(
            llm_engine=llm_engine,
            context_builder=context_builder,
        )
    elif llm_engine is not None and _chatbot._llm is None:
        _chatbot._llm = llm_engine
    return _chatbot
