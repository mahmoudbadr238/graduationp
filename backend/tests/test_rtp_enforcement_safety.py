"""Focused safety guards for RTP destructive-action hardening."""

from __future__ import annotations

import os
import sys
import time
import types
from pathlib import Path

from backend.core import realtime_protection as rtp
from backend.engines.scanning.quarantine_manager import QuarantineVault


def test_windows_brave_score_only_block_downgrades_to_log_only(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32", raising=False)
    monkeypatch.setenv("ProgramFiles", r"C:\Program Files")
    worker = rtp.RealTimeProtectionWorker()

    plan = worker._build_enforcement_plan(
        "brave.exe",
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        {
            "action": "block",
            "score": 67,
            "verdict_label": "Malicious",
            "action_reason": "Threat score 67/100 reached the block threshold.",
        },
        scan_context={
            "signature_valid": True,
            "publisher": "Brave Software, Inc.",
            "strong_evidence": False,
            "fingerprint": (100, 200),
        },
    )

    assert plan.process_action == "log_only"
    assert plan.file_action == "allow"
    assert "explicit override" in plan.reason.lower()


def test_windows_brave_clamav_only_block_stays_log_only(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32", raising=False)
    monkeypatch.setenv("ProgramFiles", r"C:\Program Files")
    worker = rtp.RealTimeProtectionWorker()

    plan = worker._build_enforcement_plan(
        "brave.exe",
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        {
            "action": "block",
            "score": 92,
            "verdict_label": "Malicious",
            "action_reason": "ClamAV confirmed malware.",
        },
        scan_context={
            "signature_valid": True,
            "publisher": "Brave Software, Inc.",
            "strong_evidence": True,
            "fingerprint": (100, 200),
        },
    )

    assert plan.process_action == "log_only"
    assert plan.file_action == "allow"
    assert "explicit override" in plan.reason.lower()


def test_windows_system_binary_clamav_only_block_stays_log_only(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32", raising=False)
    monkeypatch.setenv("SystemRoot", r"C:\Windows")
    worker = rtp.RealTimeProtectionWorker()

    plan = worker._build_enforcement_plan(
        "smartscreen.exe",
        r"C:\Windows\System32\smartscreen.exe",
        {
            "action": "block",
            "score": 94,
            "verdict_label": "Malicious",
            "action_reason": "ClamAV confirmed malware.",
        },
        scan_context={
            "signature_valid": True,
            "publisher": "Microsoft Windows",
            "strong_evidence": True,
            "fingerprint": (100, 200),
        },
    )

    assert plan.process_action == "log_only"
    assert plan.file_action == "allow"
    assert "protected" in plan.reason.lower()


def test_incomplete_block_decision_downgrades_to_log_only() -> None:
    worker = rtp.RealTimeProtectionWorker()

    plan = worker._build_enforcement_plan(
        "sample.exe",
        "/tmp/sample.exe",
        {
            "action": "block",
            "score": 0,
            "verdict_label": "Unknown",
            "action_reason": "Scanner output incomplete.",
        },
        scan_context={
            "signature_valid": None,
            "publisher": "",
            "strong_evidence": False,
            "fingerprint": (100, 200),
        },
    )

    assert plan.process_action == "log_only"
    assert plan.file_action == "allow"
    assert "incomplete" in plan.reason.lower() or "complete final decision" in plan.reason.lower()


def test_score_only_block_kills_process_but_skips_file_quarantine(monkeypatch, tmp_path: Path) -> None:
    exe_path = tmp_path / "sample.exe"
    exe_path.write_text("stub", encoding="utf-8")
    kill_calls: list[int] = []
    quarantined: list[str] = []

    class FakeProcess:
        def __init__(self, pid: int) -> None:
            self._pid = pid

        def name(self) -> str:
            return "sample.exe"

        def exe(self) -> str:
            return str(exe_path)

        def kill(self) -> None:
            kill_calls.append(self._pid)

    fake_psutil = types.SimpleNamespace(
        Process=FakeProcess,
        NoSuchProcess=RuntimeError,
        AccessDenied=PermissionError,
    )

    fake_quarantine = types.ModuleType("backend.engines.scanning.quarantine_manager")
    fake_quarantine.get_quarantine_vault = lambda: types.SimpleNamespace(
        quarantine_file=lambda path, **_kwargs: quarantined.append(path) or {"success": True}
    )
    monkeypatch.setitem(
        sys.modules,
        "backend.engines.scanning.quarantine_manager",
        fake_quarantine,
    )

    worker = rtp.RealTimeProtectionWorker()
    worker._apply_enforcement(
        99,
        "sample.exe",
        str(exe_path),
        fake_psutil,
        decision={
            "action": "block",
            "score": 60,
            "verdict_label": "Malicious",
            "triggered_rules": ["Groq:Malicious"],
            "action_reason": "Threat score 60/100 reached the block threshold.",
        },
        plan=rtp.EnforcementPlan(
            decision_action="block",
            process_action="kill_process",
            file_action="allow",
            reason="Score-only evidence; kill allowed, file quarantine skipped.",
        ),
        sha256="abc",
    )

    assert kill_calls == [99]
    assert quarantined == []


def test_strong_evidence_allows_quarantine_for_untrusted_binary(monkeypatch, tmp_path: Path) -> None:
    exe_path = tmp_path / "payload.exe"
    exe_path.write_text("stub", encoding="utf-8")
    kill_calls: list[int] = []
    quarantine_calls: list[tuple[str, dict[str, object]]] = []

    class FakeProcess:
        def __init__(self, pid: int) -> None:
            self._pid = pid

        def name(self) -> str:
            return "payload.exe"

        def exe(self) -> str:
            return str(exe_path)

        def kill(self) -> None:
            kill_calls.append(self._pid)

    fake_psutil = types.SimpleNamespace(
        Process=FakeProcess,
        NoSuchProcess=RuntimeError,
        AccessDenied=PermissionError,
    )

    fake_quarantine = types.ModuleType("backend.engines.scanning.quarantine_manager")

    def _quarantine_file(path: str, *, metadata: dict[str, object] | None = None) -> dict[str, object]:
        quarantine_calls.append((path, dict(metadata or {})))
        return {"success": True}

    fake_quarantine.get_quarantine_vault = lambda: types.SimpleNamespace(
        quarantine_file=_quarantine_file
    )
    monkeypatch.setitem(
        sys.modules,
        "backend.engines.scanning.quarantine_manager",
        fake_quarantine,
    )

    worker = rtp.RealTimeProtectionWorker()
    worker._apply_enforcement(
        7,
        "payload.exe",
        str(exe_path),
        fake_psutil,
        decision={
            "action": "block",
            "score": 88,
            "verdict_label": "Malicious",
            "triggered_rules": ["ClamAV:Eicar-Test-Signature"],
            "action_reason": "ClamAV confirmed malware.",
        },
        plan=rtp.EnforcementPlan(
            decision_action="block",
            process_action="kill_process",
            file_action="quarantine_file",
            reason="Strong corroborating evidence authorizes quarantine.",
            strong_evidence=True,
            publisher="",
            signature_valid=None,
        ),
        sha256="deadbeef",
    )

    assert kill_calls == [7]
    assert quarantine_calls
    assert quarantine_calls[0][0] == str(exe_path)
    assert quarantine_calls[0][1]["file_action"] == "quarantine_file"
    assert quarantine_calls[0][1]["enforcement_source"] == "rtp"


def test_cached_block_decision_invalidates_when_file_changes(tmp_path: Path) -> None:
    exe_path = tmp_path / "sample.exe"
    exe_path.write_text("v1", encoding="utf-8")

    worker = rtp.RealTimeProtectionWorker()
    fingerprint = rtp._file_fingerprint(str(exe_path))
    worker._cache_scan_decision(
        str(exe_path),
        {"action": "block", "score": 70},
        sha256="one",
        scan_context={"fingerprint": fingerprint},
    )

    assert worker._get_cached_scan_entry(str(exe_path)) is not None

    time.sleep(0.01)
    exe_path.write_text("v2", encoding="utf-8")
    os.utime(exe_path, None)

    assert worker._get_cached_scan_entry(str(exe_path)) is None


def test_process_kill_requires_matching_executable_path(tmp_path: Path) -> None:
    exe_path = tmp_path / "sample.exe"
    exe_path.write_text("stub", encoding="utf-8")
    kill_calls: list[int] = []

    class FakeProcess:
        def __init__(self, pid: int) -> None:
            self._pid = pid

        def name(self) -> str:
            return "sample.exe"

        def exe(self) -> str:
            return str(tmp_path / "other.exe")

        def kill(self) -> None:
            kill_calls.append(self._pid)

    fake_psutil = types.SimpleNamespace(
        Process=FakeProcess,
        NoSuchProcess=RuntimeError,
        AccessDenied=PermissionError,
    )

    worker = rtp.RealTimeProtectionWorker()
    result = worker._execute_process_action(
        123,
        "sample.exe",
        str(exe_path),
        fake_psutil,
        process_action="kill_process",
    )

    assert result == "path_mismatch"
    assert kill_calls == []


def test_bridge_marks_log_only_events_as_flagged() -> None:
    bridge = rtp.RealTimeProtectionBridge()
    logs: list[str] = []
    bridge.new_event_log.connect(logs.append)

    bridge._on_threat(
        "⚠️ [12:00:00] THREAT FLAGGED\n"
        "   Process : brave.exe (PID 777)\n"
        "   Process Action: LOG_ONLY\n"
        "   File Action   : ALLOW"
    )
    bridge._on_process_detected("12:00:00", "brave.exe", "777")

    assert logs == ["[12:00:00] RTP: Flagged brave.exe (PID: 777)"]


def test_quarantine_ledger_records_rtp_metadata(tmp_path: Path) -> None:
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"payload")
    vault = QuarantineVault(tmp_path / "vault")

    result = vault.quarantine_file(
        sample,
        metadata={
            "enforcement_source": "rtp",
            "decision_action": "block",
            "decision_verdict": "Malicious",
            "decision_score": 91,
            "process_action": "kill_process",
            "file_action": "quarantine_file",
            "action_reason": "ClamAV confirmed malware.",
            "strong_evidence": True,
        },
    )

    assert result["success"] is True
    entries = vault.list_quarantined()
    assert len(entries) == 1
    assert entries[0]["enforcement_source"] == "rtp"
    assert entries[0]["process_action"] == "kill_process"
    assert entries[0]["file_action"] == "quarantine_file"
