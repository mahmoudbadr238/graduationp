"""
AI Debug Module - Instrumentation for LLM calls.

Logs all prompts, responses, and timing to:
  %APPDATA%/Sentinel/ai_debug/

Files created:
  - last_event_prompt.json: Most recent event explanation prompt
  - last_chat_prompt.json: Most recent chat prompt
  - ai_calls.log: Rolling log of all AI calls with timing
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Dev flag - set to True to enable prompt inspection popups
PROMPT_INSPECTOR_ENABLED = os.environ.get("SENTINEL_PROMPT_INSPECTOR", "0") == "1"


def get_debug_dir() -> Path:
    """Get the AI debug directory path."""
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    debug_dir = Path(appdata) / "Sentinel" / "ai_debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    return debug_dir


@dataclass
class AICallRecord:
    """Record of a single AI call for debugging."""
    
    call_type: str  # "event_explain" or "chat"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Input
    system_prompt: str = ""
    user_prompt: str = ""
    structured_context: dict[str, Any] = field(default_factory=dict)
    
    # Model config
    model_name: str = ""
    temperature: float = 0.4
    max_tokens: int = 400
    backend: str = ""
    
    # Output
    raw_response: str = ""
    parsed_response: dict[str, Any] = field(default_factory=dict)
    
    # Timing
    inference_time_ms: float = 0.0
    total_time_ms: float = 0.0
    
    # Validation
    validation_passed: bool = False
    validation_errors: list[str] = field(default_factory=list)
    fallback_used: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class AIDebugger:
    """
    Singleton debugger for AI calls.
    
    Usage:
        debugger = get_ai_debugger()
        record = debugger.start_call("event_explain", model_name="DialoGPT-small")
        record.system_prompt = "..."
        record.user_prompt = "..."
        # ... do inference ...
        record.raw_response = response
        debugger.end_call(record)
    """
    
    _instance: "AIDebugger | None" = None
    
    def __new__(cls) -> "AIDebugger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        if self._initialized:
            return
        
        self._debug_dir = get_debug_dir()
        self._calls_log = self._debug_dir / "ai_calls.log"
        self._last_event_prompt = self._debug_dir / "last_event_prompt.json"
        self._last_chat_prompt = self._debug_dir / "last_chat_prompt.json"
        
        # Rotate log if too large (> 5MB)
        if self._calls_log.exists() and self._calls_log.stat().st_size > 5 * 1024 * 1024:
            backup = self._calls_log.with_suffix(".log.old")
            if backup.exists():
                backup.unlink()
            self._calls_log.rename(backup)
        
        self._initialized = True
        logger.info(f"AI Debugger initialized - logs at {self._debug_dir}")
    
    def start_call(
        self,
        call_type: str,
        model_name: str = "",
        temperature: float = 0.4,
        max_tokens: int = 400,
        backend: str = "",
    ) -> AICallRecord:
        """
        Start recording an AI call.
        
        Args:
            call_type: "event_explain" or "chat"
            model_name: Name of the model being used
            temperature: Generation temperature
            max_tokens: Max tokens to generate
            backend: Backend being used (onnxruntime-cuda, etc.)
        
        Returns:
            AICallRecord to populate with prompts and response
        """
        record = AICallRecord(
            call_type=call_type,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            backend=backend,
        )
        record._start_time = time.perf_counter()
        return record
    
    def record_inference_start(self, record: AICallRecord) -> None:
        """Mark when inference actually begins (after prompt building)."""
        record._inference_start = time.perf_counter()
    
    def record_inference_end(self, record: AICallRecord) -> None:
        """Mark when inference ends."""
        if hasattr(record, "_inference_start"):
            record.inference_time_ms = (time.perf_counter() - record._inference_start) * 1000
    
    def end_call(self, record: AICallRecord) -> None:
        """
        Complete recording an AI call and save to disk.
        
        Args:
            record: The AICallRecord to finalize and save
        """
        # Calculate total time
        if hasattr(record, "_start_time"):
            record.total_time_ms = (time.perf_counter() - record._start_time) * 1000
        
        # Save to appropriate last prompt file
        try:
            prompt_file = (
                self._last_event_prompt
                if record.call_type == "event_explain"
                else self._last_chat_prompt
            )
            
            with open(prompt_file, "w", encoding="utf-8") as f:
                json.dump(record.to_dict(), f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.warning(f"Failed to save last prompt: {e}")
        
        # Append to rolling log
        try:
            log_entry = {
                "timestamp": record.timestamp,
                "type": record.call_type,
                "model": record.model_name,
                "backend": record.backend,
                "inference_ms": round(record.inference_time_ms, 1),
                "total_ms": round(record.total_time_ms, 1),
                "validation_passed": record.validation_passed,
                "fallback_used": record.fallback_used,
                "prompt_hash": hashlib.md5(
                    (record.system_prompt + record.user_prompt).encode()
                ).hexdigest()[:12],
                "response_length": len(record.raw_response),
            }
            
            with open(self._calls_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
                
        except Exception as e:
            logger.warning(f"Failed to append to AI calls log: {e}")
        
        # Log summary
        logger.debug(
            f"AI call completed: type={record.call_type}, "
            f"model={record.model_name}, "
            f"inference={record.inference_time_ms:.0f}ms, "
            f"total={record.total_time_ms:.0f}ms, "
            f"valid={record.validation_passed}"
        )
    
    def get_last_event_prompt(self) -> dict[str, Any] | None:
        """Get the last event explanation prompt record."""
        try:
            if self._last_event_prompt.exists():
                with open(self._last_event_prompt, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read last event prompt: {e}")
        return None
    
    def get_last_chat_prompt(self) -> dict[str, Any] | None:
        """Get the last chat prompt record."""
        try:
            if self._last_chat_prompt.exists():
                with open(self._last_chat_prompt, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read last chat prompt: {e}")
        return None


# Module-level singleton accessor
_debugger: AIDebugger | None = None


def get_ai_debugger() -> AIDebugger:
    """Get the singleton AI debugger instance."""
    global _debugger
    if _debugger is None:
        _debugger = AIDebugger()
    return _debugger


def log_ai_call(
    call_type: str,
    system_prompt: str,
    user_prompt: str,
    response: str,
    model_name: str = "",
    inference_time_ms: float = 0.0,
    validation_passed: bool = True,
    structured_context: dict[str, Any] | None = None,
) -> None:
    """
    Convenience function to log an AI call.
    
    Use this for simple logging without the full record flow.
    """
    debugger = get_ai_debugger()
    record = debugger.start_call(call_type, model_name=model_name)
    record.system_prompt = system_prompt
    record.user_prompt = user_prompt
    record.structured_context = structured_context or {}
    record.raw_response = response
    record.inference_time_ms = inference_time_ms
    record.validation_passed = validation_passed
    debugger.end_call(record)
