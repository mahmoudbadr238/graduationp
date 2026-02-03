"""
URL scan report writer.

Generates professional TXT and JSON reports for URL scan results.
Reports are saved to %APPDATA%\\Sentinel\\scan_reports\\url\\
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.scanning.url_scanner import UrlScanResult
    from app.ai.url_explainer import UrlExplanation

logger = logging.getLogger(__name__)


def get_url_report_dir() -> Path:
    """Get the URL scan reports directory, creating it if needed."""
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    report_dir = Path(appdata) / "Sentinel" / "scan_reports" / "url"
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def sanitize_filename(url: str) -> str:
    """Convert URL to safe filename."""
    from urllib.parse import urlparse
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or "unknown"
        path = parsed.path.strip("/").replace("/", "_") or "root"
        
        # Remove/replace unsafe characters
        safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")
        domain = "".join(c if c in safe_chars else "_" for c in domain)
        path = "".join(c if c in safe_chars else "_" for c in path)
        
        # Truncate if too long
        filename = f"{domain}_{path}"
        if len(filename) > 50:
            filename = filename[:50]
        
        return filename
    except Exception:
        return "unknown_url"


def write_url_scan_report(
    result: "UrlScanResult",
    explanation: Optional["UrlExplanation"] = None,
    output_dir: Optional[Path] = None
) -> Path:
    """
    Write a TXT report for a URL scan.
    
    Args:
        result: The UrlScanResult to report on
        explanation: Optional UrlExplanation for human-readable analysis
        output_dir: Optional output directory (defaults to %APPDATA%\\Sentinel\\scan_reports\\url)
        
    Returns:
        Path to the created report file
    """
    if output_dir is None:
        output_dir = get_url_report_dir()
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    url_safe = sanitize_filename(result.normalized_url)
    filename = f"url_scan_{url_safe}_{timestamp}.txt"
    report_path = output_dir / filename
    
    # Build report content
    lines = []
    
    # Header
    lines.append("=" * 80)
    lines.append("SENTINEL URL SCAN REPORT")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Generated:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Scan Type:     URL Analysis")
    lines.append("")
    
    # URL Information
    lines.append("-" * 80)
    lines.append("URL INFORMATION")
    lines.append("-" * 80)
    lines.append(f"Input URL:     {result.input_url}")
    lines.append(f"Normalized:    {result.normalized_url}")
    lines.append(f"Final URL:     {result.final_url}")
    lines.append("")
    
    # Verdict
    lines.append("-" * 80)
    lines.append("VERDICT")
    lines.append("-" * 80)
    
    verdict_display = {
        "safe": "✓ SAFE",
        "suspicious": "⚠ SUSPICIOUS",
        "likely_malicious": "⚠ LIKELY MALICIOUS",
        "malicious": "✗ MALICIOUS",
        "error": "? ERROR",
    }
    
    verdict_text = verdict_display.get(result.verdict, result.verdict.upper())
    lines.append(f"Verdict:       {verdict_text}")
    lines.append(f"Score:         {result.score}/100")
    lines.append("")
    
    # Explanation (if available)
    if explanation:
        lines.append("-" * 80)
        lines.append("ANALYSIS")
        lines.append("-" * 80)
        lines.append("")
        lines.append(f"What It Is:")
        lines.append(f"  {explanation.what_it_is}")
        lines.append("")
        lines.append(f"Risk Assessment:")
        lines.append(f"  {explanation.why_risky}")
        lines.append("")
        lines.append(f"Recommendation:")
        lines.append(f"  {explanation.what_to_do}")
        lines.append("")
        lines.append(f"Confidence:    {explanation.confidence.upper()}")
        lines.append(f"Technical:     {explanation.technical_summary}")
        lines.append("")
    
    # HTTP Information
    if result.http:
        lines.append("-" * 80)
        lines.append("HTTP RESPONSE")
        lines.append("-" * 80)
        
        http = result.http
        lines.append(f"Status Code:   {http.get('status_code', 'N/A')}")
        lines.append(f"Content Type:  {http.get('content_type', 'N/A')}")
        lines.append(f"Content Size:  {_format_size(http.get('content_length', 0))}")
        lines.append(f"Server:        {http.get('server', 'N/A')}")
        
        if http.get("headers"):
            lines.append("")
            lines.append("Security Headers:")
            security_headers = [
                "X-Frame-Options",
                "X-Content-Type-Options", 
                "Content-Security-Policy",
                "Strict-Transport-Security",
                "X-XSS-Protection",
            ]
            headers = http.get("headers", {})
            for header in security_headers:
                value = headers.get(header, headers.get(header.lower(), "Not present"))
                status = "✓" if value != "Not present" else "✗"
                lines.append(f"  {status} {header}: {value[:50] + '...' if len(str(value)) > 50 else value}")
        
        lines.append("")
    
    # Redirect Chain
    if result.redirects and len(result.redirects) > 1:
        lines.append("-" * 80)
        lines.append("REDIRECT CHAIN")
        lines.append("-" * 80)
        
        for i, redirect_url in enumerate(result.redirects):
            prefix = "└──" if i == len(result.redirects) - 1 else "├──"
            lines.append(f"  {i+1}. {prefix} {redirect_url}")
        
        lines.append("")
    
    # Evidence/Findings
    if result.evidence:
        lines.append("-" * 80)
        lines.append("FINDINGS")
        lines.append("-" * 80)
        lines.append("")
        
        # Group by severity
        severity_order = ["critical", "high", "medium", "low", "info"]
        severity_symbols = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🔵",
            "info": "⚪",
        }
        
        for severity in severity_order:
            findings = [e for e in result.evidence if e.severity == severity]
            if findings:
                lines.append(f"[{severity.upper()}]")
                for finding in findings:
                    symbol = severity_symbols.get(severity, "•")
                    lines.append(f"  {symbol} {finding.title}")
                    lines.append(f"      {finding.detail}")
                lines.append("")
    
    # Indicators of Compromise (IOCs)
    if result.iocs:
        lines.append("-" * 80)
        lines.append("INDICATORS OF COMPROMISE (IOCs)")
        lines.append("-" * 80)
        lines.append("")
        
        if result.iocs.get("domains"):
            lines.append("Linked Domains:")
            for domain in result.iocs["domains"][:20]:
                lines.append(f"  • {domain}")
            if len(result.iocs["domains"]) > 20:
                lines.append(f"  ... and {len(result.iocs['domains']) - 20} more")
            lines.append("")
        
        if result.iocs.get("ips"):
            lines.append("IP Addresses:")
            for ip in result.iocs["ips"][:20]:
                lines.append(f"  • {ip}")
            if len(result.iocs["ips"]) > 20:
                lines.append(f"  ... and {len(result.iocs['ips']) - 20} more")
            lines.append("")
        
        if result.iocs.get("urls"):
            lines.append("Extracted URLs:")
            for url in result.iocs["urls"][:10]:
                lines.append(f"  • {url}")
            if len(result.iocs["urls"]) > 10:
                lines.append(f"  ... and {len(result.iocs['urls']) - 10} more")
            lines.append("")
        
        if result.iocs.get("emails"):
            lines.append("Email Addresses:")
            for email in result.iocs["emails"][:10]:
                lines.append(f"  • {email}")
            lines.append("")
    
    # YARA Matches
    if result.yara_matches:
        lines.append("-" * 80)
        lines.append("YARA RULE MATCHES")
        lines.append("-" * 80)
        lines.append("")
        
        for match in result.yara_matches:
            lines.append(f"  • {match}")
        
        lines.append("")
    
    # Sandbox Results
    if result.sandbox_result:
        lines.append("-" * 80)
        lines.append("SANDBOX ANALYSIS")
        lines.append("-" * 80)
        lines.append("")
        
        sandbox = result.sandbox_result
        if isinstance(sandbox, dict):
            if sandbox.get("success"):
                lines.append(f"Status:        Completed successfully")
                lines.append(f"Load Time:     {sandbox.get('load_time_ms', 'N/A')} ms")
                
                if sandbox.get("download_attempts"):
                    lines.append("")
                    lines.append("Download Attempts:")
                    for dl in sandbox["download_attempts"]:
                        lines.append(f"  ⚠ {dl}")
                
                if sandbox.get("popup_attempts", 0) > 0:
                    lines.append(f"Popup Attempts: {sandbox['popup_attempts']}")
                
                if sandbox.get("network_requests"):
                    lines.append("")
                    lines.append(f"Network Requests: {len(sandbox['network_requests'])} total")
            else:
                lines.append(f"Status:        Failed")
                lines.append(f"Error:         {sandbox.get('error', 'Unknown error')}")
        
        lines.append("")
    
    # Signals/Flags
    if result.signals:
        suspicious_signals = {k: v for k, v in result.signals.items() if v is True}
        if suspicious_signals:
            lines.append("-" * 80)
            lines.append("DETECTED SIGNALS")
            lines.append("-" * 80)
            lines.append("")
            
            signal_descriptions = {
                "punycode_domain": "Domain uses punycode (IDN homograph attack possible)",
                "suspicious_tld": "Uses high-risk top-level domain",
                "ip_address_url": "URL uses IP address instead of domain",
                "excessive_subdomains": "Unusually many subdomains",
                "has_password_field": "Page contains password input",
                "has_hidden_form": "Page contains hidden forms",
                "has_credential_form": "Page requests credentials",
                "has_download_form": "Page has download functionality",
                "has_obfuscated_js": "JavaScript is obfuscated",
                "has_auto_download": "Page triggers automatic downloads",
                "has_external_scripts": "Page loads external scripts",
                "excessive_redirects": "Unusual number of redirects",
                "cross_domain_redirect": "Redirects to different domain",
            }
            
            for signal, _ in suspicious_signals.items():
                desc = signal_descriptions.get(signal, signal.replace("_", " ").title())
                lines.append(f"  ⚑ {desc}")
            
            lines.append("")
    
    # Footer
    lines.append("=" * 80)
    lines.append("END OF REPORT")
    lines.append("=" * 80)
    lines.append("")
    lines.append("Generated by Sentinel Desktop Security Suite")
    lines.append("https://github.com/your-repo/sentinel")
    
    # Write file
    report_content = "\n".join(lines)
    
    try:
        report_path.write_text(report_content, encoding="utf-8")
        logger.info(f"URL scan report written to: {report_path}")
    except Exception as e:
        logger.error(f"Failed to write report: {e}")
        raise
    
    return report_path


def write_url_scan_json(
    result: "UrlScanResult",
    explanation: Optional["UrlExplanation"] = None,
    output_dir: Optional[Path] = None
) -> Path:
    """
    Write a JSON report for a URL scan.
    
    Args:
        result: The UrlScanResult to report on
        explanation: Optional UrlExplanation
        output_dir: Optional output directory
        
    Returns:
        Path to the created JSON file
    """
    if output_dir is None:
        output_dir = get_url_report_dir()
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    url_safe = sanitize_filename(result.normalized_url)
    filename = f"url_scan_{url_safe}_{timestamp}.json"
    report_path = output_dir / filename
    
    # Build JSON structure
    data = {
        "meta": {
            "generator": "Sentinel Desktop Security Suite",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "scan_type": "url_analysis",
        },
        "url": {
            "input": result.input_url,
            "normalized": result.normalized_url,
            "final": result.final_url,
        },
        "verdict": {
            "result": result.verdict,
            "score": result.score,
        },
        "http": result.http or {},
        "redirects": result.redirects,
        "evidence": [
            {
                "title": e.title,
                "severity": e.severity,
                "detail": e.detail,
                "category": e.category,
            }
            for e in result.evidence
        ],
        "signals": result.signals,
        "iocs": result.iocs or {},
        "yara_matches": result.yara_matches or [],
        "sandbox_result": result.sandbox_result.to_dict() if hasattr(result.sandbox_result, 'to_dict') else result.sandbox_result,
    }
    
    if explanation:
        data["explanation"] = {
            "what_it_is": explanation.what_it_is,
            "why_risky": explanation.why_risky,
            "what_to_do": explanation.what_to_do,
            "technical_summary": explanation.technical_summary,
            "confidence": explanation.confidence,
        }
    
    # Write file
    try:
        report_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"URL scan JSON written to: {report_path}")
    except Exception as e:
        logger.error(f"Failed to write JSON report: {e}")
        raise
    
    return report_path


def _format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    if size_bytes == 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB"]
    size = float(size_bytes)
    unit_index = 0
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    return f"{size:.1f} {units[unit_index]}"
