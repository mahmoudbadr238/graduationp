"""
Report Writer - Generate Scan Reports

Creates TXT reports for file and URL scans.
Reports are saved to ~/Sentinel/scan_reports/
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Import result types
from .static_scanner import ScanResult
from .url_checker import URLCheckResult
from .scoring import ScoringResult


class ReportWriter:
    """
    Generates human-readable TXT reports for scans.
    
    Features:
    - Automatic report directory creation
    - Structured report format
    - All findings included
    - IOC extraction summary
    """
    
    def __init__(self, reports_dir: Optional[Path] = None):
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
        f.write(f"Sentinel Local Scanner - 100% Offline Analysis\n\n")
        
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
                f.write(f"Signed:         {'Yes' if pe.is_signed else 'Signature present'}\n")
            
            if pe.suspicious_imports:
                f.write(f"\nSuspicious Imports ({len(pe.suspicious_imports)}):\n")
                for imp in pe.suspicious_imports:
                    f.write(f"  [{imp['severity'].upper()}] {imp['function']} - {imp['description']}\n")
            
            if pe.high_entropy_sections:
                f.write(f"\nHigh Entropy Sections:\n")
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
            
            for severity, findings in [("CRITICAL", critical), ("HIGH", high), 
                                       ("MEDIUM", medium), ("LOW", low)]:
                if findings:
                    f.write(f"\n[{severity}]\n")
                    for finding in findings:
                        f.write(f"  • {finding.title}\n")
                        f.write(f"    {finding.detail}\n")
            
            f.write("\n")
        
        # YARA Matches
        if result.yara_matches:
            f.write("-" * 70 + "\n")
            f.write(f"YARA MATCHES ({len(result.yara_matches)})\n")
            f.write("-" * 70 + "\n")
            for match in result.yara_matches:
                f.write(f"  [{match.get('severity', 'medium').upper()}] {match['title']}\n")
                f.write(f"    {match['detail']}\n")
                if match.get('matched_strings'):
                    f.write(f"    Matched: {', '.join(match['matched_strings'][:3])}\n")
            f.write("\n")
        
        # ClamAV Results
        if result.clamav.get("available"):
            f.write("-" * 70 + "\n")
            f.write("CLAMAV RESULTS\n")
            f.write("-" * 70 + "\n")
            if result.clamav.get("scanned"):
                if result.clamav.get("infected"):
                    f.write(f"Status:    INFECTED\n")
                    f.write(f"Signature: {result.clamav.get('signature', 'Unknown')}\n")
                else:
                    f.write(f"Status:    Clean\n")
            else:
                f.write(f"Status:    Not scanned\n")
            f.write("\n")
        
        # IOCs
        iocs = result.iocs
        has_iocs = (iocs.urls or iocs.ips or iocs.domains or 
                   iocs.file_paths or iocs.registry_keys or iocs.emails)
        
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
                f.write(f"\nNetwork Connections ({len(sandbox['network_connections'])}):\n")
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
        f.write(f"Sentinel Local Scanner - 100% Offline Analysis\n\n")
        
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
            if result.parsed.get('query'):
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
                score_str = f"+{score}" if score > 0 else str(score) if score < 0 else ""
                
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
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_f < 1024:
                return f"{size_f:.1f} {unit}"
            size_f /= 1024
        return f"{size_f:.1f} TB"


def get_report_writer() -> ReportWriter:
    """Get a report writer instance."""
    return ReportWriter()


def get_platform_reports_dir() -> Path:
    """
    Get the platform-specific reports directory.
    
    Windows: %APPDATA%/Sentinel/scan_reports/
    Linux/macOS: ~/.config/sentinel/scan_reports/
    """
    import sys
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "Sentinel" / "scan_reports"
    else:
        return Path.home() / ".config" / "sentinel" / "scan_reports"


def write_combined_scan_report(
    file_path: str | Path,
    static_result: dict | None = None,
    sandbox_result: dict | None = None,
    scoring_result: ScoringResult | None = None,
) -> Path:
    """
    Write a comprehensive scan report combining static and sandbox analysis.
    
    Args:
        file_path: Path to the scanned file
        static_result: Output from StaticScanner.scan_file()
        sandbox_result: Output from IntegratedSandbox.run_file().to_dict()
        scoring_result: Output from ThreatScorer.score()
    
    Returns:
        Path to the generated report file
    """
    from datetime import datetime
    
    file_path = Path(file_path)
    reports_dir = get_platform_reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sha_prefix = "unknown"
    if static_result and static_result.get("sha256"):
        sha_prefix = static_result["sha256"][:8]
    
    filename = f"scan_{timestamp}_{sha_prefix}.txt"
    report_path = reports_dir / filename
    
    with open(report_path, "w", encoding="utf-8") as f:
        # Header
        f.write("=" * 72 + "\n")
        f.write("             SENTINEL COMPREHENSIVE SCAN REPORT\n")
        f.write("=" * 72 + "\n\n")
        
        f.write(f"Generated:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Report Type: Combined Static + Sandbox Analysis\n")
        f.write(f"Mode:        100% Offline (No data sent externally)\n\n")
        
        # Verdict Section
        if scoring_result:
            f.write("-" * 72 + "\n")
            f.write("                         THREAT ASSESSMENT\n")
            f.write("-" * 72 + "\n\n")
            f.write(f"  VERDICT:    {scoring_result.verdict_label.upper()}\n")
            f.write(f"  SCORE:      {scoring_result.score}/100\n")
            f.write(f"  SUMMARY:    {scoring_result.summary}\n\n")
        
        # File Information
        f.write("-" * 72 + "\n")
        f.write("                       FILE INFORMATION\n")
        f.write("-" * 72 + "\n\n")
        f.write(f"  File Name:  {file_path.name}\n")
        f.write(f"  Full Path:  {file_path}\n")
        
        if static_result:
            if static_result.get("sha256"):
                f.write(f"  SHA256:     {static_result['sha256']}\n")
            if static_result.get("file_size"):
                size = static_result["file_size"]
                if size >= 1024 * 1024:
                    f.write(f"  Size:       {size / 1024 / 1024:.2f} MB ({size:,} bytes)\n")
                elif size >= 1024:
                    f.write(f"  Size:       {size / 1024:.2f} KB ({size:,} bytes)\n")
                else:
                    f.write(f"  Size:       {size:,} bytes\n")
            if static_result.get("mime_type"):
                f.write(f"  MIME Type:  {static_result['mime_type']}\n")
        f.write("\n")
        
        # Static Analysis Section
        if static_result:
            f.write("-" * 72 + "\n")
            f.write("                       STATIC ANALYSIS\n")
            f.write("-" * 72 + "\n\n")
            
            # PE Information
            pe_info = static_result.get("pe_info", {})
            if pe_info:
                f.write("  [PE Header Information]\n")
                if pe_info.get("architecture"):
                    f.write(f"    Architecture:   {pe_info['architecture']}\n")
                if pe_info.get("entry_point"):
                    f.write(f"    Entry Point:    0x{pe_info['entry_point']:08X}\n")
                if pe_info.get("compile_time"):
                    f.write(f"    Compile Time:   {pe_info['compile_time']}\n")
                if pe_info.get("entropy"):
                    f.write(f"    Entropy:        {pe_info['entropy']:.2f}/8.0")
                    if pe_info["entropy"] > 7.0:
                        f.write(" (HIGH - possibly packed)")
                    f.write("\n")
                f.write("\n")
                
                # Sections
                sections = pe_info.get("sections", [])
                if sections:
                    f.write("  [PE Sections]\n")
                    for sec in sections[:8]:
                        name = sec.get("name", "?")
                        entropy = sec.get("entropy", 0)
                        size = sec.get("size", 0)
                        f.write(f"    {name:10} Size: {size:>10,}  Entropy: {entropy:.2f}\n")
                    if len(sections) > 8:
                        f.write(f"    ... and {len(sections) - 8} more sections\n")
                    f.write("\n")
                
                # Imports
                imports = pe_info.get("imports", [])
                if imports:
                    f.write(f"  [Imports] {len(imports)} functions imported\n")
                    # Show first few DLLs
                    dll_counts = {}
                    for imp in imports:
                        if "!" in str(imp):
                            dll = imp.split("!")[0]
                            dll_counts[dll] = dll_counts.get(dll, 0) + 1
                    for dll, count in list(dll_counts.items())[:5]:
                        f.write(f"    {dll}: {count} functions\n")
                    f.write("\n")
            
            # YARA Matches
            yara_matches = static_result.get("yara_matches", [])
            if yara_matches:
                f.write("  [YARA Detections]\n")
                for match in yara_matches:
                    rule = match.get("rule", "Unknown")
                    severity = match.get("severity", "medium").upper()
                    f.write(f"    [{severity}] {rule}\n")
                    if match.get("description"):
                        f.write(f"           {match['description']}\n")
                f.write("\n")
            
            # IOCs
            iocs = static_result.get("iocs", {})
            has_iocs = any([
                iocs.get("urls"), iocs.get("ips"), iocs.get("domains"),
                iocs.get("registry_paths"), iocs.get("file_paths")
            ])
            if has_iocs:
                f.write("  [Indicators of Compromise]\n")
                
                if iocs.get("urls"):
                    f.write(f"    URLs ({len(iocs['urls'])}):\n")
                    for url in iocs["urls"][:5]:
                        f.write(f"      - {url}\n")
                    if len(iocs["urls"]) > 5:
                        f.write(f"      ... and {len(iocs['urls']) - 5} more\n")
                
                if iocs.get("ips"):
                    f.write(f"    IP Addresses ({len(iocs['ips'])}):\n")
                    for ip in iocs["ips"][:5]:
                        f.write(f"      - {ip}\n")
                    if len(iocs["ips"]) > 5:
                        f.write(f"      ... and {len(iocs['ips']) - 5} more\n")
                
                if iocs.get("domains"):
                    f.write(f"    Domains ({len(iocs['domains'])}):\n")
                    for dom in iocs["domains"][:5]:
                        f.write(f"      - {dom}\n")
                    if len(iocs["domains"]) > 5:
                        f.write(f"      ... and {len(iocs['domains']) - 5} more\n")
                
                if iocs.get("registry_paths"):
                    f.write(f"    Registry Paths ({len(iocs['registry_paths'])}):\n")
                    for reg in iocs["registry_paths"][:5]:
                        f.write(f"      - {reg}\n")
                    if len(iocs["registry_paths"]) > 5:
                        f.write(f"      ... and {len(iocs['registry_paths']) - 5} more\n")
                
                f.write("\n")
        
        # Sandbox Analysis Section
        if sandbox_result:
            f.write("-" * 72 + "\n")
            f.write("                      SANDBOX ANALYSIS\n")
            f.write("-" * 72 + "\n\n")
            
            if sandbox_result.get("success"):
                f.write(f"  Status:         Completed\n")
                f.write(f"  Platform:       {sandbox_result.get('platform', 'Unknown')}\n")
                f.write(f"  Duration:       {sandbox_result.get('duration_seconds', 0):.2f} seconds\n")
                f.write(f"  Exit Code:      {sandbox_result.get('exit_code', 'N/A')}\n")
                
                if sandbox_result.get("timed_out"):
                    f.write(f"  Timed Out:      YES (possible evasion)\n")
                
                if sandbox_result.get("network_blocked"):
                    f.write(f"  Network:        BLOCKED\n")
                
                f.write("\n")
                
                # Resource usage
                if sandbox_result.get("peak_cpu_percent") or sandbox_result.get("peak_memory_mb"):
                    f.write("  [Resource Usage]\n")
                    if sandbox_result.get("peak_cpu_percent"):
                        f.write(f"    Peak CPU:     {sandbox_result['peak_cpu_percent']:.1f}%\n")
                    if sandbox_result.get("peak_memory_mb"):
                        f.write(f"    Peak Memory:  {sandbox_result['peak_memory_mb']:.1f} MB\n")
                    f.write("\n")
                
                # File operations
                files_created = sandbox_result.get("files_created", [])
                files_modified = sandbox_result.get("files_modified", [])
                files_deleted = sandbox_result.get("files_deleted", [])
                
                if files_created or files_modified or files_deleted:
                    f.write("  [File System Activity]\n")
                    
                    if files_created:
                        f.write(f"    Files Created ({len(files_created)}):\n")
                        for fp in files_created[:5]:
                            f.write(f"      + {fp}\n")
                        if len(files_created) > 5:
                            f.write(f"      ... and {len(files_created) - 5} more\n")
                    
                    if files_modified:
                        f.write(f"    Files Modified ({len(files_modified)}):\n")
                        for fp in files_modified[:5]:
                            f.write(f"      ~ {fp}\n")
                        if len(files_modified) > 5:
                            f.write(f"      ... and {len(files_modified) - 5} more\n")
                    
                    if files_deleted:
                        f.write(f"    Files Deleted ({len(files_deleted)}):\n")
                        for fp in files_deleted[:5]:
                            f.write(f"      - {fp}\n")
                        if len(files_deleted) > 5:
                            f.write(f"      ... and {len(files_deleted) - 5} more\n")
                    
                    f.write("\n")
                
                # Registry modifications
                registry_mods = sandbox_result.get("registry_modifications", [])
                if registry_mods:
                    f.write(f"  [Registry Modifications] ({len(registry_mods)})\n")
                    for reg in registry_mods[:5]:
                        f.write(f"    {reg}\n")
                    if len(registry_mods) > 5:
                        f.write(f"    ... and {len(registry_mods) - 5} more\n")
                    f.write("\n")
                
                # Network connections
                network = sandbox_result.get("network_connections", [])
                if network:
                    f.write(f"  [Network Connection Attempts] ({len(network)})\n")
                    for conn in network[:5]:
                        f.write(f"    {conn}\n")
                    if len(network) > 5:
                        f.write(f"    ... and {len(network) - 5} more\n")
                    f.write("\n")
                
                # Child processes
                children = sandbox_result.get("child_processes", [])
                if children:
                    f.write(f"  [Child Processes Spawned] ({len(children)})\n")
                    for child in children[:5]:
                        name = child.get("name", "Unknown")
                        pid = child.get("pid", "?")
                        f.write(f"    {name} (PID: {pid})\n")
                    if len(children) > 5:
                        f.write(f"    ... and {len(children) - 5} more\n")
                    f.write("\n")
                
                # Console output
                stdout = sandbox_result.get("stdout", "").strip()
                stderr = sandbox_result.get("stderr", "").strip()
                
                if stdout:
                    f.write("  [Standard Output]\n")
                    for line in stdout.split("\n")[:10]:
                        f.write(f"    {line}\n")
                    if stdout.count("\n") > 10:
                        f.write("    ... (truncated)\n")
                    f.write("\n")
                
                if stderr:
                    f.write("  [Standard Error]\n")
                    for line in stderr.split("\n")[:10]:
                        f.write(f"    {line}\n")
                    if stderr.count("\n") > 10:
                        f.write("    ... (truncated)\n")
                    f.write("\n")
            
            else:
                f.write(f"  Status:         Failed\n")
                if sandbox_result.get("error_message"):
                    f.write(f"  Error:          {sandbox_result['error_message']}\n")
                f.write("\n")
        
        # Detailed Explanation
        if scoring_result and scoring_result.explanation:
            f.write("-" * 72 + "\n")
            f.write("                    DETAILED EXPLANATION\n")
            f.write("-" * 72 + "\n\n")
            f.write(scoring_result.explanation)
            f.write("\n\n")
        
        # Footer
        f.write("=" * 72 + "\n")
        f.write("                       END OF REPORT\n")
        f.write("=" * 72 + "\n")
    
    logger.info(f"Combined scan report written: {report_path}")
    return report_path
