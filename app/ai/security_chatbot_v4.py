"""
Security Chatbot v4 - Groq-powered with conversation memory.

Features:
- Security-focused responses only
- Conversation memory (last N turns)
- Context-aware answers using system state
- Request cancellation
- Thread-safe background execution
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

logger = logging.getLogger(__name__)


# =============================================================================
# CONVERSATION MEMORY
# =============================================================================


@dataclass
class ConversationTurn:
    """A single conversation turn (user + assistant)."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class ConversationMemory:
    """
    Manages conversation history with configurable memory size.

    Features:
    - Fixed-size sliding window
    - Token budget awareness
    - Context extraction for prompts
    """

    MAX_TURNS = 10  # Keep last 10 turns (5 exchanges)
    MAX_TOKENS_ESTIMATE = 4000  # Rough limit for context

    def __init__(self, max_turns: int = MAX_TURNS):
        self.max_turns = max_turns
        self._history: deque[ConversationTurn] = deque(maxlen=max_turns)
        self._lock = threading.Lock()

    def add_user_message(self, content: str, metadata: dict[str, Any] | None = None):
        """Add a user message to history."""
        with self._lock:
            self._history.append(
                ConversationTurn(
                    role="user",
                    content=content,
                    metadata=metadata or {},
                )
            )

    def add_assistant_message(
        self, content: str, metadata: dict[str, Any] | None = None
    ):
        """Add an assistant response to history."""
        with self._lock:
            self._history.append(
                ConversationTurn(
                    role="assistant",
                    content=content,
                    metadata=metadata or {},
                )
            )

    def get_messages_for_prompt(self) -> list[dict[str, str]]:
        """
        Get conversation history formatted for LLM prompt.

        Returns list of {"role": "...", "content": "..."} dicts.
        """
        with self._lock:
            total_chars = 0
            char_limit = self.MAX_TOKENS_ESTIMATE * 4  # Rough chars per token

            # Process from newest to oldest, then reverse
            turns_to_include = []
            for turn in reversed(self._history):
                if total_chars + len(turn.content) > char_limit:
                    break
                turns_to_include.append(
                    {
                        "role": turn.role,
                        "content": turn.content,
                    }
                )
                total_chars += len(turn.content)

            return list(reversed(turns_to_include))

    def get_recent_context(self, n: int = 3) -> str:
        """Get recent conversation as summary text."""
        with self._lock:
            recent = list(self._history)[-n:]
            lines = []
            for turn in recent:
                prefix = "User" if turn.role == "user" else "Assistant"
                content = turn.content[:200]
                if len(turn.content) > 200:
                    content += "..."
                lines.append(f"{prefix}: {content}")
            return "\n".join(lines)

    def clear(self):
        """Clear all conversation history."""
        with self._lock:
            self._history.clear()

    def __len__(self) -> int:
        return len(self._history)


# =============================================================================
# CHAT RESPONSE
# =============================================================================


@dataclass
class ChatResponse:
    """Structured chat response."""

    answer: str
    is_security_related: bool = True
    suggested_actions: list[str] = field(default_factory=list)
    sources_used: list[str] = field(default_factory=list)
    latency_ms: int = 0
    provider: str = "groq"
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "is_security_related": self.is_security_related,
            "suggested_actions": self.suggested_actions,
            "sources_used": self.sources_used,
            "latency_ms": self.latency_ms,
            "provider": self.provider,
            "error": self.error,
        }


# =============================================================================
# CHAT WORKER
# =============================================================================


class ChatWorker(QRunnable):
    """Background worker for chat requests."""

    class Signals(QObject):
        finished = Signal(str, str)  # request_id, response_json
        error = Signal(str, str)  # request_id, error_message
        streaming = Signal(str, str)  # request_id, partial_text

    def __init__(
        self,
        request_id: str,
        question: str,
        conversation_history: list[dict[str, str]],
        system_context: dict[str, Any],
    ):
        super().__init__()
        self.signals = self.Signals()
        self.request_id = request_id
        self.question = question
        self.conversation_history = conversation_history
        self.system_context = system_context
        self._cancelled = False
        self.setAutoDelete(True)

    def cancel(self):
        """Request cancellation."""
        self._cancelled = True

    def run(self):
        """Execute the chat request."""
        if self._cancelled:
            return

        try:
            response = asyncio.run(self._get_response())

            if self._cancelled:
                return

            response_json = json.dumps(response.to_dict())
            self.signals.finished.emit(self.request_id, response_json)

        except Exception as e:
            logger.exception(f"Chat error: {e}")
            self.signals.error.emit(self.request_id, str(e))

    async def _get_response(self) -> ChatResponse:
        """Get chat response from Groq."""
        from .providers.groq import get_groq_provider, is_groq_available

        start_time = time.time()

        # Try Groq
        if is_groq_available():
            groq = get_groq_provider()

            response = await groq.chat(
                user_message=self.question,
                conversation_history=self.conversation_history,
                system_context=self.system_context,
                request_id=self.request_id,
            )

            if response._is_valid:
                latency = int((time.time() - start_time) * 1000)

                return ChatResponse(
                    answer=response.answer,
                    is_security_related=True,
                    suggested_actions=response.what_to_do_now,
                    sources_used=["groq"],
                    latency_ms=latency,
                    provider="groq",
                )

        # Fallback response
        return ChatResponse(
            answer="I'm currently unable to process your request. Please check your network connection and API key configuration.",
            is_security_related=True,
            provider="fallback",
            error="No AI provider available",
        )


