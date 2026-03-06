"""AI explainer for the v2 SentinelReport schema (app/scanning/report_schema.py).

Produces plain-English explanations aimed at non-technical Windows users.

Return schema (ExplainerResult):
{
  "one_line_summary":   "Short summary.",
  "risk_level":         "Low|Medium|High|Critical",
  "top_reasons":        ["reason 1", "reason 2"],
  "what_to_do":         ["step 1", ..., "step 5"],
  "false_positive_note":"Context about possible FP, or empty string.",
  "raw":                "<full LLM response text>",
  "error":              "" | "<error message>"
}

Uses the Groq provider already in the repo (app/ai/providers/groq.py).
Falls back to a rule-based offline explanation if no API key is set.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """\
You are a security assistant explaining a file-scan report to a non-technical Windows user.

Rules:
- Be concise and calm.
- Do not use jargon unless you define it in a short phrase.
- Do not exaggerate risk; say "possible" or "may" when uncertain.
- If sandbox executed, mention what suspicious activity was observed.
- If only static analysis ran, note that actual execution was not tested.
- Give 3-6 clear next steps the user can actually do (no more than 6).
- Keep your reply under 260 words.

Respond with VALID JSON only — no markdown, no prose outside the JSON:
{
  "one_line_summary":   "<one sentence>",
  "risk_level":         "<Low|Medium|High|Critical>",
  "top_reasons":        ["<up to 3 concise reasons>"],
  "what_to_do":         ["<step 1>", "<step 2>", "<step 3>"  /* max 6 */],
  "false_positive_note": "<one sentence about false-positive likelihood, or empty string>"
}
"""


def _build_prompt(report: dict[str, Any]) -> str:
    """Convert a v2 SentinelReport into a concise LLM prompt."""
    fi = report.get("file", {})
    verdict = report.get("verdict", {})
    static_s = report.get("static", {})
    sandbox_s = report.get("sandbox", {})
    iocs = report.get("iocs", {})

    fname = fi.get("name", "?")
    ftype = fi.get("file_type", fi.get("type", "?"))
    fsize = fi.get("size_bytes", fi.get("size", 0))
    sha256 = str(fi.get("sha256", "?"))[:20]
    signed = fi.get("signed", None)
    pub = fi.get("publisher", "")

    risk = verdict.get("risk", "Low")
    score = verdict.get("score", 0)
    label = verdict.get("label", "")
    reasons = verdict.get("reasons", [])

    engines = static_s.get("engines", [])
    eng_lines = "\n".join(
        f"  - {e.get('name', '?')}: {e.get('status', '?')} — {str(e.get('details', ''))[:80]}"
        for e in engines[:8]
    )

    # Sandbox section — v2 flat keys (normalized, so always present)
    mode = sandbox_s.get("mode", "static_only")
    executed = sandbox_s.get("executed", False)
    n_procs = len(sandbox_s.get("processes_started", []))
    n_files = len(sandbox_s.get("files_created", []))
    n_conns = len(sandbox_s.get("network_attempts", []))
    alerts = sandbox_s.get("alerts", [])

    # Sandbox mode description for the LLM
    if executed:
        sandbox_desc = f"EXECUTED (mode={mode}) — sample ran inside the sandbox"
    elif mode in ("inspect", "extract"):
        sandbox_desc = (
            f"INSPECT-ONLY (mode={mode}) — sample was NOT run; static inspection only"
        )
    else:
        sandbox_desc = "NOT executed — static analysis only"

    # IOC section — v2 flat keys
    ioc_ips = ", ".join(iocs.get("ips", [])[:5]) or "none"
    ioc_domains = ", ".join(iocs.get("domains", [])[:5]) or "none"
    ioc_urls = ", ".join(iocs.get("urls", [])[:3]) or "none"
    ioc_reg = ", ".join(iocs.get("registry_keys", [])[:2]) or "none"
    ioc_files = ", ".join(iocs.get("file_paths", [])[:2]) or "none"

    sig_line = ""
    if signed is True and pub:
        sig_line = f"  signature: VALID — {pub}"
    elif signed is True:
        sig_line = "  signature: VALID"
    elif signed is False:
        sig_line = "  signature: UNSIGNED"

    return f"""\
FILE: {fname} ({ftype}, {fsize:,} bytes)
SHA256: {sha256}…
{sig_line}

VERDICT: {label or risk} / risk score {score} / risk level {risk}
Reasons: {"; ".join(reasons[:4]) or "none"}

SCAN ENGINES:
{eng_lines or "  (not run)"}

SANDBOX: {sandbox_desc}
  new processes={n_procs}  new files={n_files}  new connections={n_conns}
  alerts={alerts[:4]}

IOCS:
  IPs:           {ioc_ips}
  Domains:       {ioc_domains}
  URLs:          {ioc_urls}
  Registry keys: {ioc_reg}
  File paths:    {ioc_files}

