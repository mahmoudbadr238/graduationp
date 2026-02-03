"""
EventExplainerV3 - Strict structured JSON input/output with self-check validation.

Key improvements over V2:
1. Strict JSON input schema with all event context
2. Strict JSON output schema with required fields and min lengths
3. Self-check loop: validates output, retries once, then falls back to deterministic
4. Integrated debug logging for all AI calls
5. Grounded explanations that reference event_id and provider in output
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal

from app.ai.debug import AICallRecord, get_ai_debugger
from app.ai.event_summary_builder import EventSummary, get_summary_builder

logger = logging.getLogger(__name__)

# ============================================================================
# Strict Output Schema Definition
# ============================================================================

OUTPUT_SCHEMA = {
    "title": {"type": "string", "min_length": 10, "required": True},
    "plain_english": {"type": "string", "min_length": 200, "required": True},  # 6-10 sentences
    "what_it_means": {"type": "string", "min_length": 50, "required": True},
    "most_likely_causes": {"type": "list", "min_items": 2, "max_items": 6, "required": True},
    "what_to_do_next": {"type": "list", "min_items": 3, "max_items": 8, "required": True},
    "should_worry": {"type": "string", "enum": ["no", "maybe", "yes"], "required": True},
    "confidence": {"type": "string", "enum": ["low", "medium", "high"], "required": True},
    "references": {"type": "list", "min_items": 0, "required": False},
}


# ============================================================================
# Structured Prompts
# ============================================================================

SYSTEM_PROMPT = """You are a Windows Security Expert AI that explains Windows Event Log entries to users.

CRITICAL RULES:
1. ALWAYS output valid JSON matching the exact schema below
2. Reference the specific Event ID and Provider in your explanation
3. Use plain language a non-technical user can understand
4. Be specific - don't give generic advice, reference the actual event data
5. The 'plain_english' field MUST be 6-10 complete sentences explaining what happened
6. Each 'what_to_do_next' item MUST include WHERE to click or WHAT command to run

OUTPUT JSON SCHEMA (follow exactly):
{
    "title": "Short descriptive title (10+ chars)",
    "plain_english": "6-10 sentence explanation of what happened, why it matters, and what it means for the user",
    "what_it_means": "Technical impact summary in plain terms",
    "most_likely_causes": ["cause 1", "cause 2", "cause 3"],
    "what_to_do_next": [
        "Step 1: Specific action with WHERE (e.g., 'Open Settings > Update & Security')",
        "Step 2: Next action",
        "Step 3: ..."
    ],
    "should_worry": "no|maybe|yes",
    "confidence": "low|medium|high",
    "references": ["Optional reference 1"]
}"""


def build_user_prompt(event_context: dict[str, Any]) -> str:
    """Build the structured user prompt from event context."""
    return f"""Explain this Windows Event Log entry. Output ONLY valid JSON.

EVENT DATA:
{json.dumps(event_context, indent=2, ensure_ascii=False)}

