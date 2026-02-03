"""
EventExplainerV4 - Deterministic-first explanation with optional AI enhancement.

Pipeline:
1. INSTANT: Deterministic lookup via EventRulesEngine (UI thread safe)
2. OPTIONAL: AI enhancement only if user clicks "Explain Event" 
3. AI does NOT invent - only rewrites and extracts entities

Output Schema (strict):
{
    "plain_summary": "...",
    "what_happened": "...",
    "why_it_happened": ["..."],
    "what_it_affects": ["..."],
    "recommended_actions": ["..."],
    "when_to_worry": ["..."],
    "technical_details": {
        "provider": "...",
        "event_id": "...",
        "level": "...",
        "raw_message": "...",
        "extracted_entities": {...}
    }
}
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal

from app.ai.event_rules_engine import DeterministicExplanation, get_event_rules_engine
from app.ai.debug import get_ai_debugger

logger = logging.getLogger(__name__)


# ============================================================================
# Strict Output Schema
# ============================================================================

@dataclass
class StructuredExplanation:
    """
    Strict schema for event explanation output.
    
    This is what the UI receives - both from deterministic and AI paths.
    """
    
    # User-facing sections
    plain_summary: str = ""
    what_happened: str = ""
    why_it_happened: list[str] = field(default_factory=list)
    what_it_affects: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    when_to_worry: list[str] = field(default_factory=list)
    
    # Technical details (collapsible in UI)
    technical_details: dict[str, Any] = field(default_factory=dict)
    
    # UI metadata
    title: str = ""
    severity: str = "Minor"  # Safe, Minor, Warning, Critical
    source: str = "deterministic"  # deterministic, ai, cached
    is_loading: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON/QML."""
        return {
            "plain_summary": self.plain_summary,
            "what_happened": self.what_happened,
            "why_it_happened": self.why_it_happened,
            "what_it_affects": self.what_it_affects,
            "recommended_actions": self.recommended_actions,
            "when_to_worry": self.when_to_worry,
            "technical_details": self.technical_details,
            "title": self.title,
            "severity": self.severity,
            "source": self.source,
            "is_loading": self.is_loading,
        }
    
    @classmethod
    def from_deterministic(cls, det: DeterministicExplanation) -> "StructuredExplanation":
        """Create from deterministic lookup result with rich, technical yet friendly explanations."""
        
        # Build a comprehensive what_happened explanation
        what_happened = cls._build_what_happened(det)
        
        # Build plain summary from title + context
        plain_summary = det.title
        if det.impact:
            plain_summary = f"{det.title}. {det.impact}"
        
        # Build when_to_worry based on severity (calm, reassuring tone with technical context)
        when_to_worry = cls._build_when_to_worry(det)
        
        # Build what_it_affects with technical details
        what_it_affects = cls._build_what_it_affects(det)
        
        # Enhance causes with technical context
        why_it_happened = cls._build_why_it_happened(det)
        
        # Enhance actions with specific guidance
        recommended_actions = cls._build_recommended_actions(det)
        
        return cls(
            plain_summary=plain_summary,
            what_happened=what_happened,
            why_it_happened=why_it_happened,
            what_it_affects=what_it_affects,
            recommended_actions=recommended_actions,
            when_to_worry=when_to_worry,
            technical_details={
                "provider": det.provider,
                "event_id": str(det.event_id),
                "level": det.level,
                "raw_message": det.raw_message[:500] if det.raw_message else "",
                "extracted_entities": det.extracted_entities,
                "matched_in_kb": det.matched,
                "template_used": det.template_used,
            },
            title=det.title,
            severity=det.severity,
            source="deterministic",
        )
    
    @classmethod
    def _build_what_happened(cls, det: DeterministicExplanation) -> str:
        """Build a rich 'what happened' explanation combining impact with technical context."""
        parts = []
        
        # Start with the impact
        if det.impact:
            parts.append(det.impact)
        else:
            parts.append(det.title)
        
        # Add technical context based on provider/source
        provider_context = {
            "Service Control Manager": "This event comes from Windows Service Control Manager, which manages background services that keep your system running.",
            "Microsoft-Windows-Security-Auditing": "This is a security audit event — Windows tracks security-related activities to help detect unauthorized access.",
            "Microsoft-Windows-Kernel-Power": "This event is from the Windows power management system, which handles sleep, wake, and shutdown operations.",
            "Microsoft-Windows-WindowsUpdateClient": "This event is from Windows Update, which keeps your system secure with the latest patches.",
            "Application": "This event was logged by an application running on your system.",
            "System": "This is a core Windows system event that tracks fundamental operating system activities.",
            "DCOM": "DCOM (Distributed COM) handles communication between software components. These events are usually internal Windows housekeeping.",
            "Microsoft-Windows-Kernel-General": "This event comes from the Windows kernel — the core of the operating system.",
        }
        
        # Find matching provider context
        for key, context in provider_context.items():
            if key.lower() in det.provider.lower():
                parts.append(context)
                break
        
        # Add entity-specific context
        entities = det.extracted_entities
        if entities.get("service_name"):
            parts.append(f"The affected service is '{entities['service_name']}'.")
        if entities.get("application"):
            parts.append(f"The application involved is {entities['application']}.")
        if entities.get("username"):
            parts.append(f"This action was performed by or affects the user '{entities['username']}'.")
        if entities.get("error_code"):
            parts.append(f"Windows reported error code {entities['error_code']} — this code can help identify the specific problem if troubleshooting is needed.")
        
        return " ".join(parts)
    
    @classmethod
    def _build_when_to_worry(cls, det: DeterministicExplanation) -> list[str]:
        """Build severity-appropriate worry guidance with technical context."""
        base_worry = []
        
        if det.severity == "Critical":
            base_worry = [
                "This event indicates something significant happened that deserves attention",
                "If this is a one-time occurrence, it may be a temporary glitch that resolved itself",
                "Multiple critical events from the same source may indicate a persistent problem",
                "Consider checking Windows Reliability Monitor (type 'reliability' in Start menu) for patterns"
            ]
        elif det.severity == "Warning":
            base_worry = [
                "A warning means Windows noticed something suboptimal, but your system continues to function",
                "Pay attention if you see the same warning repeatedly — that suggests a pattern worth investigating",
                "Check if any software or features stopped working around the time of this event"
            ]
        elif det.severity == "Minor":
            base_worry = [
                "This is routine system activity — your computer logs thousands of these events daily",
                "Only investigate if you're troubleshooting a specific problem and this event seems related"
            ]
        else:  # Safe
            base_worry = [
                "This is completely normal system behavior — no action or concern needed",
                "Windows logs these events for record-keeping and troubleshooting purposes"
            ]
        
        # Add matched/unmatched context
        if not det.matched:
            base_worry.append("Note: This specific Event ID isn't in our knowledge base, but the explanation is based on the event level and source pattern")
        
        return base_worry
    
    @classmethod
    def _build_what_it_affects(cls, det: DeterministicExplanation) -> list[str]:
        """Build list of affected components with technical details."""
        affects = []
        
        if det.impact:
            affects.append(det.impact)
        
        entities = det.extracted_entities
        
        if entities.get("service_name"):
            service = entities["service_name"]
            affects.append(f"The '{service}' Windows service — this is a background program that may provide features to other applications")
        
        if entities.get("application"):
            app = entities["application"]
            affects.append(f"The application '{app}' and any work you were doing in it")
        
        if entities.get("file_paths"):
            for path in entities["file_paths"][:2]:
                affects.append(f"File or folder: {path}")
        
        if entities.get("username"):
            affects.append(f"User account: {entities['username']}")
        
        if not affects:
            affects.append("The specific impact depends on what you were doing at the time of this event")
        
        return affects
    
    @classmethod
    def _build_why_it_happened(cls, det: DeterministicExplanation) -> list[str]:
        """Build enhanced cause list with technical context."""
        if det.causes:
            enhanced_causes = list(det.causes)  # Start with existing causes
        else:
            enhanced_causes = []
        
        # Add level-specific technical context
        level_lower = det.level.lower()
        if "error" in level_lower and not any("error" in c.lower() for c in enhanced_causes):
            enhanced_causes.append("The system encountered a condition it couldn't handle normally")
        elif "warning" in level_lower and not any("warning" in c.lower() for c in enhanced_causes):
            enhanced_causes.append("Windows detected a condition that may need attention but isn't critical")
        
        # Add entity-specific causes
        entities = det.extracted_entities
        if entities.get("error_code"):
            code = entities["error_code"]
            enhanced_causes.append(f"Technical: Error code {code} was returned by the affected component")
        
        if not enhanced_causes:
            enhanced_causes = ["The specific cause depends on the context of when this event occurred"]
        
        return enhanced_causes
    
    @classmethod
    def _build_recommended_actions(cls, det: DeterministicExplanation) -> list[str]:
        """Build enhanced action list with specific guidance."""
        if det.actions:
            actions = list(det.actions)
        else:
            actions = []
        
        entities = det.extracted_entities
        
        # Add entity-specific actions
        if entities.get("service_name") and not any("service" in a.lower() for a in actions):
            service = entities["service_name"]
            actions.append(f"To check this service: Press Win+R, type 'services.msc', and search for '{service}'")
        
        if entities.get("application") and not any("application" in a.lower() or "reinstall" in a.lower() for a in actions):
            app = entities["application"]
            actions.append(f"If {app} is misbehaving, try restarting it or checking for updates")
        
        if entities.get("error_code") and not any("error" in a.lower() for a in actions):
            actions.append(f"For detailed troubleshooting, search online for this Event ID + error code combination")
        
        # Add severity-specific general guidance
        if det.severity == "Critical" and not any("reliability" in a.lower() for a in actions):
            actions.append("Check Windows Reliability Monitor: Press Win key, type 'reliability', and look for patterns")
        
        if not actions:
            actions = ["No specific action needed — this is logged for informational purposes"]
        
        return actions


