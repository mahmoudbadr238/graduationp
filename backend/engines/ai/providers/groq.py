"""
Groq Cloud Provider - High-performance free-tier AI.

Uses Groq's ultra-fast inference for:
- Event explanations (llama-3.3-70b-versatile)
- Chatbot responses (llama-3.1-8b-instant)

Features:
- Rate limit handling with exponential backoff
- Request cancellation support
- Prompt caching for repeated queries
- Circuit breaker for reliability

Environment variables:
- GROQ_API_KEY: Your Groq API key (required)
- AI_PROVIDER: Set to "groq" to use this provider
- AI_MODEL_CHAT: Chat model (default: llama-3.1-8b-instant)
- AI_MODEL_EVENT: Event explanation model (default: llama-3.3-70b-versatile)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import platform
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

from .base import AIProvider, AIResponse, ProviderConfig
from .privacy import redact_sensitive

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Default models optimized for each use case
DEFAULT_CHAT_MODEL = "llama-3.1-8b-instant"  # Fast, good for chat
DEFAULT_EVENT_MODEL = "llama-3.3-70b-versatile"  # Powerful, good for explanations

# Rate limits (Groq free tier: 30 requests/minute)
REQUESTS_PER_MINUTE = 30
MIN_REQUEST_INTERVAL = 2.0  # 2 seconds between requests (safe)

# Retry configuration. Keep GUI-triggered AI failures bounded so cloud issues do
# not make Sentinel feel hung.
MAX_RETRIES = 1
INITIAL_BACKOFF = 1.0
MAX_BACKOFF = 5.0


# =============================================================================
# SYSTEM PROMPTS  (dynamic, platform-aware)
# =============================================================================

_OS_NAME = platform.system()  # "Windows" or "Linux"


def _build_event_prompt(os_name: str | None = None, detail_level: str = "normal") -> str:
    """Build a platform-aware event explanation system prompt.

    Args:
        os_name: "Windows" or "Linux" (defaults to runtime detection).
        detail_level: "normal" or "simplified".

    Returns:
        The full system prompt string for the Groq API call.
    """
    os_name = os_name or _OS_NAME
    is_linux = os_name == "Linux"

    # ---------- terminology swaps ----------
    os_label = "Linux" if is_linux else "Windows"
    log_source = "syslog / journalctl" if is_linux else "Windows Event Log"
    component_label = "system daemon or service" if is_linux else "Windows component"
    example_event = (
        "Unit 'nginx.service' entered 'failed' state."
        if is_linux
        else "Service 'Windows Update' changed from running to stopped"
    )
    example_good = (
        "The nginx web server crashed and is no longer running."
        if is_linux
        else "The Windows Update service stopped running on this computer."
    )
    diag_commands = (
        "journalctl -u <unit>, systemctl status <unit>, dmesg"
        if is_linux
        else "Get-EventLog, Get-WinEvent, Get-MpComputerStatus"
    )

    # ---- simplified mode ----
    if detail_level == "simplified":
        return (
            f"You are explaining a {os_label} system event to someone who knows "
            "NOTHING about computers.\n\n"
            "RULES:\n"
            "1. Use EVERYDAY language - like explaining to a grandparent\n"
            "2. Use analogies (e.g., 'like a door being opened', 'like a car engine starting')\n"
            "3. NO technical terms AT ALL - no event IDs, no service names, no error codes\n"
            "4. Focus on: Is this okay? Should they worry? What should they do?\n\n"
            "You MUST return ONLY a raw JSON object (no markdown fences) with these EXACT keys:\n"
            "{\n"
            '    "short_title": "Super simple title (5 words max)",\n'
            '    "plain_summary": "2-3 sentences a child could understand. Use analogies. Reassure or warn.",\n'
            '    "what_happened": "Simple explanation using everyday analogies",\n'
            '    "why_it_happens": "Simple reason this occurs",\n'
            '    "what_you_can_do": "Simple action in everyday language",\n'
            '    "risk_level": "Low|Medium|High|Critical",\n'
            '    "is_normal": true or false,\n'
            '    "confidence": 0.0-1.0 float,\n'
            '    "evidence": ["list of evidence used"],\n'
            '    "brief_user": "Same as plain_summary",\n'
            '    "brief_technical": "Keep this technical for reference, 2-3 sentences.",\n'
            '    "title": "Same as short_title",\n'
            '    "why_it_happened": ["simple reason 1", "simple reason 2"],\n'
            '    "what_it_affects": [],\n'
            '    "what_to_do": ["simple action"],\n'
            '    "when_to_worry": [],\n'
            '    "technical_brief": "Technical reference (for IT)"\n'
            "}"
        )

    # ---- normal (full) mode ----
    return (
        f"You are a cybersecurity expert analyzing {os_label} system events.\n\n"
        f"The log comes from a {os_label} machine ({log_source}).\n\n"
        "CRITICAL RULES:\n"
        "1. Be SPECIFIC — reference the ACTUAL event ID, provider, and message details given\n"
        f"2. Explain WHAT happened in plain English (use the specific {component_label} names)\n"
        "3. Explain WHY it matters for security (specific to THIS event type)\n"
        "4. Tell if this is NORMAL or needs attention (based on the level and context)\n"
        f"5. Give EXACT steps to investigate or remediate (specific commands: {diag_commands})\n"
        "6. Include specific thresholds when relevant\n\n"
        "You will receive:\n"
        f"- Event ID (the {os_label} event identifier)\n"
        f"- Provider/Source (which {component_label} generated it)\n"
        "- Level (Information, Warning, Error, Critical)\n"
        f"- Log Name (which {os_label} log)\n"
        "- Timestamp (when the event occurred)\n"
        "- Message (the actual event text — VERY IMPORTANT, contains specifics)\n"
        "- Local analysis (from knowledge base — TRUST these facts, don't contradict)\n\n"
        "YOUR JOB:\n"
        "1. Read the Message carefully — it contains the SPECIFIC details\n"
        "2. Extract those specifics into your explanation\n"
        "3. Add context about what this means for the user's security\n"
        "4. Give actionable steps\n\n"
        f"EXAMPLE: If message says \"{example_event}\":\n"
        f'- DO say: "{example_good}"\n'
        "- DON'T say: \"A service state change was detected.\"\n\n"
        "You MUST return ONLY a raw JSON object (no markdown fences) with these EXACT keys:\n"
        "{\n"
        '    "short_title": "Brief descriptive title using specific names from the event",\n'
        '    "plain_summary": "1-2 sentences in super simple language for normal users. NO jargon.",\n'
        '    "what_happened": "Detailed explanation (2-4 sentences, use actual names/values from message)",\n'
        '    "why_it_happens": "Semicolon-separated reasons this occurs",\n'
        '    "what_you_can_do": "Semicolon-separated actionable steps with actual commands/paths",\n'
        '    "risk_level": "Low|Medium|High|Critical",\n'
        '    "is_normal": true or false,\n'
        '    "confidence": 0.0-1.0 float (1.0 if message is detailed; reduce if vague/missing),\n'
        '    "evidence": ["list of evidence strings"],\n'
        '    "brief_user": "Same as plain_summary",\n'
        '    "brief_technical": "2-4 sentences for IT professionals with event ID, error codes, service names.",\n'
        '    "title": "Same as short_title",\n'
        '    "why_it_happened": ["specific cause 1", "specific cause 2"],\n'
        '    "what_it_affects": ["specific impact 1", "specific impact 2"],\n'
        '    "what_to_do": ["specific step 1", "specific step 2"],\n'
        '    "when_to_worry": ["specific pattern that indicates a real problem"],\n'
        '    "technical_brief": "One-line technical summary with relevant codes/IDs"\n'
        "}\n\n"
        "IMPORTANT: If the event message is empty or vague, say so explicitly in "
        "plain_summary and set confidence lower (0.3-0.6)."
    )


def _build_chat_system_prompt(os_name: str | None = None) -> str:
    """Build a platform-aware chat system prompt."""
    os_name = os_name or _OS_NAME
    is_linux = os_name == "Linux"

    os_label = "Linux" if is_linux else "Windows"
    scope_items = (
        f"- {os_label} security and administration\n"
        "- Sentinel app features (event viewer, scans, firewall, defender)\n"
        "- Malware analysis and threat assessment\n"
        "- System hardening and security best practices"
    )
    if is_linux:
        tool_cmds = (
            "- journalctl, systemctl status (system logs)\n"
            "- ufw status, iptables -L (firewall)\n"
            "- clamav, rkhunter (malware scanners)\n"
            "- ss -tuln, netstat (network)"
        )
    else:
        tool_cmds = (
            "- Get-EventLog, Get-WinEvent (event logs)\n"
            "- Get-NetFirewallProfile (firewall)\n"
            "- Get-MpComputerStatus (defender)\n"
            "- Get-WindowsUpdateLog (updates)"
        )

    return (
        f"You are Sentinel, an expert {os_label} security assistant.\n\n"
        f"SCOPE: You ONLY answer questions about:\n{scope_items}\n\n"
        "If asked about ANYTHING else, politely redirect to security topics.\n\n"
        "STYLE:\n"
        "- Be direct and confident\n"
        "- Use bullet points for lists\n"
        "- Give specific commands/steps when relevant\n"
        "- Reference previous conversation context when applicable\n\n"
        "You have access to:\n"
        f"- {os_label} Event logs from the user's system\n"
        "- Security status (Defender/ClamAV, Firewall, Updates)\n"
        "- Scan results (file and URL analysis)\n"
        "- Previous conversation history\n\n"
        "CRITICAL BEHAVIORS:\n\n"
        "1. CONTEXT AWARENESS: Use conversation history to maintain context. If the user refers to\n"
        '   "it", "that event", "this issue", look at previous messages to understand what they mean.\n\n'
        '2. SIMPLIFICATION: If the user says "I don\'t understand", "explain simpler", "what does that mean",\n'
        "   or similar - DO NOT just repeat yourself. Instead:\n"
        "   - Use everyday analogies\n"
        "   - Avoid all technical jargon\n"
        "   - Break it into smaller, simpler concepts\n"
        "   - Give concrete real-world examples\n\n"
        "3. HELP RESOLVE: When helping resolve events, provide:\n"
        "   - Diagnosis steps (safe, read-only commands)\n"
        "   - Specific action plan\n"
        "   - Ask for confirmation before suggesting changes to system settings\n"
        "   - Verify the outcome after actions\n\n"
        f"4. TOOL ACCESS: You can suggest the user run diagnostic commands like:\n{tool_cmds}\n\n"
        "Response format (JSON only):\n"
        "{\n"
        '    "answer": "Your response (use markdown for formatting)",\n'
        '    "why_it_happened": ["relevant context points"],\n'
        '    "what_it_affects": ["security implications"],\n'
        '    "what_to_do_now": ["specific actionable steps with commands if applicable"],\n'
        '    "follow_up_suggestions": ["suggested follow-up questions user might ask"],\n'
        '    "confidence": "high|medium|low"\n'
        "}"
    )


# Keep module-level references for backward compatibility
CHAT_SYSTEM_PROMPT = _build_chat_system_prompt()


SIMPLER_REWRITE_PROMPT = """Rewrite this explanation for a non-technical user.

