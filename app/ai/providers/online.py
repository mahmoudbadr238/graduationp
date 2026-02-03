"""
Online AI Providers - Claude and OpenAI integration.

These providers ENHANCE local responses, they never override them.
All data is redacted before sending.

CRITICAL RULES:
1. No raw logs sent
2. No sensitive data (usernames, IPs, paths) unless user allows
3. Timeout and retry handling
4. Circuit breaker for failing providers
5. Responses must match the UI schema
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Optional

from .base import AIProvider, AIResponse, ProviderConfig
from .privacy import redact_sensitive

logger = logging.getLogger(__name__)


# =============================================================================
# SYSTEM PROMPTS
# =============================================================================

SOC_ANALYST_PROMPT = """You are a junior SOC (Security Operations Center) analyst assistant. 
You help explain Windows security events in a clear, actionable way.

CRITICAL RULES:
1. Be SPECIFIC - never say "this event should be reviewed"
2. Explain WHAT happened in plain English (not jargon)
3. Explain WHY it matters (security impact)
4. Tell if it's NORMAL or SUSPICIOUS (with reasoning)
5. Give EXACT Windows steps to verify
6. Provide THRESHOLDS for when to worry

For every event, you MUST provide:
- What happened (plain English, 1-2 sentences)
- Why it happened (2-3 likely causes, ranked)
- What it affects (security impact)
- What to do now (exact steps, not vague advice)
- When to worry (specific thresholds/patterns)
- Related events to check (correlation)

You will receive a "local_analysis" with facts from the knowledge base.
Your job is to ENHANCE the explanation, not contradict the facts.

