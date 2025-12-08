#!/usr/bin/env python3
"""
AI Worker - Separate process for AI inference.

This script runs as a separate process and:
1. Loads the local LLM ONCE at startup
2. Listens on stdin for JSON tasks
3. Returns JSON responses via stdout
4. NEVER blocks the UI

Input format (one JSON per line):
{
    "id": <task_id>,
    "type": "explain_event",
    "data": { ... event data ... }
}

Output format (one JSON per line):
{
    "id": <task_id>,
    "ok": true/false,
    "result": <explanation dict>,
    "error": <error message if any>
}
"""

import hashlib
import json
import logging
import os
import re
import sys
from typing import Any, Optional

# Configure minimal logging to stderr (stdout is for responses)
logging.basicConfig(
    level=logging.INFO,
    format="[AI_WORKER] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Constants
MAX_TITLE_LENGTH = 80
MAX_WHAT_HAPPENED_LENGTH = 500
MAX_WHY_IT_HAPPENS_LENGTH = 400
MAX_WHAT_TO_DO_LENGTH = 700
MAX_TECH_NOTES_LENGTH = 350
MAX_MESSAGE_INPUT_LENGTH = 600
# Legacy fields (keep for backward compat, but use longer limits)
MAX_EXPLANATION_LENGTH = 500
MAX_RECOMMENDATION_LENGTH = 500
DEFAULT_MODEL = "microsoft/DialoGPT-small"


class AIWorker:
    """
    AI Worker that processes requests from the main application.
    
    Runs in a separate process to never block the UI.
    Uses ONNX Runtime with GPU acceleration for inference.
    """

    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._model_name = os.environ.get("SENTINEL_LOCAL_MODEL", DEFAULT_MODEL)
        self._use_transformers = False
        self._cache: dict[str, dict[str, Any]] = {}
        self._initialized = False
        self._using_gpu = False

    def _initialize_model(self) -> None:
        """Load the AI model using ONNX Runtime (called once at startup)."""
        if self._initialized:
            return

        self._initialized = True

        try:
            from optimum.onnxruntime import ORTModelForCausalLM
            from transformers import AutoTokenizer
            import onnxruntime as ort

            logger.info(f"Loading local model with ONNX Runtime: {self._model_name}")

            # Check available ONNX Runtime providers
            available_providers = ort.get_available_providers()
            logger.info(f"Available ONNX Runtime providers: {available_providers}")
            
            # Determine which providers to use (prefer GPU)
            provider = "CPUExecutionProvider"
            if "CUDAExecutionProvider" in available_providers:
                provider = "CUDAExecutionProvider"
                self._using_gpu = True
                logger.info("CUDA GPU acceleration available")

            # Try local first, then download if needed
            try:
                self._tokenizer = AutoTokenizer.from_pretrained(
                    self._model_name, local_files_only=True
                )
            except OSError:
                logger.info("Tokenizer not cached, downloading...")
                self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)

            try:
                self._model = ORTModelForCausalLM.from_pretrained(
                    self._model_name, local_files_only=True, provider=provider
                )
            except OSError:
                logger.info("ONNX model not cached, exporting from transformers...")
                self._model = ORTModelForCausalLM.from_pretrained(
                    self._model_name, export=True, provider=provider
                )
                # Cache the ONNX model
                try:
                    cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "sentinel_onnx", self._model_name.replace("/", "_"))
                    os.makedirs(cache_dir, exist_ok=True)
                    self._model.save_pretrained(cache_dir)
                    logger.info(f"ONNX model cached to: {cache_dir}")
                except Exception as save_err:
                    logger.warning(f"Could not cache ONNX model: {save_err}")

            if self._tokenizer.pad_token is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token

            self._use_transformers = True
            gpu_status = "with GPU acceleration" if self._using_gpu else "CPU only"
            logger.info(f"ONNX model loaded successfully ({gpu_status})")

        except Exception as e:
            logger.warning(f"ONNX Runtime not available, using fallback: {e}")
            self._use_transformers = False

    def _make_cache_key(self, event: dict) -> str:
        """Create a cache key for an event."""
        key_parts = [
            event.get("log_name", ""),
            event.get("provider", event.get("source", "")),
            str(event.get("event_id", "")),
            event.get("level", ""),
        ]
        message = event.get("message", "")
        msg_hash = hashlib.md5(message.encode()).hexdigest()[:8]
        key_parts.append(msg_hash)
        return "|".join(key_parts)

    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text to max length."""
        if not text:
            return ""
        text = text.strip()
        if len(text) <= max_len:
            return text
        truncated = text[: max_len - 3]
        last_space = truncated.rfind(" ")
        if last_space > max_len // 2:
            truncated = truncated[:last_space]
        return truncated.rstrip() + "..."

    def _build_prompt(self, event: dict) -> str:
        """Build the prompt for event explanation."""
        event_id = event.get("event_id", "Unknown")
        source = event.get("provider", event.get("source", "Unknown"))
        level = event.get("level", "Information")
        time = event.get("time_created", "Unknown")
        message = event.get("message", "No message available")

        if len(message) > MAX_MESSAGE_INPUT_LENGTH:
            message = message[:MAX_MESSAGE_INPUT_LENGTH] + "..."

        return f"""You explain Windows event logs in very simple language for non-technical users.

