"""Shared final-decision normalization for scan results and RTP enforcement."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DEFAULT_BLOCK_THRESHOLD = 60

_POLICIES: dict[str, tuple[tuple[int, str, str], ...]] = {
    "static": (
        (19, "safe", "Safe"),
        (59, "suspicious", "Suspicious"),
        (100, "malicious", "Malicious"),
    ),
    "scoring": (
        (20, "safe", "Safe"),
        (50, "suspicious", "Suspicious"),
        (80, "likely_malicious", "Likely Malicious"),
        (100, "malicious", "Malicious"),
    ),
}

_VERDICT_ALIASES: dict[str, tuple[str, str]] = {
    "safe": ("safe", "Safe"),
    "clean": ("safe", "Safe"),
    "benign": ("safe", "Safe"),
    "suspicious": ("suspicious", "Suspicious"),
    "likely_malicious": ("likely_malicious", "Likely Malicious"),
    "likely malicious": ("likely_malicious", "Likely Malicious"),
    "malicious": ("malicious", "Malicious"),
    "unknown": ("unknown", "Unknown"),
    "inconclusive": ("unknown", "Unknown"),
}


@dataclass(frozen=True)
class FinalDecision:
    """Canonical decision shared between UI reporting and enforcement."""

    score: int
    verdict_code: str
    verdict_label: str
    action: str
    action_reason: str
    enforcement_source: str
    enforcement_threshold: int
    confidence: int | None = None
    override_type: str = ""
    triggered_rule: str = ""
    triggered_rules: list[str] = field(default_factory=list)
    policy: str = "static"
    raw_verdict: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "verdict_code": self.verdict_code,
            "verdict_label": self.verdict_label,
            "action": self.action,
            "action_reason": self.action_reason,
            "enforcement_source": self.enforcement_source,
            "enforcement_threshold": self.enforcement_threshold,
            "confidence": self.confidence,
            "override_type": self.override_type,
            "triggered_rule": self.triggered_rule,
            "triggered_rules": list(self.triggered_rules),
            "policy": self.policy,
            "raw_verdict": self.raw_verdict,
        }


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _score_band(policy: str, score: int) -> tuple[str, str]:
    bands = _POLICIES.get(policy, _POLICIES["static"])
    for upper_bound, verdict_code, verdict_label in bands:
        if score <= upper_bound:
            return verdict_code, verdict_label
    return bands[-1][1], bands[-1][2]


def _normalize_verdict(verdict: Any) -> tuple[str, str]:
    text = str(verdict or "").strip().lower()
    return _VERDICT_ALIASES.get(text, ("unknown", "Unknown"))


def _result_value(result: Any, key: str, default: Any = None) -> Any:
    if isinstance(result, dict):
        return result.get(key, default)
    return getattr(result, key, default)


def extract_triggered_rules(result: Any) -> list[str]:
    """Best-effort extraction of engine/rule hints for diagnostics."""
    rules: list[str] = []

    clamav = _result_value(result, "clamav", {})
    if isinstance(clamav, dict) and clamav.get("infected"):
        signature = str(clamav.get("signature") or "detected").strip()
        rules.append(f"ClamAV:{signature}")

    groq = _result_value(result, "groq_analysis", {})
    if isinstance(groq, dict) and groq.get("verdict"):
        rules.append(f"Groq:{groq.get('verdict')}")

    findings = _result_value(result, "findings", [])
    if isinstance(findings, list):
        for finding in findings[:3]:
            title = ""
            if isinstance(finding, dict):
                title = str(finding.get("title") or "").strip()
            else:
                title = str(getattr(finding, "title", "") or "").strip()
            if title:
                rules.append(title)

    deduped: list[str] = []
    seen: set[str] = set()
    for rule in rules:
        if rule and rule not in seen:
            seen.add(rule)
            deduped.append(rule)
    return deduped


def build_final_decision(
    *,
    score: Any,
    verdict: Any = None,
    confidence: Any = None,
    policy: str = "static",
    block_threshold: int = DEFAULT_BLOCK_THRESHOLD,
    triggered_rules: list[str] | None = None,
    scan_failed: bool = False,
    explicit_action: str | None = None,
    override_type: str = "",
    action_reason: str | None = None,
    enforcement_source: str | None = None,
) -> FinalDecision:
    """Normalize score/verdict/action into one final decision object."""
    final_score = max(0, min(100, _coerce_int(score)))
    raw_verdict = str(verdict or "").strip()

    if scan_failed:
        return FinalDecision(
            score=final_score,
            verdict_code="unknown",
            verdict_label="Unknown",
            action="allow",
            action_reason=action_reason or "Scan failed; automatic blocking is disabled.",
            enforcement_source=enforcement_source or "scan_error",
            enforcement_threshold=block_threshold,
            confidence=_coerce_int(confidence) if confidence is not None else None,
            override_type=override_type,
            triggered_rule=(triggered_rules or [""])[0],
            triggered_rules=list(triggered_rules or []),
            policy=policy,
            raw_verdict=raw_verdict,
        )

    derived_code, derived_label = _score_band(policy, final_score)
    input_code, _input_label = _normalize_verdict(raw_verdict)
    if input_code != "unknown" and input_code != derived_code:
        raw_verdict = raw_verdict or _input_label

    if explicit_action and explicit_action != "allow":
        final_action = explicit_action
        final_reason = action_reason or "Explicit override rule triggered enforcement."
        source = enforcement_source or "explicit_override"
    elif final_score >= block_threshold:
        final_action = "block"
        final_reason = action_reason or (
            f"Threat score {final_score}/100 reached the block threshold "
            f"({block_threshold}/100)."
        )
        source = enforcement_source or "score_threshold"
    else:
        final_action = "allow"
        final_reason = action_reason or (
            f"Threat score {final_score}/100 stayed below the block threshold "
            f"({block_threshold}/100)."
        )
        source = enforcement_source or "score_threshold"

    rule_list = list(triggered_rules or [])
    return FinalDecision(
        score=final_score,
        verdict_code=derived_code,
        verdict_label=derived_label,
        action=final_action,
        action_reason=final_reason,
        enforcement_source=source,
        enforcement_threshold=block_threshold,
        confidence=_coerce_int(confidence) if confidence is not None else None,
        override_type=override_type,
        triggered_rule=rule_list[0] if rule_list else "",
        triggered_rules=rule_list,
        policy=policy,
        raw_verdict=raw_verdict,
    )


def decision_from_scan_result(
    result: Any,
    *,
    policy: str = "static",
    block_threshold: int = DEFAULT_BLOCK_THRESHOLD,
) -> FinalDecision:
    """Build a final decision from a scan result object or dict."""
    existing = _result_value(result, "final_decision", {})
    if isinstance(existing, dict) and existing.get("score") is not None:
        return build_final_decision(
            score=existing.get("score", _result_value(result, "score", 0)),
            verdict=existing.get("verdict_label", existing.get("verdict_code")),
            confidence=existing.get("confidence"),
            policy=str(existing.get("policy") or policy),
            block_threshold=_coerce_int(
                existing.get("enforcement_threshold"),
                block_threshold,
            ),
            triggered_rules=list(existing.get("triggered_rules") or []),
            scan_failed=_result_value(result, "verdict", "") == "Unknown"
            and bool(_result_value(result, "errors", [])),
            explicit_action=(
                existing.get("action")
                if existing.get("enforcement_source") == "explicit_override"
                else None
            ),
            override_type=str(existing.get("override_type") or ""),
            action_reason=str(existing.get("action_reason") or ""),
            enforcement_source=str(existing.get("enforcement_source") or ""),
        )

    return build_final_decision(
        score=_result_value(result, "score", 0),
        verdict=_result_value(result, "verdict", "Unknown"),
        policy=policy,
        block_threshold=block_threshold,
        triggered_rules=extract_triggered_rules(result),
        scan_failed=_result_value(result, "verdict", "") == "Unknown"
        and bool(_result_value(result, "errors", [])),
    )

