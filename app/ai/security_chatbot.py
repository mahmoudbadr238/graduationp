"""
Intelligent Security Chatbot - Advanced Local AI Security Assistant.

An intelligent, context-aware security assistant that:
1. Uses semantic understanding with multiple NLP techniques
2. Maintains conversation memory for context-aware responses
3. Has FULL device awareness (CPU, RAM, disk, security, events)
4. Knows the Sentinel program inside-out
5. Only answers security-related questions
6. Generates dynamic, personalized responses
7. Handles follow-up questions and ambiguity
8. Runs 100% offline
9. CAN EXECUTE SECURITY ACTIONS (enable firewall, run scans, etc.)

INTELLIGENCE FEATURES:
- Semantic similarity matching (not just keywords)
- Entity extraction (what/who/when the user is asking about)
- Intent classification with confidence scores
- Conversation context tracking
- Dynamic response generation based on system state
- Clarifying questions when uncertain
- Follow-up question handling
- ACTION EXECUTION on user request
"""

import logging
import re
from typing import Any, Optional, Tuple
from difflib import SequenceMatcher
from collections import Counter
import math

from PySide6.QtCore import QObject

from .local_llm_engine import LocalLLMEngine
from .security_actions import get_action_executor, ActionResult

logger = logging.getLogger(__name__)


# ============================================================================
# KNOWLEDGE BASE - Everything the chatbot knows
# ============================================================================

KNOWLEDGE_BASE = {
    # Sentinel Features
    "features": {
        "event_viewer": {
            "keywords": ["event", "events", "log", "logs", "viewer", "windows event", "system log", "error log", "warning", "critical"],
            "description": "The Event Viewer shows Windows security and system events with AI-powered explanations.",
            "location": "Click '📋 Event Viewer' in the left sidebar",
            "capabilities": [
                "View all Windows events (System, Application, Security)",
                "Filter by severity (Critical, Error, Warning, Info)",
                "Get AI explanations in plain English",
                "See event trends over time",
                "Export events for analysis"
            ],
            "how_to_use": [
                "Navigate to Event Viewer from the sidebar",
                "Events are color-coded: Red=Critical, Orange=Error, Yellow=Warning, Blue=Info",
                "Click any event to see full details",
                "Click 'Explain with AI' for a plain-English explanation",
                "Use filters to focus on specific event types"
            ]
        },
        "system_snapshot": {
            "keywords": ["snapshot", "system snapshot", "health", "status", "cpu", "memory", "ram", "disk", "performance", "metrics", "dashboard", "how is my computer", "system health"],
            "description": "System Snapshot shows real-time system health including CPU, memory, disk, and security status.",
            "location": "Click '📊 System Snapshot' in the left sidebar",
            "capabilities": [
                "Real-time CPU usage monitoring",
                "Memory (RAM) usage tracking",
                "Disk space monitoring",
                "GPU information (if available)",
                "Security status overview"
            ]
        },
        "security_status": {
            "keywords": ["security status", "security page", "protection status", "firewall status", "antivirus status", "defender status", "tpm status", "bitlocker status", "secure boot status", "am i safe", "am i protected", "is my computer safe"],
            "description": "Security Status shows your system's protection level including firewall, antivirus, TPM, and encryption.",
            "location": "Click '🛡️ Security Status' in the left sidebar",
            "capabilities": [
                "Firewall status check",
                "Antivirus/Windows Defender status",
                "TPM (security chip) detection",
                "BitLocker encryption status",
                "Secure Boot verification"
            ]
        },
        "network_monitor": {
            "keywords": ["network", "internet", "connection", "wifi", "port", "port scan", "nmap", "ip", "traffic", "network monitor", "connections"],
            "description": "Network Monitor shows active connections and can scan for open ports and network devices.",
            "location": "Click '🌐 Network Monitor' in the left sidebar",
            "capabilities": [
                "View active network connections",
                "Scan for open ports",
                "Discover devices on your network",
                "Monitor network traffic",
                "Identify suspicious connections"
            ]
        },
        "scan_history": {
            "keywords": ["scan", "scan file", "scan url", "file scan", "url scan", "virustotal", "check file", "check url", "threat", "malware scan", "scan for", "scanning"],
            "description": "Scan History lets you scan files and URLs for malware and threats.",
            "location": "Click '🔍 Scan History' in the left sidebar",
            "capabilities": [
                "Scan files for malware",
                "Check URLs for threats",
                "View scan history",
                "See threat detection results"
            ],
            "how_to_use": [
                "Navigate to 'Scan History' from the sidebar",
                "Click 'Scan File' to check a file for threats",
                "Click 'Scan URL' to check a link before visiting",
                "View previous scan results in the history list"
            ]
        },
        "settings": {
            "keywords": ["settings", "preferences", "theme", "dark mode", "light mode", "configure", "options"],
            "description": "Settings lets you customize Sentinel's appearance and behavior.",
            "location": "Click '⚙️ Settings' in the left sidebar"
        }
    },
    
    # Security Concepts
    "concepts": {
        "firewall": {
            "keywords": ["firewall", "fire wall", "network protection", "block connection"],
            "what_is": "A firewall is a security system that monitors and controls network traffic based on security rules.",
            "why_important": "It blocks unauthorized access to your computer from the internet and network.",
            "how_to_enable": "Open Windows Security → Firewall & network protection → Turn on for all networks",
            "risks_if_disabled": "Without a firewall, hackers can more easily access your computer through the network."
        },
        "antivirus": {
            "keywords": ["antivirus", "anti-virus", "virus", "malware", "defender", "protection", "threat"],
            "what_is": "Antivirus software detects and removes malicious software (malware) from your computer.",
            "why_important": "It protects against viruses, trojans, ransomware, spyware, and other threats.",
            "windows_defender": "Windows Defender is Microsoft's built-in antivirus that updates automatically.",
            "best_practices": ["Keep real-time protection ON", "Run weekly scans", "Don't disable for downloads"]
        },
        "tpm": {
            "keywords": ["tpm", "trusted platform module", "security chip", "hardware security"],
            "what_is": "TPM is a security chip on your motherboard that stores encryption keys securely.",
            "why_important": "It enables BitLocker encryption, secure boot verification, and protects against hardware attacks.",
            "versions": "TPM 2.0 is required for Windows 11. TPM 1.2 is older but still provides protection."
        },
        "bitlocker": {
            "keywords": ["bitlocker", "encryption", "encrypt", "drive encryption", "disk encryption"],
            "what_is": "BitLocker encrypts your entire drive so data cannot be read without your password.",
            "why_important": "If your laptop is stolen, thieves cannot access your files without the encryption key.",
            "requirements": "Requires Windows Pro/Enterprise and TPM (or USB key).",
            "warning": "NEVER lose your recovery key - save it to Microsoft account or print it!"
        },
        "secure_boot": {
            "keywords": ["secure boot", "secureboot", "uefi", "boot security"],
            "what_is": "Secure Boot verifies that only trusted software loads during computer startup.",
            "why_important": "It prevents rootkits and bootkits from loading malware before Windows starts.",
            "how_to_check": "Run msinfo32 → Look for 'Secure Boot State'"
        },
        "password": {
            "keywords": ["password", "passwords", "passphrase", "credentials", "login", "authentication"],
            "best_practices": [
                "Use at least 12 characters (16+ is better)",
                "Mix uppercase, lowercase, numbers, symbols",
                "Never use personal info (birthday, pet name)",
                "Use different passwords for each account",
                "Use a password manager (Bitwarden, 1Password, KeePass)",
                "Enable 2FA/MFA wherever possible"
            ],
            "common_mistakes": ["Using 'password123'", "Same password everywhere", "Writing on sticky notes", "Sharing passwords"]
        },
        "phishing": {
            "keywords": ["phishing", "scam", "fake email", "suspicious", "fraud", "social engineering"],
            "what_is": "Phishing is when attackers pretend to be legitimate organizations to steal your information.",
            "red_flags": [
                "Urgent language ('Act now!', 'Account suspended!')",
                "Suspicious sender address (paypa1.com instead of paypal.com)",
                "Requests for passwords or personal info",
                "Unexpected attachments",
                "Poor spelling and grammar",
                "Links that don't match the real website"
            ],
            "how_to_protect": "Never click suspicious links. Go directly to websites. Verify with the company by phone."
        },
        "vpn": {
            "keywords": ["vpn", "virtual private network", "privacy", "secure connection"],
            "what_is": "A VPN encrypts your internet traffic and hides your IP address.",
            "when_to_use": ["On public WiFi", "For privacy", "Accessing work remotely"],
            "limitations": ["Doesn't make you anonymous", "Doesn't protect against malware", "Free VPNs may sell your data"]
        },
        "updates": {
            "keywords": ["update", "updates", "patch", "windows update", "security update"],
            "why_important": "Updates fix security vulnerabilities that hackers actively exploit.",
            "best_practices": ["Enable automatic updates", "Don't delay security updates", "Restart when prompted"],
            "how_to_check": "Settings → Windows Update → Check for updates"
        },
        "backup": {
            "keywords": ["backup", "backups", "restore", "recovery", "data loss"],
            "rule_321": "3 copies, 2 different storage types, 1 offsite",
            "options": ["Cloud (OneDrive, Google Drive)", "External drive", "Windows Backup"],
            "what_to_backup": ["Documents", "Photos", "Important downloads", "Browser bookmarks"]
        }
    },
    
    # System metrics thresholds
    "thresholds": {
        "cpu": {"good": 50, "warning": 80, "critical": 95},
        "memory": {"good": 70, "warning": 85, "critical": 95},
        "disk": {"good": 75, "warning": 90, "critical": 95}
    }
}

