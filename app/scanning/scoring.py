"""
Scan result scoring and verdict engine.

Combines static analysis findings and sandbox behavioral results
into a single threat score (0-100) with human-readable verdict.

Score Ranges:
    0-20:   Safe - No indicators of malicious behavior
    21-50:  Suspicious - Some concerning indicators, review recommended
    51-80:  Likely Malicious - Multiple threat indicators detected
    81-100: Malicious - High confidence threat detection
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ScoringResult:
    """Result of threat scoring analysis."""
    
    score: int  # 0-100
    verdict: str  # "safe", "suspicious", "malicious", "unknown"
    verdict_label: str  # Human-readable: "Safe", "Suspicious", etc.
    summary: str  # One-line summary
    explanation: str  # Detailed multi-line explanation
    breakdown: dict[str, int] = field(default_factory=dict)  # Category -> points
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "verdict": self.verdict,
            "verdict_label": self.verdict_label,
            "summary": self.summary,
            "explanation": self.explanation,
            "breakdown": self.breakdown,
        }


class ThreatScorer:
    """
    Calculates threat scores from static and dynamic analysis results.
    
    Scoring Philosophy:
    - Start at 0 (assume safe)
    - Add points for each indicator found
    - Cap at 100
    - Multiple indicators in same category don't stack linearly
    """
    
    # Weights for different finding categories
    WEIGHTS = {
        # Static analysis weights
        "yara_match": 30,           # YARA rule matched
        "yara_match_additional": 10, # Each additional YARA match
        "suspicious_import": 5,      # Per suspicious import
        "suspicious_import_max": 25, # Cap for import scoring
        "packed_binary": 15,         # Entropy suggests packing
        "no_version_info": 5,        # Missing PE version info
        "suspicious_section": 8,     # Unusual PE section
        "ioc_ip": 8,                 # IP address found
        "ioc_url": 10,               # URL found
        "ioc_domain": 8,             # Domain found
        "ioc_email": 5,              # Email found
        "ioc_registry": 12,          # Registry path found
        "ioc_max": 30,               # Cap for all IOCs
        
        # Sandbox behavior weights
        "sandbox_crash": 20,         # Process crashed
        "sandbox_timeout": 10,       # Took too long (evasion?)
        "high_cpu": 5,               # Excessive CPU usage
        "high_memory": 5,            # Excessive memory usage
        "file_created": 3,           # Each file created
        "file_modified": 4,          # Each file modified
        "file_deleted": 5,           # Each file deleted
        "file_ops_max": 25,          # Cap for file operations
        "registry_write": 8,         # Registry modification
        "registry_max": 20,          # Cap for registry ops
        "network_attempt": 15,       # Tried to access network
        "process_spawned": 5,        # Each child process
        "process_max": 15,           # Cap for process spawning
    }
    
    # Suspicious Windows API imports
    SUSPICIOUS_IMPORTS = {
        # Process manipulation
        "CreateRemoteThread", "OpenProcess", "WriteProcessMemory",
        "ReadProcessMemory", "VirtualAllocEx", "NtUnmapViewOfSection",
        "QueueUserAPC", "SetThreadContext",
        
        # Code injection
        "LoadLibraryA", "LoadLibraryW", "GetProcAddress",
        "VirtualAlloc", "VirtualProtect", "HeapCreate",
        
        # Persistence
        "RegSetValueExA", "RegSetValueExW", "RegCreateKeyExA",
        "CreateServiceA", "CreateServiceW",
        
        # Evasion
        "IsDebuggerPresent", "CheckRemoteDebuggerPresent",
        "NtQueryInformationProcess", "GetTickCount", "QueryPerformanceCounter",
        
        # Credentials/crypto
        "CryptEncrypt", "CryptDecrypt", "CryptAcquireContextA",
        "CredEnumerateA", "CredEnumerateW",
        
        # Network
        "WSAStartup", "socket", "connect", "send", "recv",
        "InternetOpenA", "InternetOpenW", "HttpOpenRequestA",
        "URLDownloadToFileA", "URLDownloadToFileW",
        
        # Keylogging
        "SetWindowsHookExA", "SetWindowsHookExW",
        "GetAsyncKeyState", "GetKeyState",
        
        # Screen capture
        "BitBlt", "GetDC", "CreateCompatibleDC",
    }
    
    def __init__(self):
        self._breakdown: dict[str, int] = {}
        self._explanations: list[str] = []
    
    def score(
        self,
        static_result: dict[str, Any] | None = None,
        sandbox_result: dict[str, Any] | None = None,
    ) -> ScoringResult:
        """
        Calculate threat score from analysis results.
        
        Args:
            static_result: Output from StaticScanner.scan_file()
            sandbox_result: Output from IntegratedSandbox.run_file().to_dict()
        
        Returns:
            ScoringResult with score, verdict, and explanation
        """
        self._breakdown = {}
        self._explanations = []
        total = 0
        
        # Score static analysis
        if static_result:
            total += self._score_static(static_result)
        
        # Score sandbox behavior
        if sandbox_result:
            total += self._score_sandbox(sandbox_result)
        
        # Cap at 100
        total = min(100, max(0, total))
        
        # Determine verdict
        verdict, verdict_label = self._get_verdict(total)
        
        # Build summary and explanation
        summary = self._build_summary(total, verdict_label)
        explanation = self._build_explanation(total, verdict_label)
        
        return ScoringResult(
            score=total,
            verdict=verdict,
            verdict_label=verdict_label,
            summary=summary,
            explanation=explanation,
            breakdown=self._breakdown.copy(),
        )
    
    def _score_static(self, result: dict[str, Any]) -> int:
        """Score static analysis findings."""
        points = 0
        
        # YARA matches
        yara_matches = result.get("yara_matches", [])
        if yara_matches:
            first_match_pts = self.WEIGHTS["yara_match"]
            additional_pts = (len(yara_matches) - 1) * self.WEIGHTS["yara_match_additional"]
            yara_pts = first_match_pts + additional_pts
            points += yara_pts
            self._breakdown["yara_matches"] = yara_pts
            
            rule_names = [m.get("rule", "unknown") for m in yara_matches[:5]]
            self._explanations.append(
                f"YARA rules matched: {', '.join(rule_names)}. "
                "These signature-based detections indicate known malicious patterns."
            )
        
        # PE analysis
        pe_info = result.get("pe_info", {})
        if pe_info:
            # Check entropy (high entropy = possibly packed)
            entropy = pe_info.get("entropy")
            if entropy and entropy > 7.0:
                pts = self.WEIGHTS["packed_binary"]
                points += pts
                self._breakdown["high_entropy"] = pts
                self._explanations.append(
                    f"File has high entropy ({entropy:.2f}/8.0), suggesting it may be "
                    "packed or encrypted to hide its true contents from analysis."
                )
            
            # Check for missing version info
            if not pe_info.get("version_info"):
                pts = self.WEIGHTS["no_version_info"]
                points += pts
                self._breakdown["no_version_info"] = pts
                self._explanations.append(
                    "Missing version information. Legitimate software usually includes "
                    "company name, product version, and copyright details."
                )
            
            # Check suspicious imports
            imports = pe_info.get("imports", [])
            suspicious_found = []
            for imp in imports:
                if imp in self.SUSPICIOUS_IMPORTS:
                    suspicious_found.append(imp)
            
            if suspicious_found:
                import_pts = min(
                    len(suspicious_found) * self.WEIGHTS["suspicious_import"],
                    self.WEIGHTS["suspicious_import_max"]
                )
                points += import_pts
                self._breakdown["suspicious_imports"] = import_pts
                
                shown = suspicious_found[:6]
                more = len(suspicious_found) - 6
                imp_list = ", ".join(shown)
                if more > 0:
                    imp_list += f" (+{more} more)"
                
                self._explanations.append(
                    f"Suspicious API imports detected: {imp_list}. "
                    "These functions are commonly used by malware for tasks like "
                    "code injection, keylogging, or evading detection."
                )
            
            # Check unusual sections
            sections = pe_info.get("sections", [])
            unusual_sections = []
            normal_names = {".text", ".data", ".rdata", ".bss", ".idata", ".edata", 
                          ".reloc", ".rsrc", ".tls", ".pdata", ".gfids", ".00cfg"}
            for sec in sections:
                name = sec.get("name", "").strip()
                if name and name.lower() not in {n.lower() for n in normal_names}:
                    if not name.startswith("."):
                        unusual_sections.append(name)
            
            if unusual_sections:
                sec_pts = min(len(unusual_sections) * self.WEIGHTS["suspicious_section"], 20)
                points += sec_pts
                self._breakdown["unusual_sections"] = sec_pts
                self._explanations.append(
                    f"Unusual PE sections found: {', '.join(unusual_sections[:3])}. "
                    "Non-standard section names may indicate custom packers or obfuscation."
                )
        
        # IOC extraction
        iocs = result.get("iocs", {})
        ioc_pts = 0
        ioc_details = []
        
        if iocs.get("ips"):
            ip_pts = min(len(iocs["ips"]) * self.WEIGHTS["ioc_ip"], 15)
            ioc_pts += ip_pts
            ioc_details.append(f"{len(iocs['ips'])} IP address(es)")
        
        if iocs.get("urls"):
            url_pts = min(len(iocs["urls"]) * self.WEIGHTS["ioc_url"], 20)
            ioc_pts += url_pts
            ioc_details.append(f"{len(iocs['urls'])} URL(s)")
        
        if iocs.get("domains"):
            dom_pts = min(len(iocs["domains"]) * self.WEIGHTS["ioc_domain"], 15)
            ioc_pts += dom_pts
            ioc_details.append(f"{len(iocs['domains'])} domain(s)")
        
        if iocs.get("registry_paths"):
            reg_pts = min(len(iocs["registry_paths"]) * self.WEIGHTS["ioc_registry"], 15)
            ioc_pts += reg_pts
            ioc_details.append(f"{len(iocs['registry_paths'])} registry path(s)")
        
        if ioc_pts > 0:
            ioc_pts = min(ioc_pts, self.WEIGHTS["ioc_max"])
            points += ioc_pts
            self._breakdown["iocs"] = ioc_pts
            self._explanations.append(
                f"Indicators of Compromise found: {', '.join(ioc_details)}. "
                "Embedded network addresses or registry paths may indicate "
                "communication with remote servers or system persistence mechanisms."
            )
        
        return points
    
    def _score_sandbox(self, result: dict[str, Any]) -> int:
        """Score sandbox execution behavior."""
        points = 0
        
        if not result.get("success", True):
            # Sandbox failed or wasn't run
            if result.get("error_message"):
                self._explanations.append(
                    f"Sandbox analysis note: {result.get('error_message', 'Unknown error')}"
                )
            return 0
        
        # Check exit code
        exit_code = result.get("exit_code", 0)
        if exit_code != 0 and exit_code is not None:
            pts = self.WEIGHTS["sandbox_crash"]
            points += pts
            self._breakdown["abnormal_exit"] = pts
            self._explanations.append(
                f"Process exited abnormally with code {exit_code}. "
                "This could indicate a crash, anti-analysis behavior, or "
                "the program requires specific conditions to run."
            )
        
        # Check for timeout
        if result.get("timed_out"):
            pts = self.WEIGHTS["sandbox_timeout"]
            points += pts
            self._breakdown["timeout"] = pts
            self._explanations.append(
                "Process exceeded the allowed execution time. "
                "This may indicate an infinite loop, sleep-based evasion, "
                "or waiting for user interaction."
            )
        
        # Check resource usage
        peak_cpu = result.get("peak_cpu_percent", 0)
        if peak_cpu and peak_cpu > 80:
            pts = self.WEIGHTS["high_cpu"]
            points += pts
            self._breakdown["high_cpu"] = pts
            self._explanations.append(
                f"High CPU usage detected ({peak_cpu:.1f}%). "
                "Could indicate cryptomining, intensive computation, or DoS behavior."
            )
        
        peak_mem = result.get("peak_memory_mb", 0)
        if peak_mem and peak_mem > 500:
            pts = self.WEIGHTS["high_memory"]
            points += pts
            self._breakdown["high_memory"] = pts
            self._explanations.append(
                f"High memory consumption ({peak_mem:.1f} MB). "
                "May indicate memory-based attacks or resource exhaustion attempts."
            )
        
        # File operations
        files_created = result.get("files_created", [])
        files_modified = result.get("files_modified", [])
        files_deleted = result.get("files_deleted", [])
        
        file_pts = 0
        file_details = []
        
        if files_created:
            file_pts += len(files_created) * self.WEIGHTS["file_created"]
            file_details.append(f"created {len(files_created)}")
        
        if files_modified:
            file_pts += len(files_modified) * self.WEIGHTS["file_modified"]
            file_details.append(f"modified {len(files_modified)}")
        
        if files_deleted:
            file_pts += len(files_deleted) * self.WEIGHTS["file_deleted"]
            file_details.append(f"deleted {len(files_deleted)}")
        
        if file_pts > 0:
            file_pts = min(file_pts, self.WEIGHTS["file_ops_max"])
            points += file_pts
            self._breakdown["file_operations"] = file_pts
            self._explanations.append(
                f"File system activity detected: {', '.join(file_details)} file(s). "
                "Programs that modify many files could be droppers, installers, or ransomware."
            )
        
        # Registry operations (Windows)
        registry_ops = result.get("registry_modifications", [])
        if registry_ops:
            reg_pts = min(len(registry_ops) * self.WEIGHTS["registry_write"], 
                         self.WEIGHTS["registry_max"])
            points += reg_pts
            self._breakdown["registry_modifications"] = reg_pts
            self._explanations.append(
                f"Registry modifications detected: {len(registry_ops)} operation(s). "
                "Registry changes can establish persistence, modify system settings, "
                "or disable security features."
            )
        
        # Network attempts
        network_attempts = result.get("network_connections", [])
        if network_attempts:
            pts = self.WEIGHTS["network_attempt"]
            points += pts
            self._breakdown["network_attempts"] = pts
            self._explanations.append(
                f"Network connection attempts: {len(network_attempts)}. "
                "Even blocked attempts indicate the program wants to "
                "communicate externally, possibly for C2 or data exfiltration."
            )
        
        # Process spawning
        child_procs = result.get("child_processes", [])
        if child_procs:
            proc_pts = min(len(child_procs) * self.WEIGHTS["process_spawned"],
                          self.WEIGHTS["process_max"])
            points += proc_pts
            self._breakdown["process_spawning"] = proc_pts
            
            proc_names = [p.get("name", "unknown") for p in child_procs[:3]]
            self._explanations.append(
                f"Child processes created: {', '.join(proc_names)}. "
                "Spawning additional processes can indicate multi-stage payloads "
                "or attempts to elevate privileges."
            )
        
        return points
    
    def _get_verdict(self, score: int) -> tuple[str, str]:
        """Map score to verdict."""
        if score <= 20:
            return "safe", "Safe"
        elif score <= 50:
            return "suspicious", "Suspicious"
        elif score <= 80:
            return "likely_malicious", "Likely Malicious"
        else:
            return "malicious", "Malicious"
    
    def _build_summary(self, score: int, verdict_label: str) -> str:
        """Build one-line summary."""
        if score == 0:
            return "No threats detected. File appears clean."
        elif score <= 20:
            return f"Low risk (score: {score}/100). Minor indicators found but likely benign."
        elif score <= 50:
            return f"Moderate risk (score: {score}/100). Some concerning behaviors detected."
        elif score <= 80:
            return f"High risk (score: {score}/100). Multiple threat indicators present."
        else:
            return f"Critical risk (score: {score}/100). Strong evidence of malicious behavior."
    
    def _build_explanation(self, score: int, verdict_label: str) -> str:
        """Build detailed multi-paragraph explanation."""
        lines = []
        
        # Header
        lines.append(f"=== Threat Assessment: {verdict_label} (Score: {score}/100) ===")
        lines.append("")
        
        if not self._explanations:
            lines.append("No concerning indicators were found during analysis.")
            lines.append("The file appears to be safe based on available evidence.")
        else:
            lines.append("The following indicators contributed to this assessment:")
            lines.append("")
            
            for i, exp in enumerate(self._explanations, 1):
                lines.append(f"{i}. {exp}")
                lines.append("")
        
        # Breakdown table
        if self._breakdown:
            lines.append("--- Score Breakdown ---")
            for category, pts in sorted(self._breakdown.items(), key=lambda x: -x[1]):
                lines.append(f"  {category}: +{pts} points")
            lines.append("")
        
        # Recommendation
        lines.append("--- Recommendation ---")
        if score <= 20:
            lines.append("This file is likely safe to use. No action required.")
        elif score <= 50:
            lines.append("Exercise caution. Consider scanning with additional tools ")
            lines.append("or researching the file's origin before running it.")
        elif score <= 80:
            lines.append("This file shows significant threat indicators. ")
            lines.append("Do NOT run this file unless you are certain of its safety. ")
            lines.append("Consider deleting or quarantining it.")
        else:
            lines.append("This file is almost certainly malicious. ")
            lines.append("DELETE this file immediately and scan your system for infections. ")
            lines.append("Do not share or execute this file under any circumstances.")
        
        return "\n".join(lines)


def score_scan_results(
    static_result: dict[str, Any] | None = None,
    sandbox_result: dict[str, Any] | None = None,
) -> ScoringResult:
    """
    Convenience function to score analysis results.
    
    Args:
        static_result: Output from StaticScanner.scan_file()
        sandbox_result: Output from IntegratedSandbox.run_file().to_dict()
    
    Returns:
        ScoringResult with threat assessment
    """
    scorer = ThreatScorer()
    return scorer.score(static_result, sandbox_result)