Remember:
- Reference Event ID {event_context.get('event_id')} and Provider "{event_context.get('provider')}" in your explanation
- 'plain_english' must be 6-10 complete sentences  
- Each action in 'what_to_do_next' must say WHERE to click or WHAT command to run
- Output ONLY the JSON object, no other text"""


# ============================================================================
# Result Dataclass
# ============================================================================

@dataclass
class ExplainerResultV3:
    """Structured result from EventExplainerV3."""
    
    # Core fields (strict schema)
    title: str = ""
    plain_english: str = ""
    what_it_means: str = ""
    most_likely_causes: list[str] = field(default_factory=list)
    what_to_do_next: list[str] = field(default_factory=list)
    should_worry: str = "no"  # "no", "maybe", "yes"
    confidence: str = "medium"  # "low", "medium", "high"
    references: list[str] = field(default_factory=list)
    
    # Metadata
    source: str = "deterministic"  # "deterministic", "ai", "ai_validated", "fallback"
    event_id: int = 0
    provider: str = ""
    validation_passed: bool = True
    validation_errors: list[str] = field(default_factory=list)
    inference_time_ms: float = 0.0
    
    # Legacy compatibility fields
    @property
    def severity(self) -> str:
        """Map should_worry to severity for compatibility."""
        return {
            "no": "Safe",
            "maybe": "Warning", 
            "yes": "Critical"
        }.get(self.should_worry, "Minor")
    
    @property
    def short_title(self) -> str:
        return self.title
    
    @property
    def what_happened(self) -> str:
        return self.plain_english
    
    @property
    def why_it_happens(self) -> str:
        return "\n".join(f"• {c}" for c in self.most_likely_causes)
    
    @property
    def what_to_do(self) -> str:
        return "\n".join(f"{i+1}. {a}" for i, a in enumerate(self.what_to_do_next))
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            # V3 fields
            "title": self.title,
            "plain_english": self.plain_english,
            "what_it_means": self.what_it_means,
            "most_likely_causes": self.most_likely_causes,
            "what_to_do_next": self.what_to_do_next,
            "should_worry": self.should_worry,
            "confidence": self.confidence,
            "references": self.references,
            
            # Metadata
            "source": self.source,
            "event_id": self.event_id,
            "provider": self.provider,
            "validation_passed": self.validation_passed,
            "inference_time_ms": self.inference_time_ms,
            
            # Legacy compatibility (for backend_bridge)
            "severity": self.severity,
            "severity_label": self.severity,
            "short_title": self.title,
            "what_happened": self.plain_english,
            "why_it_happens": self.why_it_happens,
            "what_to_do": self.what_to_do,
            "explanation": self.plain_english,
            "recommendation": self.what_to_do,
            "tech_notes": f"Event ID: {self.event_id} | Provider: {self.provider}",
        }
    
    @classmethod
    def from_ai_response(
        cls,
        response: dict[str, Any],
        event_id: int,
        provider: str,
    ) -> "ExplainerResultV3":
        """Create from validated AI response."""
        return cls(
            title=response.get("title", ""),
            plain_english=response.get("plain_english", ""),
            what_it_means=response.get("what_it_means", ""),
            most_likely_causes=response.get("most_likely_causes", []),
            what_to_do_next=response.get("what_to_do_next", []),
            should_worry=response.get("should_worry", "no"),
            confidence=response.get("confidence", "medium"),
            references=response.get("references", []),
            source="ai_validated",
            event_id=event_id,
            provider=provider,
            validation_passed=True,
        )
    
    @classmethod
    def from_summary(cls, summary: EventSummary, event_id: int, provider: str) -> "ExplainerResultV3":
        """Create from deterministic EventSummary."""
        # Build plain_english from summary fields
        plain_english_parts = [summary.what_happened]
        if summary.impact:
            plain_english_parts.append(summary.impact)
        if summary.likely_causes:
            plain_english_parts.append(
                f"This typically happens due to: {', '.join(summary.likely_causes[:3])}."
            )
        if summary.recommended_actions:
            plain_english_parts.append(
                f"You can address this by following the recommended steps below."
            )
        
        return cls(
            title=summary.title,
            plain_english=" ".join(plain_english_parts),
            what_it_means=summary.impact or summary.what_happened,
            most_likely_causes=summary.likely_causes[:6] if summary.likely_causes else ["Unknown cause"],
            what_to_do_next=summary.recommended_actions[:8] if summary.recommended_actions else ["No action needed"],
            should_worry="no" if summary.severity in ("Safe", "Minor") else "maybe" if summary.severity == "Warning" else "yes",
            confidence="high" if summary.source_matched else "medium",
            references=[],
            source="deterministic",
            event_id=event_id,
            provider=provider,
            validation_passed=True,
        )


# ============================================================================
# Validation Functions
# ============================================================================

def validate_ai_output(
    response: dict[str, Any],
    event_id: int,
    provider: str,
) -> tuple[bool, list[str]]:
    """
    Validate AI output against strict schema.
    
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    # Check required fields exist
    for field_name, rules in OUTPUT_SCHEMA.items():
        if rules.get("required", False) and field_name not in response:
            errors.append(f"Missing required field: {field_name}")
            continue
        
        value = response.get(field_name)
        if value is None and rules.get("required", False):
            errors.append(f"Field '{field_name}' is null")
            continue
        
        if value is None:
            continue
        
        # Type check
        if rules["type"] == "string":
            if not isinstance(value, str):
                errors.append(f"Field '{field_name}' must be string")
                continue
            
            min_len = rules.get("min_length", 0)
            if len(value) < min_len:
                errors.append(f"Field '{field_name}' too short ({len(value)} < {min_len})")
            
            if "enum" in rules and value not in rules["enum"]:
                errors.append(f"Field '{field_name}' must be one of {rules['enum']}")
        
        elif rules["type"] == "list":
            if not isinstance(value, list):
                errors.append(f"Field '{field_name}' must be list")
                continue
            
            min_items = rules.get("min_items", 0)
            max_items = rules.get("max_items", 100)
            
            if len(value) < min_items:
                errors.append(f"Field '{field_name}' needs at least {min_items} items")
            if len(value) > max_items:
                errors.append(f"Field '{field_name}' has too many items (max {max_items})")
    
    # Check that event_id and provider are mentioned in plain_english
    plain_english = response.get("plain_english", "")
    if str(event_id) not in plain_english and f"Event {event_id}" not in plain_english:
        errors.append(f"plain_english should reference Event ID {event_id}")
    
    # Check that actions have specific guidance
    actions = response.get("what_to_do_next", [])
    for i, action in enumerate(actions):
        if not any(word in action.lower() for word in ["click", "open", "run", "go to", "press", "type", "settings", "command"]):
            # Just a warning, not fatal
            logger.debug(f"Action {i+1} may lack specific guidance: {action[:50]}...")
    
    return len(errors) == 0, errors