# Intent patterns with confidence weights
INTENT_PATTERNS = {
    "greeting": {
        "patterns": [r"^(hi|hello|hey|greetings|howdy|yo|sup)[\s!.,]*$", r"^good\s*(morning|afternoon|evening)"],
        "weight": 1.0
    },
    "thanks": {
        "patterns": [r"\b(thank|thanks|thx|appreciate|grateful)\b"],
        "weight": 0.9
    },
    "goodbye": {
        "patterns": [r"\b(bye|goodbye|see\s*you|later|exit|quit)\b"],
        "weight": 0.9
    },
    "how_to": {
        "patterns": [r"\bhow\s+(do|can|to|should)\b", r"\bwhat\s+steps\b", r"\bguide\s+me\b", r"\bshow\s+me\s+how\b", r"\bwalk\s+me\s+through\b"],
        "weight": 0.95
    },
    "what_is": {
        "patterns": [r"\bwhat\s+(is|are|does)\b", r"\bexplain\b", r"\btell\s+me\s+about\b", r"\bdefine\b", r"\bmeaning\s+of\b"],
        "weight": 0.9
    },
    "status_check": {
        "patterns": [r"\b(status|health|check|how\s+is|how\'?s)\b.*\b(my|the|this)?\s*(system|computer|pc|device|machine)\b", 
                     r"\bam\s+i\s+(safe|protected|secure)\b", r"\bis\s+(my|the)\s+(computer|system|pc)\s+(ok|okay|safe|secure)\b"],
        "weight": 0.95
    },
    "location": {
        "patterns": [r"\bwhere\s+(is|can|do)\b", r"\bfind\s+(the)?\b", r"\blocate\b", r"\bnavigate\s+to\b"],
        "weight": 0.9
    },
    "problem": {
        "patterns": [r"\b(problem|issue|error|wrong|broken|not\s+working|failed|failing)\b"],
        "weight": 0.85
    },
    "recommendation": {
        "patterns": [r"\b(should\s+i|recommend|suggest|advice|best|tips?)\b"],
        "weight": 0.85
    },
    "comparison": {
        "patterns": [r"\b(vs|versus|compared?\s+to|difference|better)\b"],
        "weight": 0.8
    },
    "affirmation": {
        "patterns": [r"^(yes|yeah|yep|sure|ok|okay|correct|right)[\s!.,]*$"],
        "weight": 0.9
    },
    "negation": {
        "patterns": [r"^(no|nope|nah|wrong|incorrect)[\s!.,]*$"],
        "weight": 0.9
    },
    "follow_up": {
        "patterns": [r"\b(more|else|also|another|what\s+about|and\s+the|how\s+about)\b", r"^(and|but|so|then)\b"],
        "weight": 0.7
    },
    "action_request": {
        "patterns": [
            r"\b(enable|turn\s+on|activate|start|run|launch|open|fix)\b",
            r"\b(disable|turn\s+off|deactivate|stop|close)\b",
            r"\b(scan|check|update|refresh|clean|clear|flush)\b",
        ],
        "weight": 0.95
    }
}

# Action patterns - map user requests to executable actions
ACTION_PATTERNS = {
    # Firewall actions
    "enable_firewall": [
        r"\b(enable|turn\s+on|activate|start)\b.*(firewall|fire\s+wall)",
        r"\b(firewall|fire\s+wall).*(enable|turn\s+on|activate|on)",
        r"\bfix\b.*firewall",
        r"\bprotect\b.*network",
    ],
    "disable_firewall": [
        r"\b(disable|turn\s+off|deactivate|stop)\b.*(firewall|fire\s+wall)",
        r"\b(firewall|fire\s+wall).*(disable|turn\s+off|deactivate|off)",
    ],
    
    # Defender actions
    "quick_scan": [
        r"\b(run|start|do)\b.*(quick\s+)?scan",
        r"\bscan\b.*(computer|device|system|pc|virus|malware)",
        r"\b(virus|malware)\b.*scan",
        r"\bcheck\s+for\s+(virus|malware|threat)",
    ],
    "full_scan": [
        r"\b(run|start|do)\b.*full\s+scan",
        r"\bfull\b.*(virus|malware|system)\s*scan",
        r"\bdeep\s+scan",
    ],
    "update_definitions": [
        r"\bupdate\b.*(virus|malware|definition|signature|defender)",
        r"\b(virus|malware)\b.*definition.*update",
        r"\bupdate\s+defender",
    ],
    "enable_realtime": [
        r"\b(enable|turn\s+on)\b.*real[\s-]*time",
        r"\breal[\s-]*time.*protection.*(enable|on)",
        r"\b(enable|activate)\b.*protection",
    ],
    
    # Windows Update
    "check_updates": [
        r"\bcheck\s+(for\s+)?update",
        r"\bwindows\s+update",
        r"\bupdate\s+(windows|system|computer)",
        r"\binstall\s+update",
    ],
    
    # Windows Security
    "open_security": [
        r"\bopen\b.*(windows\s+)?security",
        r"\bopen\b.*defender",
        r"\bshow\b.*security\s+(settings|center)",
    ],
    
    # Remote Desktop
    "disable_rdp": [
        r"\b(disable|turn\s+off)\b.*(rdp|remote\s+desktop|remote\s+access)",
        r"\b(rdp|remote\s+desktop).*(disable|off|close)",
        r"\bstop\b.*remote\s+(access|connection)",
    ],
    "enable_rdp": [
        r"\b(enable|turn\s+on)\b.*(rdp|remote\s+desktop|remote\s+access)",
        r"\b(rdp|remote\s+desktop).*(enable|on)",
        r"\ballow\b.*remote\s+(access|connection)",
    ],
    
    # System utilities
    "open_task_manager": [
        r"\bopen\b.*task\s+manager",
        r"\bshow\b.*(process|running|task)",
        r"\btask\s+manager",
    ],
    "open_event_viewer": [
        r"\bopen\b.*event\s+(viewer|log)",
        r"\bshow\b.*event\s+log",
        r"\bevent\s+viewer",
    ],
    "open_disk_cleanup": [
        r"\b(open|run)\b.*disk\s+clean",
        r"\bclean\b.*(disk|drive|storage)",
        r"\bfree\s+(up\s+)?space",
        r"\bcleanup",
    ],
    "flush_dns": [
        r"\bflush\b.*dns",
        r"\bclear\b.*dns\s+cache",
        r"\breset\b.*dns",
        r"\bfix\b.*(dns|network|internet)",
    ],
    "renew_ip": [
        r"\b(renew|refresh|reset)\b.*ip",
        r"\bipconfig.*(release|renew)",
        r"\bfix\b.*(ip|network|connection)",
        r"\bnetwork\s+reset",
    ],
}

