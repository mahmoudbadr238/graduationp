"""
Event Explainer v5 - Groq-powered with offline fallback.

This module provides the event explanation pipeline:
1. Check persistent cache (SQLite)
2. Use offline rules engine (deterministic, instant)
3. If online available, enhance with Groq AI
4. Cache results for future use

Features:
- 2-level explanations (full and simplified)
- Persistent caching in SQLite
- Request cancellation
- Thread-safe for background use
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

logger = logging.getLogger(__name__)


@dataclass
class ExplanationResult:
    """Complete explanation result with both detail levels and briefs."""

    # Core fields
    title: str = ""
    what_happened: str = ""
    why_it_happened: list[str] = field(default_factory=list)
    what_it_affects: list[str] = field(default_factory=list)
    is_normal: bool = True
    risk_level: str = "low"
    what_to_do: list[str] = field(default_factory=list)
    when_to_worry: list[str] = field(default_factory=list)
    technical_brief: str = ""
    simplified_text: str = ""

    # NEW: Brief fields for Task 1
    brief_user: str = ""  # 1-2 lines for normal users
    brief_technical: str = ""  # 2-4 lines for advanced users
    confidence: float = 1.0  # 0.0-1.0 confidence score
    evidence: list[str] = field(default_factory=list)  # Evidence strings

    # Metadata
    source: str = "local_kb"  # "local_kb", "groq", "claude", "openai"
    cached: bool = False
    latency_ms: int = 0
    detail_level: str = "normal"  # "normal" or "simplified"

    # Event data
    event_id: int = 0
    provider: str = ""
    level: str = "Information"
    log_name: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "title": self.title,
            "what_happened": self.what_happened,
            "why_it_happened": self.why_it_happened,
            "what_it_affects": self.what_it_affects,
            "is_normal": self.is_normal,
            "risk_level": self.risk_level,
            "what_to_do": self.what_to_do,
            "when_to_worry": self.when_to_worry,
            "technical_brief": self.technical_brief,
            "simplified_text": self.simplified_text,
            # NEW brief fields
            "brief_user": self.brief_user,
            "brief_technical": self.brief_technical,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "detail_level": self.detail_level,
            # Metadata
            "source": self.source,
            "cached": self.cached,
            "latency_ms": self.latency_ms,
            # Event context
            "event_id": self.event_id,
            "provider": self.provider,
            "level": self.level,
            "log_name": self.log_name,
            # Legacy compatibility
            "severity": self._risk_to_severity(self.risk_level),
            "severity_label": self._risk_to_severity(self.risk_level),
            "recommended_actions": self.what_to_do,
            "plain_summary": self.brief_user or self.what_happened,
            "answer": self.what_happened,
        }

    def _risk_to_severity(self, risk: str) -> str:
        """Convert risk level to severity label."""
        mapping = {
            "none": "Safe",
            "low": "Minor",
            "medium": "Warning",
            "high": "Critical",
            "critical": "Critical",
        }
        return mapping.get(risk.lower(), "Minor")


class ExplanationWorker(QRunnable):
    """Background worker for AI-enhanced explanations."""

    class Signals(QObject):
        finished = Signal(str, str)  # request_id, result_json
        error = Signal(str, str)  # request_id, error_message

    def __init__(
        self,
        request_id: str,
        event_dict: dict[str, Any],
        kb_explanation: dict[str, Any] | None,
        detail_level: str,
        db_repo: Any,
    ):
        super().__init__()
        self.signals = self.Signals()
        self.request_id = request_id
        self.event_dict = event_dict
        self.kb_explanation = kb_explanation
        self.detail_level = detail_level
        self.db_repo = db_repo
        self._cancelled = False
        self.setAutoDelete(True)

    def cancel(self):
        """Request cancellation."""
        self._cancelled = True

    def run(self):
        """Execute the AI explanation request."""
        if self._cancelled:
            return

        try:
            result = asyncio.run(self._get_ai_explanation())

            if self._cancelled:
                return

            result_json = json.dumps(result.to_dict())
            self.signals.finished.emit(self.request_id, result_json)

        except Exception as e:
            logger.exception(f"AI explanation error: {e}")
            self.signals.error.emit(self.request_id, str(e))

    async def _get_ai_explanation(self) -> ExplanationResult:
        """Get AI-enhanced explanation with brief fields."""
        from .providers.groq import get_groq_provider, is_groq_available

        event_id = self.event_dict.get("event_id", 0)
        provider = self.event_dict.get("provider", "Unknown")
        level = self.event_dict.get("level", "Information")
        message = self.event_dict.get("message", "")
        log_name = self.event_dict.get("log_name", "Application")

        # Create message hash for caching
        message_hash = hashlib.md5(message.encode()[:500]).hexdigest()[:12]

        # Check persistent cache first
        if self.db_repo and hasattr(self.db_repo, "get_event_explanation"):
            cached = self.db_repo.get_event_explanation(
                provider, event_id, message_hash,
                detail_level=self.detail_level,
            )
            if cached:
                result = ExplanationResult(
                    title=cached.get("title", ""),
                    what_happened=cached.get("what_happened", ""),
                    why_it_happened=cached.get("why_it_happened", []),
                    what_it_affects=cached.get("what_it_affects", []),
                    is_normal=cached.get("is_normal", True),
                    risk_level=cached.get("risk_level", "low"),
                    what_to_do=cached.get("what_to_do", []),
                    when_to_worry=cached.get("when_to_worry", []),
                    technical_brief=cached.get("technical_brief", ""),
                    simplified_text=cached.get("simplified_text", ""),
                    # New brief fields
                    brief_user=cached.get("brief_user", ""),
                    brief_technical=cached.get("brief_technical", ""),
                    confidence=cached.get("confidence", 1.0),
                    evidence=cached.get("evidence", []),
                    detail_level=self.detail_level,
                    source=cached.get("ai_provider", "cached"),
                    cached=True,
                    event_id=event_id,
                    provider=provider,
                    level=level,
                    log_name=log_name,
                    message=message[:200],
                )
                return result

        # Try Groq AI
        if is_groq_available():
            groq = get_groq_provider()

            response = await groq.explain_event(
                self.event_dict,
                kb_explanation=self.kb_explanation,
                detail_level=self.detail_level,
                request_id=self.request_id,
            )

            if response._is_valid:
                td = response.technical_details
                result = ExplanationResult(
                    title=td.get("title", response.answer[:50]),
                    what_happened=td.get("full_what_happened", response.answer),
                    why_it_happened=response.why_it_happened,
                    what_it_affects=response.what_it_affects,
                    is_normal=td.get("is_normal", True),
                    risk_level=td.get("risk_level", "low"),
                    what_to_do=response.what_to_do_now,
                    when_to_worry=response.follow_up_suggestions,
                    technical_brief=td.get("technical_brief", ""),
                    # New brief fields from response
                    brief_user=td.get("brief_user", response.answer),
                    brief_technical=td.get("brief_technical", td.get("technical_brief", "")),
                    confidence=td.get("confidence", 0.9),
                    evidence=td.get("evidence", [f"Event {event_id}", f"Provider: {provider}"]),
                    detail_level=self.detail_level,
                    source="groq",
                    latency_ms=response.latency_ms,
                    event_id=event_id,
                    provider=provider,
                    level=level,
                    log_name=log_name,
                    message=message[:200],
                )

                # Save to persistent cache
                if self.db_repo and hasattr(self.db_repo, "save_event_explanation"):
                    self.db_repo.save_event_explanation(
                        provider, event_id, message_hash,
                        result.to_dict(),
                        detail_level=self.detail_level,
                        ai_provider="groq",
                    )

                return result

        # Fallback to KB-only result with generated briefs
        if self.kb_explanation:
            kb_title = self.kb_explanation.get("title", f"Event {event_id}")
            kb_severity = self.kb_explanation.get("severity", "Minor")

            # Generate briefs from KB
            brief_user = f"{kb_title}. "
            if kb_severity in ("Safe", "Minor"):
                brief_user += "This is a routine event and nothing to worry about."
            else:
                brief_user += "This may need attention - check the recommended actions."

            brief_technical = f"Event {event_id} from {provider}. {self.kb_explanation.get('impact', kb_title)}"

            return ExplanationResult(
                title=kb_title,
                what_happened=self.kb_explanation.get("impact", "Event recorded"),
                why_it_happened=self.kb_explanation.get("causes", []),
                what_it_affects=[],
                is_normal=kb_severity in ("Safe", "Minor"),
                risk_level=self._severity_to_risk(kb_severity),
                what_to_do=self.kb_explanation.get("actions", []),
                brief_user=brief_user,
                brief_technical=brief_technical,
                confidence=0.85 if self.kb_explanation.get("matched") else 0.5,
                evidence=[f"KB matched: {kb_title}"] if self.kb_explanation.get("matched") else [],
                detail_level=self.detail_level,
                source="local_kb",
                event_id=event_id,
                provider=provider,
                level=level,
            )

        return ExplanationResult(
            title=f"Event {event_id}",
            what_happened="Event recorded in Windows log",
            source="fallback",
            event_id=event_id,
            provider=provider,
            level=level,
        )

    def _severity_to_risk(self, severity: str) -> str:
        """Convert severity label to risk level."""
        mapping = {
            "Safe": "none",
            "Minor": "low",
            "Warning": "medium",
            "Critical": "high",
        }
        return mapping.get(severity, "low")


class EventExplainerV5(QObject):
    """
    Event explainer with Groq AI and persistent caching.
    
    Pipeline:
    1. explain_event_instant() - Offline KB lookup (UI thread safe)
    2. explain_event_async() - AI enhancement in background thread
    """

    # Signals for async results
    explanationReady = Signal(str, str)  # request_id, result_json
    explanationFailed = Signal(str, str)  # request_id, error_message

    def __init__(self, db_repo: Any = None, parent: QObject | None = None):
        super().__init__(parent)

        self._db_repo = db_repo
        self._rules_engine = None
        self._thread_pool = QThreadPool.globalInstance()
        self._active_workers: dict[str, ExplanationWorker] = {}
        self._request_counter = 0
        self._lock = threading.Lock()

        self._init_rules_engine()

    def _init_rules_engine(self):
        """Initialize the offline rules engine."""
        try:
            from .event_rules_engine import EventRulesEngine
            self._rules_engine = EventRulesEngine()
            logger.info("EventRulesEngine initialized for V5 explainer")
        except Exception as e:
            logger.warning(f"Failed to initialize rules engine: {e}")

    def explain_event_instant(self, event_dict: dict[str, Any]) -> ExplanationResult:
        """
        Get instant explanation using offline rules engine.
        
        This is safe to call on the UI thread - no blocking, no network.
        
        Args:
            event_dict: Event data with event_id, provider, level, message
        
        Returns:
            ExplanationResult with KB-based explanation
        """
        event_id = event_dict.get("event_id", 0)
        provider = event_dict.get("provider", event_dict.get("source", "Unknown"))
        level = event_dict.get("level", "Information")
        message = event_dict.get("message", "")

        # Use rules engine for instant lookup
        if self._rules_engine:
            kb_result = self._rules_engine.lookup(
                provider=provider,
                event_id=event_id,
                level=level,
                raw_message=message,
            )

            return ExplanationResult(
                title=kb_result.title,
                what_happened=kb_result.impact or f"Event {event_id} recorded",
                why_it_happened=kb_result.causes,
                what_it_affects=[],
                is_normal=kb_result.severity in ("Safe", "Minor"),
                risk_level=self._severity_to_risk(kb_result.severity),
                what_to_do=kb_result.actions,
                technical_brief=f"Provider: {provider}, Level: {level}",
                source="local_kb" if kb_result.matched else "template",
                event_id=event_id,
                provider=provider,
                level=level,
            )

        # Fallback if no rules engine
        return ExplanationResult(
            title=f"Event {event_id}",
            what_happened=message[:200] if message else "Event recorded",
            risk_level=self._level_to_risk(level),
            source="fallback",
            event_id=event_id,
            provider=provider,
            level=level,
        )

    def explain_event_async(
        self,
        event_dict: dict[str, Any],
        detail_level: str = "full",
    ) -> str:
        """
        Request AI-enhanced explanation in background.
        
        Emits explanationReady or explanationFailed when done.
        
        Args:
            event_dict: Event data
            detail_level: "full" or "simple"
        
        Returns:
            request_id for tracking/cancellation
        """
        with self._lock:
            self._request_counter += 1
            request_id = f"explain_{self._request_counter}"

        # Get instant KB result first
        kb_result = None
        if self._rules_engine:
            kb_result = self._rules_engine.lookup(
                provider=event_dict.get("provider", ""),
                event_id=event_dict.get("event_id", 0),
                level=event_dict.get("level", "Information"),
                raw_message=event_dict.get("message", ""),
            )
            kb_result = kb_result.to_dict()

        # Create worker
        worker = ExplanationWorker(
            request_id=request_id,
            event_dict=event_dict,
            kb_explanation=kb_result,
            detail_level=detail_level,
            db_repo=self._db_repo,
        )

        # Connect signals
        worker.signals.finished.connect(self._on_worker_finished)
        worker.signals.error.connect(self._on_worker_error)

        # Track and start
        self._active_workers[request_id] = worker
        self._thread_pool.start(worker)

        logger.debug(f"Started explanation worker: {request_id}")
        return request_id

    def cancel_request(self, request_id: str) -> bool:
        """
        Cancel a pending explanation request.
        
        Args:
            request_id: ID from explain_event_async
        
        Returns:
            True if request was found and cancelled
        """
        worker = self._active_workers.pop(request_id, None)
        if worker:
            worker.cancel()
            logger.debug(f"Cancelled explanation request: {request_id}")
            return True
        return False

    def cancel_all(self):
        """Cancel all pending requests."""
        for request_id, worker in list(self._active_workers.items()):
            worker.cancel()
        self._active_workers.clear()

    def _on_worker_finished(self, request_id: str, result_json: str):
        """Handle worker completion."""
        self._active_workers.pop(request_id, None)
        self.explanationReady.emit(request_id, result_json)

    def _on_worker_error(self, request_id: str, error_message: str):
        """Handle worker error."""
        self._active_workers.pop(request_id, None)
        self.explanationFailed.emit(request_id, error_message)

    def _severity_to_risk(self, severity: str) -> str:
        """Convert severity label to risk level."""
        mapping = {
            "Safe": "none",
            "Minor": "low",
            "Warning": "medium",
            "Critical": "high",
        }
        return mapping.get(severity, "low")

    def _level_to_risk(self, level: str) -> str:
        """Convert event level to risk level."""
        mapping = {
            "Information": "none",
            "Verbose": "none",
            "Warning": "medium",
            "Error": "high",
            "Critical": "high",
        }
        return mapping.get(level, "low")


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_explainer_v5: EventExplainerV5 | None = None
_explainer_lock = threading.Lock()


def get_event_explainer_v5(db_repo: Any = None) -> EventExplainerV5:
    """Get singleton event explainer instance."""
    global _explainer_v5
    with _explainer_lock:
        if _explainer_v5 is None:
            _explainer_v5 = EventExplainerV5(db_repo=db_repo)
        return _explainer_v5
