"""
Groq-powered Smart Assistant - Replaces online_integration for chat.

Provides the same interface as create_online_smart_assistant but uses Groq.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GroqSmartAssistant:
    """
    Smart Assistant powered by Groq Cloud AI.
    
    Provides structured responses with:
    - Conversation memory
    - System context (events, defender, firewall)
    - Tool callbacks for data access
    """

    def __init__(self, tool_callbacks: dict[str, Callable] | None = None):
        self._callbacks = tool_callbacks or {}
        self._conversation: list[dict[str, str]] = []
        self._selected_event: dict[str, Any] | None = None
        self._max_history = 10

    def ask(self, question: str) -> str:
        """
        Ask a question and get a text response.
        
        Args:
            question: User's question
        
        Returns:
            Text answer
        """
        response = self.ask_structured(question)
        return response.get("answer", "I couldn't process your question.")

    def ask_structured(self, question: str) -> dict[str, Any]:
        """
        Ask a question and get a structured response.
        
        Args:
            question: User's question
        
        Returns:
            Dict with answer, confidence, sources, etc.
        """
        try:
            # Add to conversation
            self._conversation.append({"role": "user", "content": question})
            if len(self._conversation) > self._max_history * 2:
                self._conversation = self._conversation[-self._max_history * 2:]

            # Build context
            context = self._build_context()

            # Get Groq response
            response = self._get_groq_response(question, context)

            # Add assistant response to history
            self._conversation.append({"role": "assistant", "content": response.get("answer", "")})

            return response

        except Exception as e:
            logger.exception(f"Smart assistant error: {e}")
            return {
                "answer": f"I encountered an error: {e!s}",
                "confidence": "low",
                "source": "error",
            }

    def _get_groq_response(self, question: str, context: dict[str, Any]) -> dict[str, Any]:
        """Get response from Groq API."""
        from .providers.groq import get_groq_provider, is_groq_available

        logger.info(f"Groq available check: {is_groq_available()}")

        if not is_groq_available():
            return {
                "answer": "AI is not available. Please set GROQ_API_KEY environment variable.\n\n"
                          "Get your free API key at: https://console.groq.com/",
                "confidence": "low",
                "source": "error",
            }

        groq = get_groq_provider()
        logger.info("Groq provider obtained, calling chat...")

        # Run async in sync context with fresh event loop each time
        # The Groq provider uses request-scoped sessions, so this is safe
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(
                    groq.chat(
                        user_message=question,
                        conversation_history=self._conversation[:-1],  # Exclude current question
                        system_context=context,
                    )
                )
            finally:
                # Always close the loop when done
                try:
                    loop.close()
                except Exception:
                    pass

            logger.info(f"Groq response received: valid={response._is_valid}, source={response.source}")

            if response._is_valid:
                return {
                    "answer": response.answer,
                    "why_it_happened": response.why_it_happened,
                    "what_it_affects": response.what_it_affects,
                    "what_to_do_now": response.what_to_do_now,
                    "follow_up_suggestions": response.follow_up_suggestions,
                    "confidence": response.confidence,
                    "source": "groq",
                    "latency_ms": response.latency_ms,
                }
            logger.warning(f"Groq response invalid: {response.answer}")
            return {
                "answer": response.answer or "Failed to get response from AI.",
                "confidence": "low",
                "source": "error",
            }

        except Exception as e:
            logger.exception(f"Groq API error: {e}")
            return {
                "answer": f"AI request failed: {e!s}",
                "confidence": "low",
                "source": "error",
            }

    def _build_context(self) -> dict[str, Any]:
        """Build context from callbacks."""
        context = {}

        # Get Defender status
        if "get_defender_status" in self._callbacks:
            try:
                context["defender_status"] = self._callbacks["get_defender_status"]()
            except Exception:
                pass

        # Get Firewall status
        if "get_firewall_status" in self._callbacks:
            try:
                context["firewall_status"] = self._callbacks["get_firewall_status"]()
            except Exception:
                pass

        # Get recent events
        if "get_recent_events" in self._callbacks:
            try:
                events = self._callbacks["get_recent_events"](limit=10)
                if events:
                    # Summarize events for context
                    context["recent_events"] = [
                        {
                            "event_id": e.get("event_id"),
                            "provider": e.get("provider"),
                            "level": e.get("level"),
                            "message": (e.get("message") or "")[:100],
                        }
                        for e in events[:10]
                    ]
            except Exception:
                pass

        # Include selected event if any
        if self._selected_event:
            context["selected_event"] = self._selected_event

        return context

    def set_selected_event(self, event: dict[str, Any]):
        """Set the currently selected event for context."""
        self._selected_event = event

    def clear_selected_event(self):
        """Clear the selected event."""
        self._selected_event = None

    def clear_conversation(self):
        """Clear conversation history."""
        self._conversation.clear()

    def get_conversation_summary(self) -> str:
        """Get a summary of recent conversation."""
        if not self._conversation:
            return "No conversation yet."

        lines = []
        for msg in self._conversation[-6:]:
            role = msg.get("role", "user").title()
            content = msg.get("content", "")[:100]
            if len(msg.get("content", "")) > 100:
                content += "..."
            lines.append(f"{role}: {content}")

        return "\n".join(lines)


def create_groq_smart_assistant(
    tool_callbacks: dict[str, Callable] | None = None,
) -> GroqSmartAssistant:
    """
    Create a Groq-powered smart assistant.
    
    This is a drop-in replacement for create_online_smart_assistant.
    
    Args:
        tool_callbacks: Dict of callback functions for data access
    
    Returns:
        GroqSmartAssistant instance
    """
    return GroqSmartAssistant(tool_callbacks=tool_callbacks)