Response format (JSON):
{
    "answer": "Brief 1-2 sentence summary",
    "why_it_happened": ["cause 1", "cause 2"],
    "what_it_affects": ["impact 1", "impact 2"],
    "what_to_do_now": ["step 1", "step 2"],
    "when_to_worry": ["threshold 1", "pattern to watch"],
    "follow_up_suggestions": ["question 1", "question 2"]
}
"""


# =============================================================================
# ONLINE PROVIDER BASE
# =============================================================================

class OnlineProvider(AIProvider):
    """Base class for online AI providers with common functionality."""
    
    def __init__(self, config: Optional[ProviderConfig] = None):
        super().__init__(config)
        
        # Circuit breaker state
        self._failures = 0
        self._last_failure_time = 0
        self._circuit_open = False
        self._circuit_reset_time = 60  # Seconds before retrying
        
        # Request tracking
        self._last_request_time = 0
        self._min_request_interval = 0.5  # Rate limiting
    
    def _check_circuit(self) -> bool:
        """Check if circuit breaker is open."""
        if self._circuit_open:
            if time.time() - self._last_failure_time > self._circuit_reset_time:
                # Try to reset
                self._circuit_open = False
                self._failures = 0
                logger.info(f"{self.name}: Circuit breaker reset")
                return True
            return False
        return True
    
    def _record_failure(self, error: str) -> None:
        """Record a failure for circuit breaker."""
        self._failures += 1
        self._last_failure_time = time.time()
        
        if self._failures >= 3:
            self._circuit_open = True
            logger.warning(f"{self.name}: Circuit breaker opened after {self._failures} failures")
    
    def _record_success(self) -> None:
        """Record a success, reset failure count."""
        self._failures = 0
        self._circuit_open = False
    
    async def _rate_limit(self) -> None:
        """Apply rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()
    
    def _prepare_payload(
        self,
        event: dict[str, Any],
        local_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Prepare a safe payload for the online API.
        
        Redacts sensitive information before sending.
        """
        # Create a summary without raw message
        safe_event = {
            "event_id": event.get("event_id", event.get("eventId")),
            "provider": event.get("provider", event.get("source")),
            "level": event.get("level"),
            "timestamp": event.get("time_created", event.get("timestamp")),
        }
        
        # Redact the message if present
        if "message" in event:
            message = event["message"]
            if len(message) > 500:
                message = message[:500] + "..."
            redacted, _ = redact_sensitive({"message": message})
            safe_event["message_summary"] = redacted["message"]
        
        # Include local analysis for grounding
        safe_local = {
            "title": local_analysis.get("answer", ""),
            "causes": local_analysis.get("why_it_happened", []),
            "actions": local_analysis.get("what_to_do_now", []),
            "severity": local_analysis.get("technical_details", {}).get("severity", "Minor"),
        }
        
        return {
            "event": safe_event,
            "local_analysis": safe_local,
        }
    
    def _parse_response(self, content: str, raw_value: str) -> AIResponse:
        """Parse LLM response into AIResponse."""
        try:
            # Try to extract JSON from response
            # Handle markdown code blocks
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
                answer=data.get("answer", ""),
                why_it_happened=data.get("why_it_happened", []),
                what_it_affects=data.get("what_it_affects", []),
                what_to_do_now=data.get("what_to_do_now", []),
                follow_up_suggestions=data.get("follow_up_suggestions", []),
                source=self.name,
                confidence="medium",
            )
            
        except json.JSONDecodeError:
            # If not valid JSON, treat the whole response as the answer
            return AIResponse(
                answer=content[:500] if len(content) > 500 else content,
                source=self.name,
                confidence="low",
            )


# =============================================================================
# CLAUDE PROVIDER
# =============================================================================

class ClaudeProvider(OnlineProvider):
    """
    Anthropic Claude API provider.
    
    Uses Claude for enhanced event explanations.
    Respects rate limits and handles errors gracefully.
    """
    
    def __init__(self, config: Optional[ProviderConfig] = None):
        super().__init__(config)
        
        # Get API key from config or environment
        if not self.config.api_key:
            self.config.api_key = os.environ.get("ANTHROPIC_API_KEY")
        
        if not self.config.model:
            self.config.model = "claude-3-haiku-20240307"  # Fast and cheap
        
        self._client = None
    
    @property
    def name(self) -> str:
        return "claude"
    
    @property
    def is_available(self) -> bool:
        return bool(self.config.api_key) and self._check_circuit()
    
    async def _get_client(self):
        """Get or create the Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.AsyncAnthropic(api_key=self.config.api_key)
            except ImportError:
                logger.warning("anthropic package not installed")
                return None
        return self._client
    
    async def generate(
        self,
        query: str,
        context: dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> AIResponse:
        """Generate a response using Claude."""
        if not self.is_available:
            return AIResponse.error("Claude not available", self.name)
        
        start = time.monotonic()
        
        try:
            await self._rate_limit()
            client = await self._get_client()
            if not client:
                return AIResponse.error("Anthropic client not available", self.name)
            
            # Redact context
            safe_context, _ = redact_sensitive(context)
            
            message = await client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=system_prompt or SOC_ANALYST_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"Query: {query}\n\nContext: {json.dumps(safe_context)}"
                }],
            )
            
            self._record_success()
            
            content = message.content[0].text
            response = self._parse_response(content, query)
            response.latency_ms = int((time.monotonic() - start) * 1000)
            return response
            
        except Exception as e:
            self._record_failure(str(e))
            logger.error(f"Claude generate error: {e}")
            return AIResponse.error(str(e), self.name)
    
    async def explain_event(
        self,
        event: dict[str, Any],
        kb_explanation: Optional[dict] = None,
    ) -> AIResponse:
        """Explain an event using Claude, grounded in KB facts."""
        if not self.is_available:
            return AIResponse.error("Claude not available", self.name)
        
        start = time.monotonic()
        
        try:
            await self._rate_limit()
            client = await self._get_client()
            if not client:
                return AIResponse.error("Anthropic client not available", self.name)
            
            # Prepare safe payload
            payload = self._prepare_payload(event, kb_explanation or {})
            
            prompt = f"""Explain this Windows security event. 
Use the local_analysis as your source of truth for facts.
Your job is to enhance the explanation with clearer language and more specific guidance.

Event data:
{json.dumps(payload['event'], indent=2)}

Local analysis (source of truth):
{json.dumps(payload['local_analysis'], indent=2)}

Provide your response in the exact JSON format specified."""
            
            message = await client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=SOC_ANALYST_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            
            self._record_success()
            
            content = message.content[0].text
            response = self._parse_response(content, str(event.get("event_id", "")))
            response.latency_ms = int((time.monotonic() - start) * 1000)
            return response
            
        except Exception as e:
            self._record_failure(str(e))
            logger.error(f"Claude explain_event error: {e}")
            return AIResponse.error(str(e), self.name)


