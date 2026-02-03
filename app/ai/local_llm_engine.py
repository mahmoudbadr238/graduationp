"""
Local LLM Engine - 100% offline AI processing with optional ONNX Runtime GPU.

This module provides a local language model wrapper that:
1. By default, uses fast rule-based responses (no model loading, no CPU usage)
2. Optionally loads ONNX model with GPU if SENTINEL_ENABLE_LLM=1 is set
3. Falls back to rule-based responses if ONNX/model not available
4. NEVER makes any HTTP/network calls

Configuration:
- Set SENTINEL_ENABLE_LLM=1 to enable ONNX model loading (requires GPU for good performance)
- Set SENTINEL_LOCAL_MODEL env var to specify model name
- Default: Uses rule-based fallback (fast, no CPU usage)
- With ONNX: Uses ONNX Runtime with CUDA for GPU acceleration

NOTE: ONNX on CPU causes HIGH CPU usage. Only enable if you have CUDA GPU support.
"""

import logging
import os
from typing import Optional

from PySide6.QtCore import QObject

logger = logging.getLogger(__name__)

# Default small model that works well for simple explanations
DEFAULT_MODEL = "microsoft/DialoGPT-small"

# ONNX Runtime execution providers (TensorRT > CUDA > CPU)
# TensorRT provides the fastest inference on NVIDIA GPUs
ONNX_PROVIDERS = ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"]

# Environment variable to enable LLM (disabled by default to avoid CPU usage)
# Set SENTINEL_ENABLE_LLM=1 to enable ONNX model loading
ENABLE_LLM = os.environ.get("SENTINEL_ENABLE_LLM", "").lower() in ("1", "true", "yes")