Event Information:
- Event ID: {event_id}
- Source: {source}
- Level: {level}
- Time: {time}
- Message: {message}

Return JSON:
{{
  "severity": "Safe | Minor | Warning | Critical",
  "title": "Short and simple",
  "explanation": "1-3 sentences with no technical jargon.",
  "recommendation": "One or two simple actions the user can take."
}}

Rules:
- If harmless → say clearly it's safe.
- If normal Windows behavior → say no action needed.
- If important → explain clearly and simply.
- Do NOT use jargon.

JSON response:"""

    def _generate_with_model(self, prompt: str, max_tokens: int = 300) -> str:
        """Generate response using ONNX Runtime model."""
        if not self._use_transformers or self._model is None:
            return ""

        try:
            import numpy as np
            
            # Tokenize with numpy tensors for ONNX Runtime
            inputs = self._tokenizer(
                prompt, return_tensors="np", truncation=True, max_length=512
            )

            outputs = self._model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                num_return_sequences=1,
                pad_token_id=self._tokenizer.pad_token_id,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
            )

            response = self._tokenizer.decode(outputs[0], skip_special_tokens=True)

            # Extract the generated part after the prompt
            if prompt in response:
                response = response[len(prompt) :]

            return response.strip()

        except Exception as e:
            logger.error(f"ONNX model generation failed: {e}")
            return ""

    def _parse_json_response(self, response: str, event: dict) -> dict[str, Any]:
        """Parse LLM response as JSON, with fallback."""
        if response:
            try:
                json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    return self._validate_result(parsed, event)
            except (json.JSONDecodeError, Exception) as e:
                logger.debug(f"JSON parsing failed: {e}")

        return self._create_fallback(event)

    def _validate_result(self, parsed: dict, event: dict) -> dict[str, Any]:
        """Validate and sanitize the parsed result."""
        valid_severities = ["Safe", "Minor", "Warning", "Critical"]

        severity = parsed.get("severity", "Safe")
        if severity not in valid_severities:
            # Try to match partially
            severity_lower = severity.lower()
            if "critical" in severity_lower:
                severity = "Critical"
            elif "warning" in severity_lower:
                severity = "Warning"
            elif "minor" in severity_lower:
                severity = "Minor"
            else:
                severity = "Safe"

        title = self._truncate(
            parsed.get("title", parsed.get("short_title", "")), MAX_TITLE_LENGTH
        )
        if not title:
            source = event.get("source", event.get("provider", "System"))
            title = f"{source} Activity"

        explanation = self._truncate(
            parsed.get("explanation", ""), MAX_EXPLANATION_LENGTH
        )
        if not explanation:
            explanation = "This is a standard Windows system event."

        recommendation = self._truncate(
            parsed.get("recommendation", ""), MAX_RECOMMENDATION_LENGTH
        )
        if not recommendation:
            recommendation = "No action needed."

        return {
            "severity": severity,
            "short_title": title,
            "explanation": explanation,
            "recommendation": recommendation,
        }

    def _extract_context_from_message(self, message: str) -> tuple[str, str, str]:
        """
        Extract meaningful context from the event message.
        Returns (summary, what_happened, action_hint).
        """
        if not message:
            return "", "", ""
            
        text = message.lower().strip()
        
        # =========================================================================
        # SUCCESS / COMPLETION PATTERNS
        # =========================================================================
        if any(w in text for w in ["successfully completed", "completed successfully", "success"]):
            if "install" in text:
                return "Software installed successfully", "A program was installed on your computer.", "No action needed."
            if "update" in text:
                return "Update completed successfully", "An update was installed.", "No action needed."
            if "start" in text:
                return "Service started successfully", "A Windows service or program started running.", "No action needed."
            if "stop" in text:
                return "Service stopped successfully", "A Windows service or program stopped running.", "No action needed."
            if "connect" in text:
                return "Connection established", "Your computer connected to a network or service.", "No action needed."
            if "logon" in text or "login" in text or "sign" in text:
                return "User logged in successfully", "Someone logged into the computer.", "No action needed if it was you."
            if "backup" in text:
                return "Backup completed", "A backup was created successfully.", "No action needed."
            if "sync" in text:
                return "Synchronization completed", "Data was synchronized.", "No action needed."
            return "Operation completed successfully", "An operation finished without problems.", "No action needed."
        
        # =========================================================================
        # FAILURE / ERROR PATTERNS
        # =========================================================================
        if any(w in text for w in ["failed", "failure", "error", "cannot", "unable", "denied"]):
            if "install" in text:
                return "Installation failed", "A program failed to install.", "Try running the installer again as Administrator."
            if "update" in text:
                return "Update failed", "An update couldn't be installed.", "Try Windows Update again later."
            if "start" in text:
                return "Service failed to start", "A Windows service couldn't start.", "Try restarting your computer."
            if "connect" in text:
                return "Connection failed", "Your computer couldn't connect to a network or service.", "Check your internet connection."
            if "logon" in text or "login" in text:
                return "Login failed", "A login attempt was unsuccessful.", "Check the password if it was you."
            if "access" in text or "permission" in text:
                return "Access denied", "A program was blocked from doing something.", "This is often normal security behavior."
            if "timeout" in text:
                return "Operation timed out", "Something took too long and was stopped.", "Try the operation again."
            if "network" in text:
                return "Network error", "There was a problem with the network.", "Check your internet connection."
            if "disk" in text or "drive" in text:
                return "Disk error", "There was a problem with a disk or drive.", "If this happens often, back up your data."
            return "An error occurred", "Something didn't work as expected.", "If problems persist, try restarting."
        
        # =========================================================================
        # START / STOP PATTERNS
        # =========================================================================
        if any(w in text for w in ["started", "starting", "began", "initiated", "launched"]):
            if "service" in text:
                return "Service started", "A Windows service began running.", "No action needed."
            if "driver" in text:
                return "Driver loaded", "A device driver was loaded.", "No action needed."
            if "session" in text:
                return "Session started", "A user session began.", "No action needed."
            if "download" in text:
                return "Download started", "A file is being downloaded.", "No action needed."
            if "scan" in text:
                return "Scan started", "A system scan began.", "No action needed."
            return "Operation started", "Something started running.", "No action needed."
        
        if any(w in text for w in ["stopped", "stopping", "ended", "terminated", "exited", "closed"]):
            if "service" in text:
                return "Service stopped", "A Windows service stopped running.", "No action needed."
            if "unexpected" in text or "crash" in text:
                return "Program crashed", "A program closed unexpectedly.", "If it keeps crashing, try updating or reinstalling."
            if "session" in text:
                return "Session ended", "A user session ended.", "No action needed."
            return "Operation ended", "Something finished running.", "No action needed."
        
        # =========================================================================
        # NETWORK PATTERNS
        # =========================================================================
        if any(w in text for w in ["network", "internet", "wifi", "wi-fi", "ethernet", "connection"]):
            if "connect" in text:
                return "Network connected", "Your computer connected to a network.", "No action needed."
            if "disconnect" in text:
                return "Network disconnected", "Your computer disconnected from a network.", "Check if you moved away from Wi-Fi."
            if "ip address" in text or "dhcp" in text:
                return "Network address assigned", "Your computer got a network address.", "No action needed."
            return "Network activity", "Network activity was logged.", "No action needed if internet works."
        
        # =========================================================================
        # SECURITY PATTERNS
        # =========================================================================
        if any(w in text for w in ["security", "audit", "policy", "credential", "password"]):
            if "logon" in text or "login" in text:
                return "Authentication logged", "Login activity was recorded.", "No action needed."
            if "policy" in text:
                return "Security policy applied", "A security setting was applied.", "No action needed."
            if "password" in text:
                return "Password activity", "Password-related activity occurred.", "No action needed if it was you."
            return "Security event", "A security event was recorded.", "No action needed."
        
        # =========================================================================
        # UPDATE / INSTALL PATTERNS
        # =========================================================================
        if any(w in text for w in ["update", "upgrade", "patch"]):
            if "download" in text:
                return "Update downloaded", "An update was downloaded.", "It will install when ready."
            if "install" in text:
                return "Update installed", "An update was installed.", "You may need to restart."
            if "available" in text:
                return "Updates available", "New updates are available.", "Run Windows Update when convenient."
            if "check" in text:
                return "Checking for updates", "Windows is checking for updates.", "No action needed."
            return "Update activity", "Update-related activity occurred.", "No action needed."
        
        if any(w in text for w in ["install", "uninstall", "setup"]):
            if "uninstall" in text or "remov" in text:
                return "Software uninstalled", "A program was removed from your computer.", "No action needed."
            return "Installation activity", "Software installation activity occurred.", "No action needed."
        
        # =========================================================================
        # POWER / HARDWARE PATTERNS
        # =========================================================================
        if any(w in text for w in ["power", "sleep", "hibernate", "wake", "shutdown", "restart", "reboot"]):
            if "sleep" in text or "hibernate" in text:
                return "System sleeping", "Your computer entered low-power mode.", "No action needed."
            if "wake" in text or "resume" in text:
                return "System woke up", "Your computer woke from sleep.", "No action needed."
            if "shutdown" in text:
                return "System shutdown", "A shutdown was logged.", "No action needed."
            if "restart" in text or "reboot" in text:
                return "System restart", "A restart was logged.", "No action needed."
            return "Power state changed", "Your computer's power state changed.", "No action needed."
        
        if any(w in text for w in ["driver", "device", "hardware", "usb", "bluetooth"]):
            if "load" in text or "start" in text:
                return "Device driver loaded", "A device driver was loaded.", "No action needed."
            if "error" in text or "fail" in text:
                return "Device driver issue", "There was a problem with a device driver.", "Check if your devices are working."
            if "usb" in text:
                return "USB activity", "USB device activity was logged.", "No action needed."
            if "bluetooth" in text:
                return "Bluetooth activity", "Bluetooth activity was logged.", "No action needed."
            return "Hardware activity", "Hardware activity was logged.", "No action needed."
        
        # =========================================================================
        # DISK / STORAGE PATTERNS  
        # =========================================================================
        if any(w in text for w in ["disk", "storage", "volume", "partition", "filesystem", "ntfs"]):
            if "error" in text:
                return "Disk error", "A disk error was detected.", "If this happens often, back up your data."
            if "check" in text or "scan" in text:
                return "Disk check performed", "Your disk was checked.", "No action needed."
            if "mount" in text:
                return "Volume mounted", "A drive or volume was mounted.", "No action needed."
            return "Disk activity", "Disk activity was logged.", "No action needed."
        
        # =========================================================================
        # BACKUP / RESTORE PATTERNS
        # =========================================================================
        if any(w in text for w in ["backup", "restore", "recovery", "snapshot"]):
            if "start" in text:
                return "Backup started", "A backup or restore operation started.", "No action needed."
            if "complet" in text:
                return "Backup completed", "A backup or restore operation completed.", "No action needed."
            if "fail" in text:
                return "Backup failed", "A backup or restore operation failed.", "Check your backup settings."
            return "Backup activity", "Backup activity was logged.", "No action needed."
        
        # =========================================================================
        # SCHEDULE / TASK PATTERNS
        # =========================================================================
        if any(w in text for w in ["scheduled", "task", "trigger", "schedule"]):
            if "start" in text or "launch" in text:
                return "Scheduled task started", "A scheduled task began running.", "No action needed."
            if "complet" in text:
                return "Scheduled task completed", "A scheduled task finished.", "No action needed."
            return "Scheduled task activity", "A scheduled task did something.", "No action needed."
        
        # =========================================================================
        # WINDOWS DEFENDER / ANTIVIRUS
        # =========================================================================
        if any(w in text for w in ["defender", "antivirus", "malware", "threat", "virus", "scan"]):
            if "detect" in text or "found" in text:
                return "Threat detected", "Windows Defender found something suspicious.", "Open Windows Security to see details."
            if "clean" in text or "remov" in text:
                return "Threat removed", "A security threat was removed.", "Your computer is protected."
            if "scan" in text:
                return "Security scan", "A security scan was performed.", "No action needed."
            if "update" in text:
                return "Definitions updated", "Security definitions were updated.", "Your protection is up to date."
            return "Security scan activity", "Antivirus activity was logged.", "No action needed."
        
        # =========================================================================
        # PRINT PATTERNS
        # =========================================================================
        if any(w in text for w in ["print", "printer", "spooler"]):
            if "job" in text:
                return "Print job processed", "A document was sent to the printer.", "No action needed."
            return "Printer activity", "Printer activity was logged.", "No action needed."
        
        # =========================================================================
        # APPLICATION PATTERNS
        # =========================================================================
        if any(w in text for w in ["crash", "hang", "not responding", "stopped working"]):
            return "Application crashed", "A program stopped responding.", "If it keeps happening, try updating the app."
        
        if any(w in text for w in ["exception", "fault", "access violation"]):
            return "Application error", "A program had an error.", "If it keeps happening, try reinstalling the app."
        
        # No specific pattern matched
        return "", "", ""

    def _create_fallback(self, event: dict) -> dict[str, Any]:
        """
        Create a detailed 5-section fallback explanation based on event level and content.
        
        This generates the full 5-section format that the user requested:
        1. Title - short, clear name
        2. What happened - 3-6 sentences explaining the event
        3. Why this happens - 2-4 sentences on common causes
        4. What to do - bullet list with actions + when to worry
        5. Tech notes - 1-3 sentences for advanced users
        """
        level = (event.get("level") or "Information").upper()
        source = event.get("source", event.get("provider", "Windows"))
        event_id = event.get("event_id", 0)
        message = event.get("message", "")[:400]
        
        # Truncate source for display if needed
        source_display = source[:30] + "..." if len(source) > 30 else source
        
        # Try to extract context from message for title
        title, brief_what, brief_action = self._extract_context_from_message(message)

        # Generate detailed content based on level
        if level in ("CRITICAL", "FAILURE"):
            severity = "Critical"
            title = title or f"Critical Event: {source_display} (ID: {event_id})"
            what_happened = (
                f"A critical event was logged by '{source}' (Event ID: {event_id}). "
                f"This indicates a significant system problem that may affect stability or functionality. "
                f"The event message reports: {message[:200]}{'...' if len(message) > 200 else ''}. "
                "Critical events are relatively rare and typically require attention. "
                "Your computer has detected something important enough to flag as critical."
            )
            why_it_happens = (
                "Critical events usually occur when a major system component fails unexpectedly. "
                "Common causes include hardware failures, driver crashes, severe software bugs, "
                "or critical system resources becoming unavailable. "
                "Sometimes they can be triggered by malware or severe configuration problems."
            )
            what_to_do = (
                "• Save any open work immediately to prevent data loss.\n"
                "• Restart your computer to clear any temporary issues.\n"
                "• Check if the problem affects specific programs or is system-wide.\n"
                "• Run Windows Update to ensure you have the latest fixes.\n"
                "• If the problem persists, check Event Viewer for related errors.\n"
                "• Consider contacting technical support if this keeps happening.\n\n"
                "**When to worry:** This type of event is always worth investigating. "
                "If it happens once and your computer works fine after a restart, you're probably okay. "
                "If it happens repeatedly, seek professional help."
            )
            tech_notes = f"Event ID: {event_id} | Source: {source} | Level: Critical"
            
        elif level == "ERROR":
            severity = "Warning"
            title = title or f"Error: {source_display} (ID: {event_id})"
            what_happened = (
                f"An error was recorded by '{source}' (Event ID: {event_id}). "
                f"This means an operation did not complete successfully. "
                f"The issue involves: {message[:200]}{'...' if len(message) > 200 else ''}. "
                "While errors indicate something went wrong, your computer should continue functioning. "
                "The specific feature or program affected may not work correctly until the issue is resolved."
            )
            why_it_happens = (
                "Errors can happen for many reasons - a program couldn't access a file it needed, "
                "a service failed to start properly, a network connection timed out, "
                "or there was a conflict between software components. "
                "Often these are temporary issues that resolve themselves."
            )
            what_to_do = (
                "• Check if you notice any problems with specific programs or features.\n"
                "• If this error affects a program you're using, try restarting that program.\n"
                "• Make sure your software is up to date through Windows Update.\n"
                f"• Searching for 'Event ID {event_id}' online can help identify solutions.\n"
                "• Try restarting your computer if the problem continues.\n\n"
                "**When to worry:** An occasional error is normal and usually nothing to worry about. "
                "If you see this error repeatedly (several times a day) or if it's causing visible problems, "
                "investigate further or seek help."
            )
            tech_notes = f"Event ID: {event_id} | Source: {source} | Level: Error"
            
        elif level == "WARNING":
            severity = "Minor"
            title = title or f"Warning: {source_display} (ID: {event_id})"
            what_happened = (
                f"A warning was logged by '{source}' (Event ID: {event_id}). "
                f"This indicates something that may need attention but is not immediately critical. "
                f"The warning relates to: {message[:200]}{'...' if len(message) > 200 else ''}. "
                "Your system is functioning normally, but Windows wanted to make a note of this. "
                "Warnings help you catch potential issues before they become serious problems."
            )
            why_it_happens = (
                "Warnings are like yellow traffic lights - they tell you to be aware. "
                "Common causes include a service taking longer than expected to start, "
                "a resource running low (like disk space), or a non-critical component having issues. "
                "Windows logs these to help identify potential problems before they become serious."
            )
            what_to_do = (
                "• No immediate action is typically required for warnings.\n"
                "• Keep an eye on your system's behavior over the next few hours.\n"
                "• Ensure Windows Update is current to get the latest fixes.\n"
                "• If you see this warning frequently, it may indicate a developing issue.\n"
                "• Reference this event if you need to seek help later.\n\n"
                "**When to worry:** Isolated warnings are usually safe to ignore. "
                "If you see the same warning repeatedly or notice performance issues, investigate further."
            )
            tech_notes = f"Event ID: {event_id} | Source: {source} | Level: Warning"
            
        elif level == "SUCCESS":
            severity = "Safe"
            title = title or f"Success: {source_display} (ID: {event_id})"
            what_happened = (
                f"A successful operation was recorded by '{source}' (Event ID: {event_id}). "
                f"This positive event confirms: {message[:200]}{'...' if len(message) > 200 else ''}. "
                "Success events are logged to track when important operations complete correctly. "
                "This is Windows confirming that something worked as expected."
            )
            why_it_happens = (
                "Windows logs success events to provide a record of completed operations. "
                "This is useful for verifying that updates, installations, or system tasks finished properly. "
                "It's part of normal system operation and helps with troubleshooting if problems occur later."
            )
            what_to_do = (
                "• No action needed - this event confirms successful completion.\n"
                "• You can use this as confirmation that the operation worked.\n"
                "• These events are useful for troubleshooting if you need to verify when something happened.\n\n"
                "**When to worry:** You don't need to worry about success events. They're purely informational."
            )
            tech_notes = f"Event ID: {event_id} | Source: {source} | Level: Success"
            
        else:  # INFO, INFORMATION, or unknown
            severity = "Safe"
            title = title or f"Event from {source_display} (ID: {event_id})"
            what_happened = (
                f"An informational event was logged by '{source}' (Event ID: {event_id}). "
                f"This is a routine log entry recording normal system activity. "
                f"The event records: {message[:200]}{'...' if len(message) > 200 else ''}. "
                "Windows continuously logs these for diagnostic and auditing purposes. "
                "This is just your computer keeping notes about its operations."
            )
            why_it_happens = (
                "Windows logs thousands of informational events as part of normal operation. "
                "They track system activities like services starting, users logging in, "
                "or background tasks completing. "
                "These events help track system behavior and can be useful for troubleshooting."
            )
            what_to_do = (
                "• No action needed - this is normal system activity.\n"
                "• These events are logged for record-keeping and diagnostics.\n"
                "• You can safely ignore informational events unless troubleshooting.\n\n"
                "**When to worry:** You don't need to worry about informational events. "
                "They're part of normal Windows operation and don't indicate problems."
            )
            tech_notes = f"Event ID: {event_id} | Source: {source} | Level: Information"

        return {
            "severity": severity,
            "title": self._truncate(title, MAX_TITLE_LENGTH),
            "short_title": self._truncate(title, MAX_TITLE_LENGTH),
            "what_happened": self._truncate(what_happened, MAX_WHAT_HAPPENED_LENGTH),
            "why_it_happens": self._truncate(why_it_happens, MAX_WHY_IT_HAPPENS_LENGTH),
            "what_to_do": self._truncate(what_to_do, MAX_WHAT_TO_DO_LENGTH),
            "tech_notes": self._truncate(tech_notes, MAX_TECH_NOTES_LENGTH),
            # Legacy fields for compatibility
            "explanation": self._truncate(what_happened, MAX_EXPLANATION_LENGTH),
            "recommendation": self._truncate(what_to_do, MAX_RECOMMENDATION_LENGTH),
            "what_you_can_do": self._truncate(what_to_do, MAX_WHAT_TO_DO_LENGTH),
            "used_knowledge_base": False,
            "event_id": event_id,
            "source": source,
        }

    def _lookup_knowledge_base(self, source: str, event_id: int, event: dict) -> Optional[dict[str, Any]]:
        """
        Look up event in local knowledge base and expand to detailed 5-section format.
        Returns detailed explanation dict if found, None otherwise.
        """
        try:
            # Import knowledge base (local file, no network)
            import sys
            import os
            
            # Add parent directory to path for imports
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            
            from event_id_knowledge import lookup_event_knowledge
            
            kb = lookup_event_knowledge(source, event_id)
            if kb is not None:
                # Expand the brief knowledge base entry into detailed 5-section format
                message = event.get("message", "")[:200]
                level = event.get("level", "Information")
                
                # Build expanded "what happened" from brief kb.what_happened
                what_happened = (
                    f"{kb.what_happened} "
                    f"This event was logged by '{source}' with Event ID {event_id}. "
                    f"The system recorded: {message}{'...' if len(message) >= 200 else ''}. "
                    f"Windows logs this type of event to help you track what's happening on your computer."
                )
                
                # Generate "why it happens" based on severity
                if kb.severity == "Critical":
                    why_it_happens = (
                        "Critical events usually occur when a major system component fails unexpectedly. "
                        "This could be due to hardware problems, driver issues, or severe software bugs. "
                        "Windows flags these as critical because they may affect system stability."
                    )
                elif kb.severity == "Warning":
                    why_it_happens = (
                        "Errors like this typically happen when a program or service couldn't complete an operation. "
                        "Common causes include file access issues, network timeouts, or conflicts between software. "
                        "Often these are temporary and resolve on their own."
                    )
                elif kb.severity == "Minor":
                    why_it_happens = (
                        "Warnings are logged when Windows notices something that might need attention. "
                        "They often occur during normal operation - like a service taking a bit longer to start, "
                        "or a non-essential component having a minor hiccup. Usually nothing to worry about."
                    )
                else:  # Safe
                    why_it_happens = (
                        "This type of event is part of normal Windows operation. "
                        "Windows logs these routinely to keep a record of system activities. "
                        "They help with troubleshooting if problems occur later."
                    )
                
                # Expand the brief kb.what_you_can_do into bullet points
                what_to_do = kb.what_you_can_do
                if not what_to_do.startswith("•"):
                    # Convert to bullet format if not already
                    if kb.severity in ("Critical", "Warning"):
                        what_to_do = (
                            f"• {kb.what_you_can_do}\n"
                            "• If the problem persists, try restarting your computer.\n"
                            "• Check Windows Update for the latest fixes.\n"
                            f"• Searching for 'Event ID {event_id}' online can help identify solutions.\n\n"
                            f"**When to worry:** {self._get_when_to_worry(kb.severity)}"
                        )
                    else:
                        what_to_do = (
                            f"• {kb.what_you_can_do}\n"
                            "• This is normal system behavior.\n"
                            "• No further action is typically needed.\n\n"
                            f"**When to worry:** {self._get_when_to_worry(kb.severity)}"
                        )
                
                return {
                    "severity": kb.severity,
                    "title": kb.title,
                    "short_title": kb.title,
                    "what_happened": self._truncate(what_happened, MAX_WHAT_HAPPENED_LENGTH),
                    "why_it_happens": self._truncate(why_it_happens, MAX_WHY_IT_HAPPENS_LENGTH),
                    "what_to_do": self._truncate(what_to_do, MAX_WHAT_TO_DO_LENGTH),
                    "tech_notes": self._truncate(kb.tech_notes or f"Event ID: {event_id} | Source: {source}", MAX_TECH_NOTES_LENGTH),
                    # Legacy fields for compatibility
                    "explanation": self._truncate(what_happened, MAX_EXPLANATION_LENGTH),
                    "recommendation": self._truncate(what_to_do, MAX_RECOMMENDATION_LENGTH),
                    "what_you_can_do": self._truncate(what_to_do, MAX_WHAT_TO_DO_LENGTH),
                    "used_knowledge_base": True,
                    "event_id": event_id,
                    "source": source,
                }
        except Exception as e:
            logger.debug(f"Knowledge base lookup failed: {e}")
        
        return None

    def _get_when_to_worry(self, severity: str) -> str:
        """Get 'when to worry' text based on severity."""
        if severity == "Critical":
            return ("This type of event always warrants investigation. "
                   "If it happens once and your computer works fine afterward, you're probably okay. "
                   "If it happens repeatedly, seek professional help.")
        elif severity == "Warning":
            return ("Occasional errors are normal. If you see this repeatedly "
                   "(several times a day) or notice visible problems, investigate further.")
        elif severity == "Minor":
            return ("Isolated warnings are usually safe to ignore. If you see the same "
                   "warning repeatedly or notice performance issues, investigate further.")
        else:
            return "You don't need to worry about this type of event. It's purely informational."

    def explain_event(self, event: dict) -> dict[str, Any]:
        """
        Explain a Windows event in simple terms.
        
        Uses a two-tier approach:
        1. First, check the local knowledge base for known Event IDs
        2. If not found, fall back to AI/heuristic explanation
        """
        # Lazy model initialization on first use
        if not self._initialized:
            logger.info("First AI request - loading model now...")
            try:
                self._initialize_model()
            except Exception as e:
                logger.error(f"Model initialization failed: {e}")
                self._use_transformers = False
        
        # Check cache first
        cache_key = self._make_cache_key(event)
        if cache_key in self._cache:
            logger.debug("Cache hit")
            return self._cache[cache_key]

        # Extract event info
        event_id = int(event.get("event_id") or 0)
        source = str(event.get("source") or event.get("provider") or "")
        
        # PRIORITY 1: Check knowledge base first (fast, accurate)
        kb_result = self._lookup_knowledge_base(source, event_id, event)
        if kb_result is not None:
            logger.debug(f"Knowledge base hit for {source}/{event_id}")
            self._cache[cache_key] = kb_result
            return kb_result

        # PRIORITY 2: Use local LLM if available
        if self._use_transformers:
            prompt = self._build_prompt(event)
            response = self._generate_with_model(prompt)
            result = self._parse_json_response(response, event)
            # Add metadata
            result["used_knowledge_base"] = False
            result["event_id"] = event_id
            result["source"] = source
        else:
            # FALLBACK: Use heuristic-based explanation
            result = self._create_fallback(event)

        # Cache and return
        self._cache[cache_key] = result
        return result

    def process_request(self, request: dict) -> dict:
        """Process a single request and return response."""
        task_id = request.get("id", "unknown")
        task_type = request.get("type", "")

        try:
            if task_type == "explain_event":
                event_data = request.get("data", {})
                result = self.explain_event(event_data)
                return {"id": task_id, "ok": True, "result": result, "error": None}

            elif task_type == "ping":
                return {"id": task_id, "ok": True, "result": "pong", "error": None}

            else:
                return {
                    "id": task_id,
                    "ok": False,
                    "result": None,
                    "error": f"Unknown task type: {task_type}",
                }

        except Exception as e:
            logger.exception(f"Request processing failed: {e}")
            return {"id": task_id, "ok": False, "result": None, "error": str(e)}

    def _send_response(self, response: dict) -> None:
        """Send a JSON response to stdout (safe method)."""
        try:
            print(json.dumps(response), flush=True)
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    def run(self) -> None:
        """Main loop: read requests from stdin, write responses to stdout."""
        logger.info("AI Worker starting...")

        # DON'T initialize model at startup - defer until first request
        # This prevents CPU spike when app launches
        # Model will load lazily on first explain_event request
        logger.info("AI Worker ready (model loads on first use)")

        # Send ready signal immediately (model loads lazily)
        self._send_response({"id": "init", "ok": True, "result": "ready", "error": None})

        # Main loop with proper signal handling
        try:
            while True:
                try:
                    line = sys.stdin.readline()
                    if not line:  # EOF - parent closed stdin
                        break
                    
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        request = json.loads(line)
                        logger.debug(f"Processing request: {request.get('id', 'unknown')}")
                        response = self.process_request(request)
                        logger.debug(f"Sending response for: {request.get('id', 'unknown')}")
                        self._send_response(response)
                    except json.JSONDecodeError as e:
                        self._send_response({
                            "id": "parse_error",
                            "ok": False,
                            "result": None,
                            "error": f"Invalid JSON: {e}",
                        })
                    except Exception as e:
                        logger.exception(f"Request processing error: {e}")
                        self._send_response({
                            "id": "unknown",
                            "ok": False,
                            "result": None,
                            "error": str(e),
                        })
                        
                except KeyboardInterrupt:
                    logger.info("Received interrupt signal")
                    break
                except IOError:
                    # Pipe broken - parent closed
                    break
                    
        except Exception as e:
            logger.error(f"Main loop error: {e}")

        logger.info("AI Worker shutting down")


def main():
    """Entry point for AI worker process."""
    worker = AIWorker()
    worker.run()


if __name__ == "__main__":
    main()
