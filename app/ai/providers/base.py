"""
Base classes for AI providers.

Defines the common interface and types for all AI providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class AIMode(Enum):
    """AI operating mode."""
    OFFLINE_ONLY = "offline_only"    # Rules + KB only, no network
    HYBRID = "hybrid"                 # Offline facts + online explanation
    ONLINE_ONLY = "online_only"       # Online LLM with safety guardrails


@dataclass
class ProviderConfig:
    """Configuration for an AI provider."""
    api_key: Optional[str] = None
    model: str = ""
    max_tokens: int = 1024
    temperature: float = 0.3
    timeout_seconds: float = 30.0
    max_retries: int = 2
    
    # Privacy settings
    redact_usernames: bool = True
    redact_ips: bool = True
    redact_paths: bool = True


@dataclass
class AIResponse:
    """
    Standardized response from any AI provider.
    
    Matches the UI schema for consistency.
    """
    answer: str
    why_it_happened: list[str] = field(default_factory=list)
    what_it_affects: list[str] = field(default_factory=list)
    what_to_do_now: list[str] = field(default_factory=list)
    technical_details: dict[str, Any] = field(default_factory=dict)
    follow_up_suggestions: list[str] = field(default_factory=list)
    
    # Metadata
    source: str = "local"  # "local", "claude", "openai", "hybrid"
    confidence: str = "high"  # "high", "medium", "low"
    cached: bool = False
    latency_ms: int = 0
    
    # Internal flags
    _is_valid: bool = True
    _errors: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to the strict JSON schema for UI."""
        return {
            "answer": self.answer,
            "why_it_happened": self.why_it_happened,
            "what_it_affects": self.what_it_affects,
            "what_to_do_now": self.what_to_do_now,
            "technical_details": {
                **self.technical_details,
                "source": self.source,
                "confidence": self.confidence,
            },
            "follow_up_suggestions": self.follow_up_suggestions,
        }
    
    @classmethod
    def error(cls, message: str, source: str = "error") -> "AIResponse":
        """Create an error response."""
        return cls(
            answer=f"I encountered an issue: {message}",
            why_it_happened=["An error occurred during processing"],
            what_it_affects=["The response may be incomplete"],
            what_to_do_now=["Try again", "Check manually"],
            source=source,
            confidence="low",
            _is_valid=False,
            _errors=[message],
        )
    
    def merge_with(self, other: "AIResponse") -> "AIResponse":
        """
        Merge another response into this one.
        
        Used for hybrid mode: local facts + online explanation.
        The local response is the base, online enhances it.
        """
        # Local response is the authority for facts
        # Online response enhances explanation quality
        return AIResponse(
            # Prefer online answer if available and valid
            answer=other.answer if other._is_valid and other.answer else self.answer,
            # Merge lists, local first
            why_it_happened=self.why_it_happened + [
                item for item in other.why_it_happened 
                if item not in self.why_it_happened
            ],
            what_it_affects=self.what_it_affects + [
                item for item in other.what_it_affects
                if item not in self.what_it_affects
            ],
            what_to_do_now=self.what_to_do_now + [
                item for item in other.what_to_do_now
                if item not in self.what_to_do_now
            ],
            # Keep local technical details, add online metadata
            technical_details={
                **self.technical_details,
                "enhanced_by": other.source if other._is_valid else None,
            },
            follow_up_suggestions=list(set(
                self.follow_up_suggestions + other.follow_up_suggestions
            ))[:5],
            source="hybrid",
            confidence=self.confidence,  # Trust local confidence
            cached=self.cached or other.cached,
            latency_ms=self.latency_ms + other.latency_ms,
        )


class AIProvider(ABC):
    """Base class for AI providers."""
    
    def __init__(self, config: Optional[ProviderConfig] = None):
        self.config = config or ProviderConfig()
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        pass
    
    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available for use."""
        pass
    
    @abstractmethod
    async def generate(
        self,
        query: str,
        context: dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> AIResponse:
        """
        Generate a response for the given query.
        
        Args:
            query: User's question
            context: Relevant context (events, system state, etc.)
            system_prompt: Optional custom system prompt
        
        Returns:
            AIResponse with the generated answer
        """
        pass
    
    @abstractmethod
    async def explain_event(
        self,
        event: dict[str, Any],
        kb_explanation: Optional[dict] = None,
    ) -> AIResponse:
        """
        Explain a security event.
        
        Args:
            event: The event data
            kb_explanation: Optional knowledge base explanation (from local)
        
        Returns:
            AIResponse with the explanation
        """
        pass
