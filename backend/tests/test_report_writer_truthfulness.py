"""Regression tests for report writer truthfulness."""

from __future__ import annotations

from backend.engines.scanning.report_writer import ReportWriter
from backend.engines.scanning.static_scanner import IOCExtraction, ScanResult


def test_file_report_does_not_claim_100_percent_offline_when_ai_section_exists(
    tmp_path,
):
    writer = ReportWriter(reports_dir=tmp_path)
    result = ScanResult(
        file_path="C:/sample.exe",
        file_name="sample.exe",
        file_size=1234,
        sha256="a" * 64,
        mime_type="application/octet-stream",
        extension=".exe",
        verdict="Safe",
        score=0,
        summary="No suspicious indicators detected.",
        iocs=IOCExtraction(),
        groq_analysis={"verdict": "Safe", "score": 0, "explanation": "Optional AI summary"},
        clamav={"available": False},
    )

    report_path = writer.write_file_report(result)
    report_text = report_path.read_text(encoding="utf-8")

    assert "100% Offline Analysis" not in report_text
    assert "optional AI noted separately" in report_text
