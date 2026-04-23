"""Focused regression tests for score/verdict/action alignment."""

from __future__ import annotations

import sys
import types
from pathlib import Path

from backend.api.backend_bridge import BackendBridge
from backend.core import realtime_protection as rtp
from backend.engines.scanning.decision import build_final_decision
from backend.engines.scanning import scanner_engine


def test_score_zero_malicious_text_normalizes_to_allow() -> None:
    decision = build_final_decision(score=0, verdict="Malicious", policy="static")

    assert decision.score == 0
    assert decision.verdict_code == "safe"
    assert decision.verdict_label == "Safe"
    assert decision.action == "allow"
    assert "below the block threshold" in decision.action_reason


def test_below_threshold_scoring_policy_stays_allow() -> None:
    decision = build_final_decision(
        score=55,
        verdict="Likely Malicious",
        policy="scoring",
    )

    assert decision.verdict_code == "likely_malicious"
    assert decision.action == "allow"
    assert decision.enforcement_threshold == 60


def test_explicit_override_is_modeled_explicitly() -> None:
    decision = build_final_decision(
        score=0,
        verdict="Safe",
        policy="static",
        explicit_action="block",
        override_type="hard_rule",
        action_reason="Exact signature rule matched.",
    )

    assert decision.score == 0
    assert decision.action == "block"
    assert decision.override_type == "hard_rule"
    assert decision.enforcement_source == "explicit_override"
    assert decision.action_reason == "Exact signature rule matched."


def test_qml_normalization_derives_final_decision() -> None:
    bridge = BackendBridge.__new__(BackendBridge)

    result = bridge._normalize_file_scan_result_for_qml(
        {"score": 0, "verdict": "Malicious"}
    )

    assert result["final_decision"]["score"] == 0
    assert result["final_decision"]["verdict_label"] == "Safe"
    assert result["final_decision"]["action"] == "allow"