RULES:
1. Remove jargon and technical terms
2. Keep ALL the important information
3. Use everyday analogies if helpful
4. Keep it brief but complete

Original explanation:
{original}

Respond with the simplified explanation only, no JSON."""


# =============================================================================
# PROMPT CACHE
# =============================================================================


@dataclass
class CachedPrompt:
    """Cached prompt response."""

    response: dict[str, Any]
    timestamp: float
    model: str
    token_count: int
    hit_count: int = 0


class PromptCache:
    """
    Cache for repeated prompt patterns.

    Caches by:
    - Event explanations: (event_id, provider, level, message_hash)
    - Common queries: (query_hash)
    """

    def __init__(self, max_size: int = 500, ttl_seconds: int = 3600):
        self._cache: dict[str, CachedPrompt] = {}
        self._lock = Lock()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0

    def _make_key(
        self,
        event_id: int,
        provider: str,
        level: str,
        message: str,
        detail_level: str = "normal",
    ) -> str:
        """Create cache key for event explanation with detail level."""
        msg_hash = hashlib.md5(message.encode()[:500]).hexdigest()[:12]
        return f"event:{provider}:{event_id}:{level}:{msg_hash}:{detail_level}"

    def get_event(
        self,
        event_id: int,
        provider: str,
        level: str,
        message: str,
        detail_level: str = "normal",
    ) -> dict[str, Any] | None:
        """Get cached event explanation for specific detail level."""
        key = self._make_key(event_id, provider, level, message, detail_level)
        return self._get(key)

    def set_event(
        self,
        event_id: int,
        provider: str,
        level: str,
        message: str,
        response: dict[str, Any],
        model: str,
        token_count: int = 0,
        detail_level: str = "normal",
    ) -> None:
        """Cache event explanation for specific detail level."""
        key = self._make_key(event_id, provider, level, message, detail_level)
        self._set(key, response, model, token_count)

    def _get(self, key: str) -> dict[str, Any] | None:
        """Get cached item."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # Check TTL
            if time.time() - entry.timestamp > self._ttl:
                del self._cache[key]
                self._misses += 1
                return None

            entry.hit_count += 1
            self._hits += 1
            return entry.response

    def _set(
        self,
        key: str,
        response: dict[str, Any],
        model: str,
        token_count: int,
    ) -> None:
        """Set cached item."""
        with self._lock:
            # Evict if at capacity (LRU-ish: remove oldest)
            if len(self._cache) >= self._max_size:
                oldest_key = min(
                    self._cache.keys(), key=lambda k: self._cache[k].timestamp
                )
                del self._cache[oldest_key]

            self._cache[key] = CachedPrompt(
                response=response,
                timestamp=time.time(),
                model=model,
                token_count=token_count,
            )

    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_percent": round(hit_rate, 1),
            }


