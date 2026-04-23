"""Focused tests for unified History data sources."""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from backend.core.types import ScanRecord, ScanType
from backend.engines.history.incident_repo import IncidentHistoryRepo
from backend.engines.history.unified_history import (
    list_combined_scan_history,
    list_incident_history,
    list_quarantine_history,
    list_url_history,
)
from backend.engines.scancenter.history_repo import HistoryRepo
from backend.engines.scanning.quarantine_manager import QuarantineVault


def test_combined_scan_history_merges_scancenter_and_legacy(tmp_path: Path) -> None:
    db_path = tmp_path / "sentinel.db"
    with sqlite3.connect(db_path) as con:
        con.execute(HistoryRepo.TABLE_DDL)
        con.execute(
            """CREATE TABLE scan_history (
                job_id TEXT PRIMARY KEY,
                file_name TEXT,
                sha256 TEXT,
                verdict_risk TEXT,
                confidence INTEGER,
                created_at TEXT,
                report_path TEXT
            )"""
        )
        con.execute(
            """INSERT INTO scancenter_history
               (job_id, file_name, sha256, file_type, verdict_risk, verdict_label,
                confidence, score, mode, created_at, duration_sec, report_path, engines_summary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "new-job",
                "modern.exe",
                "a" * 64,
                "exe",
                "High",
                "Malicious",
                94,
                88,
                "static",
                "2026-04-23T10:00:00",
                1.2,
                "modern-report.json",
                "ClamAV,Static",
            ),
        )
        con.execute(
            """INSERT INTO scan_history
               (job_id, file_name, sha256, verdict_risk, confidence, created_at, report_path)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                "old-job",
                "legacy.exe",
                "b" * 64,
                "Low",
                61,
                "2026-04-22T10:00:00",
                "legacy-report.json",
            ),
        )
        con.commit()

    rows = list_combined_scan_history(limit=10, db_path=db_path)

    assert [row["source_key"] for row in rows] == ["scancenter", "legacy"]
    assert rows[0]["file_name"] == "modern.exe"
    assert rows[0]["score"] == 88
    assert rows[1]["mode"] == "legacy"
    assert rows[1]["report_loader"] == "legacy"


def test_url_history_filters_url_records_and_normalizes_findings() -> None:
    now = datetime.now(timezone.utc)
    records = [
        ScanRecord(
            id=11,
            started_at=now,
            finished_at=now + timedelta(seconds=2),
            type=ScanType.URL,
            target="https://example.test",
            status="completed",
            findings={
                "verdict": "Suspicious",
                "score": 34,
                "threat_types": ["malware", "phishing"],
                "report_path": "url-report.json",
                "has_sandbox": True,
            },
            meta={},
        ),
        ScanRecord(
            id=12,
            started_at=now,
            finished_at=now,
            type=ScanType.FILE,
            target="C:/temp/file.exe",
            status="completed",
            findings={},
            meta={},
        ),
    ]
    repo = SimpleNamespace(
        get_by_type=lambda scan_type, limit=100: (
            records[:limit] if scan_type == ScanType.URL else []
        )
    )

    rows = list_url_history(repo, limit=10)

    assert len(rows) == 1
    assert rows[0]["target"] == "https://example.test"
    assert rows[0]["verdict"] == "Suspicious"
    assert rows[0]["score"] == 34
    assert rows[0]["threat_types"] == ["malware", "phishing"]
    assert rows[0]["has_sandbox"] is True


def test_quarantine_history_returns_full_ledger_including_restored_and_deleted(tmp_path: Path) -> None:
    vault = QuarantineVault(tmp_path / "vault")
    sample_a = tmp_path / "sample-a.bin"
    sample_b = tmp_path / "sample-b.bin"
    sample_a.write_bytes(b"alpha")
    sample_b.write_bytes(b"beta")

    first = vault.quarantine_file(
        sample_a,
        metadata={
            "enforcement_source": "rtp",
            "decision_score": 92,
            "decision_verdict": "Malicious",
            "decision_action": "block",
            "file_action": "quarantine_file",
            "process_action": "kill_process",
            "action_reason": "RTP quarantine after confirmed malicious verdict.",
        },
    )
    second = vault.quarantine_file(sample_b, metadata={"action_reason": "Manual quarantine"})

    assert first["success"] is True
    assert second["success"] is True

    vault.restore_file(first["quarantine_id"])
    vault.delete_permanently(second["quarantine_id"])

    rows = list_quarantine_history(vault)
    statuses = {row["id"]: row["status"] for row in rows}

    assert statuses[first["quarantine_id"]] == "restored"
    assert statuses[second["quarantine_id"]] == "deleted"
    assert all("latest_activity_at" in row for row in rows)


