"""Helpers for unified history data exposed to the UI."""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

from backend.core.types import ScanType
from backend.platform.paths import resolve_legacy_compatible_data_path

logger = logging.getLogger(__name__)


def _as_text(value: Any) -> str:
    return "" if value is None else str(value)


def _as_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _db_path(db_path: Path | str | None = None) -> Path:
    return (
        Path(db_path)
        if db_path is not None
        else resolve_legacy_compatible_data_path("sentinel.db")
    )


def _connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    con = sqlite3.connect(str(_db_path(db_path)), timeout=5)
    con.row_factory = sqlite3.Row
    return con


def _sort_timestamp(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _as_text(row.get(key))
        if value:
            return value
    return ""


def _canonical_path(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return str(Path(str(value)).resolve(strict=False)).lower()
    except OSError:
        return os.path.abspath(str(value)).lower()


def _is_windows_system_path(path: str) -> bool:
    normalized = _canonical_path(path)
    if not normalized:
        return False
    system_root = _canonical_path(os.environ.get("SystemRoot") or r"C:\Windows")
    return (
        normalized == system_root
        or normalized.startswith(system_root + "\\")
        or normalized.startswith(system_root + "/")
    )


def _quarantine_source(item: dict[str, Any]) -> tuple[str, str]:
    raw = _as_text(item.get("enforcement_source")).strip().lower()
    detail = _as_text(item.get("source_detail")).strip().lower()
    reason = _as_text(item.get("action_reason")).strip().lower()

    if raw in {"rtp", "real_time_protection"}:
        return "rtp", "Real-Time Protection"
    if raw in {"scan_center", "scancenter"}:
        return "scan_center", "Scan Center"
    if raw in {"manual", "security_assistant", "ai_assistant"}:
        return "manual", "Manual Quarantine"
    if raw in {"legacy", "imported"}:
        return "legacy", "Legacy / Imported"
    if detail == "security_assistant":
        return "manual", "Manual Quarantine"
    if "rtp" in reason or "real-time protection" in reason:
        return "rtp", "Real-Time Protection"
    if "manual" in reason or "security assistant" in reason:
        return "manual", "Manual Quarantine"
    if not raw and not reason:
        return "legacy", "Legacy Record"
    return "unknown", "Unknown Source"


def _quarantine_metadata_quality(item: dict[str, Any], source_key: str) -> tuple[str, str]:
    if _as_text(item.get("metadata_quality")):
        quality = _as_text(item.get("metadata_quality"))
    else:
        has_decision = any(
            item.get(key) not in (None, "")
            for key in ("decision_score", "decision_verdict", "decision_action")
        )
        if source_key == "legacy":
            quality = "legacy_incomplete"
        elif source_key == "manual" and not has_decision:
            quality = "manual_record"
        elif has_decision and item.get("action_reason"):
            quality = "complete"
        elif not has_decision and not item.get("action_reason"):
            quality = "legacy_incomplete"
        else:
            quality = "partial"

    labels = {
        "complete": "Complete incident context",
        "partial": "Partial incident context",
        "manual_record": "Manual action entry",
        "legacy_incomplete": "Incomplete legacy metadata",
    }
    return quality, labels.get(quality, "Unknown metadata state")


def _quarantine_final_action_label(status: str) -> str:
    normalized = status.lower()
    if normalized == "restored":
        return "Restored"
    if normalized == "deleted":
        return "Permanently deleted"
    if normalized == "quarantined":
        return "Quarantined"
    return status or "Unknown"


def _quarantine_file_action(item: dict[str, Any], status: str) -> tuple[str, str, bool]:
    raw = _as_text(item.get("file_action")).strip().lower()
    inferred = False
    if not raw and status in {"quarantined", "restored", "deleted"}:
        raw = "quarantine_file"
        inferred = True

    labels = {
        "quarantine_file": "Quarantine file",
        "allow": "Allow",
        "delete_file": "Delete file",
    }
    if not raw:
        return "", "Not recorded", inferred
    return raw, labels.get(raw, raw.replace("_", " ").title()), inferred


def _join_missing_fields(fields: list[str]) -> str:
    if not fields:
        return ""
    if len(fields) == 1:
        return fields[0]
    if len(fields) == 2:
        return f"{fields[0]} and {fields[1]}"
    return ", ".join(fields[:-1]) + f", and {fields[-1]}"


def list_combined_scan_history(
    limit: int = 200,
    *,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Return a normalized combined file-scan history from all local sources."""
    normalized: list[dict[str, Any]] = []
    limit = max(1, int(limit))

    try:
        with _connect(db_path) as con:
            for row in con.execute(
                """SELECT * FROM scancenter_history
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,),
            ):
                item = dict(row)
                normalized.append(
                    {
                        "entry_id": f"scancenter:{_as_text(item.get('job_id'))}",
                        "source_key": "scancenter",
                        "source_label": "ScanCenter",
                        "created_at": _as_text(item.get("created_at")),
                        "file_name": _as_text(item.get("file_name")) or "(unknown)",
                        "sha256": _as_text(item.get("sha256")),
                        "verdict_risk": _as_text(item.get("verdict_risk")) or "Unknown",
                        "verdict_label": _as_text(item.get("verdict_label")),
                        "confidence": int(item.get("confidence") or 0),
                        "score": int(item.get("score") or 0),
                        "mode": _as_text(item.get("mode")) or "static",
                        "report_path": _as_text(item.get("report_path")),
                        "job_id": _as_text(item.get("job_id")),
                        "report_loader": "scancenter",
                    }
                )
    except sqlite3.OperationalError:
        logger.debug("scancenter_history table not available for unified history")
    except Exception as exc:
        logger.warning("Failed reading scancenter_history: %s", exc)

    try:
        with _connect(db_path) as con:
            for row in con.execute(
                """SELECT * FROM scan_history
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,),
            ):
                item = dict(row)
                normalized.append(
                    {
                        "entry_id": f"legacy:{_as_text(item.get('job_id'))}",
                        "source_key": "legacy",
                        "source_label": "Legacy Scan",
                        "created_at": _as_text(item.get("created_at")),
                        "file_name": _as_text(item.get("file_name")) or "(unknown)",
                        "sha256": _as_text(item.get("sha256")),
                        "verdict_risk": _as_text(item.get("verdict_risk")) or "Unknown",
                        "verdict_label": "",
                        "confidence": int(item.get("confidence") or 0),
                        "score": None,
                        "mode": "legacy",
                        "report_path": _as_text(item.get("report_path")),
                        "job_id": _as_text(item.get("job_id")),
                        "report_loader": "legacy",
                    }
                )
    except sqlite3.OperationalError:
        logger.debug("scan_history table not available for unified history")
    except Exception as exc:
        logger.warning("Failed reading legacy scan_history: %s", exc)

    normalized.sort(key=lambda row: _sort_timestamp(row, "created_at"), reverse=True)
    return normalized[:limit]


def list_url_history(scan_repo: Any, limit: int = 200) -> list[dict[str, Any]]:
    """Return normalized URL scan history from the shared scan repository."""
    rows: list[dict[str, Any]] = []
    limit = max(1, int(limit))
    url_type = ScanType.URL.value

    def _is_url_record(record: Any) -> bool:
        record_type = getattr(record, "type", None)
        value = getattr(record_type, "value", record_type)
        return value == url_type

    try:
        if hasattr(scan_repo, "get_by_type"):
            records = [
                rec for rec in scan_repo.get_by_type(ScanType.URL, limit=limit)
                if _is_url_record(rec)
            ][:limit]
        else:
            all_records = scan_repo.all(limit=max(limit * 2, 50))
            records = [
                rec
                for rec in all_records
                if _is_url_record(rec)
            ][:limit]
    except Exception as exc:
        logger.warning("Failed loading URL history: %s", exc)
        return []

    for rec in records:
        findings = getattr(rec, "findings", None) or {}
        verdict = _as_text(findings.get("verdict") or findings.get("verdict_label"))
        rows.append(
            {
                "id": getattr(rec, "id", None),
                "started_at": (
                    rec.started_at.isoformat()
                    if hasattr(rec.started_at, "isoformat")
                    else _as_text(getattr(rec, "started_at", ""))
                ),
                "finished_at": (
                    rec.finished_at.isoformat()
                    if getattr(rec, "finished_at", None) and hasattr(rec.finished_at, "isoformat")
                    else _as_text(getattr(rec, "finished_at", ""))
                ),
                "target": _as_text(getattr(rec, "target", "")),
                "status": _as_text(getattr(rec, "status", "")) or "unknown",
                "verdict": verdict or "Unknown",
                "score": int(findings.get("score") or 0),
                "report_path": _as_text(findings.get("report_path")),
                "threat_types": list(findings.get("threat_types") or []),
                "has_sandbox": bool(findings.get("has_sandbox")),
            }
        )

    rows.sort(key=lambda row: _sort_timestamp(row, "started_at", "finished_at"), reverse=True)
    return rows[:limit]


def list_quarantine_history(vault: Any) -> list[dict[str, Any]]:
    """Return a normalized quarantine audit trail newest-first."""
    try:
        entries = (
            vault.list_entries()
            if hasattr(vault, "list_entries")
            else vault.list_quarantined()
        )
    except Exception as exc:
        logger.warning("Failed loading quarantine history: %s", exc)
        return []

    normalized: list[dict[str, Any]] = []
    for entry in entries or []:
        item = dict(entry or {})
        status = _as_text(item.get("status")) or "unknown"
        source_key, source_label = _quarantine_source(item)
        quality_key, quality_label = _quarantine_metadata_quality(item, source_key)
        file_action_key, file_action_label, file_action_inferred = _quarantine_file_action(item, status)
        path = _as_text(item.get("original_path"))
        system_protected = bool(item.get("system_protected")) or _is_windows_system_path(path)
        decision_score = _as_optional_int(item.get("decision_score"))
        decision_verdict = _as_text(item.get("decision_verdict"))
        decision_action = _as_text(item.get("decision_action"))
        missing_decision_fields: list[str] = []
        if decision_score is None:
            missing_decision_fields.append("score")
        if not decision_verdict:
            missing_decision_fields.append("verdict")
        if not decision_action:
            missing_decision_fields.append("decision")
        decision_metadata_note = ""
        if missing_decision_fields:
            missing_fields_label = _join_missing_fields(missing_decision_fields)
            if quality_key == "legacy_incomplete":
                decision_metadata_note = (
                    "This legacy record does not include the original "
                    + missing_fields_label
                    + "."
                )
            elif source_key == "manual":
                decision_metadata_note = (
                    "This manual quarantine entry does not include a recorded "
                    + missing_fields_label
                    + "."
                )
            else:
                decision_metadata_note = (
                    "This quarantine record does not include the original "
                    + missing_fields_label
                    + "."
                )
        metadata_note = _as_text(item.get("metadata_note"))
        if not metadata_note and quality_key == "legacy_incomplete":
            metadata_note = (
                "This quarantine record predates complete incident metadata. "
                "Score, verdict, and source details were not recorded at quarantine time."
            )
        elif not metadata_note and quality_key == "manual_record":
            metadata_note = (
                "Manual quarantine record. The file action is known, but no scan verdict or score "
                "was recorded for this action."
            )
        path_trust_note = _as_text(item.get("path_trust_note"))
        if not path_trust_note and system_protected:
            path_trust_note = (
                "Protected Windows system path. Review carefully before restoring or deleting."
            )
        latest_activity = (
            _as_text(item.get("deleted_at"))
            or _as_text(item.get("restored_at"))
            or _as_text(item.get("quarantined_at"))
        )
        normalized.append(
            {
                "id": _as_text(item.get("id")),
                "status": status,
                "status_label": _quarantine_final_action_label(status),
                "original_name": _as_text(item.get("original_name")) or "(unknown)",
                "original_path": path,
                "sha256": _as_text(item.get("sha256")),
                "size_bytes": int(item.get("size_bytes") or 0),
                "quarantined_at": _as_text(item.get("quarantined_at")),
                "restored_at": _as_text(item.get("restored_at")),
                "deleted_at": _as_text(item.get("deleted_at")),
                "latest_activity_at": latest_activity,
                "decision_score": decision_score,
                "decision_score_label": (
                    str(decision_score) if decision_score is not None else "No score recorded"
                ),
                "decision_verdict": decision_verdict,
                "decision_verdict_label": decision_verdict or "No verdict recorded",
                "decision_action": decision_action,
                "decision_action_label": (
                    decision_action.replace("_", " ").title()
                    if decision_action
                    else "No decision recorded"
                ),
                "final_action": _quarantine_final_action_label(status),
                "final_action_label": _quarantine_final_action_label(status),
                "process_action": _as_text(item.get("process_action")),
                "file_action": file_action_key,
                "file_action_label": file_action_label,
                "file_action_inferred": file_action_inferred,
                "file_action_note": (
                    "Derived from current vault state because the original record did not store a file action."
                    if file_action_inferred
                    else ""
                ),
                "file_action_taken": _as_text(item.get("file_action_taken")) or ("quarantined" if file_action_key == "quarantine_file" else ""),
                "action_reason": _as_text(item.get("action_reason")),
                "action_reason_label": _as_text(item.get("action_reason")) or "No enforcement reason recorded.",
                "enforcement_source": source_key,
                "source_label": source_label,
                "source_detail": _as_text(item.get("source_detail")),
                "decision_metadata_note": decision_metadata_note,
                "process_name": _as_text(item.get("process_name")),
                "pid": _as_optional_int(item.get("pid")),
                "publisher": _as_text(item.get("publisher")),
                "signature_valid": item.get("signature_valid"),
                "metadata_quality": quality_key,
                "metadata_quality_label": quality_label,
                "metadata_note": metadata_note,
                "system_protected": system_protected,
                "path_class": _as_text(item.get("path_class")) or ("windows_system" if system_protected else ""),
                "path_trust_note": path_trust_note,
                "requested_by": _as_text(item.get("requested_by")),
                "can_restore": _as_text(item.get("status")) == "quarantined",
                "can_delete": _as_text(item.get("status")) == "quarantined",
            }
        )

    normalized.sort(
        key=lambda row: _sort_timestamp(
            row,
            "latest_activity_at",
            "quarantined_at",
        ),
        reverse=True,
    )
    return normalized


# ---------------------------------------------------------------------------
# Incident history with computed presentation fields
# ---------------------------------------------------------------------------

_PROTECTED_APP_KEYWORDS = frozenset(
    {"protected", "signed", "system", "mainstream", "trusted install", "trusted_install"}
)


def _effective_outcome(item: dict[str, Any]) -> str:
    """Map raw RTP enforcement fields to the true final outcome label.

    The raw ``decision_action`` from the scanner can say "block" while the
    enforcement pipeline silently downgraded the action to log-only because a
    guardrail fired (e.g. protected/signed app, incomplete decision metadata).
    This function returns the label that reflects what *actually happened*.
    """
    action_taken = _as_text(item.get("action_taken"))
    file_action_taken = _as_text(item.get("file_action_taken"))
    process_action = _as_text(item.get("process_action"))
    decision_action = _as_text(item.get("decision_action"))

    # True destructive outcomes
    if action_taken == "terminated" and file_action_taken == "quarantined":
        return "Quarantined"
    if action_taken == "terminated":
        return "Blocked"

    # OS blocked the kill attempt
    if action_taken in ("access_denied", "identity_unverified") and process_action == "kill_process":
        return "Block failed"
    if action_taken in ("identity_mismatch", "path_mismatch"):
        return "Skipped"

    # Process was not killed — determine why the enforcement was softened
    if process_action == "log_only" or action_taken == "logged_only":
        reason_lower = _as_text(item.get("action_reason")).lower()
        if any(kw in reason_lower for kw in _PROTECTED_APP_KEYWORDS):
            return "Allowed — protected app"
        return "Allowed — logged"

    if file_action_taken == "guardrail_allow":
        return "Allowed — guardrail"

    if decision_action == "allow" or action_taken == "allowed":
        return "Allowed"

    return "Recorded"


def _effective_verdict_label(item: dict[str, Any]) -> str:
    """Return a verdict label that reflects the guardrail downgrade context.

    When a block decision was downgraded to log-only/allow by a guardrail,
    labelling the incident as "Malicious" is misleading because no destructive
    action was taken.  In those cases we soften the label to "Suspicious" to
    indicate elevated suspicion without claiming confirmed malice.

    The raw ``decision_verdict`` is preserved in the record for auditing; only
    the display label is adjusted here.
    """
    raw_verdict = _as_text(item.get("decision_verdict"))
    action_taken = _as_text(item.get("action_taken"))
    file_action_taken = _as_text(item.get("file_action_taken"))
    process_action = _as_text(item.get("process_action"))

    # True destructive enforcement happened — preserve the original verdict
    if action_taken == "terminated" or file_action_taken == "quarantined":
        return raw_verdict or "Unknown"

    # Enforcement was downgraded — soften strong-negative verdicts because no
    # destructive action occurred against this executable
    lower = raw_verdict.lower()
    if lower in ("malicious", "likely malicious", "likely_malicious"):
        if process_action == "log_only" or action_taken in ("logged_only", "allowed"):
            return "Suspicious"
        if file_action_taken == "guardrail_allow":
            return "Suspicious"

    return raw_verdict or "Unknown"


def _is_guardrail_downgraded(item: dict[str, Any]) -> bool:
    """Return True when a block decision was downgraded by a guardrail."""
    if _as_text(item.get("decision_action")) != "block":
        return False
    action_taken = _as_text(item.get("action_taken"))
    file_action_taken = _as_text(item.get("file_action_taken"))
    process_action = _as_text(item.get("process_action"))
    if action_taken == "terminated" or file_action_taken == "quarantined":
        return False
    return (
        process_action in ("log_only", "allow")
        or action_taken in ("logged_only", "allowed")
        or file_action_taken == "guardrail_allow"
    )


def list_incident_history(
    limit: int = 200,
    *,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Return RTP incidents newest-first with computed presentation fields.

    Adds three computed fields to every row so the UI can display the *final
    effective outcome* rather than the raw scanner verdict:

    ``effective_outcome``
        Human-readable label for the true enforcement result, e.g.
        ``"Allowed — protected app"``, ``"Blocked"``, ``"Quarantined"``.

    ``effective_verdict_label``
        Verdict softened for guardrail-downgraded cases; ``"Malicious"`` is
        shown only when a destructive action actually occurred.

    ``is_guardrail_downgraded``
        ``True`` when the scanner said "block" but the guardrail prevented
        actual enforcement.

    The raw fields (``decision_verdict``, ``decision_action``, etc.) are
    preserved unchanged so the audit trail stays complete.
    """
    from backend.engines.history.incident_repo import IncidentHistoryRepo

    raw_rows = IncidentHistoryRepo(db_path).list_recent(limit=limit)
    result: list[dict[str, Any]] = []
    for item in raw_rows:
        row = dict(item)
        row["effective_outcome"] = _effective_outcome(row)
        row["effective_verdict_label"] = _effective_verdict_label(row)
        row["is_guardrail_downgraded"] = _is_guardrail_downgraded(row)
        result.append(row)
    return result
