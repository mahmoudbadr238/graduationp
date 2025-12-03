"""
Security Chatbot - Local AI security assistant.

Provides conversational security assistance using:
- System context (CPU, RAM, security status, recent events)
- LocalLLMEngine for generation
- 100% offline operation

STYLE:
- Same tone as EventExplainer (calm, clear, practical)
- Simple language suitable for non-technical users
- Brief answers (under 8-10 sentences)
- Bullet points for recommendations
- Never contradicts raw data
"""

import logging
import re
from typing import Any, Optional

from PySide6.QtCore import QObject

from .local_llm_engine import LocalLLMEngine

logger = logging.getLogger(__name__)

# Maximum response length before truncation
MAX_RESPONSE_LENGTH = 1500


class SecurityChatbot(QObject):
    """
    Local security chatbot assistant.

    Uses system context and conversation history to provide
    helpful security guidance without any network calls.

    Style principles:
    - Calm, clear, non-alarming
    - Simple language (like talking to a 14-year-old)
    - Brief and practical
    - Never invents data or contradicts visible info
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
        logger.info("SecurityChatbot initialized (model loads on first use)")

    def build_context(self) -> str:
        """
        Build system context string from available services.

        Collects:
        - System metrics (CPU, RAM, disk)
        - Security status (firewall, AV)
        - Recent events summary with level counts
        """
        context_parts = []

        # System metrics
        if self._snapshot_service:
            try:
                context_parts.append("=== System Status ===")
                cpu = getattr(self._snapshot_service, "cpuUsage", None)
                mem = getattr(self._snapshot_service, "memoryUsage", None)
                disk = getattr(self._snapshot_service, "diskUsage", None)

                if cpu is not None:
                    context_parts.append(f"CPU Usage: {cpu:.1f}%")
                if mem is not None:
                    context_parts.append(f"Memory Usage: {mem:.1f}%")
                if disk is not None:
                    context_parts.append(f"Disk Usage: {disk:.1f}%")

                # Security info if available
                sec_info = getattr(self._snapshot_service, "securityInfo", None)
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

                    # Overall status
                    simplified = sec_info.get("simplified", {})
                    if simplified:
                        overall = simplified.get("overall", {})
                        if overall:
                            status = overall.get("status", "Unknown")
                            context_parts.append(f"Overall Security: {status}")

            except Exception as e:
                logger.debug(f"Failed to get snapshot context: {e}")
                context_parts.append("System metrics: Not available")

        # Recent events summary
        if self._event_repo:
            try:
                events = self._event_repo.get_recent(limit=20)
                if events:
                    context_parts.append("\n=== Recent Events (last 20) ===")

                    # Count by level
                    level_counts = {}
                    for evt in events:
                        level = getattr(evt, "level", "Unknown")
                        level_counts[level] = level_counts.get(level, 0) + 1

                    for level, count in sorted(level_counts.items()):
                        context_parts.append(f"- {level}: {count} events")

                    # Count serious events
                    critical_count = level_counts.get("Critical", 0)
                    error_count = level_counts.get("Error", 0)
                    warning_count = level_counts.get("Warning", 0)

                    if critical_count > 0:
                        context_parts.append(
                            f"\n⚠️ {critical_count} critical event(s) detected!"
                        )
                    if error_count > 0:
                        context_parts.append(f"❌ {error_count} error(s) detected.")
                    if warning_count > 0:
                        context_parts.append(f"⚡ {warning_count} warning(s) detected.")

                    # Show last 3 events briefly
                    context_parts.append("\nMost recent events:")
                    for evt in events[:3]:
                        level = getattr(evt, "level", "?")
                        source = getattr(evt, "source", "Unknown")
                        msg = getattr(evt, "message", "")[:60]
                        context_parts.append(f"  [{level}] {source}: {msg}...")

            except Exception as e:
                logger.debug(f"Failed to get event context: {e}")

        if not context_parts:
            context_parts.append("System context: Limited information available.")
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
            Assistant response string (cleaned and truncated if needed)
        """
        try:
            # Build context
            context = self.build_context()

            # Build conversation history (last 6 messages)
            history = ""
            for msg in conversation[-6:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    history += f"User: {content}\n"
                else:
                    history += f"Assistant: {content}\n"

            # Build prompt with refined instructions
            prompt = self._build_prompt(context, history, user_message)

            # Generate response
            response = self._llm.generate_single_turn(prompt, max_tokens=450)

            # Post-process response
            response = self._clean_response(response)
            response = self._truncate_response(response)

            return response if response else self._fallback_response(user_message)

        except Exception as e:
            logger.error(f"Chatbot answer failed: {e}")
            return self._fallback_response(user_message)

    def _build_prompt(self, context: str, history: str, user_message: str) -> str:
        """
        Build the prompt with refined style instructions.

        Style matches EventExplainer:
        - Simple language
        - Short paragraphs
        - No deep jargon
        - Grounded in context only
        """
        return f"""You are a LOCAL security assistant for this Windows computer.

STYLE RULES:
- Use SIMPLE language (like talking to a 14-year-old)
- Keep answers SHORT (under 8-10 sentences)
- If using a technical word, explain it briefly in brackets
- Use bullet points for recommendations
- Be calm and reassuring, not alarming
- NEVER mention "AI", "model", or "language model"

GROUNDING RULES:
- Base answers ONLY on the context below and general security knowledge
- If something is not visible in context, say "I don't have this information"
- Do NOT invent log entries, hardware specs, running apps, or past user actions
- Do NOT contradict the visible data

{context}

{history}User: {user_message}

Provide a helpful, brief response. If asked about system health, summarize based on VISIBLE data only.
Assistant:"""

    def _clean_response(self, response: str) -> str:
        """Clean up the LLM response."""
        if not response:
            return ""

        # Remove any prompt echo
        if "Assistant:" in response:
            response = response.split("Assistant:")[-1].strip()

        # Remove leading/trailing whitespace
        response = response.strip()

        # Remove incomplete trailing sentences (if ends mid-sentence)
        lines = response.split("\n")
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _truncate_response(self, response: str) -> str:
        """
        Truncate response if too long.

        Tries to end at a sentence boundary.
        """
        if not response or len(response) <= MAX_RESPONSE_LENGTH:
            return response

        truncated = response[:MAX_RESPONSE_LENGTH]

        # Try to end at sentence boundary
        last_period = truncated.rfind(".")
        last_exclaim = truncated.rfind("!")
        last_question = truncated.rfind("?")

        best_end = max(last_period, last_exclaim, last_question)
        if best_end > MAX_RESPONSE_LENGTH // 2:
            truncated = truncated[: best_end + 1]

        return truncated.strip()

    def _fallback_response(self, user_message: str) -> str:
        """
        Provide a fallback response when generation fails.

        Matches the calm, clear, practical style.
        """
        user_lower = user_message.lower()

        # Common greetings
        if any(word in user_lower for word in ["hello", "hi", "hey"]):
            return (
                "Hello! I'm your local security assistant. I can help you:\n"
                "• Understand your system's security status\n"
                "• Explain Windows events\n"
                "• Give security tips\n\n"
                "What would you like to know?"
            )

        # System health questions
        if any(
            phrase in user_lower
            for phrase in ["okay", "healthy", "fine", "status", "how is my"]
        ):
            return (
                "I can see some basic information about your system. "
                "To give you a proper health check, I'd need to look at your recent events and security settings. "
                "Try asking me something specific like 'Are there any errors?' or 'Is my firewall on?'"
            )

        # Firewall
        if "firewall" in user_lower:
            return (
                "Your Windows Firewall helps block unwanted connections to your computer. "
                "It's like a security guard that checks who's trying to get in.\n\n"
                "I recommend keeping it turned ON at all times."
            )

        # Virus/malware
        if any(word in user_lower for word in ["virus", "malware", "infected"]):
            return (
                "Windows Defender is built into Windows and protects against viruses.\n\n"
                "Good habits:\n"
                "• Keep Windows Defender turned on\n"
                "• Don't download files from unknown sources\n"
                "• Run a scan if you're worried\n\n"
                "If you think something is wrong, run a full scan from Windows Security."
            )

        # Updates
        if "update" in user_lower:
            return (
                "Windows updates are important because they fix security problems.\n\n"
                "My recommendations:\n"
                "• Turn on automatic updates\n"
                "• Install updates when Windows asks\n"
                "• Restart your computer when needed\n\n"
                "You can check for updates in Settings > Windows Update."
            )

        # Events/logs
        if any(word in user_lower for word in ["event", "log", "error", "warning"]):
            return (
                "Windows keeps a log of things that happen on your computer. "
                "Some messages are normal, others might need attention.\n\n"
                "• 'Info' messages are usually fine\n"
                "• 'Warning' messages are worth watching\n"
                "• 'Error' messages might need action if they repeat\n\n"
                "You can use the Event Viewer page to see recent events."
            )

        # Help
        if "help" in user_lower:
            return (
                "I can help you with:\n"
                "• Understanding your system's security\n"
                "• Explaining Windows events\n"
                "• Firewall and antivirus tips\n"
                "• Windows Update guidance\n"
                "• General security advice\n\n"
                "Just ask me a question!"
            )

        # Default
        return (
            "I'm your local security assistant. I can help with:\n"
            "• System security status\n"
            "• Windows events and logs\n"
            "• Firewall and antivirus\n"
            "• Security tips\n\n"
            "What would you like to know?"
        )


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