def test_quarantine_history_exposes_decision_fields_and_manager_flags(tmp_path: Path) -> None:
    vault = QuarantineVault(tmp_path / "vault")
    sample = tmp_path / "payload.exe"
    sample.write_bytes(b"payload")

    result = vault.quarantine_file(
        sample,
        metadata={
            "decision_score": 88,
            "decision_verdict": "High",
            "decision_action": "block",
            "process_action": "kill_process",
            "file_action": "quarantine_file",
            "action_reason": "ClamAV confirmed malware.",
            "enforcement_source": "rtp",
            "process_name": "payload.exe",
            "pid": 7331,
            "publisher": "Unknown",
        },
    )

    assert result["success"] is True

    rows = list_quarantine_history(vault)

    assert len(rows) == 1
    assert rows[0]["decision_score"] == 88
    assert rows[0]["decision_verdict"] == "High"
    assert rows[0]["decision_action"] == "block"
    assert rows[0]["final_action"] == "Quarantined"
    assert rows[0]["process_action"] == "kill_process"
    assert rows[0]["enforcement_source"] == "rtp"
    assert rows[0]["source_label"] == "Real-Time Protection"
    assert rows[0]["file_action"] == "quarantine_file"
    assert rows[0]["file_action_label"] == "Quarantine file"
    assert rows[0]["can_restore"] is True
    assert rows[0]["can_delete"] is True


def test_manual_quarantine_records_source_and_cleaner_defaults(tmp_path: Path) -> None:
    vault = QuarantineVault(tmp_path / "vault")
    sample = tmp_path / "manual.bin"
    sample.write_bytes(b"manual")

    result = vault.quarantine_file(sample)
    assert result["success"] is True

    rows = list_quarantine_history(vault)
    assert rows[0]["enforcement_source"] == "manual"
    assert rows[0]["source_label"] == "Manual Quarantine"
    assert rows[0]["decision_score"] is None
    assert rows[0]["decision_score_label"] == "No score recorded"
    assert rows[0]["decision_verdict_label"] == "No verdict recorded"
    assert rows[0]["decision_action_label"] == "No decision recorded"
    assert rows[0]["decision_metadata_note"] == (
        "This manual quarantine entry does not include a recorded score, verdict, and decision."
    )
    assert rows[0]["file_action"] == "quarantine_file"
    assert rows[0]["file_action_label"] == "Quarantine file"
    assert rows[0]["metadata_quality"] == "manual_record"


def test_legacy_quarantine_record_is_marked_incomplete(tmp_path: Path) -> None:
    vault = QuarantineVault(tmp_path / "vault")
    vault._append_entry(
        {
            "id": "legacy-entry",
            "original_path": r"C:\Windows\System32\smartscreen.exe",
            "original_name": "smartscreen.exe",
            "sha256": "a" * 64,
            "size_bytes": 1234,
            "quarantined_at": "2026-04-22T10:00:00+00:00",
            "vault_file": str(tmp_path / "vault" / "legacy-entry.quarantine"),
            "status": "quarantined",
        }
    )

    rows = list_quarantine_history(vault)
    assert rows[0]["id"] == "legacy-entry"
    assert rows[0]["enforcement_source"] == "legacy"
    assert rows[0]["source_label"] == "Legacy Record"
    assert rows[0]["metadata_quality"] == "legacy_incomplete"
    assert rows[0]["decision_score_label"] == "No score recorded"
    assert rows[0]["decision_metadata_note"] == (
        "This legacy record does not include the original score, verdict, and decision."
    )
    assert rows[0]["file_action"] == "quarantine_file"
    assert rows[0]["file_action_inferred"] is True
    assert rows[0]["file_action_note"] == (
        "Derived from current vault state because the original record did not store a file action."
    )
    assert rows[0]["path_trust_note"]