Explain this to a non-technical user following the JSON schema exactly.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Offline fallback
# ─────────────────────────────────────────────────────────────────────────────
def _offline_fallback(report: dict[str, Any]) -> dict[str, Any]:
    """Rule-based fallback when no Groq API key is available."""
    fi = report.get("file", {})
    verdict = report.get("verdict", {})
    sandbox_s = report.get("sandbox", {})

    risk = verdict.get("risk", "Low")
    reasons = verdict.get("reasons", [])
    fname = fi.get("name", "this file")

    executed = sandbox_s.get("executed", False)
    mode = sandbox_s.get("mode", "static_only")
    n_procs = len(sandbox_s.get("processes_started", []))
    alerts = sandbox_s.get("alerts", [])

    # Sandbox context note
    if executed:
        sandbox_ctx = f"The sample was executed in a sandbox (mode={mode})"
        if n_procs:
            sandbox_ctx += f" and spawned {n_procs} new process(es)"
        if alerts:
            sandbox_ctx += f", triggering {len(alerts)} alert(s)"
        sandbox_ctx += "."
    else:
        sandbox_ctx = "Only static analysis was performed; the sample was not executed."

    if risk in ("Critical", "High"):
        summary = f"{fname} shows strong signs of malicious behaviour and should not be opened or run."
        steps = [
            "Do not open or run this file.",
            "If you already ran it, disconnect from the internet immediately.",
            "Run a full antivirus scan (Windows Defender or your security tool).",
            "Contact your IT team or security administrator.",
            "Consider reimaging if the machine may already be compromised.",
        ]
    elif risk == "Medium":
        summary = f"{fname} has suspicious characteristics. Exercise caution before opening it."
        steps = [
            "Do not open this file unless you completely trust its source.",
            "Verify the sender or download origin before proceeding.",
            "Scan with an up-to-date antivirus before opening.",
        ]
    else:
        summary = f"No significant threats were identified in {fname}."
        steps = [
            "File appears low-risk based on available analysis.",
            "Keep Windows and your antivirus definitions up to date.",
        ]

    return {
        "one_line_summary": summary,
        "risk_level": risk,
        "top_reasons": reasons[:3],
        "what_to_do": steps[:6],
        "false_positive_note": (
            "False positives are possible for compressed archives, unsigned utilities, "
            "or software from small publishers. " + sandbox_ctx
        ),
        "raw": "",
        "error": "AI unavailable — showing rule-based explanation.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def explain_report(report: dict[str, Any]) -> dict[str, Any]:
    """
    Produce a plain-English explanation of a v2 SentinelReport.

    The report is normalized via ``normalize_report_v2`` before any
    processing to guarantee all expected keys are present.

    Args:
        report: Parsed SentinelReport dict (snake_case v2 schema).

    Returns:
        ExplainerResult dict — see module docstring.
    """
    # ── Guardrail: normalize before anything else ──────────────────────────
    try:
        from ..scanning.report_schema import normalize_report_v2 as _nrv2

        report = _nrv2(report if isinstance(report, dict) else {})
    except Exception:
        pass  # if schema module unavailable, continue with raw dict
    try:
        from ..ai.providers.groq import (  # type: ignore[import]
            get_groq_provider,
            is_groq_available,
        )
    except ImportError:
        return _offline_fallback(report)

    if not is_groq_available():
        result = _offline_fallback(report)
        result["error"] = (
            "GROQ_API_KEY not set — showing rule-based explanation. "
            "Set the key to enable AI-powered analysis."
        )
        return result

    groq = get_groq_provider()
    user_msg = _build_prompt(report)

    try:
        import asyncio

        async def _chat() -> str:
            messages = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ]
            return await groq.chat(
                messages=messages,
                model="llama-3.1-8b-instant",
                temperature=0.2,
                max_tokens=400,
            )

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    raw = pool.submit(asyncio.run, _chat()).result(timeout=30)
            else:
                raw = loop.run_until_complete(_chat())
        except RuntimeError:
            raw = asyncio.run(_chat())

        # Strip markdown fences if the model added them
        raw = raw.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)

        parsed = json.loads(raw)
        return {
            "one_line_summary": str(parsed.get("one_line_summary", "")),
            "risk_level": str(parsed.get("risk_level", "Low")),
            "top_reasons": list(parsed.get("top_reasons", []))[:4],
            "what_to_do": list(parsed.get("what_to_do", []))[:6],
            "false_positive_note": str(parsed.get("false_positive_note", "")),
            "raw": raw,
            "error": "",
        }

    except json.JSONDecodeError:
        # LLM returned prose — wrap it gracefully
        return {
            "one_line_summary": raw[:200] if raw else "See raw explanation.",
            "risk_level": report.get("verdict", {}).get("risk", "Low"),
            "top_reasons": [],
            "what_to_do": [],
            "false_positive_note": "",
            "raw": raw,
            "error": "AI response was not valid JSON — showing raw text.",
        }
    except Exception as exc:
        logger.exception("explain_report failed: %s", exc)
        result = _offline_fallback(report)
        result["error"] = f"AI call failed: {exc}"
        return result