def test_legacy_scanner_wrapper_uses_final_decision(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.exe"
    sample.write_bytes(b"stub")

    class FakeScanResult:
        score = 0
        verdict = "Malicious"
        sha256 = "abc123"
        groq_analysis = {"verdict": "Malicious", "explanation": "raw engine text"}
        errors: list[str] = []
        final_decision: dict[str, object] = {}

        def to_dict(self) -> dict[str, object]:
            return {
                "score": self.score,
                "verdict": self.verdict,
                "groq_analysis": self.groq_analysis,
            }

    class FakeStaticScanner:
        def scan_file(self, _path: str) -> FakeScanResult:
            return FakeScanResult()

    monkeypatch.setattr(scanner_engine, "StaticScanner", FakeStaticScanner)
    scanner = scanner_engine.MalwareScanner()
    result = scanner.scan_file(sample)

    assert result["score"] == 0
    assert result["verdict"] == "Safe"
    assert result["action"] == "allow"
    assert result["is_malicious"] is False


def test_windows_rtp_does_not_kill_zero_score_process(monkeypatch, tmp_path: Path) -> None:
    exe_path = tmp_path / "sample.exe"
    exe_path.write_text("stub", encoding="utf-8")
    kill_calls: list[int] = []

    class FakeTimedOut(Exception):
        pass

    class FakeWmiConnection:
        def __init__(self) -> None:
            self._emitted = False

        def watch_for(self, **_kwargs):
            def watcher(*, timeout_ms: int):  # noqa: ARG001
                if not self._emitted:
                    self._emitted = True
                    return types.SimpleNamespace(
                        Name="sample.exe",
                        ProcessId=9001,
                        ExecutablePath=str(exe_path),
                    )
                raise FakeTimedOut()

            return watcher

    class FakeProcess:
        def __init__(self, pid: int) -> None:
            self._pid = pid

        def name(self) -> str:
            return "sample.exe"

        def kill(self) -> None:
            kill_calls.append(self._pid)

    fake_pythoncom = types.SimpleNamespace(
        CoInitialize=lambda: None,
        CoUninitialize=lambda: None,
    )
    fake_wmi = types.SimpleNamespace(
        WMI=lambda: FakeWmiConnection(),
        x_wmi_timed_out=FakeTimedOut,
    )
    fake_psutil = types.SimpleNamespace(
        Process=FakeProcess,
        NoSuchProcess=RuntimeError,
        AccessDenied=PermissionError,
    )

    class FakeStaticScanner:
        def scan_file(self, _path: str):
            return types.SimpleNamespace(
                score=0,
                verdict="Malicious",
                sha256="abc",
                groq_analysis={"verdict": "Malicious"},
                errors=[],
            )

    fake_static_scanner = types.ModuleType("backend.engines.scanning.static_scanner")
    fake_static_scanner.StaticScanner = FakeStaticScanner

    monkeypatch.setattr(sys, "platform", "win32", raising=False)
    monkeypatch.setitem(sys.modules, "pythoncom", fake_pythoncom)
    monkeypatch.setitem(sys.modules, "wmi", fake_wmi)
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
    monkeypatch.setitem(
        sys.modules,
        "backend.engines.scanning.static_scanner",
        fake_static_scanner,
    )

    worker = rtp.RealTimeProtectionWorker()

    def _capture_detection(_timestamp: str, _name: str, _pid: str) -> None:
        worker.stop()

    worker.process_detected.connect(_capture_detection)
    worker.run()

    assert kill_calls == []


def test_windows_rtp_blocks_at_threshold(monkeypatch, tmp_path: Path) -> None:
    exe_path = tmp_path / "sample.exe"
    exe_path.write_text("stub", encoding="utf-8")
    kill_calls: list[int] = []

    class FakeTimedOut(Exception):
        pass

    class FakeWmiConnection:
        def __init__(self) -> None:
            self._emitted = False

        def watch_for(self, **_kwargs):
            def watcher(*, timeout_ms: int):  # noqa: ARG001
                if not self._emitted:
                    self._emitted = True
                    return types.SimpleNamespace(
                        Name="sample.exe",
                        ProcessId=31337,
                        ExecutablePath=str(exe_path),
                    )
                raise FakeTimedOut()

            return watcher

    class FakeProcess:
        def __init__(self, pid: int) -> None:
            self._pid = pid

        def name(self) -> str:
            return "sample.exe"

        def kill(self) -> None:
            kill_calls.append(self._pid)

    fake_pythoncom = types.SimpleNamespace(
        CoInitialize=lambda: None,
        CoUninitialize=lambda: None,
    )
    fake_wmi = types.SimpleNamespace(
        WMI=lambda: FakeWmiConnection(),
        x_wmi_timed_out=FakeTimedOut,
    )
    fake_psutil = types.SimpleNamespace(
        Process=FakeProcess,
        NoSuchProcess=RuntimeError,
        AccessDenied=PermissionError,
    )

    class FakeVault:
        def quarantine_file(self, _path: str) -> dict[str, object]:
            return {"ok": True}

    fake_quarantine = types.ModuleType(
        "backend.engines.scanning.quarantine_manager"
    )
    fake_quarantine.get_quarantine_vault = lambda: FakeVault()

    class FakeStaticScanner:
        def scan_file(self, _path: str):
            return types.SimpleNamespace(
                score=60,
                verdict="Malicious",
                sha256="abc",
                groq_analysis={"verdict": "Malicious"},
                errors=[],
            )

    fake_static_scanner = types.ModuleType("backend.engines.scanning.static_scanner")
    fake_static_scanner.StaticScanner = FakeStaticScanner

    monkeypatch.setattr(sys, "platform", "win32", raising=False)
    monkeypatch.setitem(sys.modules, "pythoncom", fake_pythoncom)
    monkeypatch.setitem(sys.modules, "wmi", fake_wmi)
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
    monkeypatch.setitem(
        sys.modules,
        "backend.engines.scanning.static_scanner",
        fake_static_scanner,
    )
    monkeypatch.setitem(
        sys.modules,
        "backend.engines.scanning.quarantine_manager",
        fake_quarantine,
    )

    worker = rtp.RealTimeProtectionWorker()

    def _capture_threat(_message: str) -> None:
        worker.stop()

    worker.threat_detected.connect(_capture_threat)
    worker.run()

    assert kill_calls == [31337]
