"""Focused RTP runtime tests for Windows/Linux process-monitor truthfulness."""

from __future__ import annotations

import sys
import types
from pathlib import Path

from backend.core import realtime_protection as rtp


def test_windows_worker_accepts_raw_wmi_process_instances(monkeypatch, tmp_path: Path) -> None:
    """Windows WMI watch_for(raw_wql=...) returns Win32_Process, not TargetInstance."""

    exe_path = tmp_path / "calc.exe"
    exe_path.write_text("stub", encoding="utf-8")

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
                        Name="calc.exe",
                        ProcessId=4242,
                        ExecutablePath=str(exe_path),
                    )
                raise FakeTimedOut()

            return watcher

    fake_pythoncom = types.SimpleNamespace(
        CoInitialize=lambda: None,
        CoUninitialize=lambda: None,
    )
    fake_wmi = types.SimpleNamespace(
        WMI=lambda: FakeWmiConnection(),
        x_wmi_timed_out=FakeTimedOut,
    )
    fake_psutil = types.SimpleNamespace(
        NoSuchProcess=RuntimeError,
        AccessDenied=PermissionError,
    )

    class FakeStaticScanner:
        def scan_file(self, _path: str):
            return types.SimpleNamespace(
                score=0,
                sha256="",
                groq_analysis={},
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
    scanned: list[str] = []
    detected: list[tuple[str, str, str]] = []
    statuses: list[str] = []

    worker.process_scanned.connect(scanned.append)
    worker.status_changed.connect(statuses.append)

    def _capture_detection(timestamp: str, name: str, pid: str) -> None:
        detected.append((timestamp, name, pid))
        worker.stop()

    worker.process_detected.connect(_capture_detection)
    worker.run()

    assert statuses[0] == "started"
    assert scanned == ["[1] Scanning: calc.exe (PID 4242)"]
    assert detected
    assert detected[0][1:] == ("calc.exe", "4242")


def test_bridge_runtime_detail_separates_monitor_and_scanner_state(monkeypatch) -> None:
    bridge = rtp.RealTimeProtectionBridge()
    bridge._capability = {
        "state": "available",
        "detail": "Monitoring new process launches via WMI.",
    }
    bridge._enabled = True
    bridge._worker = types.SimpleNamespace(
        _monitoring_running=True,
        _scanner_ready=True,
        _monitoring_backend="WMI process watcher",
        _scanner_detail="Static scanner loaded.",
    )
    monkeypatch.setattr(bridge, "getConfiguredEnabled", lambda: True)

    assert bridge.getMonitoringState() == "running"
    assert bridge.getProcessScannerState() == "running"
    assert "Monitoring running via WMI process watcher." in bridge.getRuntimeDetail()
    assert "Process scanner active." in bridge.getRuntimeDetail()


def test_linux_worker_process_polling_still_emits_scan_events(monkeypatch, tmp_path: Path) -> None:
    exe_path = tmp_path / "sample"
    exe_path.write_text("stub", encoding="utf-8")

    class FakeProc:
        def __init__(self, info: dict[str, object]) -> None:
            self.info = info

    class FakePsutil:
        STATUS_ZOMBIE = "zombie"
        NoSuchProcess = RuntimeError
        AccessDenied = PermissionError

        def __init__(self) -> None:
            self._calls = 0

        def process_iter(self, fields):  # noqa: ANN001
            self._calls += 1
            if fields == ["pid"]:
                return [FakeProc({"pid": 1})]
            return [
                FakeProc({"pid": 1, "name": "python", "exe": "", "status": "running"}),
                FakeProc(
                    {
                        "pid": 2,
                        "name": "sample",
                        "exe": str(exe_path),
                        "status": "running",
                    }
                ),
            ]

    fake_psutil = FakePsutil()

    class FakeStaticScanner:
        def scan_file(self, _path: str):
            return types.SimpleNamespace(
                score=0,
                sha256="",
                groq_analysis={},
            )

    fake_static_scanner = types.ModuleType("backend.engines.scanning.static_scanner")
    fake_static_scanner.StaticScanner = FakeStaticScanner

    monkeypatch.setattr(sys, "platform", "linux", raising=False)
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
    monkeypatch.setitem(
        sys.modules,
        "backend.engines.scanning.static_scanner",
        fake_static_scanner,
    )
    monkeypatch.setattr(rtp.time, "sleep", lambda _secs: None)

    worker = rtp.RealTimeProtectionWorker()
    scanned: list[str] = []
    detected: list[tuple[str, str, str]] = []

    worker.process_scanned.connect(scanned.append)

    def _capture_detection(timestamp: str, name: str, pid: str) -> None:
        detected.append((timestamp, name, pid))
        worker.stop()

    worker.process_detected.connect(_capture_detection)
    worker.run()

    assert scanned == ["[1] Scanning: sample (PID 2)"]
    assert detected
    assert detected[0][1:] == ("sample", "2")


def test_bridge_runtime_detail_reports_degraded_scanner(monkeypatch) -> None:
    bridge = rtp.RealTimeProtectionBridge()
    bridge._capability = {
        "state": "available",
        "detail": "Monitoring new process launches via process polling.",
    }
    bridge._enabled = True
    bridge._worker = types.SimpleNamespace(
        _monitoring_running=True,
        _scanner_ready=False,
        _monitoring_backend="process polling",
        _scanner_detail="Static scanner unavailable: model load failed",
    )
    monkeypatch.setattr(bridge, "getConfiguredEnabled", lambda: True)

    assert bridge.getMonitoringState() == "running"
    assert bridge.getProcessScannerState() == "degraded"
    assert "Process scanner degraded." in bridge.getRuntimeDetail()
    assert "model load failed" in bridge.getRuntimeDetail()


def test_bridge_emits_event_console_log_for_detected_process() -> None:
    bridge = rtp.RealTimeProtectionBridge()
    logs: list[str] = []
    bridge.new_event_log.connect(logs.append)

    bridge._on_process_detected("12:34:56", "sample.exe", "77")

    assert logs == ["[12:34:56] RTP: Allowed sample.exe (PID: 77)"]


def test_system_monitor_qml_reads_runtime_state_slots() -> None:
    content = Path("frontend/qml/pages/SystemMonitor.qml").read_text(encoding="utf-8")

    for token in (
        "getConfiguredEnabled",
        "getMonitoringState",
        "getProcessScannerState",
        "getRuntimeDetail",
        'rtpMonitoringState === "running"',
    ):
        assert token in content