# ============================================================================
# AI Enhancement Prompts
# ============================================================================

AI_SYSTEM_PROMPT = """You are "Sentinel Smart Security Assistant", an embedded AI for Windows Event analysis.

Your job is to explain Windows events in human language, like a security analyst would.

CORE IDENTITY:
• Product: Sentinel – Endpoint Security Suite
• Mode: Local-first, Offline-capable, Privacy-focused
• Audience: Non-technical users AND power users

EVENT EXPLANATION CONTRACT:
When explaining ANY Windows event, provide:

1. Plain Summary - One sentence a normal person understands
2. What Happened - What Windows did, why it logged this event
3. Is This Dangerous? - Yes/No/Depends with clear reasoning
4. Why You're Seeing It NOW - Startup, update, login, background task, etc.
5. What You Should Do - Clear actions, or "No action needed"

EVENT ANALYSIS RULES:
• DO NOT just list events or say "SUCCESS"
• ALWAYS explain what triggered it and whether repetition matters
• Correlate patterns: "Event 4799 repeating = normal audit noise"
• Use the deterministic explanation as source of truth - do NOT invent
• Extract entities (service names, file paths) and make actions specific

OUTPUT JSON SCHEMA:
{
    "plain_summary": "1-2 sentence summary - confident and direct",
    "what_happened": "What Windows detected, what triggered it, what component caused it",
    "why_it_happened": ["specific cause 1", "specific cause 2"],
    "what_it_affects": ["what this impacts with context"],
    "recommended_actions": ["specific action with WHERE to click - only if needed"],
    "when_to_worry": ["when this IS concerning", "reassure if normal"]
}

TONE: Calm, confident, clear. Zero fluff. Sound like a senior security engineer explaining things to a colleague.

SEVERITY LABELS:
- Safe: Normal system behavior, no concern
- Minor: Informational, usually ignore
- Warning: Worth monitoring if it repeats
- Critical: Needs attention, explain calmly without panic"""


