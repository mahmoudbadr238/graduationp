"""Parse collected guest artifacts into a structured SandboxJobResult.

Reads:
  - <host_job_dir>/summary.json   (written by guest_agent.ps1)
  - <host_job_dir>/steps.jsonl    (line-delimited JSON, written by guest_agent.ps1)

Returns a partially-filled SandboxJobResult dict merged with static analysis.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .job_schema import SandboxJobResult, StaticAnalysisResult

logger = logging.getLogger(__name__)


def _safe_load_json(path: Path) -> dict[str, Any] | None:
    """Load JSON with UTF-8-SIG handling. Returns None on error."""
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8-sig") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning("Could not parse %s: %s", path, exc)
        return None


def _load_steps_jsonl(path: Path) -> list[dict]:
    """Load a .jsonl file (one JSON object per line)."""
    if not path.exists():
        return []
    steps = []
    with path.open(encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                steps.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return steps


def score_dynamic(guest_summary: dict[str, Any]) -> dict[str, Any]:
    """
    Rule-based scoring for dynamic (behavioral) analysis.
    Returns {"verdict": str, "score": int, "summary": str, "highlights": list}.
    """

    def _count(*keys: str) -> int:
        total = 0
        for key in keys:
            v = guest_summary.get(key)
            if isinstance(v, list):
                total += len(v)
        return total

    score = 0
    score += min(30, _count("alerts") * 10)
    score += min(20, _count("new_processes") * 4)
    score += min(20, _count("new_files", "modified_files") * 3)
    score += min(15, _count("new_connections") * 4)
    score += min(15, _count("errors") * 3)

    executed = bool(guest_summary.get("executed"))
    if not executed:
        score = max(0, score)  # no execution → keep raw static signals only

    if score >= 70:
        verdict = "Malicious"
    elif score >= 35:
        verdict = "Suspicious"
    elif score <= 10 and executed:
        verdict = "Benign"
    else:
        verdict = "Inconclusive"

    highlights: list[str] = []
    if not executed:
        highlights.append("Sample did not execute successfully.")
    alerts = _count("alerts")
    procs = _count("new_processes")
    files = _count("new_files", "modified_files")
    conns = _count("new_connections")
    errors = _count("errors")

    if alerts:
        highlights.append(f"{alerts} agent alert(s) raised.")
    if procs:
        highlights.append(f"{procs} new process(es) spawned during execution.")
    if files:
        highlights.append(f"{files} file creation/modification event(s) observed.")
    if conns:
        highlights.append(f"{conns} new network connection(s) observed.")
    if errors:
        highlights.append(f"{errors} error(s) recorded by guest agent.")
    if not highlights:
        highlights.append("No significant behavioral indicators observed.")

    duration = float(guest_summary.get("duration_sec", 0))
    exit_code = guest_summary.get("exit_code")

    summary_parts = [f"{verdict} ({score}/100)."]
    if duration:
        summary_parts.append(f"Duration: {duration:.1f}s.")
    if exit_code is not None:
        summary_parts.append(f"Exit code: {exit_code}.")
    summary_parts.extend(highlights[:2])

    return {
        "verdict": verdict,
        "score": score,
        "summary": " ".join(summary_parts),
        "highlights": highlights,
    }


def merge_verdicts(
    static_score: int, dynamic_score: int, static_verdict: str, dynamic_verdict: str
) -> tuple[str, int]:
    """Merge static + dynamic verdicts, taking the more alarming one."""
    order = {"Malicious": 3, "Suspicious": 2, "Inconclusive": 1, "Benign": 0}
    combined_score = min(100, static_score + dynamic_score // 2)
    final_verdict = (
        static_verdict
        if order.get(static_verdict, 0) >= order.get(dynamic_verdict, 0)
        else dynamic_verdict
    )
    return final_verdict, combined_score


def parse_artifacts(
    host_job_dir: Path,
    job_id: str,
    sample_path: str,
    static_result: StaticAnalysisResult | None = None,
) -> SandboxJobResult:
    """
    Parse all artifacts in host_job_dir and return a SandboxJobResult.

    Args:
        host_job_dir: Local directory where guest artifacts were copied.
        job_id: Unique job identifier string.
        sample_path: Original host path of the sample.
        static_result: Pre-computed static analysis (merged into result).
    """
    result: SandboxJobResult = {
        "job_id": job_id,
        "sample_path": sample_path,
        "sample_name": Path(sample_path).name,
        "run_dir": str(host_job_dir),
        "success": False,
        "error": "",
        "verdict": "Inconclusive",
        "score": 0,
        "summary": "No analysis data available.",
        "highlights": [],
        "steps": [],
    }

    # Load static analysis
    if static_result:
        result["static"] = static_result
        sta_verdict = "Inconclusive"
        sta_score = 0
        if static_result.get("defender_detected"):
            sta_verdict = "Malicious"
            sta_score = 80
    else:
        sta_verdict = "Inconclusive"
        sta_score = 0

    # Load guest summary
    summary_path = host_job_dir / "summary.json"
    guest_summary = _safe_load_json(summary_path)

    if guest_summary is None:
        result["error"] = (
            "summary.json was not produced by the guest agent. "
            "Possible causes: guest agent failed to launch, PowerShell execution policy blocked it, "
            "or the job folder could not be created in the guest."
        )
        result["highlights"] = [result["error"]]
        result["summary"] = result["error"]
        if static_result:
            result["dynamic"] = {}
            # Fall back to static-only scoring
            if static_result.get("defender_detected"):
                result.update(
                    {
                        "verdict": "Malicious",
                        "score": 80,
                        "summary": "[Static only] Defender detected threat: "
                        + str(static_result.get("defender_threat", "unknown")),
                        "highlights": ["Defender detected a threat in the file."],
                        "success": True,
                    }
                )
            else:
                result.update(
                    {
                        "verdict": "Inconclusive",
                        "score": sta_score,
                        "summary": "Dynamic analysis failed; static analysis inconclusive.",
                        "success": False,
                    }
                )
        return result

    # Score dynamic
    dyn_scoring = score_dynamic(guest_summary)
    result["dynamic"] = guest_summary  # type: ignore[typeddict-item]

    # Merge with static
    final_verdict, final_score = merge_verdicts(
        sta_score, dyn_scoring["score"], sta_verdict, dyn_scoring["verdict"]
    )

    # Combine highlights
    highlights = list(dyn_scoring["highlights"])
    if static_result and static_result.get("defender_detected"):
        highlights.insert(
            0, f"Defender: {static_result.get('defender_threat', 'threat detected')}"
        )

    result.update(
        {
            "success": True,
            "error": "",
            "verdict": final_verdict,
            "score": final_score,
            "summary": dyn_scoring["summary"],
            "highlights": highlights[:8],
        }
    )

    # Load agent step log (best-effort)
    steps_path = host_job_dir / "steps.jsonl"
    result["steps"] = _load_steps_jsonl(steps_path)

    # Load errors from guest errors.txt if any
    errors_path = host_job_dir / "errors.txt"
    if errors_path.exists():
        try:
            err_text = errors_path.read_text(encoding="utf-8-sig").strip()
            if err_text:
                result["error"] = err_text[:2000]
        except OSError:
            pass

    # Convenience flag for QML ("IOCs" badge)
    iocs_found = False
    if guest_summary:
        iocs_found = bool(
            guest_summary.get("new_files")
            or guest_summary.get("new_connections")
            or guest_summary.get("new_processes")
        )
    result["iocs_found"] = iocs_found  # type: ignore[typeddict-unknown-key]

    return result
