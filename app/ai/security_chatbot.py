"""
Security Chatbot - Local AI security assistant.

Provides conversational security assistance using:
- System context (CPU, RAM, security status, recent events)
- LocalLLMEngine for generation
- 100% offline operation
"""

import logging
from typing import Any, Optional

from PySide6.QtCore import QObject

from .local_llm_engine import LocalLLMEngine

logger = logging.getLogger(__name__)


class SecurityChatbot(QObject):
    """
    Local security chatbot assistant.

    Uses system context and conversation history to provide
    helpful security guidance without any network calls.
    """

    def __init__(
        self,
        llm_engine: LocalLLMEngine,
        snapshot_service: Optional[Any] = None,
        event_repo: Optional[Any] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._llm = llm_engine
        self._snapshot_service = snapshot_service
        self._event_repo = event_repo
        # Don't check llm.is_available here - triggers lazy model loading
        logger.info("SecurityChatbot initialized (model loads on first use)")

    def build_context(self) -> str:
        """
        Build system context string from available services.

        Collects:
        - System metrics (CPU, RAM, disk)
        - Security status (firewall, AV)
        - Recent events summary
        """
        context_parts = []

        # System metrics
        if self._snapshot_service:
            try:
                context_parts.append("=== System Status ===")
                context_parts.append(
                    f"CPU Usage: {self._snapshot_service.cpuUsage:.1f}%"
                )
                context_parts.append(
                    f"Memory Usage: {self._snapshot_service.memoryUsage:.1f}%"
                )
                context_parts.append(
                    f"Disk Usage: {self._snapshot_service.diskUsage:.1f}%"
                )

                # Security info if available
                sec_info = self._snapshot_service.securityInfo
                if sec_info:
                    context_parts.append("\n=== Security Status ===")
                    context_parts.append(
                        f"Firewall: {sec_info.get('firewallStatus', 'Unknown')}"
                    )
                    context_parts.append(
                        f"Antivirus: {sec_info.get('antivirus', 'Unknown')}"
                    )
                    context_parts.append(
                        f"Secure Boot: {sec_info.get('secureBoot', 'N/A')}"
                    )
                    context_parts.append(f"TPM: {sec_info.get('tpmPresent', 'N/A')}")

                    # Simplified status if available
                    simplified = sec_info.get("simplified", {})
                    if simplified:
                        overall = simplified.get("overall", {})
                        if overall:
                            status = overall.get("status", "Unknown")
                            detail = overall.get("detail", "")
                            context_parts.append(f"Overall Security: {status}")
                            if detail:
                                context_parts.append(f"Details: {detail}")

            except Exception as e:
                logger.debug(f"Failed to get snapshot context: {e}")
                context_parts.append("System metrics: Not available")

        # Recent events summary
        if self._event_repo:
            try:
                # Get recent events from repo
                events = self._event_repo.get_recent(limit=15)
                if events:
                    context_parts.append("\n=== Recent Events (last 15) ===")

                    # Count by level
                    level_counts = {}
                    for evt in events:
                        level = getattr(evt, "level", "Unknown")
                        level_counts[level] = level_counts.get(level, 0) + 1

                    for level, count in level_counts.items():
                        context_parts.append(f"- {level}: {count} events")

                    # Show last 5 events briefly
                    context_parts.append("\nMost recent:")
                    for evt in events[:5]:
                        level = getattr(evt, "level", "?")
                        source = getattr(evt, "source", "Unknown")
                        msg = getattr(evt, "message", "")[:80]
                        context_parts.append(f"  [{level}] {source}: {msg}")

            except Exception as e:
                logger.debug(f"Failed to get event context: {e}")

        if not context_parts:
            context_parts.append("System context: Limited information available")
            context_parts.append(
                "The assistant can still help with general security questions."
            )

        return "\n".join(context_parts)

    def answer(
        self,
        conversation: list[dict[str, str]],
        user_message: str,
    ) -> str:
        """
        Generate a response to user message.

        Args:
            conversation: List of previous messages [{"role": "user"|"assistant", "content": "..."}]
            user_message: The new user message

        Returns:
            Assistant response string
        """
        try:
            # Build context
            context = self.build_context()

            # Build conversation history
            history = ""
            for msg in conversation[-6:]:  # Last 6 messages for context
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    history += f"User: {content}\n"
                else:
                    history += f"Assistant: {content}\n"

            # Build prompt
            prompt = self._build_prompt(context, history, user_message)

            # Generate response
            response = self._llm.generate_single_turn(prompt, max_tokens=400)

            # Clean up response
            response = self._clean_response(response)

            return response if response else self._fallback_response(user_message)

        except Exception as e:
            logger.error(f"Chatbot answer failed: {e}")
            return self._fallback_response(user_message)

    def _build_prompt(self, context: str, history: str, user_message: str) -> str:
        """Build the prompt for the LLM."""
        return f"""You are a local security assistant for this Windows computer. You help users understand their system security status and provide guidance.

{context}

Conversation so far:
{history}
User: {user_message}

Provide a helpful, clear response based ONLY on the provided context and general security knowledge. 
Do not mention any online services, cloud APIs, or external tools.
Keep responses concise but informative.
If you don't have enough information, say so honestly.Assistant:"""

    def _clean_response(self, response: str) -> str:
        """Clean up the LLM response."""
        if not response:
            return ""

        # Remove any prompt echo
        if "Assistant:" in response:
            response = response.split("Assistant:")[-1].strip()

        # Remove trailing incomplete sentences
        lines = response.strip().split("\n")
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _fallback_response(self, user_message: str) -> str:
        """Provide a fallback response when generation fails."""
        user_lower = user_message.lower()

        # Check for common queries
        if any(word in user_lower for word in ["hello", "hi", "hey"]):
            return "Hello! I'm your local security assistant. I can help you understand your system's security status, explain events, and provide security guidance. What would you like to know?"

        if "firewall" in user_lower:
            return "Your Windows Firewall is an important security feature that monitors network traffic. It helps block unauthorized access while allowing legitimate connections. I recommend keeping it enabled at all times."

        if "virus" in user_lower or "malware" in user_lower:
            return "Windows Defender provides built-in antivirus protection. Make sure real-time protection is enabled and definitions are up to date. If you suspect an infection, run a full system scan."

        if "update" in user_lower:
            return "Keeping Windows updated is crucial for security. Windows Update provides important security patches. I recommend enabling automatic updates and installing them promptly."

        if "event" in user_lower or "log" in user_lower:
            return "Windows Event Viewer logs system activities. Error and Warning events may indicate issues that need attention. You can use the Event Viewer page to see recent events and get AI explanations for them."

        if "help" in user_lower:
            return """I can help you with:
 Understanding your system's security status
 Explaining Windows events
 Firewall and antivirus guidance
 Windows Update recommendations
 General security best practices

What would you like to know more about?"""

        return "I'm your local security assistant. I can help with questions about your system's security status, Windows events, firewall settings, and general security guidance. What would you like to know?"


# Singleton instance
_security_chatbot: Optional[SecurityChatbot] = None


def get_security_chatbot(
    llm_engine: LocalLLMEngine,
    snapshot_service: Optional[Any] = None,
    event_repo: Optional[Any] = None,
) -> SecurityChatbot:
    """Get the singleton SecurityChatbot instance."""
    global _security_chatbot
    if _security_chatbot is None:
        _security_chatbot = SecurityChatbot(llm_engine, snapshot_service, event_repo)
    return _security_chatbot
