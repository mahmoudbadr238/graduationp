"""
SOC-Grade Event Correlation and Scoring
========================================

This module provides:
- Event correlation rules (which events relate to each other)
- Threat scoring based on patterns
- Detection of attack patterns (brute force, lateral movement, etc.)
- Context-aware severity adjustments

Used by the AI providers to give SOC-analyst quality responses.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ThreatLevel(Enum):
    """Threat level classification."""
    SAFE = "safe"          # Normal operation
    LOW = "low"            # Minor concern, monitor
    MEDIUM = "medium"      # Investigate soon
    HIGH = "high"          # Investigate immediately
    CRITICAL = "critical"  # Active threat, immediate action


class AttackPattern(Enum):
    """Known attack patterns."""
    BRUTE_FORCE = "brute_force"
    CREDENTIAL_STUFFING = "credential_stuffing"
    LATERAL_MOVEMENT = "lateral_movement"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    PERSISTENCE = "persistence"
    DEFENSE_EVASION = "defense_evasion"
    DATA_EXFILTRATION = "data_exfiltration"
    MALWARE_EXECUTION = "malware_execution"


@dataclass
class CorrelationRule:
    """A rule for correlating related events."""
    name: str
    description: str
    primary_event_id: int
    related_event_ids: list[int]
    attack_pattern: Optional[AttackPattern] = None
    
    # Thresholds for threat escalation
    count_threshold: int = 5  # Number before escalation
    time_window_minutes: int = 15  # Time window for counting
    
    # Context keys to match (e.g., same account, same IP)
    match_fields: list[str] = field(default_factory=list)
    
    # Scoring adjustment when pattern detected
    threat_score_bonus: int = 20


@dataclass
class EventScore:
    """Scored assessment of an event."""
    event_id: int
    base_score: int  # 0-100, from event type alone
    context_score: int  # Adjustment based on context
    pattern_score: int  # Bonus if part of attack pattern
    
    @property
    def total_score(self) -> int:
        return min(100, max(0, self.base_score + self.context_score + self.pattern_score))
    
    @property
    def threat_level(self) -> ThreatLevel:
        if self.total_score >= 80:
            return ThreatLevel.CRITICAL
        elif self.total_score >= 60:
            return ThreatLevel.HIGH
        elif self.total_score >= 40:
            return ThreatLevel.MEDIUM
        elif self.total_score >= 20:
            return ThreatLevel.LOW
        return ThreatLevel.SAFE


# =============================================================================
# CORRELATION RULES
# =============================================================================

CORRELATION_RULES: dict[int, CorrelationRule] = {
    # Failed login → successful login (credential compromise)
    4625: CorrelationRule(
        name="Failed Login Correlation",
        description="Multiple failed logins followed by success may indicate compromised credentials",
        primary_event_id=4625,
        related_event_ids=[4624, 4768, 4776, 4771],
        attack_pattern=AttackPattern.BRUTE_FORCE,
        count_threshold=5,
        time_window_minutes=10,
        match_fields=["TargetUserName", "IpAddress"],
        threat_score_bonus=30,
    ),
    
    # New service installation → process creation (malware persistence)
    7045: CorrelationRule(
        name="Service Persistence Check",
        description="New service installation may indicate malware persistence mechanism",
        primary_event_id=7045,
        related_event_ids=[4697, 4688, 4689],
        attack_pattern=AttackPattern.PERSISTENCE,
        count_threshold=1,
        time_window_minutes=5,
        match_fields=["ServiceName", "ImagePath"],
        threat_score_bonus=25,
    ),
    
    # Special privileges → sensitive operations (privilege escalation)
    4672: CorrelationRule(
        name="Privilege Escalation Check",
        description="Special privileges assigned - check for unusual elevation patterns",
        primary_event_id=4672,
        related_event_ids=[4624, 4648, 4688],
        attack_pattern=AttackPattern.PRIVILEGE_ESCALATION,
        count_threshold=3,
        time_window_minutes=30,
        match_fields=["SubjectUserName", "LogonType"],
        threat_score_bonus=20,
    ),
    
    # Defender detections → actions taken
    1116: CorrelationRule(
        name="Defender Detection Correlation",
        description="Malware detection - verify remediation was successful",
        primary_event_id=1116,
        related_event_ids=[1117, 1118, 1119],
        attack_pattern=AttackPattern.MALWARE_EXECUTION,
        count_threshold=1,
        time_window_minutes=60,
        match_fields=["ThreatName", "Path"],
        threat_score_bonus=40,
    ),
    
    # Audit policy change → potential defense evasion
    4719: CorrelationRule(
        name="Audit Tampering Check",
        description="Audit policy changes may indicate attempt to hide activity",
        primary_event_id=4719,
        related_event_ids=[4670, 4912],
        attack_pattern=AttackPattern.DEFENSE_EVASION,
        count_threshold=1,
        time_window_minutes=60,
        match_fields=["SubjectUserName"],
        threat_score_bonus=35,
    ),
}


# =============================================================================
# BASE SCORES
# =============================================================================

EVENT_BASE_SCORES: dict[int, int] = {
    # Security events
    4624: 5,    # Successful login - very common
    4625: 25,   # Failed login - concerning if repeated
    4634: 5,    # Logoff - informational
    4648: 20,   # Explicit credentials - worth monitoring
    4672: 15,   # Special privileges - expected for admins
    4688: 5,    # Process created - informational
    4689: 5,    # Process ended - informational
    4697: 30,   # Service installed via security - more suspicious
    4719: 45,   # Audit policy change - significant
    4732: 25,   # Added to group - monitor
    4733: 20,   # Removed from group - monitor
    4768: 10,   # Kerberos TGT request - normal
    4769: 10,   # Kerberos service ticket - normal
    4771: 20,   # Kerberos preauth failed
    4776: 15,   # NTLM auth attempt
    
    # Service events
    7000: 25,   # Service failed to start
    7001: 20,   # Service dependency failure
    7009: 15,   # Service timeout
    7023: 20,   # Service terminated with error
    7031: 15,   # Service crash recovered
    7034: 25,   # Service crashed
    7036: 5,    # Service state change - informational
    7040: 10,   # Startup type changed
    7045: 30,   # New service installed
    
    # Power events
    41: 35,     # Unexpected shutdown
    42: 5,      # Sleep - informational
    
    # Defender events
    1116: 60,   # Malware detected
    1117: 40,   # Malware action taken
    1118: 30,   # Malware action failed
    1119: 20,   # Malware action completed
    
    # DCOM
    10016: 5,   # DCOM permission - usually noise
}


# =============================================================================
# CONTEXT ADJUSTMENTS
# =============================================================================

@dataclass 
class ContextFactor:
    """A factor that adjusts threat score based on context."""
    name: str
    description: str
    score_adjustment: int
    applies_to_events: list[int]  # Empty = all events
    
    def matches(self, event: dict, context: dict) -> bool:
        """Check if this factor applies to the given event/context."""
        raise NotImplementedError


class NetworkLoginFactor(ContextFactor):
    """Network logins (type 3) are more suspicious for failed attempts."""
    
    def __init__(self):
        super().__init__(
            name="Network Login",
            description="Failed network login - possible remote attack",
            score_adjustment=15,
            applies_to_events=[4625],
        )
    
    def matches(self, event: dict, context: dict) -> bool:
        logon_type = event.get("fields", {}).get("LogonType", "")
        return str(logon_type) == "3"


class AdminAccountFactor(ContextFactor):
    """Activities involving admin accounts are more significant."""
    
    def __init__(self):
        super().__init__(
            name="Admin Account",
            description="Activity involves administrator account",
            score_adjustment=10,
            applies_to_events=[],  # All events
        )
    
    def matches(self, event: dict, context: dict) -> bool:
        username = (
            event.get("fields", {}).get("TargetUserName", "") or
            event.get("fields", {}).get("SubjectUserName", "")
        ).lower()
        return "admin" in username or username == "administrator"


class AfterHoursFactor(ContextFactor):
    """Activity outside business hours is more suspicious."""
    
    def __init__(self):
        super().__init__(
            name="After Hours",
            description="Activity occurred outside normal business hours",
            score_adjustment=10,
            applies_to_events=[4624, 4625, 4648, 7045],
        )
    
    def matches(self, event: dict, context: dict) -> bool:
        # This would check the event timestamp
        # Simplified: assume context provides this
        return context.get("is_after_hours", False)


class ExternalIPFactor(ContextFactor):
    """Logins from external IPs are more suspicious."""
    
    def __init__(self):
        super().__init__(
            name="External IP",
            description="Login from external/public IP address",
            score_adjustment=20,
            applies_to_events=[4624, 4625],
        )
    
    def matches(self, event: dict, context: dict) -> bool:
        ip = event.get("fields", {}).get("IpAddress", "")
        if not ip or ip == "-" or ip == "127.0.0.1":
            return False
        # Check if private IP
        return not (
            ip.startswith("10.") or
            ip.startswith("192.168.") or
            ip.startswith("172.16.") or
            ip.startswith("172.17.") or
            ip.startswith("172.18.") or
            ip.startswith("172.19.") or
            ip.startswith("172.2") or
            ip.startswith("172.30.") or
            ip.startswith("172.31.")
        )


# All context factors
CONTEXT_FACTORS: list[ContextFactor] = [
    NetworkLoginFactor(),
    AdminAccountFactor(),
    AfterHoursFactor(),
    ExternalIPFactor(),
]


# =============================================================================
# SCORING ENGINE
# =============================================================================

class EventScoringEngine:
    """
    Scores events based on type, context, and patterns.
    
    Used to prioritize events and determine threat level.
    """
    
    def __init__(self):
        self._correlation_rules = CORRELATION_RULES
        self._base_scores = EVENT_BASE_SCORES
        self._context_factors = CONTEXT_FACTORS
    
    def score_event(
        self,
        event: dict[str, Any],
        related_events: Optional[list[dict]] = None,
        context: Optional[dict] = None,
    ) -> EventScore:
        """
        Score a single event.
        
        Args:
            event: The event to score
            related_events: Other recent events for correlation
            context: Additional context (user info, time, etc.)
        
        Returns:
            EventScore with breakdown and threat level
        """
        event_id = event.get("event_id", event.get("eventId", 0))
        context = context or {}
        
        # Base score from event type
        base_score = self._base_scores.get(event_id, 15)
        
        # Context adjustments
        context_score = 0
        for factor in self._context_factors:
            if not factor.applies_to_events or event_id in factor.applies_to_events:
                if factor.matches(event, context):
                    context_score += factor.score_adjustment
        
        # Pattern detection
        pattern_score = 0
        if related_events and event_id in self._correlation_rules:
            rule = self._correlation_rules[event_id]
            pattern_score = self._check_pattern(event, related_events, rule)
        
        return EventScore(
            event_id=event_id,
            base_score=base_score,
            context_score=context_score,
            pattern_score=pattern_score,
        )
    
    def _check_pattern(
        self,
        event: dict,
        related_events: list[dict],
        rule: CorrelationRule,
    ) -> int:
        """Check if event is part of an attack pattern."""
        # Count related events within time window
        # Simplified: just check count for now
        related_count = sum(
            1 for e in related_events
            if e.get("event_id", e.get("eventId")) in rule.related_event_ids
        )
        
        if related_count >= rule.count_threshold:
            return rule.threat_score_bonus
        
        return 0
    
    def get_correlation_info(self, event_id: int) -> Optional[CorrelationRule]:
        """Get correlation rule for an event."""
        return self._correlation_rules.get(event_id)
    
    def get_related_events_to_check(self, event_id: int) -> list[int]:
        """Get list of related event IDs to check for correlation."""
        rule = self._correlation_rules.get(event_id)
        if rule:
            return rule.related_event_ids
        return []


# =============================================================================
# SOC RESPONSE TEMPLATES
# =============================================================================

SOC_TEMPLATES: dict[int, dict[str, Any]] = {
    4625: {
        "normal_explanation": "A single failed login is usually just a typo. Nothing to worry about.",
        "suspicious_explanation": "Multiple failed logins from the same source may indicate a brute force attack.",
        "when_to_worry": [
            "More than 5 failed attempts in 10 minutes from same IP",
            "Failed logins for admin/administrator accounts",
            "Failed logins from external/public IP addresses",
            "Failed logins outside business hours",
            "Pattern: many failures followed by success (credential compromise)",
        ],
        "verification_steps": [
            "Check Event Viewer: Security log, filter for Event ID 4625",
            "Look at the IP address in the event details",
            "Check if the account is a real user or service account",
            "Look for Event 4624 (success) after multiple 4625 (failures)",
            "Run: net user [username] to check account status",
        ],
        "related_events": {
            4624: "Success after failures = possible credential compromise",
            4768: "Kerberos ticket request - indicates domain authentication",
            4776: "NTLM authentication - check for pass-the-hash",
        },
    },
    
    7045: {
        "normal_explanation": "Service installation during software updates is expected.",
        "suspicious_explanation": "Unexpected service installation may indicate malware persistence.",
        "when_to_worry": [
            "Service installed from unusual path (not Program Files)",
            "Service name is random characters or mimics system names",
            "Installation without corresponding software update",
            "Service runs as SYSTEM with unusual executable",
            "Service points to script (.bat, .ps1, .cmd) instead of .exe",
        ],
        "verification_steps": [
            "Check the ImagePath in event details - is it a known location?",
            "Run: sc query [servicename] to check service status",
            "Check if the executable is digitally signed",
            "Look up the executable hash on VirusTotal",
            "Check file creation date vs service installation date",
        ],
        "related_events": {
            4697: "Security audit of service installation",
            4688: "Process that installed the service",
            7036: "Service start after installation",
        },
    },
    
    4672: {
        "normal_explanation": "Admin logging in gets special privileges - this is expected.",
        "suspicious_explanation": "Unexpected privilege assignments may indicate escalation attack.",
        "when_to_worry": [
            "Non-admin account receiving special privileges",
            "Privileges assigned to newly created accounts",
            "Privileges assigned outside normal admin activity",
            "SeDebugPrivilege on non-developer accounts",
            "Pattern: new account → privileges → sensitive actions",
        ],
        "verification_steps": [
            "Check which account received privileges",
            "Verify the logon type (interactive vs network)",
            "Check what actions followed this event",
            "Run: whoami /priv on the affected account",
        ],
        "related_events": {
            4624: "The logon event that triggered privileges",
            4648: "Explicit credential use",
            4688: "Processes started with elevated privileges",
        },
    },
    
    1116: {
        "normal_explanation": "Defender detected and blocked a threat. The action taken shows if remediation worked.",
        "suspicious_explanation": "Detection indicates malware was present. Verify it was fully removed.",
        "when_to_worry": [
            "Action = 'No Action Taken' (remediation failed)",
            "Same threat detected repeatedly",
            "Threat in sensitive directory (System32, user profile)",
            "Threat name indicates ransomware or RAT",
            "Multiple different threats in short time (active infection)",
        ],
        "verification_steps": [
            "Open Windows Security → Virus & threat protection → Protection history",
            "Check if 'Threat removed' or 'Quarantined'",
            "Run a full system scan",
            "Check the file path where threat was found",
            "Look up the threat name on Microsoft Security Intelligence",
        ],
        "related_events": {
            1117: "Action taken by Defender",
            1118: "Action failed - needs manual remediation",
            1119: "Action completed successfully",
        },
    },
}


# Singleton
_scoring_engine: Optional[EventScoringEngine] = None

def get_scoring_engine() -> EventScoringEngine:
    """Get the singleton scoring engine."""
    global _scoring_engine
    if _scoring_engine is None:
        _scoring_engine = EventScoringEngine()
    return _scoring_engine
