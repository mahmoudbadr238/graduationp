"""AI explainer — takes a SentinelReport and asks an LLM to produce
a plain-English explanation aimed at non-technical Windows users.

Returns an ExplainerResult dict:
{
  "summary":       "One-sentence summary.",
  "risk":          "Low|Medium|High",
  "risk_reasons":  ["reason 1", "reason 2"],
  "user_actions":  ["bullet 1", ..., "bullet 6"],
  "false_positive": "If this is a false positive, it means...",
  "raw":           "<full LLM response text>",
  "error":         "" | "<error message>"
}

Uses the Groq provider already in the repo (app/ai/providers/groq.py).
Falls back to an offline rule-based explanation if no API key is set.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a security assistant explaining a file scan report to a non-technical Windows user.

Rules:
- Be concise and calm.
- Do not use jargon unless you explain it in one short phrase.
- Do not exaggerate; if uncertain, say "possible" or "likely".
- Provide clear next steps.
- Keep your entire reply SHORT (under 250 words).

Structure your reply as VALID JSON with exactly these keys:
{
  "summary": "<one sentence describing what this file is and what happened>",
  "risk": "<Low|Medium|High>",
  "risk_reasons": ["<reason 1>", "<reason 2>"],
  "user_actions": ["<step 1>", "<step 2>", "<step 3>"],
  "false_positive": "<when/why a false positive is possible, or empty string>"
}
"""


def _build_user_message(report: dict[str, Any]) -> str:
    file_info = report.get("file", {})
    verdict = report.get("verdict", {})
    engines = report.get("static", {}).get("engines", [])
    sandbox = report.get("sandbox", {})
    iocs = report.get("iocs", {})

    engine_lines = "\n".join(
        f"  - {e['name']}: {e['status']} — {e.get('details', '')[:80]}" for e in engines
    )
    ioc_ips = ", ".join(iocs.get("ips", [])[:5]) or "none"
    ioc_domains = ", ".join(iocs.get("domains", [])[:5]) or "none"
    new_procs = len(sandbox.get("processes", {}).get("started", []))
    new_files = len(sandbox.get("files", {}).get("created", []))
    new_conns = len(sandbox.get("network", {}).get("attempts", []))

    return f"""\
FILE: {file_info.get("name", "?")} ({file_info.get("type", "?")}, {file_info.get("sizeBytes", 0):,} bytes)
SHA256: {file_info.get("sha256", "?")[:20]}…

VERDICT: {verdict.get("risk", "?")} / confidence {verdict.get("confidence", 0)}%
Reasons: {"; ".join(verdict.get("reasons", [])[:4])}

ENGINES:
{engine_lines or "  (none)"}

SANDBOX:
  mode={sandbox.get("mode", "?")}  executed={sandbox.get("executed", False)}
  new processes={new_procs}  new files={new_files}  new connections={new_conns}
  errors={sandbox.get("errors", [])}

IOCS:
  IPs: {ioc_ips}
  Domains: {ioc_domains}
  Files: {", ".join(iocs.get("paths", [])[:3]) or "none"}

Explain this to a non-technical user following the JSON schema exactly.
"""


def _offline_fallback(report: dict[str, Any]) -> dict[str, Any]:
    """Rule-based fallback when no AI is available."""
    verdict = report.get("verdict", {})
    risk = verdict.get("risk", "Low")
    reasons = verdict.get("reasons", [])
    file_name = report.get("file", {}).get("name", "this file")

    if risk == "High":
        summary = f"This file ({file_name}) shows signs of malicious activity and should not be opened."
        actions = [
            "Do not open or run this file.",
            "If you already ran it, disconnect from the internet and run a full antivirus scan.",
            "Contact your IT or security team.",
        ]
    elif risk == "Medium":
        summary = f"This file ({file_name}) has suspicious characteristics and should be treated carefully."
        actions = [
            "Do not open this file unless you trust its source.",
            "Verify the sender or download origin.",
            "Scan with a fully updated antivirus before opening.",
        ]
    else:
        summary = f"No significant threats were detected in {file_name}."
        actions = [
            "File appears low-risk based on available analysis.",
            "Keep your antivirus and Windows up to date.",
        ]

    return {
        "summary": summary,
        "risk": risk,
        "risk_reasons": reasons[:2],
        "user_actions": actions,
        "false_positive": (
            "False positives are possible for compressed archives, custom utilities, "
            "or digitally signed software from small publishers."
        ),
        "raw": "",
        "error": "AI unavailable — showing rule-based explanation.",
    }


def explain_report(report: dict[str, Any]) -> dict[str, Any]:
    """
    Produce a plain-English explanation of a SentinelReport for a normal user.

    Args:
        report: The parsed SentinelReport dict (or loaded from report.json).

    Returns:
        ExplainerResult dict (see module docstring).
    """
    try:
        from ..ai.providers.groq import (  # type: ignore
            get_groq_provider,
            is_groq_available,
        )
    except ImportError:
        return _offline_fallback(report)

    if not is_groq_available():
        result = _offline_fallback(report)
        result["error"] = (
            "GROQ_API_KEY not set — showing rule-based explanation. Configure it to enable AI."
        )
        return result

    groq = get_groq_provider()
    user_msg = _build_user_message(report)

    try:
        # Use the provider's synchronous chat
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
                    future = pool.submit(asyncio.run, _chat())
                    raw = future.result(timeout=30)
            else:
                raw = loop.run_until_complete(_chat())
        except RuntimeError:
            raw = asyncio.run(_chat())

        # Parse JSON from response
        raw = raw.strip()
        # Strip markdown code block if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)
        return {
            "summary": str(parsed.get("summary", "")),
            "risk": str(parsed.get("risk", "Low")),
            "risk_reasons": list(parsed.get("risk_reasons", []))[:4],
            "user_actions": list(parsed.get("user_actions", []))[:6],
            "false_positive": str(parsed.get("false_positive", "")),
            "raw": raw,
            "error": "",
        }

    except json.JSONDecodeError:
        # LLM returned prose instead of JSON — wrap it
        return {
            "summary": raw[:200] if raw else "See raw explanation.",
            "risk": report.get("verdict", {}).get("risk", "Low"),
            "risk_reasons": [],
            "user_actions": [],
            "false_positive": "",
            "raw": raw,
            "error": "AI response was not valid JSON — showing raw text.",
        }
    except Exception as exc:
        logger.exception("explain_report failed: %s", exc)
        result = _offline_fallback(report)
        result["error"] = f"AI call failed: {exc}"
        return result
