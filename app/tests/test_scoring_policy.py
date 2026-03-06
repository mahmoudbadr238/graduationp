"""Policy tests for threat scoring calibration."""

from app.scanning.scoring import score_scan_results


def test_pe_with_generic_indicators_is_not_forced_malicious():
    """Generic URL/IP-style indicators on PE binaries should not auto-score as malicious."""
    static_result = {
        "yara_matches": [
            {
                "rule": "Suspicious_URL_Pattern",
                "severity": "low",
                "category": "indicator",
            },
            {
                "rule": "Suspicious_IP_Address",
                "severity": "low",
                "category": "indicator",
            },
            {
                "rule": "Suspicious_Base64_Blob",
                "severity": "medium",
                "category": "obfuscation",
            },
        ],
        "pe_info": {"is_pe": True},
        "iocs": {
            "ips": ["1.1.1.1", "8.8.8.8"],
            "urls": ["https://example.com", "https://example.org"],
            "domains": ["example.com", "example.org", "cdn.example.net"],
            "emails": ["a@example.com"],
        },
    }

    result = score_scan_results(static_result=static_result)
    assert result.score <= 30
    assert result.verdict in {"safe", "suspicious"}


def test_high_confidence_yara_still_scores_high():
    """High/critical YARA hits still produce a high-risk verdict."""
    static_result = {
        "yara_matches": [
            {
                "rule": "Suspicious_Process_Injection",
                "severity": "critical",
                "category": "defense_evasion",
            },
            {
                "rule": "Suspicious_Credential_Access",
                "severity": "critical",
                "category": "credential_access",
            },
            {
                "rule": "Suspicious_Disable_Security",
                "severity": "high",
                "category": "defense_evasion",
            },
        ],
        "pe_info": {"is_pe": True},
        "iocs": {},
    }

    result = score_scan_results(static_result=static_result)
    assert result.score >= 40
    assert result.verdict in {"suspicious", "likely_malicious", "malicious"}


def test_sandbox_timeout_does_not_count_forced_exit_as_crash():
    """Timeout kill should not also be penalized as abnormal exit."""
    sandbox_result = {
        "success": True,
        "timed_out": True,
        "exit_code": 1,  # expected after forced kill
        "files_created": [],
        "files_modified": [],
        "files_deleted": [],
        "child_processes": [],
        "registry_modifications": [],
        "network_connections": [],
    }

    result = score_scan_results(static_result={}, sandbox_result=sandbox_result)
    assert "abnormal_exit" not in result.breakdown
