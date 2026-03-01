"""Parse and score VMware Sandbox Lab reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def load_report(report_path: str | Path) -> dict[str, Any]:
    """Load a JSON report from disk."""
    path = Path(report_path)
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Sandbox report must be a JSON object.")
    return data


def _count_items(payload: Mapping[str, Any], *keys: str) -> int:
    total = 0
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            total += len(value)
        elif isinstance(value, dict):
            total += len(value)
        elif value:
            total += 1
    return total


def score_report(report_json: Mapping[str, Any]) -> dict[str, Any]:
    """Apply a simple rule-based score to a sandbox report."""
    if not isinstance(report_json, Mapping):
        return {
            "score": 0,
            "verdict": "Inconclusive",
            "summary": "Sandbox report could not be parsed.",
            "highlights": ["Invalid report payload."],
        }

    if isinstance(report_json.get("verdict"), str) and isinstance(report_json.get("score"), (int, float)):
        score = max(0, min(100, int(report_json["score"])))
    else:
        score = 0
        score += min(25, _count_items(report_json, "alerts", "detections", "findings") * 8)
        score += min(20, _count_items(report_json, "processes", "spawned_processes") * 4)
        score += min(20, _count_items(report_json, "files_created", "dropped_files") * 3)
        score += min(15, _count_items(report_json, "registry_modified", "persistence") * 5)
        score += min(15, _count_items(report_json, "network_connections", "dns_queries", "http_requests") * 4)
        score += min(10, _count_items(report_json, "errors", "crashes") * 4)

    if _count_items(report_json, "alerts", "detections", "findings", "processes", "spawned_processes") == 0:
        verdict = "Inconclusive"
    elif score >= 70:
        verdict = "Malicious"
    elif score >= 35:
        verdict = "Suspicious"
    elif score <= 15:
        verdict = "Benign"
    else:
        verdict = "Inconclusive"

    highlights: list[str] = []
    alert_count = _count_items(report_json, "alerts", "detections", "findings")
    process_count = _count_items(report_json, "processes", "spawned_processes")
    file_count = _count_items(report_json, "files_created", "dropped_files")
    network_count = _count_items(report_json, "network_connections", "dns_queries", "http_requests")

    if alert_count:
        highlights.append(f"{alert_count} alert/finding entries reported.")
    if process_count:
        highlights.append(f"{process_count} process entries observed.")
    if file_count:
        highlights.append(f"{file_count} file creation or drop events observed.")
    if network_count:
        highlights.append(f"{network_count} network indicators observed.")
    if not highlights:
        highlights.append("Report contains little behavioral data.")

    summary = f"{verdict} ({score}/100). " + " ".join(highlights[:2])

    return {
        "score": score,
        "verdict": verdict,
        "summary": summary.strip(),
        "highlights": highlights,
    }


def build_llm_prompt(report_json: Mapping[str, Any], automation_steps: list[str]) -> str:
    """Build a local-only prompt string for later LLM use."""
    pretty_report = json.dumps(dict(report_json), indent=2, sort_keys=True, default=str)
    pretty_steps = "\n".join(f"- {step}" for step in automation_steps) or "- No steps recorded."
    return (
        "You are reviewing a local VMware sandbox detonation report for Sentinel.\n"
        "Summarize the behavior, identify risky indicators, and explain why the final verdict makes sense.\n\n"
        "Automation steps:\n"
        f"{pretty_steps}\n\n"
        "Sandbox report JSON:\n"
        f"{pretty_report}\n"
    )
