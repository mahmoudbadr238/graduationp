"""Regression tests for scan result contracts and URL detonator CLI."""

from __future__ import annotations

import json
import sys

from app.ui.backend_bridge import BackendBridge
from tools.url_detonator import webview2_detonator


def _bridge() -> BackendBridge:
    """Create BackendBridge instance without running heavy __init__."""
    return BackendBridge.__new__(BackendBridge)


def test_file_scan_contract_normalization_defaults() -> None:
    bridge = _bridge()

    result = bridge._normalize_file_scan_result_for_qml({"error": "boom"})

    assert result["error"] == "boom"
    assert result["yara_matches_count"] == 0
    assert result["iocs_found"] is False
    assert result["pe_analyzed"] is False
    assert result["has_sandbox"] is False
    assert result["sandbox_duration"] == 0
    assert result["sandbox_error"] == ""
    assert result["report_content"] == ""


def test_url_scan_contract_normalization_mapping() -> None:
    bridge = _bridge()

    payload = {
        "input_url": "https://example.com",
        "redirects": [{"to": "https://example.com/home"}],
        "evidence": [{"title": "Test", "severity": "low"}],
        "iocs": {"urls": ["https://cdn.example.com/a.js"]},
        "yara_matches": [{"rule": "ExampleRule"}],
        "explanation": "plain text",
    }
    result = bridge._normalize_url_scan_result_for_qml(payload)

    assert result["url"] == "https://example.com"
    assert result["final_url"] == "https://example.com"
    assert result["redirect_count"] == 1
    assert result["evidence_count"] == 1
    assert result["has_iocs"] is True
    assert result["yara_match_count"] == 1
    assert result["success"] is True
    assert isinstance(result["explanation"], dict)
    assert result["explanation"]["technical_summary"] == "plain text"
    assert result["explanation"]["confidence"] == ""


def test_url_detonator_cli_writes_output(monkeypatch, tmp_path) -> None:
    output_file = tmp_path / "detonation.json"

    fake_result = webview2_detonator.DetonationResult(
        url="https://example.com",
        final_url="https://example.com",
        success=True,
    )

    monkeypatch.setattr(
        webview2_detonator,
        "detonate_url",
        lambda url, config=None: fake_result,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "webview2_detonator.py",
            "--url",
            "https://example.com",
            "--output",
            str(output_file),
            "--timeout",
            "5",
        ],
    )

    exit_code = webview2_detonator.main()

    assert exit_code == 0
    assert output_file.exists()
    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["url"] == "https://example.com"
    assert payload["success"] is True


def test_url_detonator_cli_error_writes_output(monkeypatch, tmp_path) -> None:
    output_file = tmp_path / "detonation_error.json"

    def _raise(url, config=None):
        raise RuntimeError("detonation failure")

    monkeypatch.setattr(webview2_detonator, "detonate_url", _raise)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "webview2_detonator.py",
            "--url",
            "https://example.com",
            "--output",
            str(output_file),
        ],
    )

    exit_code = webview2_detonator.main()

    assert exit_code == 1
    assert output_file.exists()
    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["success"] is False
    assert "detonation failure" in payload["error"]
