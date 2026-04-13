from __future__ import annotations

from backend.engines.scancenter.report_schema import SandboxSection
from backend.engines.scancenter.scanner_orchestrator import ScannerOrchestrator


def test_apply_behavior_log_populates_sandbox_sections() -> None:
    sandbox = SandboxSection(enabled=True, executed=True)
    behavior_log = (
        "Sentinel behavioral monitor\n"
        "=== PROCESSES ===\n"
        "payload.exe 1234 0.1 4096\n"
        "\n"
        "=== NETWORK ===\n"
        "TCP 127.0.0.1:4242 93.184.216.34:443 ESTABLISHED 1234\n"
    )

    ScannerOrchestrator._apply_behavior_log(sandbox, behavior_log)

    assert sandbox.process_diff == [{"raw": "payload.exe 1234 0.1 4096"}]
    assert sandbox.network_attempts == [
        {"raw": "TCP 127.0.0.1:4242 93.184.216.34:443 ESTABLISHED 1234"}
    ]


def test_apply_behavior_report_maps_json_summary() -> None:
    sandbox = SandboxSection(enabled=True, executed=True)
    behavior_report = {
        "executed": True,
        "sample_exit_code": 7,
        "processes": [
            {
                "name": "payload.exe",
                "pid": 1234,
                "path": "C:\\Users\\Public\\Downloads\\payload.exe",
            }
        ],
        "network_connections": [
            "TCP 127.0.0.1:4242 93.184.216.34:443 ESTABLISHED 1234"
        ],
        "errors": ["payload terminated unexpectedly"],
        "summary": {"new_processes": 1, "network_connections": 1, "errors": 1},
    }

    ScannerOrchestrator._apply_behavior_report(sandbox, behavior_report)

    assert sandbox.process_diff == behavior_report["processes"]
    assert sandbox.network_attempts == [
        {"raw": "TCP 127.0.0.1:4242 93.184.216.34:443 ESTABLISHED 1234"}
    ]
    assert sandbox.exit_code == 7
    assert "payload terminated unexpectedly" in sandbox.errors
    assert "Processes observed: 1" in sandbox.highlights
    assert "Network events observed: 1" in sandbox.highlights
    assert "Monitor reported 1 collection error(s)" in sandbox.warnings
