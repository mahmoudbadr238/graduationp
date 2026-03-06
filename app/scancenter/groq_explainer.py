"""ScanCenter – Groq AI explainer for normal-user-friendly scan summaries.

Takes a V3Report and returns an AiExplanation by calling the Groq provider.
Falls back gracefully if the Groq key is missing or the API call fails.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from .report_schema import AiExplanation, V3Report

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a security assistant explaining a file scan result to a NON-TECHNICAL user.

STRICT RULES:
- Use plain English (no jargon, no acronyms without explanation).
- Be CALM and BALANCED – do NOT exaggerate. Benign files get clean bills of health.
- If only static analysis was run, say "We inspected the file without running it."
- If the sandbox ran in inspect-only mode, say "We ran it in a safe isolated environment
  but did not allow it to execute."
- If sandbox execution happened, clearly note "The file ran inside an isolated sandbox."
- Maximum 6 bullet points in what_to_do.
- If confidence is below 40, include a false_positive_note.
- Reference the 4-source breakdown scores (Defender, ClamAV, YARA, Sandbox) in your
  top_reasons when relevant.
- END your response with ONLY valid JSON (no markdown fences).

OUTPUT FORMAT (JSON only, no trailing text outside the JSON):
{
  "one_line_summary": "...",
  "risk_level": "Low|Medium|High|Critical",
  "top_reasons": ["..."],
  "what_to_do": ["..."],
  "false_positive_note": "...",
  "sandbox_note": "Sandbox: <executed/inspect-only/not used> – <brief outcome>"
}
"""


def _build_prompt(report: V3Report) -> str:
    """Summarize the V3Report into a compact prompt for the LLM."""
    v = report.verdict
    f = report.file
    sb = report.sandbox

    # Execution context
    if sb and sb.enabled:
        if sb.executed:
            exec_ctx = f"Sandbox execution: YES (mode={sb.mode}, exit_code={sb.exit_code})"
        else:
            exec_ctx = f"Sandbox: inspect-only (executed=False)"
    else:
        exec_ctx = "Analysis: static-only (no sandbox)"

    # 4-source score breakdown
    bd = v.breakdown or {}
    _src_nice = {"defender": "Defender", "clamav": "ClamAV",
                 "yara": "YARA", "sandbox": "Sandbox"}
    breakdown_lines: list[str] = []
    for key in ["defender", "clamav", "yara", "sandbox"]:
        src = bd.get(key, {})
        if isinstance(src, dict):
            if src.get("available", False):
                breakdown_lines.append(
                    f"  {_src_nice[key]}: {src.get('score', 0)}/100"
                    f" (weight {src.get('weight', 0):.0%})"
                )
            else:
                breakdown_lines.append(f"  {_src_nice[key]}: N/A (not available)")

    # Engine detections
    detections = []
    for eng in report.static.engines:
        if eng.status == "detected":
            detections.append(f"  {eng.name}: DETECTED – {eng.details}")
        elif eng.status == "clean":
            detections.append(f"  {eng.name}: clean")

    # IOC summary
    iocs = report.iocs
    ioc_lines = []
    if iocs.ips:
        ioc_lines.append(f"  IPs: {', '.join(iocs.ips[:5])}{'...' if len(iocs.ips) > 5 else ''}")
    if iocs.domains:
        ioc_lines.append(f"  Domains: {', '.join(iocs.domains[:5])}{'...' if len(iocs.domains) > 5 else ''}")
    if iocs.urls:
        ioc_lines.append(f"  URLs: {len(iocs.urls)} found")

    # YARA
    yara_hits = [m.get("title", "?") for m in report.static.yara_matches[:5]]

    eng_lines = detections if detections else ["  (no detections)"]
    ioc_part  = ioc_lines if ioc_lines else ["  none"]

    lines = [
        f"File: {f.name} ({f.file_type or f.mime_type}, {f.size_bytes} bytes)",
        f"SHA-256: {f.sha256[:16]}...",
        f"Signed: {f.signed}  Publisher: {f.publisher or 'none'}",
        "",
        f"Verdict: {v.risk} / {v.label}  Total Score: {v.score}/100  Confidence: {v.confidence}%",
        f"Reasons: {'; '.join(v.reasons[:5]) or 'none'}",
        "",
        exec_ctx,
        "",
        "4-source score breakdown:",
    ] + (breakdown_lines or ["  (no breakdown available)"]) + [
        "",
        "Engine results:",
    ] + eng_lines + [
        "",
        "YARA matches: " + (", ".join(yara_hits) if yara_hits else "none"),
        "",
        "IOCs:",
    ] + ioc_part

    if sb and sb.highlights:
        lines += ["", "Sandbox highlights:"] + [f"  {h}" for h in sb.highlights[:6]]

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────