# =============================================================================
# SECURITY CHATBOT V4
# =============================================================================

# Security topic keywords for filtering
SECURITY_KEYWORDS = [
    # General security
    "security",
    "secure",
    "threat",
    "malware",
    "virus",
    "trojan",
    "worm",
    "ransomware",
    "spyware",
    "adware",
    "phishing",
    "exploit",
    "vulnerability",
    "attack",
    "breach",
    "intrusion",
    "compromise",
    "infection",
    # Windows security
    "event",
    "log",
    "audit",
    "windows defender",
    "firewall",
    "antivirus",
    "credential",
    "authentication",
    "authorization",
    "permission",
    "privilege",
    "elevation",
    "uac",
    "admin",
    "administrator",
    "service",
    "process",
    # Network security
    "network",
    "port",
    "ip",
    "dns",
    "connection",
    "traffic",
    "packet",
    "scan",
    "nmap",
    "firewall",
    "router",
    "vpn",
    "proxy",
    # File security
    "file",
    "hash",
    "checksum",
    "signature",
    "certificate",
    "executable",
    "dll",
    "script",
    "powershell",
    "cmd",
    "suspicious",
    "quarantine",
    # Investigation
    "investigate",
    "analyze",
    "explain",
    "what",
    "why",
    "how",
    "when",
    "mean",
    "normal",
    "safe",
    "dangerous",
    "risk",
    "critical",
    "warning",
    # System
    "system",
    "cpu",
    "memory",
    "disk",
    "registry",
    "startup",
    "boot",
    "driver",
    "update",
    "patch",
    "vulnerability",
    "cve",
    # URLs and files
    "url",
    "link",
    "website",
    "domain",
    "sandbox",
    "scan",
    "check",
]


