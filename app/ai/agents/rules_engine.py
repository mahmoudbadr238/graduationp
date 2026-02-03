"""
Rules Engine Agent
==================
Applies offline knowledge base rules for deterministic explanations.

This is the CRITICAL agent that ensures offline-first behavior.
It MUST be consulted BEFORE any LLM reasoning.

RESPONSIBILITIES:
1. Look up event IDs in the offline KB
2. Provide deterministic explanations based on rules
3. Set is_normal flags based on KB data
4. Provide what_to_do_now based on KB recommendations

KB STRUCTURE (from event_knowledge.json):
{
    "event_id": {
        "title": "...",
        "description": "...",
        "category": "security|system|application|...",
        "severity": "info|low|medium|high|critical",
        "is_normal": true|false,
        "causes": ["..."],
        "affects": ["..."],
        "recommendations": ["..."],
        "when_to_worry": "...",
        "related_events": [...]
    }
}
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .schema import (
    AssistantState,
    EventEvidence,
    KBRuleEvidence,
    SecurityAnalysis,
)

logger = logging.getLogger(__name__)


# =============================================================================
# KB Rule Structures
# =============================================================================

@dataclass
class EventKBEntry:
    """A knowledge base entry for a Windows event."""
    event_id: int
    title: str
    description: str
    category: str = "system"
    severity: str = "info"  # info, low, medium, high, critical
    is_normal: bool = True
    causes: List[str] = field(default_factory=list)
    affects: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    when_to_worry: str = ""
    related_events: List[int] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, event_id: int, data: Dict[str, Any]) -> "EventKBEntry":
        """Create from dictionary."""
        return cls(
            event_id=event_id,
            title=data.get("title", f"Event {event_id}"),
            description=data.get("description", ""),
            category=data.get("category", "system"),
            severity=data.get("severity", "info"),
            is_normal=data.get("is_normal", True),
            causes=data.get("causes", []),
            affects=data.get("affects", []),
            recommendations=data.get("recommendations", []),
            when_to_worry=data.get("when_to_worry", ""),
            related_events=data.get("related_events", []),
        )


# =============================================================================
# Built-in Event Knowledge Base
# =============================================================================

# This is a subset of common Windows security events
# The full KB should be loaded from event_knowledge.json
BUILTIN_EVENT_KB: Dict[int, Dict[str, Any]] = {
    # Logon Events
    4624: {
        "title": "Successful Logon",
        "description": "An account was successfully logged on.",
        "category": "security",
        "severity": "info",
        "is_normal": True,
        "causes": [
            "User logging into their workstation",
            "Service accounts authenticating",
            "Scheduled tasks running",
            "Remote desktop connections",
        ],
        "affects": ["User session", "Security audit log"],
        "recommendations": [
            "Review if logon type is expected (interactive, network, batch, etc.)",
            "Verify the account name is legitimate",
        ],
        "when_to_worry": "Unexpected logons from unknown accounts, logons at unusual times, or logon type 10 (RemoteInteractive) from unexpected sources.",
    },
    4625: {
        "title": "Failed Logon Attempt",
        "description": "An account failed to log on.",
        "category": "security",
        "severity": "medium",
        "is_normal": False,
        "causes": [
            "Incorrect password entered",
            "Account lockout",
            "Expired password",
            "Brute force attack attempt",
        ],
        "affects": ["Account security", "System access"],
        "recommendations": [
            "Check if multiple failures from same source (possible attack)",
            "Verify the account hasn't been compromised",
            "Review account lockout policies",
        ],
        "when_to_worry": "Multiple failed attempts in short time, failures from external IPs, or targeting administrative accounts.",
    },
    4648: {
        "title": "Explicit Credential Logon",
        "description": "A logon was attempted using explicit credentials.",
        "category": "security",
        "severity": "low",
        "is_normal": True,
        "causes": [
            "RunAs command used",
            "Scheduled task with stored credentials",
            "Network share access with different credentials",
        ],
        "affects": ["Credential usage audit"],
        "recommendations": [
            "Verify the target server and account are expected",
            "Review if this is authorized activity",
        ],
        "when_to_worry": "Credentials being used to access unexpected systems or by unexpected processes.",
    },
    4672: {
        "title": "Special Privileges Assigned",
        "description": "Special privileges were assigned to a new logon.",
        "category": "security",
        "severity": "low",
        "is_normal": True,
        "causes": [
            "Administrator or privileged user logon",
            "Service account with elevated privileges",
        ],
        "affects": ["Privilege tracking"],
        "recommendations": [
            "Verify the account should have these privileges",
            "Audit privileged account usage",
        ],
        "when_to_worry": "Unexpected accounts receiving admin privileges or privileges assigned at unusual times.",
    },
    
    # Account Management
    4720: {
        "title": "User Account Created",
        "description": "A user account was created.",
        "category": "security",
        "severity": "medium",
        "is_normal": False,
        "causes": [
            "IT administrator creating new user",
            "Automated provisioning system",
            "Malware creating backdoor account",
        ],
        "affects": ["User management", "Access control"],
        "recommendations": [
            "Verify the account creation was authorized",
            "Review who created the account",
            "Check account permissions",
        ],
        "when_to_worry": "Accounts created outside normal provisioning, created by unexpected users, or with suspicious names.",
    },
    4726: {
        "title": "User Account Deleted",
        "description": "A user account was deleted.",
        "category": "security",
        "severity": "medium",
        "is_normal": False,
        "causes": [
            "Employee offboarding",
            "Account cleanup",
            "Covering tracks after compromise",
        ],
        "affects": ["User management", "Audit trail"],
        "recommendations": [
            "Verify deletion was authorized",
            "Ensure proper offboarding procedures followed",
        ],
        "when_to_worry": "Unexpected account deletions or deletion of admin accounts.",
    },
    4732: {
        "title": "Member Added to Security Group",
        "description": "A member was added to a security-enabled local group.",
        "category": "security",
        "severity": "medium",
        "is_normal": False,
        "causes": [
            "User added to group for access",
            "Role change requiring new permissions",
            "Privilege escalation attempt",
        ],
        "affects": ["Group membership", "Access control"],
        "recommendations": [
            "Verify the membership change was authorized",
            "Review if group grants sensitive permissions",
        ],
        "when_to_worry": "Users added to Administrators, Domain Admins, or other high-privilege groups unexpectedly.",
    },
    
    # Policy Changes
    4719: {
        "title": "Audit Policy Changed",
        "description": "System audit policy was changed.",
        "category": "security",
        "severity": "high",
        "is_normal": False,
        "causes": [
            "Security configuration update",
            "GPO policy refresh",
            "Attacker disabling auditing",
        ],
        "affects": ["Security monitoring", "Compliance"],
        "recommendations": [
            "Verify the change was authorized",
            "Review what audit categories were modified",
            "Ensure critical auditing wasn't disabled",
        ],
        "when_to_worry": "Audit policy disabled or reduced unexpectedly, especially for logon or object access events.",
    },
    
    # Service Events
    7045: {
        "title": "New Service Installed",
        "description": "A service was installed in the system.",
        "category": "system",
        "severity": "medium",
        "is_normal": False,
        "causes": [
            "Software installation",
            "Windows updates",
            "Malware persistence mechanism",
        ],
        "affects": ["System services", "Startup behavior"],
        "recommendations": [
            "Verify the service is from legitimate software",
            "Check the service executable path",
            "Review service account permissions",
        ],
        "when_to_worry": "Services installed from temp directories, with random names, or running as SYSTEM from unusual locations.",
    },
    7036: {
        "title": "Service State Changed",
        "description": "A service entered a running or stopped state.",
        "category": "system",
        "severity": "info",
        "is_normal": True,
        "causes": [
            "Service started on boot",
            "Manual service start/stop",
            "Service crash and restart",
        ],
        "affects": ["System functionality"],
        "recommendations": [
            "Normal operation - no action needed for expected services",
        ],
        "when_to_worry": "Critical security services stopping unexpectedly.",
    },
    
    # Firewall Events
    5152: {
        "title": "Packet Dropped by Firewall",
        "description": "The Windows Filtering Platform blocked a packet.",
        "category": "network",
        "severity": "info",
        "is_normal": True,
        "causes": [
            "Firewall rules blocking traffic",
            "Unauthorized connection attempts",
            "Network scanning",
        ],
        "affects": ["Network connectivity"],
        "recommendations": [
            "Review if blocked traffic is expected or not",
            "Check for patterns indicating attack",
        ],
        "when_to_worry": "High volume of drops from same source or to sensitive ports.",
    },
    5156: {
        "title": "Network Connection Permitted",
        "description": "The Windows Filtering Platform permitted a connection.",
        "category": "network",
        "severity": "info",
        "is_normal": True,
        "causes": [
            "Normal application network activity",
            "System services communicating",
        ],
        "affects": ["Network audit log"],
        "recommendations": [
            "Normal operation - review if specific application behavior is concerning",
        ],
        "when_to_worry": "Connections to known malicious IPs or unexpected outbound connections.",
    },
    
    # Windows Defender
    1116: {
        "title": "Defender Detected Malware",
        "description": "Windows Defender detected malware or potentially unwanted software.",
        "category": "security",
        "severity": "high",
        "is_normal": False,
        "causes": [
            "Malware download or execution",
            "Infected file access",
            "False positive detection",
        ],
        "affects": ["System security", "File access"],
        "recommendations": [
            "Review the detected threat details",
            "Ensure threat was quarantined or removed",
            "Scan system for additional threats",
            "Investigate how the malware arrived",
        ],
        "when_to_worry": "Always investigate malware detections. Multiple detections may indicate active infection.",
    },
    1117: {
        "title": "Defender Remediation Action",
        "description": "Windows Defender took action to protect the system.",
        "category": "security",
        "severity": "medium",
        "is_normal": False,
        "causes": [
            "Automatic remediation of detected threat",
            "User-initiated scan cleanup",
        ],
        "affects": ["System security"],
        "recommendations": [
            "Verify the threat was successfully removed",
            "Check quarantine for false positives",
        ],
        "when_to_worry": "If action failed or threat keeps reappearing.",
    },
}


# =============================================================================
# Rules Engine Agent
# =============================================================================

class RulesEngineAgent:
    """
    Applies offline knowledge base rules for deterministic explanations.
    
    This agent does NOT use LLM - it provides pure rule-based analysis.
    KB rules are the AUTHORITATIVE source for event explanations.
    """
    
    def __init__(self, kb_path: Optional[Path] = None):
        self.knowledge_base: Dict[int, EventKBEntry] = {}
        self._load_builtin_kb()
        
        if kb_path:
            self._load_external_kb(kb_path)
        else:
            # Try to load from default location
            default_path = Path(__file__).parent.parent / "event_knowledge.json"
            if default_path.exists():
                self._load_external_kb(default_path)
        
        logger.info(f"RulesEngineAgent initialized with {len(self.knowledge_base)} event rules")
    
    def _load_builtin_kb(self):
        """Load the built-in event knowledge base."""
        for event_id, data in BUILTIN_EVENT_KB.items():
            self.knowledge_base[event_id] = EventKBEntry.from_dict(event_id, data)
    
    def _load_external_kb(self, path: Path):
        """Load external knowledge base from JSON file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for event_id_str, event_data in data.items():
                try:
                    event_id = int(event_id_str)
                    self.knowledge_base[event_id] = EventKBEntry.from_dict(event_id, event_data)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid event ID in KB: {event_id_str}")
            
            logger.info(f"Loaded {len(data)} entries from external KB: {path}")
        except Exception as e:
            logger.warning(f"Could not load external KB from {path}: {e}")
    
    def lookup_event(self, event_id: int) -> Optional[EventKBEntry]:
        """Look up an event in the knowledge base."""
        return self.knowledge_base.get(event_id)
    
    def analyze_event(self, event: EventEvidence) -> Dict[str, Any]:
        """
        Analyze an event using KB rules.
        
        Returns analysis with:
        - is_normal: Whether this event is typically normal
        - severity: The severity level
        - explanation: KB-based explanation
        - causes: Why this event happened
        - affects: What this event affects
        - recommendations: What to do
        - when_to_worry: When this becomes concerning
        """
        kb_entry = self.lookup_event(event.event_id)
        
        if not kb_entry:
            # No KB entry - return basic analysis
            return {
                "is_normal": event.level in ('Information', 'Verbose'),
                "severity": self._level_to_severity(event.level),
                "explanation": f"Event {event.event_id} from {event.provider}",
                "causes": ["No specific information available for this event ID"],
                "affects": ["System behavior may vary"],
                "recommendations": ["Review the event details for more context"],
                "when_to_worry": "If this event appears frequently or correlates with issues",
                "kb_found": False,
            }
        
        return {
            "is_normal": kb_entry.is_normal,
            "severity": kb_entry.severity,
            "explanation": f"{kb_entry.title}: {kb_entry.description}",
            "causes": kb_entry.causes,
            "affects": kb_entry.affects,
            "recommendations": kb_entry.recommendations,
            "when_to_worry": kb_entry.when_to_worry,
            "related_events": kb_entry.related_events,
            "category": kb_entry.category,
            "kb_found": True,
        }
    
    def _level_to_severity(self, level: str) -> str:
        """Convert event level to severity."""
        level_map = {
            'Critical': 'critical',
            'Error': 'high',
            'Warning': 'medium',
            'Information': 'info',
            'Verbose': 'info',
        }
        return level_map.get(level, 'info')
    
    def analyze_kb_rules(self, kb_evidence: KBRuleEvidence) -> List[Dict[str, Any]]:
        """Analyze multiple events from KB rule evidence."""
        results = []
        for event_id in kb_evidence.event_ids:
            kb_entry = self.lookup_event(event_id)
            if kb_entry:
                results.append({
                    "event_id": event_id,
                    "title": kb_entry.title,
                    "description": kb_entry.description,
                    "is_normal": kb_entry.is_normal,
                    "severity": kb_entry.severity,
                    "causes": kb_entry.causes,
                    "recommendations": kb_entry.recommendations,
                    "when_to_worry": kb_entry.when_to_worry,
                })
        return results
    
    def run(self, state: AssistantState) -> AssistantState:
        """
        Run the rules engine on the current state.
        
        Updates state with:
        - kb_analysis: Dict containing KB-based analysis for all events
        - has_kb_match: Whether KB rules were found
        """
        kb_analysis = {
            "events": [],
            "overall_is_normal": True,
            "max_severity": "info",
            "recommendations": [],
            "has_kb_match": False,
        }
        
        severity_order = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        
        # Process events from the Evidence object
        if state.evidence and state.evidence.events:
            for event in state.evidence.events:
                analysis = self.analyze_event(event)
                kb_analysis["events"].append({
                    "event_id": event.event_id,
                    **analysis,
                })
                
                if analysis.get("kb_found"):
                    kb_analysis["has_kb_match"] = True
                
                if not analysis["is_normal"]:
                    kb_analysis["overall_is_normal"] = False
                
                if severity_order.get(analysis["severity"], 0) > severity_order.get(kb_analysis["max_severity"], 0):
                    kb_analysis["max_severity"] = analysis["severity"]
                
                kb_analysis["recommendations"].extend(analysis.get("recommendations", []))
        
        # Deduplicate recommendations
        kb_analysis["recommendations"] = list(set(kb_analysis["recommendations"]))
        
        state.kb_analysis = kb_analysis
        
        logger.info(
            f"KB analysis complete: {len(kb_analysis['events'])} events analyzed, "
            f"KB match: {kb_analysis['has_kb_match']}, "
            f"max severity: {kb_analysis['max_severity']}"
        )
        
        return state


# =============================================================================
# Factory Function
# =============================================================================

def create_rules_engine(kb_path: Optional[Path] = None) -> RulesEngineAgent:
    """Create a RulesEngineAgent instance."""
    return RulesEngineAgent(kb_path)
