"""Focused tests for AI explanation payload normalization."""

import json

import pytest

from backend.api.backend_bridge import BackendBridge


def test_normalize_v5_explanation_payload_adds_legacy_fields() -> None:
    payload = {
        "title": "Service Started",
        "what_happened": "A service started successfully.",
        "what_to_do": ["No action needed", "Keep monitoring"],
        "why_it_happened": ["The service was launched during startup"],
        "severity": "Minor",
    }

    normalized = BackendBridge._normalize_v5_explanation_payload(json.dumps(payload))

    assert normalized["ai_enhanced"] is True
    assert normalized["source"] == "groq"
    assert normalized["short_title"] == "Service Started"
    assert normalized["recommendation"] == "No action needed; Keep monitoring"
    assert normalized["what_you_can_do"] == normalized["recommendation"]
    assert normalized["severity_label"] == "Minor"


def test_normalize_v5_explanation_payload_rejects_non_object_json() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        BackendBridge._normalize_v5_explanation_payload("[]")