def extract_json_from_response(raw_response: str) -> dict[str, Any] | None:
    """
    Extract JSON object from LLM response.
    
    Handles:
    - Pure JSON
    - JSON wrapped in markdown code blocks
    - JSON with trailing text
    """
    text = raw_response.strip()
    
    # Try direct parse first
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


# ============================================================================
# EventExplainerV3 Class
# ============================================================================

class EventExplainerV3(QObject):
    """
    Event explainer with strict structured I/O and self-check validation.
    
    Flow:
    1. Always return deterministic result immediately
    2. If AI requested, run in background with strict validation
    3. Self-check: validate output, retry once on failure
    4. Fallback to deterministic if validation fails twice
    
    Signals:
        explanationReady(event_key, result_dict): Emitted when AI enhancement completes
        explanationFailed(event_key, error): Emitted on AI failure (still has deterministic)
    """
    
    explanationReady = Signal(str, dict)
    explanationFailed = Signal(str, str)
    
    def __init__(self, llm_engine=None, parent=None):
        """
        Initialize the V3 explainer.
        
        Args:
            llm_engine: LLM engine with generate_single_turn() method
            parent: Qt parent object
        """
        super().__init__(parent)
        
        self._llm = llm_engine
        self._summary_builder = get_summary_builder()
        self._debugger = get_ai_debugger()
        
        # Background processing
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="EventAI_V3")
        self._pending: set[str] = set()
        self._lock = threading.Lock()
        
        # Cache
        self._cache: dict[str, ExplainerResultV3] = {}
        self._max_cache = 200
        
        logger.info("EventExplainerV3 initialized")
    
    def _make_cache_key(self, event: dict[str, Any]) -> str:
        """Generate cache key from event data."""
        provider = event.get("provider", event.get("source", ""))
        event_id = event.get("event_id", event.get("id", 0))
        message = event.get("message", "")
        
        # Hash the message for cache key
        msg_hash = hashlib.md5(message.encode()).hexdigest()[:12]
        return f"{provider}:{event_id}:{msg_hash}"
    
    def _build_event_context(self, event: dict[str, Any]) -> dict[str, Any]:
        """Build structured context for AI input."""
        return {
            "event_id": event.get("event_id", event.get("id", 0)),
            "provider": event.get("provider", event.get("source", "")),
            "channel": event.get("channel", event.get("log_name", "")),
            "level": event.get("level", "Information"),
            "time_created": event.get("time_created", event.get("timestamp", "")),
            "message": event.get("message", "")[:2000],  # Truncate long messages
            "task_category": event.get("task_category", ""),
            "computer": event.get("computer", ""),
            "user_id": event.get("user_id", ""),
        }
    
    def explain_event(
        self,
        event: dict[str, Any],
        use_ai: bool = False,
        callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """
        Explain a Windows event.
        
        Always returns immediately with deterministic result.
        If use_ai=True, starts background AI enhancement.
        
        Args:
            event: Event dict
            use_ai: Whether to request AI enhancement
            callback: Optional callback for AI result
        
        Returns:
            Immediate deterministic explanation dict
        """
        cache_key = self._make_cache_key(event)
        event_id = event.get("event_id", event.get("id", 0))
        provider = event.get("provider", event.get("source", ""))
        
        # Check cache first
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            logger.debug(f"Cache hit for {cache_key}")
            return cached.to_dict()
        
        # Generate deterministic result
        summary = self._summary_builder.build_summary(
            event_id=event_id,
            provider=provider,
            level=event.get("level", "Information"),
            message=event.get("message", ""),
            time_created=event.get("time_created"),
            task_category=event.get("task_category"),
        )
        
        result = ExplainerResultV3.from_summary(summary, event_id, provider)
        
        # Cache deterministic result
        self._update_cache(cache_key, result)
        
        # Start AI enhancement if requested
        if use_ai and self._llm:
            self._start_ai_enhancement(cache_key, event, callback)
        
        return result.to_dict()
    
    def _update_cache(self, key: str, result: ExplainerResultV3) -> None:
        """Update cache with LRU eviction."""
        if len(self._cache) >= self._max_cache:
            # Remove oldest entry
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = result
    
    def _start_ai_enhancement(
        self,
        cache_key: str,
        event: dict[str, Any],
        callback: Callable[[dict[str, Any]], None] | None,
    ) -> None:
        """Start background AI enhancement."""
        with self._lock:
            if cache_key in self._pending:
                logger.debug(f"AI already pending for {cache_key}")
                return
            self._pending.add(cache_key)
        
        def task():
            try:
                result = self._run_ai_with_validation(cache_key, event)
                
                # Update cache
                self._update_cache(cache_key, result)
                
                # Emit signal
                result_dict = result.to_dict()
                self.explanationReady.emit(cache_key, result_dict)
                
                # Call callback if provided
                if callback:
                    callback(result_dict)
                    
            except Exception as e:
                logger.error(f"AI enhancement failed: {e}")
                self.explanationFailed.emit(cache_key, str(e))
            finally:
                with self._lock:
                    self._pending.discard(cache_key)
        
        self._executor.submit(task)
    
    def _run_ai_with_validation(
        self,
        cache_key: str,
        event: dict[str, Any],
    ) -> ExplainerResultV3:
        """
        Run AI with self-check validation.
        
        Retries once on validation failure, then falls back to deterministic.
        """
        event_id = event.get("event_id", event.get("id", 0))
        provider = event.get("provider", event.get("source", ""))
        event_context = self._build_event_context(event)
        
        # Get model info
        model_name = getattr(self._llm, "model_name", "unknown")
        backend = getattr(self._llm, "backend_info", "unknown")
        
        max_attempts = 2
        last_errors = []
        
        for attempt in range(max_attempts):
            # Start debug record
            record = self._debugger.start_call(
                call_type="event_explain",
                model_name=model_name,
                backend=backend,
                temperature=0.4,
                max_tokens=600,
            )
            record.structured_context = event_context
            record.system_prompt = SYSTEM_PROMPT
            record.user_prompt = build_user_prompt(event_context)
            
            try:
                # Run inference
                self._debugger.record_inference_start(record)
                raw_response = self._llm.generate_single_turn(
                    f"{SYSTEM_PROMPT}\n\n{record.user_prompt}",
                    max_tokens=600,
                )
                self._debugger.record_inference_end(record)
                record.raw_response = raw_response
                
                # Parse JSON
                parsed = extract_json_from_response(raw_response)
                if parsed is None:
                    last_errors = ["Failed to parse JSON from response"]
                    record.validation_passed = False
                    record.validation_errors = last_errors
                    self._debugger.end_call(record)
                    continue
                
                record.parsed_response = parsed
                
                # Validate
                is_valid, errors = validate_ai_output(parsed, event_id, provider)
                record.validation_passed = is_valid
                record.validation_errors = errors
                
                if is_valid:
                    self._debugger.end_call(record)
                    result = ExplainerResultV3.from_ai_response(parsed, event_id, provider)
                    result.inference_time_ms = record.inference_time_ms
                    logger.info(f"AI explanation validated for {cache_key} (attempt {attempt+1})")
                    return result
                
                last_errors = errors
                logger.warning(f"AI validation failed (attempt {attempt+1}): {errors}")
                self._debugger.end_call(record)
                
            except Exception as e:
                last_errors = [str(e)]
                record.validation_passed = False
                record.validation_errors = last_errors
                self._debugger.end_call(record)
                logger.error(f"AI inference error (attempt {attempt+1}): {e}")
        
        # All attempts failed - return deterministic with fallback flag
        logger.warning(f"AI validation failed after {max_attempts} attempts, using deterministic")
        summary = self._summary_builder.build_summary(
            event_id=event_id,
            provider=provider,
            level=event.get("level", "Information"),
            message=event.get("message", ""),
        )
        result = ExplainerResultV3.from_summary(summary, event_id, provider)
        result.source = "fallback"
        result.validation_passed = False
        result.validation_errors = last_errors
        return result
    
    def shutdown(self) -> None:
        """Clean up resources."""
        self._executor.shutdown(wait=False)
        logger.info("EventExplainerV3 shutdown")


# ============================================================================
# Module-level accessor
# ============================================================================

_explainer: EventExplainerV3 | None = None


def get_event_explainer_v3(llm_engine=None) -> EventExplainerV3:
    """Get or create the singleton EventExplainerV3 instance."""
    global _explainer
    if _explainer is None:
        _explainer = EventExplainerV3(llm_engine=llm_engine)
    elif llm_engine is not None and _explainer._llm is None:
        _explainer._llm = llm_engine
    return _explainer