# =============================================================================
# GROQ PROVIDER
# =============================================================================


class GroqProvider(AIProvider):
    """
    Groq Cloud AI provider using Llama models.

    Features:
    - Ultra-fast inference (tokens/sec)
    - Free tier with generous limits
    - Multiple model options
    - Rate limiting and circuit breaker
    """

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config)

        # Get API key from environment variable
        if not self.config.api_key:
            self.config.api_key = os.environ.get("GROQ_API_KEY", "")

        if not self.config.api_key:
            self._last_error = "GROQ_API_KEY is not configured."
            logger.warning(
                "GROQ_API_KEY not set. Set it in your .env file or environment variables."
            )
            logger.info("Get a free API key at: https://console.groq.com/keys")

        # Model selection
        self._chat_model = os.environ.get("AI_MODEL_CHAT", DEFAULT_CHAT_MODEL)
        self._event_model = os.environ.get("AI_MODEL_EVENT", DEFAULT_EVENT_MODEL)

        # Rate limiting state
        self._last_request_time = 0.0
        self._request_count = 0
        self._request_window_start = time.time()
        self._token_count = 0
        self._rate_lock = Lock()

        # Circuit breaker state
        self._failures = 0
        self._last_failure_time = 0.0
        self._circuit_open = False
        self._circuit_reset_time = 60  # seconds

        # Cancellation support
        self._cancelled_requests: set[str] = set()

        # Prompt cache
        self._cache = PromptCache()

        # Last error message (surfaced to callers for specific UI messages)
        if not hasattr(self, "_last_error"):
            self._last_error: str | None = None

        # HTTP client (lazy init)
        self._client = None

        logger.info(
            f"GroqProvider initialized: chat={self._chat_model}, "
            f"event={self._event_model}, available={self.is_available}"
        )

    @property
    def name(self) -> str:
        return "groq"

    @property
    def is_available(self) -> bool:
        return bool(self.config.api_key) and not self._circuit_open

    def _create_session(self):
        """
        Create a new aiohttp session for this request.

        We use request-scoped sessions to avoid event loop issues
        when the session is reused across different event loops.
        """
        try:
            import aiohttp

            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            return aiohttp.ClientSession(timeout=timeout)
        except ImportError:
            logger.error("aiohttp not installed. Run: pip install aiohttp")
            return None

    def _check_circuit(self) -> bool:
        """Check if circuit breaker allows requests."""
        if not self._circuit_open:
            return True

        # Check if enough time has passed to reset
        if time.time() - self._last_failure_time > self._circuit_reset_time:
            self._circuit_open = False
            self._failures = 0
            logger.info("Groq circuit breaker reset")
            return True

        return False

    def _record_failure(self, error: str) -> None:
        """Record a failure for circuit breaker."""
        self._failures += 1
        self._last_failure_time = time.time()

        if self._failures >= 3:
            self._circuit_open = True
            logger.warning(
                f"Groq circuit breaker opened after {self._failures} failures: {error}"
            )

    def _record_success(self) -> None:
        """Record success, reset failure count."""
        self._failures = 0
        self._last_error = None

    async def _rate_limit(self) -> None:
        """Apply rate limiting with token awareness."""
        with self._rate_lock:
            now = time.time()

            # Reset counters if window expired
            if now - self._request_window_start > 60:
                self._request_count = 0
                self._token_count = 0
                self._request_window_start = now

            # Check request limit
            if self._request_count >= REQUESTS_PER_MINUTE:
                wait_time = 60 - (now - self._request_window_start)
                if wait_time > 0:
                    logger.info(f"Rate limit reached, waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    self._request_count = 0
                    self._token_count = 0
                    self._request_window_start = time.time()

            # Enforce minimum interval
            elapsed = now - self._last_request_time
            if elapsed < MIN_REQUEST_INTERVAL:
                await asyncio.sleep(MIN_REQUEST_INTERVAL - elapsed)

            self._last_request_time = time.time()
            self._request_count += 1

    def _is_cancelled(self, request_id: str) -> bool:
        """Check if request was cancelled."""
        return request_id in self._cancelled_requests

    def _clear_cancelled(self, request_id: str) -> None:
        """Clear cancelled request from set."""
        self._cancelled_requests.discard(request_id)

    async def _make_request(
        self,
        model: str,
        messages: list[dict[str, str]],
        request_id: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> tuple[str | None, dict[str, Any] | None]:
        """
        Make a request to Groq API.

        Uses request-scoped aiohttp sessions to avoid event loop issues.

        Returns:
            (content, usage) or (None, None) on error
        """
        if not self.config.api_key:
            self._last_error = "GROQ_API_KEY is not configured."
            return None, None

        if not self._check_circuit():
            return None, None

        if request_id and self._is_cancelled(request_id):
            self._clear_cancelled(request_id)
            return None, None

        await self._rate_limit()

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Sentinel-Enterprise-Agent/1.0",
        }

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature or self.config.temperature,
        }

        attempts = max(1, int(getattr(self.config, "max_retries", MAX_RETRIES)))
        for attempt in range(attempts):
            if request_id and self._is_cancelled(request_id):
                self._clear_cancelled(request_id)
                return None, None

            # Create fresh session for each attempt to avoid event loop issues
            session = self._create_session()
            if not session:
                return None, None

            try:
                async with session:
                    async with session.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            self._record_success()

                            content = data["choices"][0]["message"]["content"]
                            usage = data.get("usage", {})

                            # Track token usage
                            with self._rate_lock:
                                self._token_count += usage.get("total_tokens", 0)

                            return content, usage

                        if response.status == 429:
                            # Rate limited
                            retry_after = min(
                                int(response.headers.get("retry-after", 5)),
                                MAX_BACKOFF,
                            )
                            logger.warning(f"Groq rate limited, waiting {retry_after}s")
                            await asyncio.sleep(retry_after)
                            continue

                        if response.status in {401, 403}:
                            error_text = await response.text()
                            logger.error(
                                "Groq API access denied (%s): %s",
                                response.status,
                                error_text[:200],
                            )
                            self._record_failure(f"HTTP {response.status}")
                            self._last_error = (
                                "AI unavailable: GROQ_API_KEY is invalid, expired, "
                                "or the endpoint is blocked."
                            )
                            return None, None

                        error_text = await response.text()
                        logger.error(
                            f"Groq API error {response.status}: {error_text[:200]}"
                        )
                        self._record_failure(f"HTTP {response.status}")

                        if response.status >= 500:
                            # Server error, retry with backoff
                            backoff = min(INITIAL_BACKOFF * (2**attempt), MAX_BACKOFF)
                            await asyncio.sleep(backoff)
                            continue

                        return None, None

            except TimeoutError:
                logger.warning(f"Groq request timeout (attempt {attempt + 1})")
                self._record_failure("Timeout")
                backoff = min(INITIAL_BACKOFF * (2**attempt), MAX_BACKOFF)
                await asyncio.sleep(backoff)
                continue

            except Exception as e:
                logger.exception(f"Groq request error: {e}")
                self._record_failure(str(e))
                return None, None

        return None, None

    async def generate(
        self,
        query: str,
        context: dict[str, Any],
        system_prompt: str | None = None,
        request_id: str | None = None,
    ) -> AIResponse:
        """Generate a response using Groq."""
        if not self.is_available:
            return AIResponse.error("Groq not available (check GROQ_API_KEY)", "groq")

        start = time.monotonic()

        # Build messages
        messages = [
            {"role": "system", "content": system_prompt or CHAT_SYSTEM_PROMPT},
        ]

        # Add conversation history if present
        if "conversation" in context:
            for msg in context["conversation"][-10:]:  # Last 10 messages
                messages.append(
                    {
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", ""),
                    }
                )

        # Add context summary
        context_summary = self._build_context_summary(context)
        if context_summary:
            messages.append(
                {
                    "role": "user",
                    "content": f"[Context: {context_summary}]\n\n{query}",
                }
            )
        else:
            messages.append({"role": "user", "content": query})

        # Make request
        content, usage = await self._make_request(
            model=self._chat_model,
            messages=messages,
            request_id=request_id,
        )

        latency = int((time.monotonic() - start) * 1000)

        if not content:
            return AIResponse.error("Failed to get response from Groq", "groq")

        # Parse response
        response = self._parse_response(content)
        response.latency_ms = latency
        response.source = "groq"

        return response

    async def explain_event(
        self,
        event: dict[str, Any],
        kb_explanation: dict[str, Any] | None = None,
        detail_level: str = "normal",
        request_id: str | None = None,
    ) -> AIResponse:
        """
        Explain a security event using Groq.

        Args:
            event: Event data (event_id, provider, level, message, log_name, timestamp)
            kb_explanation: Local knowledge base explanation (trusted facts)
            detail_level: "normal" or "simplified" for simpler language
            request_id: Optional request ID for cancellation

        Returns:
            AIResponse with structured explanation including brief_user and brief_technical
        """
        if not self.is_available:
            # Fall back to KB explanation if available
            if kb_explanation:
                return self._kb_to_response(kb_explanation, event)
            return AIResponse.error("Groq not available (check GROQ_API_KEY)", "groq")

        event_id = event.get("event_id", 0)
        provider = event.get("provider", event.get("source", "Unknown"))
        level = event.get("level", "Information")
        message = event.get("message", "")
        log_name = event.get("log_name", "Application")
        timestamp = event.get("timestamp", event.get("time_created", ""))

        # Detect platform for prompt context
        os_name = platform.system()  # "Windows" or "Linux"

        # Check cache first (keyed by detail_level too)
        cached = self._cache.get_event(
            event_id, provider, level, message, detail_level=detail_level
        )
        if cached:
            response = self._dict_to_response(cached)
            response.cached = True
            response.technical_details["detail_level"] = detail_level
            return response

        start = time.monotonic()

        # Build prompt with full event context
        safe_message = self._redact_message(message)

        context_parts = [
            f"Operating System: {os_name}",
            f"Event ID: {event_id}",
            f"Provider: {provider}",
            f"Level: {level}",
            f"Log Name: {log_name}",
            f"Timestamp: {timestamp}",
            f"Message: {safe_message[:800] if safe_message else '(No message provided - reduce confidence)'}",
        ]

        # Add KB context as trusted evidence
        evidence = [f"Event ID: {event_id}", f"Provider: {provider}", f"Level: {level}"]
        if kb_explanation:
            context_parts.append("\nLocal Analysis (trust these facts):")
            context_parts.append(
                f"- Title: {kb_explanation.get('title', 'Unknown event')}"
            )
            context_parts.append(
                f"- Severity: {kb_explanation.get('severity', 'Minor')}"
            )
            evidence.append(f"KB: {kb_explanation.get('title', 'matched')}")
            if kb_explanation.get("causes"):
                context_parts.append(
                    f"- Known causes: {', '.join(kb_explanation['causes'][:3])}"
                )
            if kb_explanation.get("actions"):
                context_parts.append(
                    f"- Recommended: {', '.join(kb_explanation['actions'][:3])}"
                )

        # Build dynamic platform-aware prompt
        prompt = _build_event_prompt(os_name=os_name, detail_level=detail_level)

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "\n".join(context_parts)},
        ]

        content, usage = await self._make_request(
            model=self._event_model,
            messages=messages,
            request_id=request_id,
            max_tokens=1500,  # Increased for complete JSON responses
        )

        latency = int((time.monotonic() - start) * 1000)

        if not content:
            # Fall back to KB
            if kb_explanation:
                return self._kb_to_response(kb_explanation, event)
            err = self._last_error or "Failed to explain event"
            return AIResponse.error(err, "groq")

        # Parse response with new fields
        response = self._parse_event_response(content, evidence=evidence)
        response.latency_ms = latency
        response.source = "groq"
        response.technical_details["detail_level"] = detail_level
        response.technical_details["log_name"] = log_name

        # Cache the result (keyed by detail_level)
        self._cache.set_event(
            event_id,
            provider,
            level,
            message,
            response.to_dict(),
            self._event_model,
            usage.get("total_tokens", 0) if usage else 0,
            detail_level=detail_level,
        )

        return response

    async def chat(
        self,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
        system_context: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> AIResponse:
        """
        Chat with the AI using conversation history.

        Args:
            user_message: Current user message
            conversation_history: Previous messages [{"role": "...", "content": "..."}]
            system_context: System state context (defender, events, etc.)
            request_id: Optional request ID for cancellation

        Returns:
            AIResponse with the chat response
        """
        if not self.is_available:
            return AIResponse.error("Groq not available (check GROQ_API_KEY)", "groq")

        start = time.monotonic()

        # Build messages
        messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]

        # Add conversation history
        if conversation_history:
            for msg in conversation_history[-10:]:  # Last 10 messages
                messages.append(
                    {
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", ""),
                    }
                )

        # Build context summary
        context_summary = ""
        if system_context:
            context_summary = self._build_context_summary(system_context)

        # Add current message with context
        if context_summary:
            messages.append(
                {
                    "role": "user",
                    "content": f"[System Context: {context_summary}]\n\nUser: {user_message}",
                }
            )
        else:
            messages.append({"role": "user", "content": user_message})

        # Make request
        content, usage = await self._make_request(
            model=self._chat_model,
            messages=messages,
            request_id=request_id,
        )

        latency = int((time.monotonic() - start) * 1000)

        if not content:
            err = self._last_error or "Failed to get response from Groq"
            return AIResponse.error(err, "groq")

        # Parse response
        response = self._parse_response(content)
        response.latency_ms = latency
        response.source = "groq"

        return response

    def _build_context_summary(self, context: dict[str, Any]) -> str:
        """Build a concise context summary for the chat model."""
        parts = []

        if context.get("defender_status"):
            d = context["defender_status"]
            status = "enabled" if d.get("realtime_protection") else "disabled"
            parts.append(f"Defender: {status}")

        if context.get("firewall_status"):
            f = context["firewall_status"]
            status = "enabled" if f.get("enabled") else "disabled"
            parts.append(f"Firewall: {status}")

        if context.get("recent_events"):
            count = len(context["recent_events"])
            parts.append(f"Recent events: {count}")

        if context.get("current_scan"):
            parts.append(f"Scan in progress: {context['current_scan']}")

        return ", ".join(parts) if parts else ""

    def _redact_message(self, message: str) -> str:
        """Redact sensitive information from message."""
        if not message:
            return ""

        redacted, _ = redact_sensitive({"message": message})
        return redacted.get("message", message)

    def _parse_response(self, content: str) -> AIResponse:
        """Parse chat response into AIResponse."""
        try:
            # Handle JSON wrapped in markdown
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()

            data = json.loads(content)

            return AIResponse(
                answer=data.get("answer", content),
                why_it_happened=data.get("why_it_happened", []),
                what_it_affects=data.get("what_it_affects", []),
                what_to_do_now=data.get("what_to_do_now", []),
                follow_up_suggestions=data.get("follow_up_suggestions", []),
                technical_details={"confidence": data.get("confidence", "medium")},
                source="groq",
                confidence=data.get("confidence", "medium"),
            )
        except json.JSONDecodeError:
            # Treat entire response as answer
            return AIResponse(
                answer=content,
                source="groq",
                confidence="low",
            )

    @staticmethod
    def _normalize_risk_level(raw: str) -> str:
        """Normalize risk_level to one of Low/Medium/High/Critical.

        Groq may return 'none', 'low', 'medium', 'high', 'critical' in
        varying cases.  Map them to the capitalised form the QML UI expects.
        """
        mapping = {
            "none": "Low",
            "low": "Low",
            "medium": "Medium",
            "high": "High",
            "critical": "Critical",
        }
        return mapping.get(raw.strip().lower(), "Low")

    def _parse_event_response(
        self, content: str, evidence: list[str] | None = None
    ) -> AIResponse:
        """Parse event explanation response with strict UI-key validation.

        Ensures the 6 required UI keys always exist:
        short_title, plain_summary, what_happened,
        why_it_happens, what_you_can_do, risk_level
        """
        try:
            # Handle JSON wrapped in markdown
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end > start:
                    content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                if end > start:
                    content = content[start:end].strip()

            # Try to parse JSON, handling truncated responses
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Try to repair truncated JSON by closing brackets
                repaired = content.rstrip()
                if repaired.endswith(","):
                    repaired = repaired[:-1]
                # Count unclosed brackets
                open_braces = repaired.count("{") - repaired.count("}")
                open_brackets = repaired.count("[") - repaired.count("]")
                if repaired.endswith('"'):
                    pass  # String is closed
                elif not repaired.endswith("}") and not repaired.endswith("]"):
                    # Try to close an incomplete string
                    repaired = repaired + '"'
                repaired = repaired + "]" * open_brackets + "}" * open_braces
                try:
                    data = json.loads(repaired)
                    logger.debug("Repaired truncated JSON response from Groq")
                except json.JSONDecodeError:
                    # Extract fields with regex as last resort
                    data = self._extract_fields_from_text(content)

            # ----------------------------------------------------------
            # Enforce the 6 required UI keys with safe defaults
            # ----------------------------------------------------------
            short_title = (
                data.get("short_title")
                or data.get("title")
                or "Event Information"
            )
            plain_summary = (
                data.get("plain_summary")
                or data.get("brief_user")
                or data.get("what_happened")
                or short_title
            )
            what_happened = data.get("what_happened") or plain_summary
            # why_it_happens can be a string or list; normalise to string
            raw_why = data.get("why_it_happens") or data.get("why_it_happened", [])
            if isinstance(raw_why, list):
                why_it_happens = "; ".join(raw_why) if raw_why else ""
            else:
                why_it_happens = str(raw_why)
            # what_you_can_do can be a string or list; normalise to string
            raw_do = data.get("what_you_can_do") or data.get("what_to_do", [])
            if isinstance(raw_do, list):
                what_you_can_do = "; ".join(raw_do) if raw_do else ""
            else:
                what_you_can_do = str(raw_do)
            risk_level = self._normalize_risk_level(
                str(data.get("risk_level", "Low"))
            )

            # Extract existing brief fields
            brief_user = data.get("brief_user", "") or plain_summary
            brief_technical = data.get(
                "brief_technical", data.get("technical_brief", "")
            )
            confidence_value = data.get("confidence", 1.0)
            evidence_list = data.get("evidence", evidence or [])

            # Use brief_user as primary answer, fall back to what_happened
            answer = brief_user or plain_summary or what_happened

            return AIResponse(
                answer=answer,
                why_it_happened=data.get("why_it_happened", []),
                what_it_affects=data.get("what_it_affects", []),
                what_to_do_now=data.get("what_to_do", data.get("what_to_do_now", [])),
                follow_up_suggestions=data.get("when_to_worry", []),
                technical_details={
                    "title": short_title,
                    "is_normal": data.get("is_normal", True),
                    "risk_level": risk_level,
                    "technical_brief": data.get("technical_brief", ""),
                    "full_what_happened": what_happened,
                    # UI-required keys
                    "short_title": short_title,
                    "plain_summary": plain_summary,
                    "what_happened": what_happened,
                    "why_it_happens": why_it_happens,
                    "what_you_can_do": what_you_can_do,
                    # Brief fields
                    "brief_user": brief_user,
                    "brief_technical": brief_technical,
                    "confidence": confidence_value,
                    "evidence": evidence_list,
                },
                source="groq",
                confidence="high"
                if confidence_value >= 0.7
                else "medium"
                if confidence_value >= 0.4
                else "low",
            )
        except Exception as e:
            logger.warning(f"Failed to parse Groq response: {e}")
            return AIResponse(
                answer=content[:500] if content else "Failed to parse response",
                source="groq",
                confidence="low",
            )

    def _extract_fields_from_text(self, text: str) -> dict[str, Any]:
        """Extract key fields from text using regex when JSON parsing fails."""
        import re

        result = {}

        # Try to extract key fields
        patterns = {
            "title": r'"title"\s*:\s*"([^"]+)"',
            "brief_user": r'"brief_user"\s*:\s*"([^"]+)"',
            "brief_technical": r'"brief_technical"\s*:\s*"([^"]+)"',
            "what_happened": r'"what_happened"\s*:\s*"([^"]+)"',
            "is_normal": r'"is_normal"\s*:\s*(true|false)',
            "risk_level": r'"risk_level"\s*:\s*"([^"]+)"',
            "confidence": r'"confidence"\s*:\s*([0-9.]+)',
        }

        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1)
                if field == "is_normal":
                    result[field] = value.lower() == "true"
                elif field == "confidence":
                    try:
                        result[field] = float(value)
                    except ValueError:
                        result[field] = 0.5
                else:
                    result[field] = value

        return result

    def _kb_to_response(
        self, kb: dict[str, Any], event: dict[str, Any] | None = None
    ) -> AIResponse:
        """Convert KB explanation to AIResponse with brief fields.

        Uses platform.system() so the fallback text never says
        'Windows' on a Linux machine.
        """
        title = kb.get("title", "Event recorded")
        event_id = event.get("event_id", 0) if event else 0
        provider = event.get("provider", "Unknown") if event else "Unknown"
        os_name = platform.system()

        # Generate OS-aware briefs from KB data
        if kb.get("severity") in ("Warning", "Critical"):
            brief_user = f"{title}. This event may need attention — check the recommended actions."
        elif os_name == "Linux":
            brief_user = f"{title}. A Linux system service recorded this event. No immediate action required."
        else:
            brief_user = f"{title}. This is a routine event that doesn't require immediate action."

        brief_technical = f"Event {event_id} from {provider}. {kb.get('impact', title)}"

        # Build the 6 required UI keys for the fallback too
        raw_why = kb.get("causes", [])
        why_str = "; ".join(raw_why) if isinstance(raw_why, list) else str(raw_why)
        raw_do = kb.get("actions", [])
        do_str = "; ".join(raw_do) if isinstance(raw_do, list) else str(raw_do)
        risk = self._normalize_risk_level(
            {"Safe": "low", "Minor": "low", "Warning": "medium", "Critical": "high"}
            .get(kb.get("severity", "Minor"), "low")
        )

        return AIResponse(
            answer=brief_user,
            why_it_happened=kb.get("causes", []),
            what_it_affects=[kb.get("impact", "")] if kb.get("impact") else [],
            what_to_do_now=kb.get("actions", []),
            technical_details={
                "severity": kb.get("severity", "Minor"),
                "matched": kb.get("matched", False),
                "brief_user": brief_user,
                "brief_technical": brief_technical,
                "confidence": 0.9 if kb.get("matched") else 0.6,
                "evidence": [f"KB rule matched: {title}"] if kb.get("matched") else [],
                # 6 required UI keys
                "short_title": title,
                "plain_summary": brief_user,
                "what_happened": kb.get("impact", title),
                "why_it_happens": why_str,
                "what_you_can_do": do_str,
                "risk_level": risk,
            },
            source="local_kb",
            confidence="high" if kb.get("matched") else "medium",
        )

    def _dict_to_response(self, data: dict[str, Any]) -> AIResponse:
        """Convert cached dict to AIResponse."""
        return AIResponse(
            answer=data.get("answer", ""),
            why_it_happened=data.get("why_it_happened", []),
            what_it_affects=data.get("what_it_affects", []),
            what_to_do_now=data.get("what_to_do_now", []),
            follow_up_suggestions=data.get("follow_up_suggestions", []),
            technical_details=data.get("technical_details", {}),
            source=data.get("source", "groq"),
            confidence=data.get("confidence", "medium"),
        )


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_groq_provider: GroqProvider | None = None
_groq_lock = Lock()


def get_groq_provider() -> GroqProvider:
    """Get singleton Groq provider instance."""
    global _groq_provider
    with _groq_lock:
        if _groq_provider is None:
            _groq_provider = GroqProvider()
        return _groq_provider


def reset_groq_provider() -> None:
    """Discard the cached singleton so the next call creates a fresh instance.

    Call this after updating GROQ_API_KEY in os.environ (e.g. from Settings)
    so the new key is picked up immediately without restarting the app.
    """
    global _groq_provider
    with _groq_lock:
        _groq_provider = None


def is_groq_available() -> bool:
    """Check if Groq is available and configured."""
    return get_groq_provider().is_available
