"""
Report Writer - Generate Scan Reports

Creates TXT reports for file and URL scans.
Reports are saved to ~/Sentinel/scan_reports/
"""

import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Import result types
from .scoring import ScoringResult
from .static_scanner import ScanResult
from .url_checker import URLCheckResult


class ReportWriter:
    """
    Generates human-readable TXT reports for scans.

    Features:
    - Automatic report directory creation
    - Structured report format
    - All findings included
    - IOC extraction summary
    """

    def __init__(self, reports_dir: Path | None = None):
        """
        Initialize the report writer.

        Args:
            reports_dir: Optional path to reports directory.
                        Defaults to ~/Sentinel/scan_reports/
        """
        self._reports_dir = reports_dir or self._get_default_reports_dir()
        self._ensure_dir_exists()

    def _get_default_reports_dir(self) -> Path:
        """Get the default reports directory."""
        home = Path.home()
        return home / "Sentinel" / "scan_reports"

    def _ensure_dir_exists(self) -> None:
        """Ensure the reports directory exists."""
        self._reports_dir.mkdir(parents=True, exist_ok=True)

    @property
    def reports_dir(self) -> Path:
        """Get the reports directory path."""
        return self._reports_dir

    def write_file_report(self, result: ScanResult) -> Path:
        """
        Write a file scan report.

        Args:
            result: ScanResult from static scanner

        Returns:
            Path to the generated report file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sha_prefix = result.sha256[:8] if result.sha256 else "unknown"
        filename = f"file_{timestamp}_{sha_prefix}.txt"
        filepath = self._reports_dir / filename

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                self._write_file_report_content(f, result)

            logger.info(f"Report written: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Failed to write report: {e}")
            raise

    def _write_file_report_content(self, f, result: ScanResult) -> None:
        """Write file report content."""
        # Header
        f.write("=" * 70 + "\n")
        f.write("SENTINEL FILE SCAN REPORT\n")
        f.write("=" * 70 + "\n\n")

        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("Sentinel Local Scanner - 100% Offline Analysis\n\n")

        # Verdict
        f.write("-" * 70 + "\n")
        f.write("VERDICT\n")
        f.write("-" * 70 + "\n")
        f.write(f"Result:  {result.verdict}\n")
        f.write(f"Score:   {result.score}/100\n")
        f.write(f"Summary: {result.summary}\n\n")

        # File Information
        f.write("-" * 70 + "\n")
        f.write("FILE INFORMATION\n")
        f.write("-" * 70 + "\n")
        f.write(f"Name:      {result.file_name}\n")
        f.write(f"Path:      {result.file_path}\n")
        f.write(f"Size:      {self._format_size(result.file_size)}\n")
        f.write(f"SHA256:    {result.sha256}\n")
        f.write(f"MIME Type: {result.mime_type}\n")
        f.write(f"Extension: {result.extension}\n\n")

        # PE Analysis (if applicable)
        if result.pe_analysis and result.pe_analysis.is_pe:
            pe = result.pe_analysis
            f.write("-" * 70 + "\n")
            f.write("PE ANALYSIS\n")
            f.write("-" * 70 + "\n")
            f.write(f"Type:           {'DLL' if pe.is_dll else 'Executable'}\n")
            f.write(f"Architecture:   {'64-bit' if pe.is_64bit else '32-bit'}\n")
            f.write(f"Sections:       {pe.sections_count}\n")
            f.write(f"Imports:        {pe.imports_count}\n")
            f.write(f"Exports:        {pe.exports_count}\n")
            f.write(f"Entry Point:    0x{pe.entry_point:08X}\n")
            f.write(f"Image Base:     0x{pe.image_base:08X}\n")

            if pe.compile_time:
                f.write(f"Compile Time:   {pe.compile_time}\n")
            if pe.packer_detected:
                f.write(f"Packer:         {pe.packer_detected}\n")
            if pe.has_signature:
                f.write(
                    f"Signed:         {'Yes' if pe.is_signed else 'Signature present'}\n"
                )

            if pe.suspicious_imports:
                f.write(f"\nSuspicious Imports ({len(pe.suspicious_imports)}):\n")
                for imp in pe.suspicious_imports:
                    f.write(
                        f"  [{imp['severity'].upper()}] {imp['function']} - {imp['description']}\n"
                    )

            if pe.high_entropy_sections:
                f.write("\nHigh Entropy Sections:\n")
                for section in pe.high_entropy_sections:
                    f.write(f"  {section['name']}: {section['entropy']:.2f}\n")

            if pe.rwx_sections:
                f.write(f"\nRWX Sections (suspicious): {', '.join(pe.rwx_sections)}\n")

            f.write("\n")

        # Findings
        if result.findings:
            f.write("-" * 70 + "\n")
            f.write(f"FINDINGS ({len(result.findings)})\n")
            f.write("-" * 70 + "\n")

            # Group by severity
            critical = [f for f in result.findings if f.severity == "critical"]
            high = [f for f in result.findings if f.severity == "high"]
            medium = [f for f in result.findings if f.severity == "medium"]
            low = [f for f in result.findings if f.severity == "low"]

            for severity, findings in [
                ("CRITICAL", critical),
                ("HIGH", high),
                ("MEDIUM", medium),
                ("LOW", low),
            ]:
                if findings:
                    f.write(f"\n[{severity}]\n")
                    for finding in findings:
                        f.write(f"  • {finding.title}\n")
                        f.write(f"    {finding.detail}\n")

            f.write("\n")

        # Groq AI analysis
        if result.groq_analysis:
            f.write("-" * 70 + "\n")
            f.write("GROQ AI ANALYSIS\n")
            f.write("-" * 70 + "\n")
            f.write(
                f"Verdict: {result.groq_analysis.get('verdict', 'Unknown')}\n"
            )
            f.write(
                f"Score:   {result.groq_analysis.get('score', 0)}/100\n"
            )
            explanation = result.groq_analysis.get("explanation", "")
            if explanation:
                f.write(f"Reason:  {explanation}\n")
            f.write("\n")

        # ClamAV Results
        if result.clamav.get("available"):
            f.write("-" * 70 + "\n")
            f.write("CLAMAV RESULTS\n")
            f.write("-" * 70 + "\n")
            if result.clamav.get("scanned"):
                if result.clamav.get("infected"):
                    f.write("Status:    INFECTED\n")
                    f.write(f"Signature: {result.clamav.get('signature', 'Unknown')}\n")
                else:
                    f.write("Status:    Clean\n")
            else:
                f.write("Status:    Not scanned\n")
            f.write("\n")

        # IOCs
        iocs = result.iocs
        has_iocs = (
            iocs.urls
            or iocs.ips
            or iocs.domains
            or iocs.file_paths
            or iocs.registry_keys
            or iocs.emails
        )

        if has_iocs:
            f.write("-" * 70 + "\n")
            f.write("EXTRACTED IOCs\n")
            f.write("-" * 70 + "\n")

            if iocs.urls:
                f.write(f"\nURLs ({len(iocs.urls)}):\n")
                for url in iocs.urls[:10]:
                    f.write(f"  {url}\n")

            if iocs.ips:
                f.write(f"\nIP Addresses ({len(iocs.ips)}):\n")
                for ip in iocs.ips[:10]:
                    f.write(f"  {ip}\n")

            if iocs.domains:
                f.write(f"\nDomains ({len(iocs.domains)}):\n")
                for domain in iocs.domains[:10]:
                    f.write(f"  {domain}\n")

            if iocs.file_paths:
                f.write(f"\nFile Paths ({len(iocs.file_paths)}):\n")
                for path in iocs.file_paths[:10]:
                    f.write(f"  {path}\n")

            if iocs.registry_keys:
                f.write(f"\nRegistry Keys ({len(iocs.registry_keys)}):\n")
                for key in iocs.registry_keys[:10]:
                    f.write(f"  {key}\n")

            if iocs.emails:
                f.write(f"\nEmail Addresses ({len(iocs.emails)}):\n")
                for email in iocs.emails[:10]:
                    f.write(f"  {email}\n")

            f.write("\n")

        # Sandbox Results (if any)
        if result.sandbox:
            f.write("-" * 70 + "\n")
            f.write("SANDBOX ANALYSIS\n")
            f.write("-" * 70 + "\n")
            sandbox = result.sandbox

            f.write(f"Status: {sandbox.get('status', 'Unknown')}\n")
            f.write(f"Duration: {sandbox.get('duration', 0)} seconds\n")

            if sandbox.get("processes"):
                f.write(f"\nProcesses Created ({len(sandbox['processes'])}):\n")
                for proc in sandbox["processes"][:10]:
                    f.write(f"  {proc}\n")

            if sandbox.get("files_created"):
                f.write(f"\nFiles Created ({len(sandbox['files_created'])}):\n")
                for file in sandbox["files_created"][:10]:
                    f.write(f"  {file}\n")

            if sandbox.get("registry_modified"):
                f.write(f"\nRegistry Modified ({len(sandbox['registry_modified'])}):\n")
                for reg in sandbox["registry_modified"][:10]:
                    f.write(f"  {reg}\n")

            if sandbox.get("network_connections"):
                f.write(
                    f"\nNetwork Connections ({len(sandbox['network_connections'])}):\n"
                )
                for conn in sandbox["network_connections"][:10]:
                    f.write(f"  {conn}\n")

            f.write("\n")

        # Errors
        if result.errors:
            f.write("-" * 70 + "\n")
            f.write("ERRORS\n")
            f.write("-" * 70 + "\n")
            for error in result.errors:
                f.write(f"  • {error}\n")
            f.write("\n")

        # Footer
        f.write("=" * 70 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 70 + "\n")

    def write_url_report(self, result: URLCheckResult) -> Path:
        """
        Write a URL check report.

        Args:
            result: URLCheckResult from URL checker

        Returns:
            Path to the generated report file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"url_{timestamp}.txt"
        filepath = self._reports_dir / filename

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                self._write_url_report_content(f, result)

            logger.info(f"Report written: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Failed to write report: {e}")
            raise

    def _write_url_report_content(self, f, result: URLCheckResult) -> None:
        """Write URL report content."""
        # Header
        f.write("=" * 70 + "\n")
        f.write("SENTINEL URL CHECK REPORT\n")
        f.write("=" * 70 + "\n\n")

        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("Sentinel Local Scanner - 100% Offline Analysis\n\n")

        # Verdict
        f.write("-" * 70 + "\n")
        f.write("VERDICT\n")
        f.write("-" * 70 + "\n")
        f.write(f"Result:  {result.verdict}\n")
        f.write(f"Score:   {result.score}/100\n")
        f.write(f"Summary: {result.summary}\n\n")

        # URL Information
        f.write("-" * 70 + "\n")
        f.write("URL INFORMATION\n")
        f.write("-" * 70 + "\n")
        f.write(f"Original:   {result.original_url}\n")
        f.write(f"Normalized: {result.normalized_url}\n\n")

        if result.parsed:
            f.write("Parsed Components:\n")
            f.write(f"  Scheme: {result.parsed.get('scheme', 'N/A')}\n")
            f.write(f"  Domain: {result.parsed.get('domain', 'N/A')}\n")
            f.write(f"  TLD:    {result.parsed.get('tld', 'N/A')}\n")
            f.write(f"  Path:   {result.parsed.get('path', 'N/A')}\n")
            if result.parsed.get("query"):
                f.write(f"  Query:  {result.parsed['query']}\n")
        f.write("\n")

        # Flags
        f.write("-" * 70 + "\n")
        f.write("STATUS\n")
        f.write("-" * 70 + "\n")
        f.write(f"Blocked:     {'Yes' if result.is_blocked else 'No'}\n")
        f.write(f"Allowlisted: {'Yes' if result.is_allowlisted else 'No'}\n\n")

        # Reasons/Findings
        if result.reasons:
            f.write("-" * 70 + "\n")
            f.write(f"ANALYSIS ({len(result.reasons)} findings)\n")
            f.write("-" * 70 + "\n")

            for reason in result.reasons:
                severity = reason.get("severity", "info").upper()
                score = reason.get("score", 0)
                score_str = (
                    f"+{score}" if score > 0 else str(score) if score < 0 else ""
                )

                f.write(f"\n[{severity}] {reason['title']}")
                if score_str:
                    f.write(f" ({score_str})")
                f.write(f"\n    {reason['detail']}\n")

        f.write("\n")

        # Footer
        f.write("=" * 70 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 70 + "\n")

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        size_f: float = float(size)
        for unit in ["B", "KB", "MB", "GB"]:
            if size_f < 1024:
                return f"{size_f:.1f} {unit}"
            size_f /= 1024
        return f"{size_f:.1f} TB"


def get_report_writer() -> ReportWriter:
    """Get a report writer instance."""
    return ReportWriter()


def get_platform_reports_dir() -> Path:
    """
    Get the Windows reports directory: %APPDATA%/Sentinel/scan_reports/
    """
    base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    return base / "Sentinel" / "scan_reports"