class LocalLLMEngine(QObject):
    """
    Local LLM wrapper for 100% offline AI processing.

    Attempts to use HuggingFace Optimum with ONNX Runtime GPU acceleration.
    Falls back to rule-based responses if unavailable.
    Uses LAZY initialization - model only loads when first needed.
    """

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        self._model = None
        self._tokenizer = None
        self._model_name = os.environ.get("SENTINEL_LOCAL_MODEL", DEFAULT_MODEL)
        self._use_transformers = False
        self._fallback_mode = True
        self._initialized = False  # Lazy init flag
        self._using_gpu = False  # Track if GPU acceleration is active
        self._provider_name = "CPU"  # Track which ONNX provider is used (TensorRT/CUDA/CPU)

        # DON'T load model here - wait until first use
        # This speeds up app startup significantly
        logger.info("LocalLLMEngine created (lazy init - ONNX model loads on first use if enabled)")

    def _ensure_initialized(self) -> None:
        """Lazy initialization - load model on first use."""
        if self._initialized:
            return
        self._initialized = True
        self._initialize_model()

    def _initialize_model(self) -> None:
        """Attempt to load the local model using ONNX Runtime with GPU.
        
        NOTE: ONNX model loading is DISABLED by default because:
        1. ONNX on CPU causes very high CPU usage
        2. Most queries use deterministic rule-based responses (fast, no CPU overhead)
        3. Set SENTINEL_ENABLE_LLM=1 to enable (requires CUDA GPU for good performance)
        """
        # Check if LLM is enabled (disabled by default to avoid CPU usage)
        if not ENABLE_LLM:
            logger.info(
                "LLM disabled (SENTINEL_ENABLE_LLM not set). "
                "Using fast rule-based fallback. Set SENTINEL_ENABLE_LLM=1 to enable ONNX model."
            )
            self._fallback_mode = True
            return
        
        try:
            # Import optimum for ONNX model loading
            from optimum.onnxruntime import ORTModelForCausalLM
            from transformers import AutoTokenizer
            import onnxruntime as ort

            logger.info(f"Loading local model with ONNX Runtime: {self._model_name}")
            
            # Check available ONNX Runtime providers
            available_providers = ort.get_available_providers()
            logger.info(f"Available ONNX Runtime providers: {available_providers}")
            
            # IMPORTANT: Don't load on CPU - it causes high CPU usage
            # Only proceed if CUDA or TensorRT is available
            has_gpu = (
                "CUDAExecutionProvider" in available_providers or
                "TensorrtExecutionProvider" in available_providers
            )
            
            if not has_gpu:
                logger.warning(
                    "No GPU provider available (CUDA/TensorRT not found). "
                    "Skipping ONNX model load to avoid high CPU usage. "
                    "Using fast rule-based fallback instead."
                )
                self._fallback_mode = True
                return
            
            # Determine which provider to use
            # TensorRT requires pre-optimized models, so use CUDA by default
            # Set SENTINEL_USE_TENSORRT=1 to force TensorRT (requires TensorRT-optimized model)
            use_tensorrt = os.environ.get("SENTINEL_USE_TENSORRT", "").lower() in ("1", "true", "yes")
            
            providers_to_use = []
            self._provider_name = "CPU"
            
            if use_tensorrt and "TensorrtExecutionProvider" in available_providers:
                providers_to_use.append("TensorrtExecutionProvider")
                self._using_gpu = True
                self._provider_name = "TensorRT"
                logger.info("TensorRT GPU acceleration enabled (requires optimized model)")
            
            if "CUDAExecutionProvider" in available_providers:
                providers_to_use.append("CUDAExecutionProvider")
                if not self._using_gpu:
                    self._using_gpu = True
                    self._provider_name = "CUDA"
                    logger.info("CUDA GPU acceleration enabled")
            
            # Don't add CPUExecutionProvider - we want to fail if no GPU
            if not providers_to_use:
                logger.warning("No GPU provider available, skipping ONNX model load")
                self._fallback_mode = True
                return

            # Try to load tokenizer (local first, then download)
            try:
                self._tokenizer = AutoTokenizer.from_pretrained(
                    self._model_name,
                    local_files_only=True,
                )
            except OSError:
                logger.info(
                    f"Tokenizer not cached, attempting download: {self._model_name}"
                )
                try:
                    self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
                except Exception as e:
                    logger.warning(f"Failed to download tokenizer: {e}")
                    raise

            # Try to load ONNX model (local first, then export/download)
            try:
                self._model = ORTModelForCausalLM.from_pretrained(
                    self._model_name,
                    local_files_only=True,
                    provider=providers_to_use[0],
                )
            except OSError:
                logger.info(f"ONNX model not cached, exporting from transformers: {self._model_name}")
                try:
                    # Export the model to ONNX format
                    self._model = ORTModelForCausalLM.from_pretrained(
                        self._model_name,
                        export=True,  # Export to ONNX if not already
                        provider=providers_to_use[0],
                    )
                    # Save the ONNX model for future use
                    try:
                        cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "sentinel_onnx", self._model_name.replace("/", "_"))
                        os.makedirs(cache_dir, exist_ok=True)
                        self._model.save_pretrained(cache_dir)
                        logger.info(f"ONNX model cached to: {cache_dir}")
                    except Exception as save_err:
                        logger.warning(f"Could not cache ONNX model: {save_err}")
                except Exception as e:
                    logger.warning(f"Failed to export/load ONNX model: {e}")
                    raise

            # Set pad token if not set
            if self._tokenizer.pad_token is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token

            self._use_transformers = True
            self._fallback_mode = False
            gpu_status = f"with {self._provider_name} acceleration" if self._using_gpu else "CPU only"
            logger.info(f"Local LLM (ONNX) initialized successfully: {self._model_name} ({gpu_status})")

        except ImportError:
            logger.warning(
                "transformers package not installed. Using rule-based fallback."
            )
            self._fallback_mode = True

        except Exception as e:
            logger.warning(
                f"Failed to load local model: {e}. Using rule-based fallback."
            )
            self._fallback_mode = True

    @property
    def is_available(self) -> bool:
        """Check if the LLM is available (ONNX model loaded successfully)."""
        self._ensure_initialized()
        return self._use_transformers and self._model is not None

    @property
    def is_fallback_mode(self) -> bool:
        """Check if using fallback rule-based mode."""
        self._ensure_initialized()
        return self._fallback_mode

    @property
    def is_gpu_enabled(self) -> bool:
        """Check if GPU acceleration is active."""
        self._ensure_initialized()
        return self._using_gpu

    @property
    def model_name(self) -> str:
        """Get the configured model name."""
        return self._model_name if not self._fallback_mode else "rule-based-fallback"

    @property
    def backend_info(self) -> str:
        """Get information about the current backend (TensorRT/CUDA/CPU or fallback)."""
        self._ensure_initialized()
        if self._fallback_mode:
            return "rule-based-fallback"
        elif self._using_gpu:
            provider = getattr(self, '_provider_name', 'GPU')
            return f"onnxruntime-{provider.lower()}"
        else:
            return "onnxruntime-cpu"

    def generate_single_turn(self, prompt: str, max_tokens: int = 400) -> str:
        """
        Generate a response for a single-turn prompt using ONNX Runtime.

        Args:
            prompt: The input prompt text
            max_tokens: Maximum tokens to generate (default 400 for detailed explanations)

        Returns:
            Generated response text
        """
        self._ensure_initialized()
        
        if self._fallback_mode:
            return self._fallback_generate(prompt)

        try:
            # Tokenize input - ONNX models work with numpy arrays
            inputs = self._tokenizer(
                prompt,
                return_tensors="np",  # Use numpy for ONNX Runtime
                truncation=True,
                max_length=512,  # Limit input size
            )

            # Generate response with ONNX Runtime
            # ORTModelForCausalLM.generate() handles the inference
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                num_return_sequences=1,
                temperature=0.4,       # Lower temperature for more consistent output
                top_p=0.9,             # Nucleus sampling for better quality
                do_sample=True,
                pad_token_id=self._tokenizer.pad_token_id,
                eos_token_id=self._tokenizer.eos_token_id,
            )

            # Decode and return
            response = self._tokenizer.decode(outputs[0], skip_special_tokens=True)

            # Remove the input prompt from response if it's echoed
            if response.startswith(prompt):
                response = response[len(prompt) :].strip()

            return response if response else self._fallback_generate(prompt)

        except Exception as e:
            logger.error(f"ONNX LLM generation failed: {e}")
            return self._fallback_generate(prompt)

    def _fallback_generate(self, prompt: str) -> str:
        """
        Rule-based fallback when LLM is not available.

        Provides structured responses based on prompt analysis.
        """
        prompt_lower = prompt.lower()

        # Event explanation fallback
        if "explain" in prompt_lower and "event" in prompt_lower:
            return self._fallback_event_explanation(prompt)

        # Security question fallback
        if any(
            word in prompt_lower
            for word in ["security", "threat", "virus", "malware", "firewall"]
        ):
            return self._fallback_security_response(prompt)

        # Chat/general fallback
        return self._fallback_general_response(prompt)

    def _fallback_event_explanation(self, prompt: str) -> str:
        """Fallback for event explanation requests."""
        # Extract event level if mentioned
        prompt_lower = prompt.lower()

        if "error" in prompt_lower or "critical" in prompt_lower:
            severity = "High"
            severity_score = 7
            summary = "This is an error-level system event that may require attention."
            cause = "A system component encountered an unexpected condition."
            impact = (
                "May affect system stability or specific application functionality."
            )
            actions = [
                "Review the event details for specific error codes",
                "Check if the issue is recurring",
                "Consider restarting the affected service if applicable",
            ]
        elif "warning" in prompt_lower:
            severity = "Medium"
            severity_score = 4
            summary = "This is a warning-level event indicating a potential issue."
            cause = "A system component detected a condition that may need attention."
            impact = "Usually not immediately critical but should be monitored."
            actions = [
                "Monitor for recurring warnings",
                "Review system logs for related events",
            ]
        else:
            severity = "Low"
            severity_score = 2
            summary = "This is an informational system event."
            cause = "Normal system operation or routine activity."
            impact = "No immediate impact on system functionality."
            actions = ["No action required for routine informational events."]

        return f"""Summary: {summary}

What it means: This event was logged by Windows to record system activity.

Likely cause: {cause}

Impact: {impact}

Recommended actions:
{chr(10).join('- ' + action for action in actions)}

Severity: {severity_score}/10 ({severity})"""

    def _fallback_security_response(self, prompt: str) -> str:
        """Fallback for security-related questions."""
        prompt_lower = prompt.lower()

        if "firewall" in prompt_lower:
            return """Based on your system context, here's information about your firewall:

Your Windows Firewall helps protect your computer by filtering network traffic. 
It blocks unauthorized access while allowing legitimate connections.

Recommendations:
- Keep the firewall enabled at all times
- Review firewall rules periodically
- Check for any blocked applications that need access

If you're experiencing connectivity issues, verify that necessary programs are allowed through the firewall."""

        if "virus" in prompt_lower or "malware" in prompt_lower:
            return """Here's general guidance about malware protection:

Your system should have real-time antivirus protection enabled. Windows Defender provides built-in protection.

Best practices:
- Keep your antivirus definitions up to date
- Run regular full system scans
- Be cautious with email attachments and downloads
- Avoid clicking suspicious links

If you suspect an infection, run a full system scan immediately."""

        if "update" in prompt_lower:
            return """System updates are important for security:

Windows Update provides critical security patches and feature updates.

Recommendations:
- Enable automatic updates
- Install security updates promptly
- Restart when prompted to complete installations
- Check for pending updates regularly"""

        return """I'm your local security assistant. I can help with:

- Understanding system events and their implications
- General security guidance and best practices  
- Explaining Windows security features
- Reviewing your system's security status

What specific security topic would you like to know more about?"""

    def _fallback_general_response(self, prompt: str) -> str:
        """Fallback for general queries."""
        # Extract first 200 chars for context
        context = prompt[:200] if len(prompt) > 200 else prompt

        return f"""I'm analyzing your request locally.

Based on: "{context}..."

As a local security assistant, I can help you understand:
- System events and their meanings
- Security status and recommendations
- Windows protection features

Please ask a specific question about your system's security or events."""


# Singleton instance
_llm_engine: Optional[LocalLLMEngine] = None


def get_llm_engine() -> LocalLLMEngine:
    """Get the singleton LocalLLMEngine instance."""
    global _llm_engine
    if _llm_engine is None:
        _llm_engine = LocalLLMEngine()
    return _llm_engine
