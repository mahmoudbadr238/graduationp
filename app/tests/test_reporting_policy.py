"""Policy tests for user-facing report formatting."""

from app.scanning.friendly_report import FriendlyReportGenerator


def test_report_deduplicates_yara_findings_and_avoids_unknown_rule_label():
    """YARA findings should not be duplicated and should have a stable label."""
    gen = FriendlyReportGenerator()
    static_result = {
        "file_size": 123,
        "mime_type": "application/x-dosexec",
        "sha256": "a" * 64,
        "findings": [
            {
                "severity": "high",
                "title": "YARA: PE_Suspicious_Imports",
                "detail": "PE with suspicious import combination",
            }
        ],
        "yara_matches": [
            {
                "severity": "high",
                "title": "YARA: PE_Suspicious_Imports",
                "detail": "PE with suspicious import combination",
            }
        ],
    }

    report = gen.generate_file_report(
        file_path="C:/tmp/sample.exe",
        static_result=static_result,
        sandbox_result={"success": False},
        scoring_result=None,
    )

    assert report.count("YARA: PE_Suspicious_Imports") == 1
    assert "Matched known pattern: Unknown" not in report