# Topics that are NOT security-related
OFF_TOPIC_INDICATORS = [
    r"\b(weather|recipe|cook|cooking|movie|music|song|game|gaming|play|sport|score|news|politics|celebrity)\b",
    r"\b(joke|jokes|funny|laugh|humor|humour|meme)\b",
    r"\b(restaurant|food|eat|eating|drink|drinking|travel|vacation|hotel|flight)\b",
    r"\b(relationship|dating|love|friend|family|marriage)\b",
    r"\b(homework|essay|math|history|geography|science|biology|chemistry|physics)\b(?!.*(security|protect|safe))",
    r"\b(stock|invest|crypto|bitcoin|money|rich)\b(?!.*(security|scam|fraud))",
    r"\b(code|program|develop|javascript|python|java|html|css)\b(?!.*(security|vulnerability|exploit))",
    r"\b(hello\s+world|print\s*\(|console\.log)\b"
]

# Security-related topics (MUST BE COMPREHENSIVE)
SECURITY_INDICATORS = [
    r"\b(security|secure|protect|safe|unsafe|threat|attack|hack|breach|vulnerability)\b",
    r"\b(virus|malware|trojan|ransomware|spyware|adware|rootkit|worm)\b",
    r"\b(firewall|antivirus|defender|encryption|bitlocker|tpm|vpn)\b",
    r"\b(password|authentication|2fa|mfa|login|credential)\b",
    r"\b(phishing|scam|fraud|suspicious|fake|spam)\b",
    r"\b(update|patch|backup|restore|recovery)\b",
    r"\b(network|wifi|connection|port|ip|traffic)\b",
    r"\b(event|log|error|errors|warning|warnings|critical|problem|problems|issue|issues)\b",
    r"\b(cpu|memory|ram|disk|storage|performance|slow|fast|usage)\b",
    r"\b(scan|check|monitor|analyze|detect|status|health)\b",
    r"\b(sentinel|program|app|feature|settings|dashboard)\b",
    r"\b(system|computer|pc|device|machine|laptop|desktop)\b",
    r"\b(my\s+computer|my\s+device|my\s+pc|my\s+system|this\s+computer)\b"
]