class SecurityChatbotV4(QObject):
    """
    Security-focused chatbot with Groq AI and conversation memory.

    Features:
    - Only answers security-related questions
    - Maintains conversation context
    - Integrates with system state (events, scans, etc.)
    - Background processing for UI responsiveness
    """

    # Signals
    chatResponseReady = Signal(str, str)  # request_id, response_json
    chatResponseFailed = Signal(str, str)  # request_id, error_message

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

        self._memory = ConversationMemory()
        self._thread_pool = QThreadPool.globalInstance()
        self._active_workers: dict[str, ChatWorker] = {}
        self._request_counter = 0
        self._lock = threading.Lock()

        # System context (updated by backend)
        self._system_context: dict[str, Any] = {}

        # Current resolution session context
        self._current_event_context: dict[str, Any] | None = None

    def set_system_context(self, context: dict[str, Any]):
        """
        Update system context for chat responses.

        Context can include:
        - recent_events: List of recent security events
        - scan_results: Latest scan results
        - system_info: CPU, memory, etc.
        """
        self._system_context = context

    def start_resolution_session(
        self,
        event_id: int | None = None,
        event_source: str | None = None,
        event_summary: str | None = None,
    ) -> str:
        """
        Start a new resolution session for tracking AI actions.

        Called when user clicks "Ask Chatbot to Help Resolve" on an event.

        Args:
            event_id: Event ID being resolved
            event_source: Source of the event
            event_summary: Brief summary of the event

        Returns:
            Session ID
        """
        try:
            from .action_record import get_action_log

            action_log = get_action_log()
            session = action_log.start_session(
                event_id=event_id,
                event_source=event_source,
                event_summary=event_summary,
            )
            self._current_event_context = {
                "event_id": event_id,
                "event_source": event_source,
                "event_summary": event_summary,
            }
            logger.info(f"Started resolution session: {session.session_id}")
            return session.session_id
        except Exception as e:
            logger.warning(f"Failed to start resolution session: {e}")
            return ""

    def end_resolution_session(self, summary: str = "") -> dict[str, Any] | None:
        """
        End the current resolution session.

        Returns:
            Session data dict or None
        """
        try:
            from .action_record import get_action_log

            action_log = get_action_log()
            session = action_log.end_session(summary)
            self._current_event_context = None
            if session:
                return session.to_dict()
            return None
        except Exception as e:
            logger.warning(f"Failed to end resolution session: {e}")
            return None

    def is_security_related(self, question: str) -> bool:
        """
        Check if question is security-related.

        Returns True if question contains security keywords.
        """
        question_lower = question.lower()

        for keyword in SECURITY_KEYWORDS:
            if keyword in question_lower:
                return True

        return False

    def ask(self, question: str, force: bool = False) -> str:
        """
        Ask a security question.

        Args:
            question: User's question
            force: If True, skip security relevance check

        Returns:
            request_id for tracking/cancellation
        """
        with self._lock:
            self._request_counter += 1
            request_id = f"chat_{self._request_counter}"

        # Check if security-related
        if not force and not self.is_security_related(question):
            # Return immediate non-security response
            response = ChatResponse(
                answer="I'm a security-focused assistant. I can help you with:\n\n"
                "• **Event Analysis**: Explain Windows security events\n"
                "• **Threat Investigation**: Analyze suspicious files and URLs\n"
                "• **System Security**: Check for vulnerabilities\n"
                "• **Security Guidance**: Best practices and recommendations\n\n"
                "Please ask me something related to security!",
                is_security_related=False,
                provider="local",
            )
            # Emit immediately
            self.chatResponseReady.emit(request_id, json.dumps(response.to_dict()))
            return request_id

        # Add to memory
        self._memory.add_user_message(question)

        # Get conversation history
        history = self._memory.get_messages_for_prompt()

        # Create worker
        worker = ChatWorker(
            request_id=request_id,
            question=question,
            conversation_history=history[:-1],  # Exclude current question
            system_context=self._system_context,
        )

        # Connect signals
        worker.signals.finished.connect(self._on_worker_finished)
        worker.signals.error.connect(self._on_worker_error)

        # Track and start
        self._active_workers[request_id] = worker
        self._thread_pool.start(worker)

        logger.debug(f"Started chat worker: {request_id}")
        return request_id

    def cancel_request(self, request_id: str) -> bool:
        """Cancel a pending chat request."""
        worker = self._active_workers.pop(request_id, None)
        if worker:
            worker.cancel()
            logger.debug(f"Cancelled chat request: {request_id}")
            return True
        return False

    def cancel_all(self):
        """Cancel all pending requests."""
        for request_id, worker in list(self._active_workers.items()):
            worker.cancel()
        self._active_workers.clear()

    def clear_memory(self):
        """Clear conversation history."""
        self._memory.clear()

    def get_conversation_summary(self) -> str:
        """Get a summary of recent conversation."""
        return self._memory.get_recent_context()

    def _on_worker_finished(self, request_id: str, response_json: str):
        """Handle worker completion."""
        self._active_workers.pop(request_id, None)

        # Add assistant response to memory
        try:
            response = json.loads(response_json)
            answer = response.get("answer", "")
            self._memory.add_assistant_message(answer)

            # Log action for resolution report
            try:
                from .action_record import ActionOutcome, ActionType, get_action_log

                action_log = get_action_log()
                action_log.log_action(
                    action_type=ActionType.ANALYZE,
                    description="Responded to user question",
                    input_data={
                        "question_preview": answer[:100]
                        if len(answer) > 100
                        else answer
                    },
                    output_data={
                        "suggested_actions": response.get("suggested_actions", []),
                        "latency_ms": response.get("latency_ms", 0),
                    },
                    outcome=ActionOutcome.SUCCESS,
                    duration_ms=response.get("latency_ms", 0),
                )
            except Exception as e:
                logger.debug(f"Failed to log action: {e}")

        except Exception as e:
            logger.warning(f"Failed to add response to memory: {e}")

        self.chatResponseReady.emit(request_id, response_json)

    def _on_worker_error(self, request_id: str, error_message: str):
        """Handle worker error."""
        self._active_workers.pop(request_id, None)

        # Log failed action
        try:
            from .action_record import ActionOutcome, ActionType, get_action_log

            action_log = get_action_log()
            action_log.log_action(
                action_type=ActionType.ANALYZE,
                description="Chat response failed",
                outcome=ActionOutcome.FAILED,
                error=error_message,
            )
        except Exception as e:
            logger.debug(f"Failed to log action: {e}")

        self.chatResponseFailed.emit(request_id, error_message)


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_chatbot_v4: SecurityChatbotV4 | None = None
_chatbot_lock = threading.Lock()


def get_security_chatbot_v4() -> SecurityChatbotV4:
    """Get singleton chatbot instance."""
    global _chatbot_v4
    with _chatbot_lock:
        if _chatbot_v4 is None:
            _chatbot_v4 = SecurityChatbotV4()
        return _chatbot_v4