def build_ai_prompt(det: DeterministicExplanation) -> str:
    """Build the AI enhancement prompt from deterministic result."""
    return f"""Rewrite this Windows Event explanation into clear, simple English that a non-technical user can understand.

DETERMINISTIC DATA (your source of truth):
- Title: {det.title}
- Severity: {det.severity}
- Impact: {det.impact}
- Causes: {json.dumps(det.causes)}
- Actions: {json.dumps(det.actions)}

RAW EVENT MESSAGE (extract entities from this):
Provider: {det.provider}
Event ID: {det.event_id}
Level: {det.level}
Message: {det.raw_message[:1000]}

ALREADY EXTRACTED ENTITIES:
{json.dumps(det.extracted_entities, indent=2)}

INSTRUCTIONS:
1. Rewrite the explanation to be clearer and more friendly
2. Make actions reference specific entities (service names, file paths, etc.)
3. Use a calm, reassuring tone - never panic the user
4. If this is normal behavior, say so clearly
5. Output ONLY the JSON object, no other text."""


# ============================================================================
# EventExplainerV4 Class
# ============================================================================

class EventExplainerV4(QObject):
    """
    Event explainer with deterministic-first approach.
    
    Signals:
        explanationReady(cache_key, result_dict): Deterministic result ready
        aiEnhancementReady(cache_key, result_dict): AI enhancement complete
        aiEnhancementFailed(cache_key, error): AI enhancement failed
    """
    
    explanationReady = Signal(str, dict)
    aiEnhancementReady = Signal(str, dict)
    aiEnhancementFailed = Signal(str, str)
    
    def __init__(self, llm_engine=None, parent=None):
        super().__init__(parent)
        
        self._llm = llm_engine
        self._rules_engine = get_event_rules_engine()
        self._debugger = get_ai_debugger()
        
        # Background processing for AI
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="EventAI_V4")
        self._pending: set[str] = set()
        self._lock = threading.Lock()
        
        # Cache: cache_key -> StructuredExplanation
        self._cache: dict[str, StructuredExplanation] = {}
        self._max_cache = 500
        
        logger.info("EventExplainerV4 initialized (deterministic-first)")
    
    def explain_event_instant(
        self,
        event_dict_or_provider: str | dict[str, Any],
        event_id: int | None = None,
        level: str = "Information",
        raw_message: str = "",
    ) -> dict[str, Any]:
        """
        Get INSTANT deterministic explanation.
        
        This is safe to call from UI thread - no blocking, no network.
        
        Args:
            event_dict_or_provider: Either a dict with event data, or provider name
            event_id: Event ID (if first arg is provider name)
            level: Event level
            raw_message: Raw event message
        
        Returns:
            StructuredExplanation as dict
        """
        # Support both dict and individual params
        if isinstance(event_dict_or_provider, dict):
            event_dict = event_dict_or_provider
            provider = event_dict.get("provider", event_dict.get("source", "Unknown"))
            event_id = event_dict.get("event_id", 0)
            level = event_dict.get("level", "Information")
            raw_message = event_dict.get("message", "")
        else:
            provider = event_dict_or_provider
            if event_id is None:
                event_id = 0
        
        # Generate cache key
        cache_key = self._make_cache_key(provider, event_id, raw_message)
        
        # Check cache first
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            result = cached.to_dict()
            result["source"] = "cached"
            return result
        
        # Deterministic lookup (instant)
        det = self._rules_engine.lookup(
            provider=provider,
            event_id=event_id,
            level=level,
            raw_message=raw_message,
        )
        
        # Convert to structured explanation
        result = StructuredExplanation.from_deterministic(det)
        
        # Cache it
        self._update_cache(cache_key, result)
        
        logger.debug(f"Instant explanation: {provider}:{event_id} (matched={det.matched})")
        
        return result.to_dict()
    
    def request_ai_enhancement(
        self,
        event_dict_or_provider: str | dict[str, Any],
        event_id: int | None = None,
        level: str = "Information",
        raw_message: str = "",
        on_ready: Callable[[StructuredExplanation], None] | None = None,
        on_failed: Callable[[str], None] | None = None,
        callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> str:
        """
        Request AI enhancement (async, background thread).
        
        This is called when user clicks "Explain Event" button.
        
        Args:
            event_dict_or_provider: Either a dict with event data, or provider name
            event_id: Event ID (if first arg is provider name)
            level: Event level
            raw_message: Raw event message
            on_ready: Callback when AI enhancement ready (receives StructuredExplanation)
            on_failed: Callback when AI enhancement fails (receives error string)
            callback: Legacy callback for result dict
        
        Returns:
            Cache key for tracking
        """
        # Support both dict and individual params
        if isinstance(event_dict_or_provider, dict):
            event_dict = event_dict_or_provider
            provider = event_dict.get("provider", event_dict.get("source", "Unknown"))
            event_id = event_dict.get("event_id", 0)
            level = event_dict.get("level", "Information")
            raw_message = event_dict.get("message", "")
        else:
            provider = event_dict_or_provider
            if event_id is None:
                event_id = 0
        
        cache_key = self._make_cache_key(provider, event_id, raw_message)
        
        # Check if AI result already cached
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if cached.source == "ai":
                logger.debug(f"AI result already cached: {cache_key}")
                if on_ready:
                    on_ready(cached)
                elif callback:
                    callback(cached.to_dict())
                return cache_key
        
        # Check if already pending
        with self._lock:
            if cache_key in self._pending:
                logger.debug(f"AI already pending: {cache_key}")
                return cache_key
            self._pending.add(cache_key)
        
        # Submit AI task
        def ai_task():
            try:
                result = self._run_ai_enhancement(provider, event_id, level, raw_message)
                
                # Update cache with AI result
                self._update_cache(cache_key, result)
                
                # Emit signal
                result_dict = result.to_dict()
                self.aiEnhancementReady.emit(cache_key, result_dict)
                
                # Call the new-style callback first
                if on_ready:
                    on_ready(result)
                elif callback:
                    callback(result_dict)
                    
            except Exception as e:
                logger.error(f"AI enhancement failed: {e}")
                self.aiEnhancementFailed.emit(cache_key, str(e))
                if on_failed:
                    on_failed(str(e))
            finally:
                with self._lock:
                    self._pending.discard(cache_key)
        
        self._executor.submit(ai_task)
        logger.info(f"AI enhancement requested: {cache_key}")
        
        return cache_key
    
    def _run_ai_enhancement(
        self,
        provider: str,
        event_id: int,
        level: str,
        raw_message: str,
    ) -> StructuredExplanation:
        """Run AI enhancement (called in background thread)."""
        
        # First get deterministic result as base
        det = self._rules_engine.lookup(
            provider=provider,
            event_id=event_id,
            level=level,
            raw_message=raw_message,
        )
        
        # If no LLM, return deterministic
        if not self._llm:
            result = StructuredExplanation.from_deterministic(det)
            result.source = "deterministic"
            return result
        
        # Build AI prompt
        system_prompt = AI_SYSTEM_PROMPT
        user_prompt = build_ai_prompt(det)
        
        # Debug logging
        record = self._debugger.start_call(
            call_type="event_explain",
            model_name=getattr(self._llm, "model_name", "unknown"),
            backend=getattr(self._llm, "backend_info", "unknown"),
        )
        record.system_prompt = system_prompt
        record.user_prompt = user_prompt
        
        try:
            # Run inference
            self._debugger.record_inference_start(record)
            raw_response = self._llm.generate_single_turn(
                f"{system_prompt}\n\n{user_prompt}",
                max_tokens=600,
            )
            self._debugger.record_inference_end(record)
            record.raw_response = raw_response
            
            # Parse AI response
            parsed = self._parse_ai_response(raw_response)
            
            if parsed:
                record.parsed_response = parsed
                record.validation_passed = True
                self._debugger.end_call(record)
                
                # Merge AI response with deterministic data
                result = StructuredExplanation(
                    plain_summary=parsed.get("plain_summary", det.title),
                    what_happened=parsed.get("what_happened", det.impact),
                    why_it_happened=parsed.get("why_it_happened", det.causes),
                    what_it_affects=parsed.get("what_it_affects", [det.impact] if det.impact else []),
                    recommended_actions=parsed.get("recommended_actions", det.actions),
                    when_to_worry=parsed.get("when_to_worry", []),
                    technical_details={
                        "provider": provider,
                        "event_id": str(event_id),
                        "level": level,
                        "raw_message": raw_message[:500],
                        "extracted_entities": det.extracted_entities,
                        "matched_in_kb": det.matched,
                    },
                    title=det.title,
                    severity=det.severity,
                    source="ai",
                )
                return result
            
            # AI parsing failed, use deterministic
            record.validation_passed = False
            record.validation_errors = ["Failed to parse AI JSON response"]
            self._debugger.end_call(record)
            
        except Exception as e:
            record.validation_passed = False
            record.validation_errors = [str(e)]
            self._debugger.end_call(record)
            logger.error(f"AI generation error: {e}")
        
        # Fallback to deterministic
        result = StructuredExplanation.from_deterministic(det)
        result.source = "deterministic"
        return result
    
    def _parse_ai_response(self, raw_response: str) -> dict[str, Any] | None:
        """Parse JSON from AI response."""
        text = raw_response.strip()
        
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try extracting from code blocks
        code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try finding JSON object
        json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _make_cache_key(self, provider: str, event_id: int, raw_message: str) -> str:
        """Generate cache key."""
        msg_hash = hashlib.md5(raw_message.encode()).hexdigest()[:12]
        return f"{provider}:{event_id}:{msg_hash}"
    
    def _update_cache(self, key: str, result: StructuredExplanation) -> None:
        """Update cache with LRU eviction."""
        if len(self._cache) >= self._max_cache:
            # Remove oldest entry
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = result
    
    def is_pending(self, cache_key: str) -> bool:
        """Check if an AI enhancement is pending."""
        with self._lock:
            return cache_key in self._pending
    
    def shutdown(self) -> None:
        """Clean up resources."""
        self._executor.shutdown(wait=False)
        logger.info("EventExplainerV4 shutdown")


# ============================================================================
# Module accessor
# ============================================================================

_explainer: EventExplainerV4 | None = None


def get_event_explainer_v4(llm_engine=None) -> EventExplainerV4:
    """Get or create the singleton EventExplainerV4 instance."""
    global _explainer
    if _explainer is None:
        _explainer = EventExplainerV4(llm_engine=llm_engine)
    elif llm_engine is not None and _explainer._llm is None:
        _explainer._llm = llm_engine
    return _explainer
