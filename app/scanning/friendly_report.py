"""
Friendly Report Generator - User-friendly scan reports

Creates easy-to-understand reports for non-technical users.
Avoids jargon and explains findings in plain language.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FriendlyReportGenerator:
    """
    Generates user-friendly scan reports with plain language.
    
    Designed for normal users, not security professionals.
    """
    
    # Verdict explanations in plain language
    VERDICT_EXPLANATIONS = {
        "Safe": "This file appears to be safe. No threats were detected during our analysis.",
        "Suspicious": "This file has some characteristics that could indicate a problem. We recommend caution.",
        "Likely Malicious": "This file shows multiple warning signs and is likely harmful. We strongly recommend not using it.",
        "Malicious": "This file is dangerous! It shows clear signs of being malware. Do NOT run this file.",
    }
    
    # Severity explanations
    SEVERITY_LABELS = {
        "critical": "🔴 Critical Risk",
        "high": "🟠 High Risk", 
        "medium": "🟡 Medium Risk",
        "low": "🟢 Low Risk",
        "info": "ℹ️ Information",
    }
    
    def generate_file_report(
        self,
        file_path: str | Path,
        static_result: dict | None = None,
        sandbox_result: dict | None = None,
        scoring_result = None,
    ) -> str:
        """
        Generate a user-friendly file scan report.
        
        Returns the report as a string (not saved to file).
        """
        file_path = Path(file_path)
        lines = []
        
        # Header
        lines.append("=" * 60)
        lines.append("📋 SECURITY SCAN REPORT")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"📅 Scanned on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
        lines.append(f"📁 File: {file_path.name}")
        lines.append("")
        
        # Main Verdict - Big and Clear
        lines.append("-" * 60)
        if scoring_result:
            verdict = getattr(scoring_result, 'verdict_label', 'Unknown')
            score = getattr(scoring_result, 'score', 0)
            
            # Verdict emoji and label
            if verdict == "Malicious" or score > 80:
                lines.append("⛔ VERDICT: DANGEROUS")
                lines.append("")
                lines.append("This file is NOT safe to use!")
            elif verdict == "Likely Malicious" or score > 50:
                lines.append("🚨 VERDICT: PROBABLY DANGEROUS")
                lines.append("")
                lines.append("This file shows many warning signs. Avoid using it.")
            elif verdict == "Suspicious" or score > 20:
                lines.append("⚠️ VERDICT: SUSPICIOUS")
                lines.append("")
                lines.append("This file has some concerning characteristics.")
                lines.append("Use with caution or get a second opinion.")
            else:
                lines.append("✅ VERDICT: SAFE")
                lines.append("")
                lines.append("No threats detected. This file appears safe to use.")
            
            lines.append("")
            lines.append(f"Risk Score: {score}/100 " + self._score_bar(score))
            lines.append("")
            
            # Simple explanation
            explanation = self.VERDICT_EXPLANATIONS.get(verdict, "")
            if explanation:
                lines.append(explanation)
        else:
            lines.append("❓ VERDICT: UNKNOWN")
            lines.append("")
            lines.append("We couldn't determine the safety of this file.")
        
        lines.append("-" * 60)
        lines.append("")
        
        # File Details (simplified)
        lines.append("📄 FILE DETAILS")
        lines.append("")
        lines.append(f"  Name: {file_path.name}")
        
        if static_result:
            file_size = static_result.get("file_size", 0)
            lines.append(f"  Size: {self._format_size(file_size)}")
            
            mime = static_result.get("mime_type", "")
            if mime:
                lines.append(f"  Type: {self._friendly_mime_type(mime)}")
            
            # Only show hash if user might need it
            sha256 = static_result.get("sha256", "")
            if sha256:
                lines.append(f"  Fingerprint: {sha256[:16]}...")
        
        lines.append("")
        
        # What We Checked
        lines.append("🔍 WHAT WE CHECKED")
        lines.append("")
        
        checks = []
        if static_result:
            checks.append("✓ File structure and code patterns")
            if static_result.get("pe_info"):
                checks.append("✓ Program header information")
            if static_result.get("yara_matches"):
                checks.append("✓ Known malware signatures")
        
        if sandbox_result and sandbox_result.get("success"):
            checks.append("✓ Behavior when running (sandbox test)")
        
        if not checks:
            checks.append("○ Basic file analysis")
        
        for check in checks:
            lines.append(f"  {check}")
        
        lines.append("")
        
        # Problems Found (if any)
        findings = []
        
        # Collect findings from static analysis
        if static_result:
            for finding in static_result.get("findings", []):
                findings.append({
                    "severity": finding.get("severity", "medium"),
                    "title": finding.get("title", "Unknown issue"),
                    "detail": finding.get("detail", ""),
                    "source": "file analysis"
                })
            
            # YARA matches
            for match in static_result.get("yara_matches", []):
                findings.append({
                    "severity": match.get("severity", "high"),
                    "title": f"Matched known pattern: {match.get('rule', 'Unknown')}",
                    "detail": match.get("description", ""),
                    "source": "signature matching"
                })
        
        # Collect findings from sandbox
        if sandbox_result and sandbox_result.get("success"):
            if sandbox_result.get("timed_out"):
                findings.append({
                    "severity": "medium",
                    "title": "Program took too long to finish",
                    "detail": "The file ran longer than expected. Some malware does this to avoid detection.",
                    "source": "behavior test"
                })
            
            # Network attempts (bad sign)
            network = sandbox_result.get("network_connections", [])
            if network:
                findings.append({
                    "severity": "high",
                    "title": f"Tried to connect to the internet ({len(network)} attempts)",
                    "detail": "This file tried to reach external servers, which could be for malicious purposes.",
                    "source": "behavior test"
                })
            
            # File modifications
            files_created = sandbox_result.get("files_created", [])
            if len(files_created) > 5:
                findings.append({
                    "severity": "medium",
                    "title": f"Created many files ({len(files_created)})",
                    "detail": "Programs that create lots of files might be installing unwanted software.",
                    "source": "behavior test"
                })
            
            # Registry modifications
            registry = sandbox_result.get("registry_modifications", [])
            if registry:
                findings.append({
                    "severity": "high",
                    "title": f"Modified Windows settings ({len(registry)} changes)",
                    "detail": "This file tried to change system settings, which is often a sign of malware.",
                    "source": "behavior test"
                })
            
            # Child processes
            children = sandbox_result.get("child_processes", [])
            if len(children) > 2:
                findings.append({
                    "severity": "medium",
                    "title": f"Launched other programs ({len(children)})",
                    "detail": "Starting multiple programs can indicate spreading or installing additional malware.",
                    "source": "behavior test"
                })
        
        if findings:
            lines.append("⚠️ PROBLEMS FOUND")
            lines.append("")
            
            # Sort by severity
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
            findings.sort(key=lambda x: severity_order.get(x["severity"], 5))
            
            for i, finding in enumerate(findings[:10], 1):  # Limit to 10
                severity_label = self.SEVERITY_LABELS.get(finding["severity"], "")
                lines.append(f"  {i}. {severity_label}")
                lines.append(f"     {finding['title']}")
                if finding["detail"]:
                    # Wrap long details
                    detail = finding["detail"][:100]
                    if len(finding["detail"]) > 100:
                        detail += "..."
                    lines.append(f"     → {detail}")
                lines.append("")
            
            if len(findings) > 10:
                lines.append(f"  ... and {len(findings) - 10} more issues")
                lines.append("")
        else:
            if scoring_result and getattr(scoring_result, 'score', 0) < 20:
                lines.append("✓ NO PROBLEMS FOUND")
                lines.append("")
                lines.append("  Our analysis didn't find any issues with this file.")
                lines.append("")
        
        # Recommendations
        lines.append("-" * 60)
        lines.append("💡 WHAT SHOULD YOU DO?")
        lines.append("")
        
        if scoring_result:
            score = getattr(scoring_result, 'score', 0)
            if score > 80:
                lines.append("  ❌ DELETE this file immediately")
                lines.append("  ❌ Do NOT open or run it")
                lines.append("  ❌ Run a full system antivirus scan")
                lines.append("  ❌ If you already ran it, check your system for issues")
            elif score > 50:
                lines.append("  ⚠️ Do NOT run this file unless you absolutely trust the source")
                lines.append("  ⚠️ Consider deleting it to be safe")
                lines.append("  ⚠️ If you must use it, scan with another antivirus first")
            elif score > 20:
                lines.append("  ⚠️ Be cautious - only run if you trust where it came from")
                lines.append("  ⚠️ Consider getting a second opinion from another scanner")
                lines.append("  ⚠️ Watch for unusual behavior if you run it")
            else:
                lines.append("  ✅ This file looks safe to use")
                lines.append("  ✅ You can run it normally")
                lines.append("  ℹ️ Always download files from trusted sources")
        else:
            lines.append("  ⚠️ Unable to fully analyze - use caution")
        
        lines.append("")
        lines.append("-" * 60)
        
        # Footer
        lines.append("")
        lines.append("This scan was performed 100% offline on your computer.")
        lines.append("No data was sent to any external servers.")
        lines.append("")
        lines.append("Powered by Sentinel Security Suite")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def generate_url_report(
        self,
        url: str,
        result: dict,
    ) -> str:
        """
        Generate a user-friendly URL scan report.
        
        Returns the report as a string.
        """
        lines = []
        
        # Header
        lines.append("=" * 60)
        lines.append("🌐 URL SAFETY REPORT")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"📅 Checked on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
        lines.append(f"🔗 URL: {url}")
        lines.append("")
        
        # Verdict
        lines.append("-" * 60)
        verdict = result.get("verdict", "unknown").lower()
        score = result.get("score", 0)
        
        if verdict == "malicious" or score > 80:
            lines.append("⛔ VERDICT: DANGEROUS WEBSITE")
            lines.append("")
            lines.append("Do NOT visit this website! It may harm your computer.")
        elif verdict == "likely_malicious" or score > 50:
            lines.append("🚨 VERDICT: PROBABLY DANGEROUS")
            lines.append("")
            lines.append("This website shows many warning signs. Avoid visiting.")
        elif verdict == "suspicious" or score > 20:
            lines.append("⚠️ VERDICT: SUSPICIOUS")
            lines.append("")
            lines.append("This website has some concerning characteristics.")
        else:
            lines.append("✅ VERDICT: APPEARS SAFE")
            lines.append("")
            lines.append("No major threats detected for this URL.")
        
        lines.append("")
        lines.append(f"Risk Score: {score}/100 " + self._score_bar(score))
        lines.append("-" * 60)
        lines.append("")
        
        # Reasons (in plain language)
        reasons = result.get("reasons", [])
        if reasons:
            lines.append("🔍 WHAT WE FOUND")
            lines.append("")
            
            for reason in reasons[:8]:
                severity = reason.get("severity", "info")
                emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(severity, "ℹ️")
                lines.append(f"  {emoji} {reason.get('title', 'Unknown')}")
                if reason.get("detail"):
                    lines.append(f"     → {reason['detail'][:80]}")
                lines.append("")
        
        # Recommendations
        lines.append("-" * 60)
        lines.append("💡 WHAT SHOULD YOU DO?")
        lines.append("")
        
        if score > 50:
            lines.append("  ❌ Do NOT visit this website")
            lines.append("  ❌ Do NOT enter any personal information")
            lines.append("  ❌ If you visited, run an antivirus scan")
        elif score > 20:
            lines.append("  ⚠️ Be very careful if you visit")
            lines.append("  ⚠️ Don't download anything from this site")
            lines.append("  ⚠️ Don't enter passwords or personal info")
        else:
            lines.append("  ✅ This website appears safe to visit")
            lines.append("  ℹ️ Still be cautious with downloads and links")
        
        lines.append("")
        lines.append("-" * 60)
        lines.append("")
        lines.append("Powered by Sentinel Security Suite")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def _score_bar(self, score: int) -> str:
        """Create a visual score bar."""
        filled = score // 10
        empty = 10 - filled
        
        if score > 80:
            bar = "🔴" * filled + "⚪" * empty
        elif score > 50:
            bar = "🟠" * filled + "⚪" * empty
        elif score > 20:
            bar = "🟡" * filled + "⚪" * empty
        else:
            bar = "🟢" * filled + "⚪" * empty
        
        return f"[{bar}]"
    
    def _format_size(self, size: int) -> str:
        """Format file size in friendly way."""
        if size < 1024:
            return f"{size} bytes"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"
    
    def _friendly_mime_type(self, mime: str) -> str:
        """Convert MIME type to friendly name."""
        mapping = {
            "application/x-msdownload": "Windows Program",
            "application/x-dosexec": "Windows Program",
            "application/x-executable": "Program File",
            "application/pdf": "PDF Document",
            "application/zip": "ZIP Archive",
            "application/x-rar": "RAR Archive",
            "application/javascript": "JavaScript File",
            "text/html": "Web Page",
            "image/jpeg": "JPEG Image",
            "image/png": "PNG Image",
        }
        return mapping.get(mime, mime)


# Singleton instance
_generator = None


def get_friendly_report_generator() -> FriendlyReportGenerator:
    """Get the friendly report generator instance."""
    global _generator
    if _generator is None:
        _generator = FriendlyReportGenerator()
    return _generator