def explain_report(report: V3Report) -> AiExplanation:
    """
    Call Groq to generate a plain-language explanation of *report*.

    Returns an AiExplanation (never raises; falls back to a template on error).
    """
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return _fallback_explanation(report, note="Groq API key not configured")

    prompt_text = _build_prompt(report)
    raw = _call_groq_sync(api_key, _SYSTEM_PROMPT, prompt_text)
    if raw.startswith("ERROR:"):
        return _fallback_explanation(report, note=raw)
    return _parse_response(raw, report)


def _call_groq_sync(api_key: str, system: str, user: str) -> str:
    """Blocking HTTP call to Groq chat/completions. Returns response text or 'ERROR: ...'."""
    import urllib.error
    import urllib.request

    payload = json.dumps({
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 600,
        "temperature": 0.3,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as exc:
        body = exc.read(500).decode("utf-8", errors="replace")
        return f"ERROR: HTTP {exc.code} – {body}"
    except Exception as exc:
        return f"ERROR: {exc}"


def _parse_response(raw: str, report: V3Report) -> AiExplanation:
    """Extract JSON from the LLM response."""
    # Strip markdown fences if present
    text = raw.strip()
    for fence in ("```json", "```JSON", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        data: dict[str, Any] = json.loads(text)
    except Exception:
        # Try to find the JSON block
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end])
            except Exception:
                return _fallback_explanation(report, raw=raw)
        else:
            return _fallback_explanation(report, raw=raw)

    return AiExplanation(
        one_line_summary=str(data.get("one_line_summary", "")),
        risk_level=str(data.get("risk_level", report.verdict.risk)),
        top_reasons=list(data.get("top_reasons", [])),
        what_to_do=list(data.get("what_to_do", [])),
        false_positive_note=str(data.get("false_positive_note", "")),
        executed_note=str(data.get("sandbox_note") or data.get("executed_note", "")),
        raw_response=raw,
    )


def _fallback_explanation(
    report: V3Report,
    note: str = "",
    raw: str = "",
) -> AiExplanation:
    """Return a template-based explanation when Groq is unavailable."""
    v = report.verdict
    risk_map = {
        "Low": "The file appears safe based on automatic analysis.",
        "Medium": "The file has some suspicious characteristics that may warrant review.",
        "High": "The file shows multiple threat indicators. Exercise caution.",
        "Critical": "The file appears malicious. Do not run it.",
        "Unknown": "Analysis was inconclusive. Treat with caution.",
    }
    summary = risk_map.get(v.risk, risk_map["Unknown"])

    actions: list[str] = []
    if v.risk in ("High", "Critical"):
        actions = [
            "Quarantine the file immediately.",
            "Do not open or execute it.",
            "Scan with Windows Defender or another AV.",
            "Report to your IT/security team.",
        ]
    elif v.risk == "Medium":
        actions = [
            "Verify the file comes from a trusted source.",
            "Run a full system scan.",
            "Consider quarantining if source is unknown.",
        ]
    else:
        actions = ["No immediate action required.", "Keep your AV updated."]

    return AiExplanation(
        one_line_summary=summary + (f" ({note})" if note else ""),
        risk_level=v.risk,
        top_reasons=v.reasons[:4],
        what_to_do=actions,
        false_positive_note=(
            "Automatic analysis can produce false positives. "
            "Context and source matter." if v.confidence < 50 else ""
        ),
        executed_note=(
            "File was not executed – analysis is static only."
            if not (report.sandbox and report.sandbox.executed)
            else "File executed in isolated sandbox."
        ),
        raw_response=raw,
    )