def test_protected_windows_system_file_requires_stronger_evidence(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("backend.engines.scanning.quarantine_manager.sys.platform", "win32")
    monkeypatch.setenv("SystemRoot", str(tmp_path / "Windows"))
    monkeypatch.setattr(
        "backend.engines.scanning.quarantine_manager._probe_windows_signature",
        lambda _path: (True, "Microsoft Windows"),
    )

    system_dir = tmp_path / "Windows" / "System32"
    system_dir.mkdir(parents=True)
    sample = system_dir / "smartscreen.exe"
    sample.write_bytes(b"trusted")

    vault = QuarantineVault(tmp_path / "vault")
    result = vault.quarantine_file(sample)

    assert result["success"] is False
    assert "protected Windows system binaries" in result["message"]
    assert sample.exists()
    assert vault.list_entries() == []


def test_protected_windows_system_file_requires_explicit_override_for_quarantine(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("backend.engines.scanning.quarantine_manager.sys.platform", "win32")
    monkeypatch.setenv("SystemRoot", str(tmp_path / "Windows"))
    monkeypatch.setattr(
        "backend.engines.scanning.quarantine_manager._probe_windows_signature",
        lambda _path: (True, "Microsoft Windows"),
    )

    system_dir = tmp_path / "Windows" / "System32"
    system_dir.mkdir(parents=True)
    sample = system_dir / "smartscreen.exe"
    sample.write_bytes(b"trusted")

    vault = QuarantineVault(tmp_path / "vault")
    result = vault.quarantine_file(
        sample,
        metadata={
            "enforcement_source": "rtp",
            "decision_action": "block",
            "decision_verdict": "Malicious",
            "decision_score": 95,
            "file_action": "quarantine_file",
            "action_reason": "ClamAV confirmed malware.",
            "strong_evidence": True,
            "decision_enforcement_source": "explicit_override",
            "override_type": "hard_rule",
            "allow_protected_quarantine": True,
        },
    )

    assert result["success"] is True
    rows = list_quarantine_history(vault)
    assert rows[0]["enforcement_source"] == "rtp"
    assert rows[0]["decision_action"] == "block"
    assert rows[0]["metadata_quality"] == "complete"


def test_protected_program_files_binary_is_blocked_for_manual_quarantine(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("backend.engines.scanning.quarantine_manager.sys.platform", "win32")
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "Program Files"))
    monkeypatch.setattr(
        "backend.engines.scanning.quarantine_manager._probe_windows_signature",
        lambda _path: (True, "Brave Software, Inc."),
    )

    program_dir = tmp_path / "Program Files" / "BraveSoftware" / "Brave-Browser" / "Application"
    program_dir.mkdir(parents=True)
    sample = program_dir / "brave.exe"
    sample.write_bytes(b"trusted")

    vault = QuarantineVault(tmp_path / "vault")
    result = vault.quarantine_file(
        sample,
        metadata={
            "enforcement_source": "manual",
            "source_detail": "security_assistant",
        },
    )

    assert result["success"] is False
    assert "trusted signed windows applications" in result["message"].lower()
    assert sample.exists()
    assert vault.list_entries() == []


def test_automatic_quarantine_rejects_incomplete_decision_metadata(tmp_path: Path) -> None:
    vault = QuarantineVault(tmp_path / "vault")
    sample = tmp_path / "payload.bin"
    sample.write_bytes(b"payload")

    result = vault.quarantine_file(
        sample,
        metadata={
            "enforcement_source": "rtp",
            "decision_action": "block",
            "decision_verdict": "Unknown",
            "decision_score": 0,
            "file_action": "quarantine_file",
            "action_reason": "Scan incomplete.",
        },
    )

    assert result["success"] is False
    assert "requires a positive final threat score" in result["message"].lower()
    assert sample.exists()
    assert vault.list_entries() == []


def test_restore_deleted_entry_is_rejected_truthfully(tmp_path: Path) -> None:
    vault = QuarantineVault(tmp_path / "vault")
    sample = tmp_path / "payload.bin"
    sample.write_bytes(b"payload")

    result = vault.quarantine_file(sample)
    assert result["success"] is True

    delete_result = vault.delete_permanently(result["quarantine_id"])
    assert delete_result["success"] is True

    restore_result = vault.restore_file(result["quarantine_id"])
    assert restore_result["success"] is False
    assert "cannot be restored" in restore_result["message"]

    entries = vault.list_entries()
    assert entries[0]["status"] == "deleted"


def test_delete_restored_entry_is_rejected_truthfully(tmp_path: Path) -> None:
    vault = QuarantineVault(tmp_path / "vault")
    sample = tmp_path / "payload.bin"
    sample.write_bytes(b"payload")

    result = vault.quarantine_file(sample)
    assert result["success"] is True

    restore_result = vault.restore_file(result["quarantine_id"])
    assert restore_result["success"] is True

    delete_result = vault.delete_permanently(result["quarantine_id"])
    assert delete_result["success"] is False
    assert "already restored" in delete_result["message"]

    entries = vault.list_entries()
    assert entries[0]["status"] == "restored"


def test_restore_and_delete_results_expose_structured_ui_fields(tmp_path: Path) -> None:
    vault = QuarantineVault(tmp_path / "vault")
    sample = tmp_path / "payload.bin"
    sample.write_bytes(b"payload")

    result = vault.quarantine_file(sample, metadata={"enforcement_source": "manual"})
    assert result["success"] is True

    restore_result = vault.restore_file(result["quarantine_id"])
    assert restore_result["success"] is True
    assert restore_result["message"] == "File restored successfully."
    assert restore_result["original_path"].endswith("payload.bin")
    assert restore_result["restored_sha256"]
    assert restore_result["integrity_verified"] is True

    second = tmp_path / "payload-2.bin"
    second.write_bytes(b"payload-2")
    second_result = vault.quarantine_file(second, metadata={"enforcement_source": "manual"})
    delete_result = vault.delete_permanently(second_result["quarantine_id"])
    assert delete_result["success"] is True
    assert delete_result["message"] == "Vault payload permanently deleted."
    assert delete_result["audit_retained"] is True


def test_incident_history_repo_round_trip(tmp_path: Path) -> None:
    repo = IncidentHistoryRepo(tmp_path / "sentinel.db")
    repo.append(
        {
            "occurred_at": "2026-04-23T12:00:00+00:00",
            "process_name": "brave.exe",
            "executable_path": "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe",
            "pid": 4242,
            "threat_score": 72,
            "decision_verdict": "High",
            "decision_action": "block",
            "process_action": "kill_process",
            "file_action": "quarantine_file",
            "action_reason": "Strong corroborating evidence authorizes quarantine.",
            "action_taken": "terminated",
            "file_action_taken": "quarantined",
            "sha256": "c" * 64,
            "publisher": "Brave Software, Inc.",
            "signature_valid": True,
            "matched_rules": ["clamav_positive"],
        },
        raw_message="structured incident",
    )

    rows = repo.list_recent(limit=10)

    assert len(rows) == 1
    assert rows[0]["process_name"] == "brave.exe"
    assert rows[0]["signature_valid"] is True
    assert rows[0]["matched_rules"] == ["clamav_positive"]


def _make_incident_db(tmp_path: Path, rows: list[dict]) -> Path:
    """Seed an in-memory-style incident DB for list_incident_history tests."""
    db = tmp_path / "sentinel.db"
    repo = IncidentHistoryRepo(db)
    for row in rows:
        repo.append(row)
    return db


def test_list_incident_history_protected_app_is_not_malicious(tmp_path: Path) -> None:
    """mousocoreworker.exe / amdinstallmanager.exe: guardrail downgrade must show
    'Allowed — protected app' and 'Suspicious', never 'Malicious' or 'Blocked'."""
    db = _make_incident_db(
        tmp_path,
        [
            {
                "occurred_at": "2026-04-23T10:00:00+00:00",
                "process_name": "mousocoreworker.exe",
                "executable_path": r"C:\Windows\System32\MoUsoCoreWorker.exe",
                "pid": 1234,
                "threat_score": 78,
                "decision_verdict": "Malicious",
                "decision_action": "block",
                "process_action": "log_only",
                "file_action": "allow",
                "action_reason": (
                    "Threat score 78/100 reached the block threshold. "
                    "Enforcement downgraded to log_only because this is a protected "
                    "signed/system or mainstream installed application. "
                    "Sentinel requires an explicit override before taking "
                    "destructive action against this class of software."
                ),
                "action_taken": "logged_only",
                "file_action_taken": "guardrail_allow",
                "sha256": "a" * 64,
                "publisher": "Microsoft Windows",
                "signature_valid": True,
            }
        ],
    )

    rows = list_incident_history(db_path=db)

    assert len(rows) == 1
    row = rows[0]

    # Effective outcome must NOT say Blocked or Flagged
    assert row["effective_outcome"] == "Allowed — protected app"
    assert "blocked" not in row["effective_outcome"].lower()
    assert "flagged" not in row["effective_outcome"].lower()

    # Effective verdict must NOT say Malicious
    assert row["effective_verdict_label"] == "Suspicious"
    assert "malicious" not in row["effective_verdict_label"].lower()

    # Guardrail flag must be set
    assert row["is_guardrail_downgraded"] is True

    # Raw fields preserved for audit
    assert row["decision_verdict"] == "Malicious"
    assert row["decision_action"] == "block"
    assert row["process_action"] == "log_only"
    assert row["file_action_taken"] == "guardrail_allow"


def test_list_incident_history_amd_signed_install_is_not_malicious(tmp_path: Path) -> None:
    """amdinstallmanager.exe from Program Files: signed install guardrail."""
    db = _make_incident_db(
        tmp_path,
        [
            {
                "occurred_at": "2026-04-23T11:00:00+00:00",
                "process_name": "amdinstallmanager.exe",
                "executable_path": r"C:\Program Files\AMD\CIM\bin\amdinstallmanager.exe",
                "pid": 5678,
                "threat_score": 65,
                "decision_verdict": "Malicious",
                "decision_action": "block",
                "process_action": "log_only",
                "file_action": "allow",
                "action_reason": (
                    "Threat score 65/100 reached the block threshold. "
                    "Enforcement downgraded to log_only because this is a protected "
                    "signed/system or mainstream installed application."
                ),
                "action_taken": "logged_only",
                "file_action_taken": "guardrail_allow",
                "sha256": "b" * 64,
                "publisher": "Advanced Micro Devices, Inc.",
                "signature_valid": True,
            }
        ],
    )

    rows = list_incident_history(db_path=db)

    row = rows[0]
    assert row["effective_outcome"] == "Allowed — protected app"
    assert row["effective_verdict_label"] == "Suspicious"
    assert row["is_guardrail_downgraded"] is True


def test_list_incident_history_true_block_preserves_malicious(tmp_path: Path) -> None:
    """Actual malware that was terminated and quarantined must still show 'Malicious'."""
    db = _make_incident_db(
        tmp_path,
        [
            {
                "occurred_at": "2026-04-23T12:00:00+00:00",
                "process_name": "dropper.exe",
                "executable_path": r"C:\Temp\dropper.exe",
                "pid": 9999,
                "threat_score": 92,
                "decision_verdict": "Malicious",
                "decision_action": "block",
                "process_action": "kill_process",
                "file_action": "quarantine_file",
                "action_reason": "ClamAV confirmed malware. Strong corroborating evidence.",
                "action_taken": "terminated",
                "file_action_taken": "quarantined",
                "sha256": "c" * 64,
                "publisher": "",
                "signature_valid": None,
            }
        ],
    )

    rows = list_incident_history(db_path=db)

    row = rows[0]
    assert row["effective_outcome"] == "Quarantined"
    assert row["effective_verdict_label"] == "Malicious"
    assert row["is_guardrail_downgraded"] is False


def test_list_incident_history_kill_only_no_quarantine(tmp_path: Path) -> None:
    """Process terminated but file not quarantined → 'Blocked', keeps raw verdict."""
    db = _make_incident_db(
        tmp_path,
        [
            {
                "occurred_at": "2026-04-23T13:00:00+00:00",
                "process_name": "payload.exe",
                "executable_path": r"C:\Temp\payload.exe",
                "pid": 7777,
                "threat_score": 75,
                "decision_verdict": "Malicious",
                "decision_action": "block",
                "process_action": "kill_process",
                "file_action": "allow",
                "action_reason": "Score-only block. File quarantine skipped.",
                "action_taken": "terminated",
                "file_action_taken": "allowed",
                "sha256": "d" * 64,
                "publisher": "",
                "signature_valid": None,
            }
        ],
    )

    rows = list_incident_history(db_path=db)

    row = rows[0]
    assert row["effective_outcome"] == "Blocked"
    assert row["effective_verdict_label"] == "Malicious"
    assert row["is_guardrail_downgraded"] is False


def test_list_incident_history_incomplete_decision_stays_logged(tmp_path: Path) -> None:
    """Block with incomplete decision metadata downgraded to log_only (generic, not protected app)."""
    db = _make_incident_db(
        tmp_path,
        [
            {
                "occurred_at": "2026-04-23T14:00:00+00:00",
                "process_name": "unknown.exe",
                "executable_path": r"C:\Users\user\Downloads\unknown.exe",
                "pid": 4444,
                "threat_score": 65,
                "decision_verdict": "Malicious",
                "decision_action": "block",
                "process_action": "log_only",
                "file_action": "allow",
                "action_reason": (
                    "The final decision does not request blocking. "
                    "Enforcement downgraded to log_only until a complete final decision is available."
                ),
                "action_taken": "logged_only",
                "file_action_taken": "guardrail_allow",
                "sha256": "e" * 64,
                "publisher": "",
                "signature_valid": None,
            }
        ],
    )

    rows = list_incident_history(db_path=db)

    row = rows[0]
    # Not a "protected app" because the reason text doesn't mention protected/signed/system
    assert row["effective_outcome"] == "Allowed — logged"
    assert row["effective_verdict_label"] == "Suspicious"
    assert row["is_guardrail_downgraded"] is True


def test_list_incident_history_below_threshold_allows_safely(tmp_path: Path) -> None:
    """Score below threshold → action=allow → outcome 'Allowed', verdict unchanged."""
    db = _make_incident_db(
        tmp_path,
        [
            {
                "occurred_at": "2026-04-23T15:00:00+00:00",
                "process_name": "legit.exe",
                "executable_path": r"C:\Program Files\App\legit.exe",
                "pid": 3333,
                "threat_score": 30,
                "decision_verdict": "Suspicious",
                "decision_action": "allow",
                "process_action": "allow",
                "file_action": "allow",
                "action_reason": "Threat score 30/100 stayed below the block threshold.",
                "action_taken": "allowed",
                "file_action_taken": "allowed",
                "sha256": "f" * 64,
                "publisher": "Trusted Corp",
                "signature_valid": True,
            }
        ],
    )

    rows = list_incident_history(db_path=db)

    row = rows[0]
    assert row["effective_outcome"] == "Allowed"
    assert row["effective_verdict_label"] == "Suspicious"
    assert row["is_guardrail_downgraded"] is False


def test_list_incident_history_adds_fields_without_removing_raw(tmp_path: Path) -> None:
    """Raw audit fields must be preserved alongside computed fields."""
    db = _make_incident_db(
        tmp_path,
        [
            {
                "occurred_at": "2026-04-23T16:00:00+00:00",
                "process_name": "sample.exe",
                "executable_path": r"C:\Temp\sample.exe",
                "pid": 1111,
                "threat_score": 80,
                "decision_verdict": "Malicious",
                "decision_action": "block",
                "process_action": "log_only",
                "file_action": "allow",
                "action_reason": "Enforcement downgraded due to protected signed app.",
                "action_taken": "logged_only",
                "file_action_taken": "guardrail_allow",
                "sha256": "a" * 64,
                "publisher": "Acme Corp",
                "signature_valid": True,
            }
        ],
    )

    rows = list_incident_history(db_path=db)
    row = rows[0]

    # New computed fields present
    assert "effective_outcome" in row
    assert "effective_verdict_label" in row
    assert "is_guardrail_downgraded" in row

    # Raw audit fields preserved intact
    assert row["decision_verdict"] == "Malicious"
    assert row["decision_action"] == "block"
    assert row["process_action"] == "log_only"
    assert row["action_taken"] == "logged_only"
    assert row["file_action_taken"] == "guardrail_allow"