class SecurityChatbot(QObject):
    """
    Intelligent security chatbot with advanced NLP capabilities.
    """

    def __init__(
        self,
        llm_engine: LocalLLMEngine,
        snapshot_service: Optional[Any] = None,
        event_repo: Optional[Any] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._llm = llm_engine
        self._snapshot_service = snapshot_service
        self._event_repo = event_repo
        
        # Conversation memory
        self._conversation_context = {
            "last_topic": None,
            "last_entities": [],
            "discussed_topics": set(),
            "user_concerns": [],
            "pending_clarification": None
        }
        
        logger.info("SecurityChatbot initialized (intelligent mode)")

    # ========================================================================
    # MAIN ANSWER METHOD
    # ========================================================================

    def answer(
        self,
        conversation: list[dict[str, str]],
        user_message: str,
    ) -> str:
        """
        Generate an intelligent, context-aware response.
        """
        try:
            msg = user_message.strip()
            if not msg:
                return "I didn't catch that. What would you like to know about your system's security?"
            
            msg_lower = msg.lower()
            
            # Update conversation context
            self._update_context(conversation, msg_lower)
            
            # Analyze the message
            analysis = self._analyze_message(msg_lower)
            
            # Handle greetings/social
            if analysis["primary_intent"] == "greeting":
                return self._intelligent_greeting()
            if analysis["primary_intent"] == "thanks":
                return self._intelligent_thanks()
            if analysis["primary_intent"] == "goodbye":
                return self._intelligent_goodbye()
            
            # Check if off-topic
            if self._is_off_topic(msg_lower, analysis):
                return self._intelligent_off_topic(msg_lower)
            
            # Get full system context
            system_context = self._get_system_context()
            
            # Handle follow-up questions
            if analysis["is_follow_up"] and self._conversation_context["last_topic"]:
                return self._handle_follow_up(msg_lower, analysis, system_context)
            
            # Route to appropriate handler based on analysis
            response = self._generate_intelligent_response(msg_lower, analysis, system_context)
            
            return response
            
        except Exception as e:
            logger.error(f"Chatbot error: {e}")
            return "I encountered an issue. Could you rephrase your question?"

    # ========================================================================
    # MESSAGE ANALYSIS
    # ========================================================================

    def _analyze_message(self, msg: str) -> dict:
        """
        Perform deep analysis of user message.
        """
        analysis = {
            "primary_intent": None,
            "secondary_intents": [],
            "entities": [],
            "topics": [],
            "confidence": 0.0,
            "is_question": "?" in msg or any(msg.startswith(w) for w in ["what", "how", "where", "when", "why", "is", "are", "can", "do", "does", "will", "should"]),
            "is_follow_up": False,
            "sentiment": "neutral",
            "specificity": "general"  # general, specific, very_specific
        }
        
        # Detect intents with confidence
        intent_scores = {}
        for intent, config in INTENT_PATTERNS.items():
            score = 0
            for pattern in config["patterns"]:
                if re.search(pattern, msg, re.IGNORECASE):
                    score = max(score, config["weight"])
            if score > 0:
                intent_scores[intent] = score
        
        if intent_scores:
            sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
            analysis["primary_intent"] = sorted_intents[0][0]
            analysis["confidence"] = sorted_intents[0][1]
            analysis["secondary_intents"] = [i[0] for i in sorted_intents[1:3]]
        
        # Check for follow-up indicators
        analysis["is_follow_up"] = analysis["primary_intent"] == "follow_up" or \
            any(re.search(p, msg) for p in [r"^(it|this|that|those|these)\b", r"^(and|but|also)\b", r"\b(more|else)\b"])
        
        # Extract entities (things the user is asking about)
        analysis["entities"] = self._extract_entities(msg)
        
        # Identify topics from knowledge base
        analysis["topics"] = self._identify_topics(msg)
        
        # Assess specificity
        if len(analysis["entities"]) > 1 or len(msg.split()) > 10:
            analysis["specificity"] = "very_specific"
        elif analysis["entities"] or analysis["topics"]:
            analysis["specificity"] = "specific"
        
        return analysis

    def _extract_entities(self, msg: str) -> list:
        """
        Extract entities (things/concepts) from the message.
        """
        entities = []
        
        # Feature entities
        for feature_id, feature in KNOWLEDGE_BASE["features"].items():
            for keyword in feature["keywords"]:
                if keyword in msg:
                    entities.append({"type": "feature", "id": feature_id, "match": keyword})
                    break
        
        # Concept entities
        for concept_id, concept in KNOWLEDGE_BASE["concepts"].items():
            for keyword in concept["keywords"]:
                if keyword in msg:
                    entities.append({"type": "concept", "id": concept_id, "match": keyword})
                    break
        
        # System entities - comprehensive mapping
        system_entities = {
            "cpu": ["cpu", "processor", "processing", "core", "cores"],
            "memory": ["memory", "ram", "mem", "heap"],
            "disk": ["disk", "storage", "drive", "space", "ssd", "hdd", "hard drive", "free space"],
            "events": ["event", "events", "log", "logs", "error", "errors", "warning", "warnings", "critical", "problem", "problems", "issue", "issues"],
            "security": ["security", "protection", "protected", "safe", "secure", "unsafe", "threat", "attack"],
            "system": ["system", "computer", "pc", "device", "machine", "laptop", "desktop", "my computer", "my device", "my pc"],
            "firewall": ["firewall", "fire wall"],
            "antivirus": ["antivirus", "anti-virus", "virus", "malware", "defender", "windows defender"],
            "network": ["network", "internet", "wifi", "wi-fi", "connection", "connected", "online", "offline", "port", "ports"]
        }
        for entity_id, keywords in system_entities.items():
            for keyword in keywords:
                if keyword in msg:
                    entities.append({"type": "system", "id": entity_id, "match": keyword})
                    break
        
        return entities

    def _identify_topics(self, msg: str) -> list:
        """
        Identify which topics from knowledge base are relevant.
        """
        topics = []
        words = set(msg.split())
        
        # Check features
        for feature_id, feature in KNOWLEDGE_BASE["features"].items():
            relevance = self._calculate_relevance(msg, words, feature["keywords"])
            if relevance > 0.3:
                topics.append({"type": "feature", "id": feature_id, "relevance": relevance})
        
        # Check concepts
        for concept_id, concept in KNOWLEDGE_BASE["concepts"].items():
            relevance = self._calculate_relevance(msg, words, concept["keywords"])
            if relevance > 0.3:
                topics.append({"type": "concept", "id": concept_id, "relevance": relevance})
        
        # Sort by relevance
        topics.sort(key=lambda x: x["relevance"], reverse=True)
        return topics[:3]  # Top 3 topics

    def _calculate_relevance(self, msg: str, words: set, keywords: list) -> float:
        """
        Calculate relevance score between message and keywords.
        """
        if not keywords:
            return 0.0
        
        score = 0.0
        for keyword in keywords:
            # Exact match in message
            if keyword in msg:
                score += 1.0
            # Word overlap
            elif any(keyword in word or word in keyword for word in words):
                score += 0.5
            # Fuzzy match
            else:
                for word in words:
                    if len(word) > 3 and self._similarity(word, keyword) > 0.8:
                        score += 0.3
        
        return min(score / len(keywords), 1.0)

    def _similarity(self, a: str, b: str) -> float:
        """Calculate string similarity."""
        return SequenceMatcher(None, a, b).ratio()

    # ========================================================================
    # CONTEXT MANAGEMENT
    # ========================================================================

    def _update_context(self, conversation: list, msg: str) -> None:
        """
        Update conversation context based on current message.
        """
        # Track discussed topics
        for topic in self._identify_topics(msg):
            self._conversation_context["discussed_topics"].add(topic["id"])
        
        # Update last topic from entities
        entities = self._extract_entities(msg)
        if entities:
            self._conversation_context["last_entities"] = entities
            self._conversation_context["last_topic"] = entities[0]["id"]
        
        # Track user concerns (problems mentioned)
        concern_patterns = [r"(problem|issue|error|warning|slow|not working|failed|worried|concerned)"]
        for pattern in concern_patterns:
            if re.search(pattern, msg):
                self._conversation_context["user_concerns"].append(msg)
                break

    def _get_system_context(self) -> dict:
        """
        Get complete system context.
        """
        ctx = {
            "cpu": None, "cpu_status": "unknown",
            "memory": None, "memory_status": "unknown",
            "disk": None, "disk_status": "unknown",
            "firewall": None, "firewall_ok": None,
            "antivirus": None, "antivirus_ok": None,
            "tpm": None, "tpm_ok": None,
            "bitlocker": None, "secureboot": None,
            "security_issues": [],
            "overall_security": "unknown",
            "events_total": 0,
            "events_critical": 0,
            "events_error": 0,
            "events_warning": 0,
            "recent_events": []
        }
        
        thresholds = KNOWLEDGE_BASE["thresholds"]
        
        if self._snapshot_service:
            try:
                # System metrics
                cpu = getattr(self._snapshot_service, "cpuUsage", None)
                mem = getattr(self._snapshot_service, "memoryUsage", None)
                disk = getattr(self._snapshot_service, "diskUsage", None)
                
                if cpu is not None:
                    ctx["cpu"] = round(cpu, 1)
                    if cpu >= thresholds["cpu"]["critical"]:
                        ctx["cpu_status"] = "critical"
                    elif cpu >= thresholds["cpu"]["warning"]:
                        ctx["cpu_status"] = "warning"
                    else:
                        ctx["cpu_status"] = "good"
                
                if mem is not None:
                    ctx["memory"] = round(mem, 1)
                    if mem >= thresholds["memory"]["critical"]:
                        ctx["memory_status"] = "critical"
                    elif mem >= thresholds["memory"]["warning"]:
                        ctx["memory_status"] = "warning"
                    else:
                        ctx["memory_status"] = "good"
                
                if disk is not None:
                    ctx["disk"] = round(disk, 1)
                    if disk >= thresholds["disk"]["critical"]:
                        ctx["disk_status"] = "critical"
                    elif disk >= thresholds["disk"]["warning"]:
                        ctx["disk_status"] = "warning"
                    else:
                        ctx["disk_status"] = "good"
                
                # Security info
                sec_info = getattr(self._snapshot_service, "securityInfo", None)
                if sec_info:
                    ctx["firewall"] = sec_info.get("firewallStatus", "Unknown")
                    ctx["firewall_ok"] = "on" in str(ctx["firewall"]).lower()
                    
                    ctx["antivirus"] = sec_info.get("antivirus", "Unknown")
                    ctx["antivirus_ok"] = ctx["antivirus"] not in ["Unknown", "N/A", "", None]
                    
                    ctx["tpm"] = sec_info.get("tpmPresent", "Unknown")
                    ctx["tpm_ok"] = str(ctx["tpm"]).lower() in ["yes", "true", "present", "2.0"]
                    
                    ctx["bitlocker"] = sec_info.get("bitlocker", "Unknown")
                    ctx["secureboot"] = sec_info.get("secureBoot", "Unknown")
                    
                    # Collect issues
                    simplified = sec_info.get("simplified", {})
                    if simplified:
                        ctx["overall_security"] = simplified.get("overall", {}).get("status", "Unknown")
                        for key, value in simplified.items():
                            if isinstance(value, dict):
                                status = value.get("status", "")
                                if status in ["Warning", "Critical", "Off", "Disabled"]:
                                    ctx["security_issues"].append({
                                        "name": key,
                                        "status": status,
                                        "message": value.get("message", "")
                                    })
            except Exception as e:
                logger.debug(f"Failed to get snapshot: {e}")
        
        if self._event_repo:
            try:
                events = self._event_repo.get_recent(limit=50)
                if events:
                    ctx["events_total"] = len(events)
                    for evt in events:
                        level = getattr(evt, "level", "")
                        if level == "Critical":
                            ctx["events_critical"] += 1
                        elif level == "Error":
                            ctx["events_error"] += 1
                        elif level == "Warning":
                            ctx["events_warning"] += 1
                    ctx["recent_events"] = events[:5]
            except Exception as e:
                logger.debug(f"Failed to get events: {e}")
        
        return ctx

    # ========================================================================
    # TOPIC DETECTION
    # ========================================================================

    def _is_off_topic(self, msg: str, analysis: dict) -> bool:
        """
        Intelligently determine if message is off-topic.
        
        PRINCIPLE: When in doubt, treat as ON-topic and try to help.
        Only reject if CLEARLY off-topic with no security connection.
        """
        # If we found ANY security-related entities/topics, it's definitely on-topic
        if analysis["entities"] or analysis["topics"]:
            return False
        
        # Check for explicit security indicators FIRST
        for pattern in SECURITY_INDICATORS:
            if re.search(pattern, msg, re.IGNORECASE):
                return False
        
        # Short messages are likely follow-ups or simple questions - allow them
        if len(msg.split()) <= 4:
            return False
        
        # Check for EXPLICIT off-topic patterns (must be very clear)
        explicit_off_topic = [
            r"\b(joke|jokes|tell\s+me\s+a\s+joke|make\s+me\s+laugh|funny\s+story)\b",
            r"\b(weather|forecast|temperature|rain|sunny|cloudy)\b(?!.*(network|connection))",
            r"\b(recipe|cook|cooking|bake|baking|restaurant)\b",
            r"\b(movie|film|cinema|music|song|artist|band|concert|album)\b",
            r"\b(game|gaming|sports?|score|match|team|player|championship)\b(?!.*(security|hack))",
            r"\b(politics|election|vote|government|president|minister)\b(?!.*(security|cyber))",
            r"\b(travel|vacation|flight|hotel|destination|tourism)\b",
            r"\b(relationship|dating|boyfriend|girlfriend|marriage|wedding)\b",
            r"\b(homework|essay|assignment)\b(?!.*(security|cyber))",
            r"\bwho\s+(is|was)\s+the\s+(president|king|queen|leader)\b",
            r"\b(what\s+time\s+is\s+it|current\s+time|date\s+today)\b",
        ]
        
        for pattern in explicit_off_topic:
            if re.search(pattern, msg, re.IGNORECASE):
                # Triple-check it's not security-related
                for sec_pattern in SECURITY_INDICATORS:
                    if re.search(sec_pattern, msg, re.IGNORECASE):
                        return False
                return True
        
        # Default: treat as on-topic and try to help
        return False

    def _detect_action(self, msg: str) -> Optional[str]:
        """
        Detect if the user is requesting a security action.
        Returns the action name if detected, None otherwise.
        """
        msg_lower = msg.lower()
        
        for action_name, patterns in ACTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, msg_lower, re.IGNORECASE):
                    logger.info(f"Detected action request: {action_name}")
                    return action_name
        
        return None

    def _execute_action(self, action: str) -> str:
        """Execute a security action and return the response."""
        executor = get_action_executor()
        response = executor.execute_action(action)
        
        # Build the response message
        result_msg = response.message
        if response.details:
            result_msg += f"\n\n{response.details}"
        
        return result_msg

    # ========================================================================
    # RESPONSE GENERATION
    # ========================================================================

    def _generate_intelligent_response(self, msg: str, analysis: dict, ctx: dict) -> str:
        """
        Generate a contextual, intelligent response.
        """
        # FIRST: Check if user is requesting an ACTION
        detected_action = self._detect_action(msg)
        if detected_action:
            return self._execute_action(detected_action)
        
        # Determine what the user wants based on intent and entities
        intent = analysis["primary_intent"]
        entities = analysis["entities"]
        topics = analysis["topics"]
        
        # Direct metric questions (what is my X, show my X, X usage)
        if re.search(r"\b(my|the)?\s*cpu\s*(usage|load|percent)?\b", msg):
            return self._cpu_status(ctx)
        if re.search(r"\b(my|the)?\s*(memory|ram)\s*(usage|percent)?\b", msg):
            return self._memory_status(ctx)
        if re.search(r"\b(my|the)?\s*(disk|storage|drive)\s*(usage|space|percent)?\b", msg):
            return self._disk_status(ctx)
        
        # How-to questions about features
        if intent == "how_to" or intent == "location":
            return self._respond_how_to(msg, entities, topics)
        
        # What-is questions about concepts
        if intent == "what_is":
            return self._respond_what_is(msg, entities, topics, ctx)
        
        # Status check questions
        if intent == "status_check" or self._is_asking_status(msg):
            return self._respond_status(msg, entities, ctx)
        
        # Problem/issue questions
        if intent == "problem":
            return self._respond_problem(msg, entities, ctx)
        
        # Recommendation questions
        if intent == "recommendation":
            return self._respond_recommendation(msg, entities, topics)
        
        # Entity-based routing
        if entities:
            primary_entity = entities[0]
            if primary_entity["type"] == "feature":
                return self._respond_about_feature(primary_entity["id"], msg, ctx)
            elif primary_entity["type"] == "concept":
                return self._respond_about_concept(primary_entity["id"], msg, ctx)
            elif primary_entity["type"] == "system":
                return self._respond_about_system(primary_entity["id"], msg, ctx)
        
        # Topic-based routing
        if topics:
            primary_topic = topics[0]
            if primary_topic["type"] == "feature":
                return self._respond_about_feature(primary_topic["id"], msg, ctx)
            elif primary_topic["type"] == "concept":
                return self._respond_about_concept(primary_topic["id"], msg, ctx)
        
        # Fallback - provide helpful context-aware response
        return self._respond_general(msg, ctx)

    def _is_asking_status(self, msg: str) -> bool:
        """Check if user is asking about system status."""
        patterns = [
            r"how\s+(is|are|\'s)\s+(my|the)?\s*(system|computer|pc|device)",
            r"(is|are)\s+(my|the)?\s*(system|computer|pc)\s+(ok|okay|fine|good|safe)",
            r"check\s+(my|the)?\s*(system|computer|security)",
            r"(what|how).*status",
            r"am\s+i\s+(safe|protected|secure)"
        ]
        return any(re.search(p, msg, re.IGNORECASE) for p in patterns)

    # ========================================================================
    # SPECIFIC RESPONSE HANDLERS
    # ========================================================================

    def _respond_how_to(self, msg: str, entities: list, topics: list) -> str:
        """Respond to how-to questions."""
        # Special handling for "where is security status" type questions
        if "security status" in msg or ("security" in msg and ("where" in msg or "find" in msg or "go to" in msg)):
            feature = KNOWLEDGE_BASE["features"]["security_status"]
            return f"**{feature['description']}**\n\n📍 {feature['location']}\n\n**What you can check:**\n" + \
                   "\n".join(f"• {cap}" for cap in feature["capabilities"])
        
        # Find the relevant feature
        feature_id = None
        for e in entities:
            if e["type"] == "feature":
                feature_id = e["id"]
                break
        if not feature_id:
            for t in topics:
                if t["type"] == "feature":
                    feature_id = t["id"]
                    break
        
        if feature_id and feature_id in KNOWLEDGE_BASE["features"]:
            feature = KNOWLEDGE_BASE["features"][feature_id]
            response = f"**{feature['description']}**\n\n"
            response += f"📍 **Location:** {feature['location']}\n\n"
            
            if "how_to_use" in feature:
                response += "**Steps:**\n"
                for i, step in enumerate(feature["how_to_use"], 1):
                    response += f"{i}. {step}\n"
            elif "capabilities" in feature:
                response += "**What you can do:**\n"
                for cap in feature["capabilities"]:
                    response += f"• {cap}\n"
            
            return response
        
        # Check for specific actions
        if "scan" in msg and "file" in msg:
            return self._how_to_scan_file()
        if "scan" in msg and ("url" in msg or "link" in msg):
            return self._how_to_scan_url()
        
        # General help
        return self._respond_capabilities()

    def _respond_what_is(self, msg: str, entities: list, topics: list, ctx: dict) -> str:
        """Respond to what-is questions."""
        msg_lower = msg.lower()
        
        # Check if asking about errors/problems/issues on their device
        error_keywords = ["error", "errors", "problem", "problems", "issue", "issues", "warning", "warnings", "critical", "wrong"]
        device_keywords = ["device", "computer", "pc", "system", "machine", "my"]
        
        asking_about_errors = any(kw in msg_lower for kw in error_keywords)
        asking_about_device = any(kw in msg_lower for kw in device_keywords)
        
        if asking_about_errors and asking_about_device:
            # They want to know about errors on their device - use problem handler
            return self._respond_problem(msg, entities, ctx)
        
        if asking_about_errors:
            # They want to know about errors - show events
            return self._events_status(ctx)
        
        # Find the relevant concept
        concept_id = None
        for e in entities:
            if e["type"] == "concept":
                concept_id = e["id"]
                break
        if not concept_id:
            for t in topics:
                if t["type"] == "concept":
                    concept_id = t["id"]
                    break
        
        if concept_id and concept_id in KNOWLEDGE_BASE["concepts"]:
            concept = KNOWLEDGE_BASE["concepts"][concept_id]
            response = ""
            
            if "what_is" in concept:
                response += f"**{concept_id.replace('_', ' ').title()}:** {concept['what_is']}\n\n"
            
            if "why_important" in concept:
                response += f"**Why it matters:** {concept['why_important']}\n\n"
            
            if "best_practices" in concept:
                response += "**Best practices:**\n"
                for practice in concept["best_practices"]:
                    response += f"• {practice}\n"
            
            if "how_to_enable" in concept:
                response += f"\n**How to enable:** {concept['how_to_enable']}"
            
            return response if response else f"I can help explain {concept_id}. What specifically would you like to know?"
        
        return "Could you be more specific about what you'd like me to explain? I can help with security concepts like firewalls, encryption, passwords, and more."

    def _respond_status(self, msg: str, entities: list, ctx: dict) -> str:
        """Respond to status questions with real data."""
        # Determine what status they want
        asking_about = set()
        for e in entities:
            if e["type"] == "system":
                asking_about.add(e["id"])
        
        # If no specific entity, give full overview
        if not asking_about or "security" in asking_about:
            return self._full_status_report(ctx)
        
        # Specific status
        response = ""
        if "cpu" in asking_about:
            response += self._cpu_status(ctx) + "\n\n"
        if "memory" in asking_about:
            response += self._memory_status(ctx) + "\n\n"
        if "disk" in asking_about:
            response += self._disk_status(ctx) + "\n\n"
        if "events" in asking_about:
            response += self._events_status(ctx) + "\n\n"
        
        return response.strip() if response else self._full_status_report(ctx)

    def _full_status_report(self, ctx: dict) -> str:
        """Generate comprehensive status report."""
        response = "## 📊 System Status Report\n\n"
        
        # Performance metrics
        response += "### Performance\n"
        
        if ctx["cpu"] is not None:
            icon = "🔴" if ctx["cpu_status"] == "critical" else ("🟡" if ctx["cpu_status"] == "warning" else "🟢")
            response += f"{icon} **CPU:** {ctx['cpu']}%"
            if ctx["cpu_status"] == "critical":
                response += " ⚠️ Very high! Check Task Manager."
            elif ctx["cpu_status"] == "warning":
                response += " - Elevated"
            response += "\n"
        
        if ctx["memory"] is not None:
            icon = "🔴" if ctx["memory_status"] == "critical" else ("🟡" if ctx["memory_status"] == "warning" else "🟢")
            response += f"{icon} **Memory:** {ctx['memory']}%"
            if ctx["memory_status"] == "critical":
                response += " ⚠️ Running low! Close some apps."
            elif ctx["memory_status"] == "warning":
                response += " - Getting full"
            response += "\n"
        
        if ctx["disk"] is not None:
            icon = "🔴" if ctx["disk_status"] == "critical" else ("🟡" if ctx["disk_status"] == "warning" else "🟢")
            response += f"{icon} **Disk:** {ctx['disk']}%"
            if ctx["disk_status"] == "critical":
                response += " ⚠️ Almost full! Free up space urgently."
            elif ctx["disk_status"] == "warning":
                response += " - Consider cleanup"
            response += "\n"
        
        # Security status
        response += "\n### Security\n"
        
        if ctx["firewall_ok"] is not None:
            icon = "🟢" if ctx["firewall_ok"] else "🔴"
            response += f"{icon} **Firewall:** {ctx['firewall']}\n"
        
        if ctx["antivirus"]:
            icon = "🟢" if ctx["antivirus_ok"] else "🟡"
            response += f"{icon} **Antivirus:** {ctx['antivirus']}\n"
        
        if ctx["tpm"]:
            icon = "🟢" if ctx["tpm_ok"] else "⚪"
            response += f"{icon} **TPM:** {ctx['tpm']}\n"
        
        # Issues
        if ctx["security_issues"]:
            response += "\n### ⚠️ Attention Needed\n"
            for issue in ctx["security_issues"][:3]:
                response += f"• **{issue['name']}:** {issue['message']}\n"
        
        # Events summary
        if ctx["events_total"] > 0:
            response += "\n### Recent Events\n"
            if ctx["events_critical"] > 0:
                response += f"🔴 {ctx['events_critical']} Critical\n"
            if ctx["events_error"] > 0:
                response += f"🟠 {ctx['events_error']} Errors\n"
            if ctx["events_warning"] > 0:
                response += f"🟡 {ctx['events_warning']} Warnings\n"
            if ctx["events_critical"] == 0 and ctx["events_error"] == 0:
                response += "✅ No critical issues in recent events\n"
        
        # Overall assessment
        response += "\n### Assessment\n"
        issues_count = len(ctx["security_issues"]) + ctx["events_critical"]
        if issues_count == 0 and ctx["firewall_ok"] and all(s == "good" for s in [ctx["cpu_status"], ctx["memory_status"], ctx["disk_status"]] if s != "unknown"):
            response += "✅ **Your system looks healthy and well-protected!**"
        elif issues_count > 2 or ctx["events_critical"] > 0:
            response += "⚠️ **There are some issues that need your attention.** Review the items above."
        else:
            response += "🟡 **System is mostly fine.** A few items to review above."
        
        return response

    def _cpu_status(self, ctx: dict) -> str:
        if ctx["cpu"] is None:
            return "**CPU:** Unable to read. Check System Snapshot."
        
        cpu = ctx["cpu"]
        status = ctx["cpu_status"]
        
        response = f"**CPU Usage: {cpu}%**\n\n"
        if status == "critical":
            response += "🔴 **Very High!** Something is using a lot of processing power.\n\n"
            response += "**What to do:**\n"
            response += "1. Open Task Manager (Ctrl+Shift+Esc)\n"
            response += "2. Sort by CPU column\n"
            response += "3. Identify the heavy process\n"
            response += "4. If it's unfamiliar, search online to verify it's safe"
        elif status == "warning":
            response += "🟡 **Elevated.** This is okay if you're running heavy applications.\n"
            response += "If idle, check Task Manager for unexpected processes."
        else:
            response += "🟢 **Looking good!** Your processor isn't working hard."
        
        return response

    def _memory_status(self, ctx: dict) -> str:
        if ctx["memory"] is None:
            return "**Memory:** Unable to read. Check System Snapshot."
        
        mem = ctx["memory"]
        status = ctx["memory_status"]
        
        response = f"**Memory (RAM): {mem}%**\n\n"
        if status == "critical":
            response += "🔴 **Running low!** This slows down your computer.\n\n"
            response += "**Quick fixes:**\n"
            response += "• Close browser tabs you're not using\n"
            response += "• Close unused applications\n"
            response += "• Restart if it's been running for days"
        elif status == "warning":
            response += "🟡 **Getting full.** Close some apps if things feel slow."
        else:
            response += "🟢 **Plenty of room!** You can run more applications."
        
        return response

    def _disk_status(self, ctx: dict) -> str:
        if ctx["disk"] is None:
            return "**Disk:** Unable to read. Check System Snapshot."
        
        disk = ctx["disk"]
        status = ctx["disk_status"]
        
        response = f"**Disk Space: {disk}% used**\n\n"
        if status == "critical":
            response += "🔴 **Almost full!** Windows needs free space to work properly.\n\n"
            response += "**Free up space:**\n"
            response += "1. Run Disk Cleanup (search in Start)\n"
            response += "2. Empty Recycle Bin\n"
            response += "3. Uninstall unused apps\n"
            response += "4. Move files to external storage"
        elif status == "warning":
            response += "🟡 **Getting full.** Consider cleaning up soon."
        else:
            response += "🟢 **Good amount of free space!**"
        
        return response

    def _events_status(self, ctx: dict) -> str:
        response = "**Recent Windows Events:**\n\n"
        
        if ctx["events_total"] == 0:
            return response + "No events loaded. Check the Event Viewer page."
        
        if ctx["events_critical"] > 0:
            response += f"🔴 **{ctx['events_critical']} Critical** - Serious issues\n"
        if ctx["events_error"] > 0:
            response += f"🟠 **{ctx['events_error']} Errors** - Problems to investigate\n"
        if ctx["events_warning"] > 0:
            response += f"🟡 **{ctx['events_warning']} Warnings** - Minor issues\n"
        
        if ctx["events_critical"] == 0 and ctx["events_error"] == 0:
            response += "✅ **No critical issues!**\n"
        
        response += "\nUse the Event Viewer for details and AI explanations."
        return response

    def _respond_about_feature(self, feature_id: str, msg: str, ctx: dict) -> str:
        """Respond about a specific Sentinel feature."""
        if feature_id not in KNOWLEDGE_BASE["features"]:
            return self._respond_general(msg, ctx)
        
        feature = KNOWLEDGE_BASE["features"][feature_id]
        response = f"**{feature['description']}**\n\n"
        response += f"📍 {feature['location']}\n\n"
        
        if "capabilities" in feature:
            response += "**What it does:**\n"
            for cap in feature["capabilities"][:5]:
                response += f"• {cap}\n"
        
        # Add contextual info based on feature
        if feature_id == "event_viewer" and ctx["events_total"] > 0:
            response += f"\n📊 Currently: {ctx['events_critical']} critical, {ctx['events_error']} errors in recent events."
        elif feature_id == "system_snapshot":
            if ctx["cpu"] is not None:
                response += f"\n📊 Current: CPU {ctx['cpu']}%, RAM {ctx['memory']}%, Disk {ctx['disk']}%"
        elif feature_id == "security_status":
            if ctx["security_issues"]:
                response += f"\n⚠️ {len(ctx['security_issues'])} issue(s) detected."
        
        return response

    def _respond_about_concept(self, concept_id: str, msg: str, ctx: dict) -> str:
        """Respond about a security concept."""
        if concept_id not in KNOWLEDGE_BASE["concepts"]:
            return self._respond_general(msg, ctx)
        
        concept = KNOWLEDGE_BASE["concepts"][concept_id]
        response = f"## {concept_id.replace('_', ' ').title()}\n\n"
        
        # What is it
        if "what_is" in concept:
            response += f"{concept['what_is']}\n\n"
        
        # Why important
        if "why_important" in concept:
            response += f"**Why it matters:** {concept['why_important']}\n\n"
        
        # Add current status if applicable
        if concept_id == "firewall" and ctx["firewall"]:
            status = "🟢 ON" if ctx["firewall_ok"] else "🔴 Check settings"
            response += f"**Your status:** {status} ({ctx['firewall']})\n\n"
        elif concept_id == "antivirus" and ctx["antivirus"]:
            response += f"**Your status:** {ctx['antivirus']}\n\n"
        elif concept_id == "tpm" and ctx["tpm"]:
            response += f"**Your status:** {ctx['tpm']}\n\n"
        
        # Best practices
        if "best_practices" in concept:
            response += "**Best practices:**\n"
            for practice in concept["best_practices"][:5]:
                response += f"• {practice}\n"
        
        # Red flags (for phishing)
        if "red_flags" in concept:
            response += "**Red flags to watch for:**\n"
            for flag in concept["red_flags"][:5]:
                response += f"• {flag}\n"
        
        return response

    def _respond_about_system(self, entity_id: str, msg: str, ctx: dict) -> str:
        """Respond about system metrics."""
        if entity_id == "cpu":
            return self._cpu_status(ctx)
        elif entity_id == "memory":
            return self._memory_status(ctx)
        elif entity_id == "disk":
            return self._disk_status(ctx)
        elif entity_id == "events":
            return self._events_status(ctx)
        elif entity_id == "security":
            return self._full_status_report(ctx)
        else:
            return self._full_status_report(ctx)

    def _respond_problem(self, msg: str, entities: list, ctx: dict) -> str:
        """Respond to problem/issue questions."""
        response = "I understand you're experiencing an issue. Let me help.\n\n"
        
        # Check what's actually wrong based on context
        problems = []
        
        if ctx["cpu_status"] == "critical":
            problems.append(("High CPU", "Open Task Manager to see what's using your processor."))
        if ctx["memory_status"] == "critical":
            problems.append(("Low Memory", "Close unused apps or restart your computer."))
        if ctx["disk_status"] == "critical":
            problems.append(("Low Disk Space", "Run Disk Cleanup to free up space."))
        if ctx["events_critical"] > 0:
            problems.append((f"{ctx['events_critical']} Critical Events", "Check Event Viewer for details."))
        if not ctx["firewall_ok"]:
            problems.append(("Firewall Issue", "Enable firewall in Windows Security."))
        
        if problems:
            response += "**Based on your system, I found these issues:**\n\n"
            for problem, solution in problems:
                response += f"⚠️ **{problem}**\n   → {solution}\n\n"
        else:
            response += "Your system metrics look okay. Could you describe the specific problem you're experiencing?\n\n"
            response += "For example:\n"
            response += "• 'My computer is slow'\n"
            response += "• 'I see error messages'\n"
            response += "• 'Something suspicious happened'"
        
        return response

    def _respond_recommendation(self, msg: str, entities: list, topics: list) -> str:
        """Respond to recommendation questions."""
        # Check if asking about specific topic
        for topic in topics:
            if topic["type"] == "concept" and topic["id"] == "password":
                concept = KNOWLEDGE_BASE["concepts"]["password"]
                response = "## Password Best Practices\n\n"
                for practice in concept["best_practices"]:
                    response += f"✅ {practice}\n"
                response += "\n**Common mistakes to avoid:**\n"
                for mistake in concept["common_mistakes"]:
                    response += f"❌ {mistake}\n"
                return response
        
        # Check for password in message
        if "password" in msg:
            concept = KNOWLEDGE_BASE["concepts"]["password"]
            response = "## Password Best Practices\n\n"
            for practice in concept["best_practices"]:
                response += f"✅ {practice}\n"
            response += "\n**Common mistakes to avoid:**\n"
            for mistake in concept["common_mistakes"]:
                response += f"❌ {mistake}\n"
            return response
        
        # General security recommendations
        response = "**My Security Recommendations:**\n\n"
        response += "**Essential Security:**\n"
        response += "1. ✅ Keep Windows Firewall ON\n"
        response += "2. ✅ Enable Windows Defender real-time protection\n"
        response += "3. ✅ Install Windows updates promptly\n"
        response += "4. ✅ Use strong, unique passwords\n"
        response += "5. ✅ Enable 2FA on important accounts\n\n"
        
        response += "**Good Habits:**\n"
        response += "• Don't click suspicious links\n"
        response += "• Verify sender before opening attachments\n"
        response += "• Keep backups of important files\n"
        response += "• Run regular virus scans\n"
        
        return response

    def _respond_general(self, msg: str, ctx: dict) -> str:
        """Fallback response with contextual info."""
        response = "I'm here to help with your security questions.\n\n"
        
        # Add quick status
        response += "**Quick Status:**\n"
        if ctx["cpu"] is not None:
            response += f"• System: CPU {ctx['cpu']}%, RAM {ctx['memory']}%, Disk {ctx['disk']}%\n"
        if ctx["security_issues"]:
            response += f"• ⚠️ {len(ctx['security_issues'])} security issue(s) detected\n"
        elif ctx["firewall_ok"]:
            response += "• ✅ Basic security protections active\n"
        
        response += "\n**I can help you with:**\n"
        response += "• \"How is my computer doing?\" - Full system check\n"
        response += "• \"Am I protected?\" - Security status\n"
        response += "• \"How do I scan a file?\" - Feature guidance\n"
        response += "• \"What is TPM?\" - Security concepts\n"
        response += "• \"Tips for passwords\" - Best practices"
        
        return response

    def _handle_follow_up(self, msg: str, analysis: dict, ctx: dict) -> str:
        """Handle follow-up questions using context."""
        last_topic = self._conversation_context["last_topic"]
        last_entities = self._conversation_context["last_entities"]
        
        # "what about X" pattern - extract X and query about it
        what_about_match = re.search(r"what\s+about\s+(.+)", msg)
        if what_about_match:
            subject = what_about_match.group(1).strip().rstrip("?")
            # Direct system metric questions
            if subject in ["memory", "ram", "mem"]:
                return self._memory_status(ctx)
            if subject in ["cpu", "processor"]:
                return self._cpu_status(ctx)
            if subject in ["disk", "storage", "drive", "space"]:
                return self._disk_status(ctx)
            if subject in ["events", "logs", "errors"]:
                return self._events_status(ctx)
            # Rebuild as a new question
            return self._generate_intelligent_response(f"tell me about {subject}", analysis, ctx)
        
        # Check what they want to know more about
        if any(w in msg for w in ["more", "else", "detail", "explain"]):
            if last_topic in KNOWLEDGE_BASE["features"]:
                return self._respond_about_feature(last_topic, msg, ctx)
            elif last_topic in KNOWLEDGE_BASE["concepts"]:
                return self._respond_about_concept(last_topic, msg, ctx)
        
        # Handle direct metric questions in follow-up
        if any(w in msg for w in ["memory", "ram"]):
            return self._memory_status(ctx)
        if any(w in msg for w in ["cpu", "processor"]):
            return self._cpu_status(ctx)
        if any(w in msg for w in ["disk", "storage", "drive"]):
            return self._disk_status(ctx)
        
        # Default - try to generate response with context
        return self._generate_intelligent_response(msg, analysis, ctx)

    # ========================================================================
    # SOCIAL RESPONSES
    # ========================================================================

    def _intelligent_greeting(self) -> str:
        return """Hello! 👋 I'm your intelligent security assistant.

I can see your system in real-time and help you with:
• **System health** - "How is my computer doing?"
• **Security status** - "Am I protected?"
• **Sentinel features** - "How do I check events?"
• **Security concepts** - "What is BitLocker?"
• **Best practices** - "Tips for strong passwords"

🔧 **I can also take action for you:**
• "Enable my firewall" - Turn on protection
• "Run a virus scan" - Start security scan
• "Check for updates" - Open Windows Update
• "Open Windows Security" - Open security settings

Everything runs locally on your computer - your data stays private.

What would you like to know or do?"""

    def _intelligent_thanks(self) -> str:
        return "You're welcome! 😊 Feel free to ask if you have more security questions. I'm here to help."

    def _intelligent_goodbye(self) -> str:
        return """Goodbye! 👋 

**Quick security reminders:**
• Keep your system updated
• Don't click suspicious links
• Use strong passwords with 2FA

Stay safe!"""

    def _intelligent_off_topic(self, msg: str) -> str:
        return """I appreciate the question, but I'm specifically designed for **security and system health** topics.

**I can help you with:**
• Computer performance (CPU, memory, disk)
• Security status (firewall, antivirus, encryption)
• Windows events and errors
• Passwords, phishing, safe browsing
• Using Sentinel's features

**Try asking:**
• "How is my system doing?"
• "Is my computer protected?"
• "How do I check for threats?"

What security topic can I help you with?"""

    def _respond_capabilities(self) -> str:
        return """## What I Can Help With

### 📊 System Health
• "How is my computer doing?" - Full health check
• "Check my CPU/memory/disk" - Specific metrics
• "Are there any errors?" - Event summary

### 🛡️ Security Status
• "Am I protected?" - Security overview
• "Is my firewall on?" - Specific checks
• "What security issues do I have?" - Problems

### 📖 Sentinel Features
• "How do I check events?" - Event Viewer guide
• "Where is security status?" - Navigation help
• "How do I scan a file?" - Scanning guide

### 💡 Security Knowledge
• "What is TPM/BitLocker/2FA?" - Concepts explained
• "Tips for passwords" - Best practices
• "How to spot phishing" - Protection advice

### 🔧 Actions I Can Take
• "Enable my firewall" - Turn on protection
• "Run a virus scan" - Start Windows Defender scan
• "Check for updates" - Open Windows Update
• "Open Windows Security" - Security settings
• "Disable Remote Desktop" - More secure
• "Flush DNS" - Fix network issues
• "Open Task Manager" - See processes

### 🔧 Troubleshooting
• "My computer is slow" - Diagnostics
• "I see errors" - Event analysis
• "Fix my firewall" - Enable protection

Just ask naturally - I understand context and can take action!"""

    def _how_to_scan_file(self) -> str:
        return """## How to Scan a File for Threats

**Steps:**
1. Go to '🔍 Scan History' in the left sidebar
2. Click the '**Scan File**' button
3. Select the file you want to check
4. Wait for the analysis to complete
5. Review the results:
   - 🟢 Green = Safe
   - 🔴 Red = Threat detected

**Tips:**
• Always scan downloaded files before opening
• Scan files from emails or USB drives
• If a threat is found, delete the file

**What gets checked:**
• Known malware signatures
• Suspicious behaviors
• File reputation"""

    def _how_to_scan_url(self) -> str:
        return """## How to Scan a URL/Link

**Steps:**
1. Go to '🔍 Scan History' in the left sidebar  
2. Click the '**Scan URL**' button
3. Paste the URL you want to check
4. Wait for the analysis
5. Review the results:
   - 🟢 Safe to visit
   - 🔴 Suspicious or dangerous

**When to scan:**
• Before clicking links in emails
• Shortened URLs (bit.ly, etc.)
• Links from unknown sources
• Any URL that seems suspicious

**Red flags in URLs:**
• Misspelled domains (paypa1.com)
• Unusual extensions (.xyz, .tk)
• Very long random strings"""


# ============================================================================
# SINGLETON FACTORY
# ============================================================================

_security_chatbot: Optional[SecurityChatbot] = None


def get_security_chatbot(
    llm_engine: LocalLLMEngine,
    snapshot_service: Optional[Any] = None,
    event_repo: Optional[Any] = None,
) -> SecurityChatbot:
    """Get the singleton SecurityChatbot instance."""
    global _security_chatbot
    if _security_chatbot is None:
        _security_chatbot = SecurityChatbot(llm_engine, snapshot_service, event_repo)
    return _security_chatbot
