"""Policy tests for user-facing report formatting."""

from backend.engines.scanning.friendly_report import FriendlyReportGenerator


def test_report_deduplicates_groq_findings_and_avoids_unknown_rule_label():
    """Groq AI findings should not be duplicated and should have a stable label."""
    gen = FriendlyReportGenerator()
    static_result = {
        "file_size": 123,
        "mime_type": "application/x-dosexec",
        "sha256": "a" * 64,
        "findings": [
            {
                "severity": "high",
                "title": "Groq AI: Malicious",
                "detail": "Detected process injection behavior markers",
            }
        ],
        "groq_analysis": {
            "score": 95,
            "verdict": "Malicious",
            "explanation": "Detected process injection behavior markers",
        },
    }

    report = gen.generate_file_report(
        file_path="C:/tmp/sample.exe",
        static_result=static_result,
        sandbox_result={"success": False},
        scoring_result=None,
    )

    assert report.count("Groq AI: Malicious") == 1
    assert "Matched known pattern: Unknown" not in report