# =============================================================================
# OPENAI PROVIDER
# =============================================================================

class OpenAIProvider(OnlineProvider):
    """
    OpenAI GPT API provider.
    
    Alternative to Claude for enhanced explanations.
    """
    
    def __init__(self, config: Optional[ProviderConfig] = None):
        super().__init__(config)
        
        if not self.config.api_key:
            self.config.api_key = os.environ.get("OPENAI_API_KEY")
        
        if not self.config.model:
            self.config.model = "gpt-4o-mini"  # Fast and cheap
        
        self._client = None
    
    @property
    def name(self) -> str:
        return "openai"
    
    @property
    def is_available(self) -> bool:
        return bool(self.config.api_key) and self._check_circuit()
    
    async def _get_client(self):
        """Get or create the OpenAI client."""
        if self._client is None:
            try:
                import openai
                self._client = openai.AsyncOpenAI(api_key=self.config.api_key)
            except ImportError:
                logger.warning("openai package not installed")
                return None
        return self._client
    
    async def generate(
        self,
        query: str,
        context: dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> AIResponse:
        """Generate a response using OpenAI."""
        if not self.is_available:
            return AIResponse.error("OpenAI not available", self.name)
        
        start = time.monotonic()
        
        try:
            await self._rate_limit()
            client = await self._get_client()
            if not client:
                return AIResponse.error("OpenAI client not available", self.name)
            
            safe_context, _ = redact_sensitive(context)
            
            response = await client.chat.completions.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=[
                    {"role": "system", "content": system_prompt or SOC_ANALYST_PROMPT},
                    {"role": "user", "content": f"Query: {query}\n\nContext: {json.dumps(safe_context)}"}
                ],
            )
            
            self._record_success()
            
            content = response.choices[0].message.content
            result = self._parse_response(content, query)
            result.latency_ms = int((time.monotonic() - start) * 1000)
            return result
            
        except Exception as e:
            self._record_failure(str(e))
            logger.error(f"OpenAI generate error: {e}")
            return AIResponse.error(str(e), self.name)
    
    async def explain_event(
        self,
        event: dict[str, Any],
        kb_explanation: Optional[dict] = None,
    ) -> AIResponse:
        """Explain an event using OpenAI."""
        if not self.is_available:
            return AIResponse.error("OpenAI not available", self.name)
        
        start = time.monotonic()
        
        try:
            await self._rate_limit()
            client = await self._get_client()
            if not client:
                return AIResponse.error("OpenAI client not available", self.name)
            
            payload = self._prepare_payload(event, kb_explanation or {})
            
            prompt = f"""Explain this Windows security event.
Use the local_analysis as your source of truth for facts.
Enhance the explanation with clearer language and specific guidance.

Event: {json.dumps(payload['event'], indent=2)}
Local analysis: {json.dumps(payload['local_analysis'], indent=2)}

Respond in the exact JSON format specified."""
            
            response = await client.chat.completions.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=[
                    {"role": "system", "content": SOC_ANALYST_PROMPT},
                    {"role": "user", "content": prompt}
                ],
            )
            
            self._record_success()
            
            content = response.choices[0].message.content
            result = self._parse_response(content, str(event.get("event_id", "")))
            result.latency_ms = int((time.monotonic() - start) * 1000)
            return result
            
        except Exception as e:
            self._record_failure(str(e))
            logger.error(f"OpenAI explain_event error: {e}")
            return AIResponse.error(str(e), self.name)
