"""
Static Scanner - Local File Analysis Engine

Performs comprehensive static analysis on files:
- SHA256 hashing (chunked for large files)
- Metadata extraction
- PE header analysis for executables
- Entropy calculation
- YARA rule matching
- Optional ClamAV integration

100% Offline - No network required.
"""

import hashlib
import logging
import math
import mimetypes
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import cupy as cp  # type: ignore[import]
    import numpy as np

    GPU_COMPUTE_AVAILABLE = True
except Exception:
    cp = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    GPU_COMPUTE_AVAILABLE = False

# Try to import pefile for PE analysis
try:
    import pefile
    PEFILE_AVAILABLE = True
except ImportError:
    PEFILE_AVAILABLE = False
    logger.warning("pefile not installed. Install with: pip install pefile")

from .clamav_adapter import get_clamav_adapter
from .yara_engine import get_pattern_scanner, get_yara_engine

# Suspicious PE imports that indicate potential malicious behavior
SUSPICIOUS_IMPORTS = {
    # Process injection
    "VirtualAllocEx": ("Process injection", "critical"),
    "WriteProcessMemory": ("Process memory manipulation", "critical"),
    "CreateRemoteThread": ("Remote thread creation", "critical"),
    "NtCreateThreadEx": ("Low-level thread creation", "critical"),
    "RtlCreateUserThread": ("Undocumented thread creation", "critical"),
    "QueueUserAPC": ("APC injection", "high"),
    "SetThreadContext": ("Thread context manipulation", "critical"),

    # Memory manipulation
    "VirtualAlloc": ("Memory allocation", "medium"),
    "VirtualProtect": ("Memory protection change", "high"),
    "VirtualProtectEx": ("Remote memory protection change", "critical"),
    "RtlMoveMemory": ("Memory copy operation", "low"),

    # Code execution
    "WinExec": ("Command execution", "high"),
    "ShellExecuteA": ("Shell execution", "medium"),
    "ShellExecuteW": ("Shell execution", "medium"),
    "ShellExecuteExA": ("Extended shell execution", "medium"),
    "ShellExecuteExW": ("Extended shell execution", "medium"),
    "CreateProcessA": ("Process creation", "medium"),
    "CreateProcessW": ("Process creation", "medium"),

    # Registry manipulation
    "RegSetValueA": ("Registry modification", "medium"),
    "RegSetValueW": ("Registry modification", "medium"),
    "RegSetValueExA": ("Registry modification", "medium"),
    "RegSetValueExW": ("Registry modification", "medium"),
    "RegCreateKeyA": ("Registry key creation", "medium"),
    "RegCreateKeyW": ("Registry key creation", "medium"),

    # DLL injection
    "LoadLibraryA": ("DLL loading", "low"),
    "LoadLibraryW": ("DLL loading", "low"),
    "LoadLibraryExA": ("Extended DLL loading", "medium"),
    "LoadLibraryExW": ("Extended DLL loading", "medium"),
    "GetProcAddress": ("Function resolution", "low"),

    # Privilege escalation
    "AdjustTokenPrivileges": ("Privilege adjustment", "high"),
    "OpenProcessToken": ("Token access", "medium"),
    "ImpersonateLoggedOnUser": ("User impersonation", "high"),

    # Keylogging/Hooking
    "SetWindowsHookExA": ("Windows hook installation", "high"),
    "SetWindowsHookExW": ("Windows hook installation", "high"),
    "GetAsyncKeyState": ("Keystroke monitoring", "high"),
    "GetKeyState": ("Key state monitoring", "medium"),

    # Network
    "URLDownloadToFileA": ("File download", "high"),
    "URLDownloadToFileW": ("File download", "high"),
    "InternetOpenA": ("Internet access", "medium"),
    "InternetOpenW": ("Internet access", "medium"),
    "HttpOpenRequestA": ("HTTP request", "medium"),
    "HttpOpenRequestW": ("HTTP request", "medium"),
    "WSAStartup": ("Network socket initialization", "low"),

    # Crypto
    "CryptEncrypt": ("Data encryption", "medium"),
    "CryptDecrypt": ("Data decryption", "medium"),
    "CryptAcquireContextA": ("Cryptographic context", "low"),

    # Anti-debugging
    "IsDebuggerPresent": ("Debugger detection", "high"),
    "CheckRemoteDebuggerPresent": ("Remote debugger detection", "high"),
    "NtQueryInformationProcess": ("Process information query", "medium"),
    "OutputDebugStringA": ("Debug output", "low"),
}

# Script file extensions
SCRIPT_EXTENSIONS = {".ps1", ".vbs", ".js", ".bat", ".cmd", ".wsf", ".hta"}

# Executable extensions
EXECUTABLE_EXTENSIONS = {".exe", ".dll", ".sys", ".scr", ".com", ".pif", ".msi"}


@dataclass
class Finding:
    """A single finding from static analysis."""
    title: str
    detail: str
    severity: str  # low, medium, high, critical
    category: str = "general"


@dataclass
class IOCExtraction:
    """Extracted Indicators of Compromise."""
    urls: list[str] = field(default_factory=list)
    ips: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    file_paths: list[str] = field(default_factory=list)
    registry_keys: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)


@dataclass
class PEAnalysis:
    """PE file analysis results."""
    is_pe: bool = False
    is_dll: bool = False
    is_64bit: bool = False
    imports_count: int = 0
    exports_count: int = 0
    sections_count: int = 0
    suspicious_imports: list[dict[str, str]] = field(default_factory=list)
    high_entropy_sections: list[dict[str, Any]] = field(default_factory=list)
    rwx_sections: list[str] = field(default_factory=list)
    has_signature: bool = False
    is_signed: bool = False
    compile_time: str | None = None
    packer_detected: str | None = None
    entry_point: int = 0
    image_base: int = 0


@dataclass
class ScanResult:
    """Complete scan result."""
    # Basic info
    file_path: str
    file_name: str
    file_size: int
    sha256: str
    mime_type: str
    extension: str

    # Verdict
    verdict: str  # Safe, Suspicious, Malicious, Unknown
    score: int  # 0-100
    summary: str

    # Detailed results
    findings: list[Finding] = field(default_factory=list)
    iocs: IOCExtraction = field(default_factory=IOCExtraction)
    pe_analysis: PEAnalysis | None = None
    yara_matches: list[dict[str, Any]] = field(default_factory=list)
    clamav: dict[str, Any] = field(default_factory=dict)

    # Static analysis details
    static: dict[str, Any] = field(default_factory=dict)

    # Sandbox results (if run)
    sandbox: dict[str, Any] | None = None

    # Error tracking
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict for PySide6 signal emission."""
        from dataclasses import asdict
        return asdict(self)


class StaticScanner:
    """
    Local static file scanner.
    
    Performs comprehensive offline analysis:
    - Hash calculation
    - Metadata extraction
    - PE analysis (for Windows executables)
    - YARA rule matching
    - Pattern detection
    - IOC extraction
    - Optional ClamAV scanning
    """

    # Entropy threshold for suspicious sections
    HIGH_ENTROPY_THRESHOLD = 7.0

    def __init__(self):
        """Initialize the static scanner."""
        self._yara_engine = get_yara_engine()
        self._clamav = get_clamav_adapter()
        self._pattern_scanner = get_pattern_scanner()
        self._compute_backend = "cpu"
        self._init_compute_backend()

    def _init_compute_backend(self) -> None:
        """
        Select compute backend for expensive numeric operations.

        Modes via SENTINEL_SCAN_COMPUTE:
        - auto (default): use GPU only if available and healthy
        - gpu: force GPU (falls back to CPU if unavailable)
        - cpu: force CPU
        """
        requested = os.environ.get("SENTINEL_SCAN_COMPUTE", "auto").strip().lower()
        if requested not in {"auto", "gpu", "cpu"}:
            requested = "auto"

        if requested == "cpu":
            self._compute_backend = "cpu"
            return

        if not GPU_COMPUTE_AVAILABLE:
            if requested == "gpu":
                logger.warning("GPU compute requested but CuPy/Numpy is unavailable; falling back to CPU")
            self._compute_backend = "cpu"
            return

        try:
            device_count = int(cp.cuda.runtime.getDeviceCount())  # type: ignore[union-attr]
            self._compute_backend = "gpu" if device_count > 0 else "cpu"
            if requested == "gpu" and device_count <= 0:
                logger.warning("GPU compute requested but no CUDA device found; falling back to CPU")
        except Exception as e:
            if requested == "gpu":
                logger.warning(f"GPU compute requested but initialization failed; falling back to CPU ({e})")
            self._compute_backend = "cpu"

        logger.info(f"Static scanner compute backend: {self._compute_backend}")

    def scan_file(self, file_path: str, run_clamav: bool = True) -> ScanResult:
        """
        Perform static analysis on a file.
        
        Args:
            file_path: Path to file to scan
            run_clamav: Whether to run ClamAV if available
            
        Returns:
            ScanResult with all analysis data
        """
        path = Path(file_path)

        if not path.exists():
            return self._error_result(file_path, "File not found")

        if not path.is_file():
            return self._error_result(file_path, "Not a file")

        # Initialize result
        result = ScanResult(
            file_path=str(path.absolute()),
            file_name=path.name,
            file_size=path.stat().st_size,
            sha256="",
            mime_type="",
            extension=path.suffix.lower(),
            verdict="Unknown",
            score=0,
            summary="",
        )

        try:
            # Stage 1: Hash and metadata
            result.sha256 = self._compute_sha256(path)
            result.mime_type = self._get_mime_type(path)

            # Stage 2: Read file content for analysis
            try:
                with open(path, "rb") as f:
                    # Read up to 10MB for analysis
                    content = f.read(10 * 1024 * 1024)
            except Exception as e:
                result.errors.append(f"Could not read file: {e}")
                content = b""

            # Stage 3: PE analysis (if applicable)
            if result.extension in EXECUTABLE_EXTENSIONS or self._is_pe_file(content):
                result.pe_analysis = self._analyze_pe(path, content)
                self._add_pe_findings(result)

            # Stage 4: Script analysis (if applicable)
            if result.extension in SCRIPT_EXTENSIONS:
                self._analyze_script(result, content)

            # Stage 5: YARA scanning
            if self._yara_engine.is_available:
                yara_matches = self._yara_engine.scan_file(str(path))
                result.yara_matches = self._yara_engine.get_findings(yara_matches)
                for match in result.yara_matches:
                    result.findings.append(Finding(
                        title=match["title"],
                        detail=match["detail"],
                        severity=match["severity"],
                        category=match.get("category", "yara")
                    ))
            else:
                # Use fallback pattern scanner (results count as YARA matches in UI)
                pattern_findings = self._pattern_scanner.scan_data(content)
                result.yara_matches = pattern_findings  # show in YARA count
                for f in pattern_findings:
                    result.findings.append(Finding(
                        title=f["title"],
                        detail=f["detail"],
                        severity=f["severity"],
                        category=f.get("category", "pattern")
                    ))

            # Stage 6: IOC extraction
            result.iocs = self._extract_iocs(content)

            # Stage 7: ClamAV (optional)
            if run_clamav and self._clamav.is_available:
                clamav_result = self._clamav.scan_file(str(path))
                result.clamav = {
                    "available": True,
                    "scanned": clamav_result.scanned,
                    "infected": clamav_result.infected,
                    "signature": clamav_result.signature_name,
                }
                if clamav_result.infected:
                    result.findings.append(Finding(
                        title=f"ClamAV Detection: {clamav_result.signature_name}",
                        detail="File detected as malware by ClamAV",
                        severity="critical",
                        category="antivirus"
                    ))
            else:
                result.clamav = {"available": False, "scanned": False}

            # Stage 8: Calculate score and verdict
            result.score = self._calculate_score(result)
            result.verdict = self._determine_verdict(result.score)
            result.summary = self._generate_summary(result)

            # Store static analysis metadata
            result.static = {
                "yara_available": self._yara_engine.is_available,
                "clamav_available": self._clamav.is_available,
                "pe_analysis_available": PEFILE_AVAILABLE,
                "file_entropy": self._calculate_entropy(content),
            }

        except Exception as e:
            logger.error(f"Scan error for {file_path}: {e}")
            result.errors.append(str(e))
            result.verdict = "Unknown"
            result.summary = f"Error during scan: {e}"

        return result

    def _compute_sha256(self, path: Path) -> str:
        """Compute SHA256 hash using chunked reading."""
        sha256 = hashlib.sha256()

        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)

        return sha256.hexdigest()

    def _get_mime_type(self, path: Path) -> str:
        """Get MIME type of file."""
        mime_type, _ = mimetypes.guess_type(str(path))
        return mime_type or "application/octet-stream"

    def _is_pe_file(self, content: bytes) -> bool:
        """Check if content is a PE file."""
        return content[:2] == b"MZ"

    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of data."""
        if self._compute_backend == "gpu":
            try:
                return self._calculate_entropy_gpu(data)
            except Exception as e:
                logger.warning(f"GPU entropy calculation failed, switching to CPU: {e}")
                self._compute_backend = "cpu"

        return self._calculate_entropy_cpu(data)

    @staticmethod
    def _calculate_entropy_cpu(data: bytes) -> float:
        """Calculate Shannon entropy on CPU."""
        if not data:
            return 0.0

        counter = Counter(data)
        length = len(data)

        entropy = 0.0
        for count in counter.values():
            if count > 0:
                prob = count / length
                entropy -= prob * math.log2(prob)

        return round(entropy, 2)

    @staticmethod
    def _calculate_entropy_gpu(data: bytes) -> float:
        """Calculate Shannon entropy with GPU (CuPy)."""
        if not data:
            return 0.0
        if not GPU_COMPUTE_AVAILABLE:
            raise RuntimeError("GPU backend unavailable")

        np_arr = np.frombuffer(data, dtype=np.uint8)  # type: ignore[union-attr]
        cp_arr = cp.asarray(np_arr, dtype=cp.uint8)  # type: ignore[union-attr]
        histogram = cp.bincount(cp_arr, minlength=256).astype(cp.float64)  # type: ignore[union-attr]
        probabilities = histogram / len(data)
        probabilities = probabilities[probabilities > 0]
        entropy = -cp.sum(probabilities * cp.log2(probabilities))  # type: ignore[union-attr]
        return round(float(entropy.get()), 2)

    def _analyze_pe(self, path: Path, content: bytes) -> PEAnalysis:
        """Analyze PE file headers and structure."""
        analysis = PEAnalysis(is_pe=True)

        if not PEFILE_AVAILABLE:
            return analysis

        try:
            pe: Any = pefile.PE(str(path), fast_load=True)
            pe.parse_data_directories()

            # Basic info
            analysis.is_64bit = pe.FILE_HEADER.Machine == 0x8664
            analysis.is_dll = pe.is_dll()
            analysis.entry_point = pe.OPTIONAL_HEADER.AddressOfEntryPoint
            analysis.image_base = pe.OPTIONAL_HEADER.ImageBase

            # Compile time
            try:
                import datetime
                timestamp = pe.FILE_HEADER.TimeDateStamp
                compile_time = datetime.datetime.fromtimestamp(timestamp)
                analysis.compile_time = compile_time.isoformat()
            except Exception:
                pass

            # Sections analysis
            analysis.sections_count = len(pe.sections)
            for section in pe.sections:
                section_name = section.Name.rstrip(b"\x00").decode("utf-8", errors="replace")
                section_data = section.get_data()
                entropy = self._calculate_entropy(section_data)

                # High entropy detection
                if entropy > self.HIGH_ENTROPY_THRESHOLD:
                    analysis.high_entropy_sections.append({
                        "name": section_name,
                        "entropy": entropy,
                        "size": len(section_data),
                    })

                # RWX section detection (read, write, execute)
                characteristics = section.Characteristics
                is_rwx = (characteristics & 0xE0000000) == 0xE0000000
                if is_rwx:
                    analysis.rwx_sections.append(section_name)

            # Imports analysis
            if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
                for entry in pe.DIRECTORY_ENTRY_IMPORT:
                    for imp in entry.imports:
                        if imp.name:
                            analysis.imports_count += 1
                            func_name = imp.name.decode("utf-8", errors="replace")

                            if func_name in SUSPICIOUS_IMPORTS:
                                desc, severity = SUSPICIOUS_IMPORTS[func_name]
                                analysis.suspicious_imports.append({
                                    "function": func_name,
                                    "dll": entry.dll.decode("utf-8", errors="replace"),
                                    "description": desc,
                                    "severity": severity,
                                })

            # Exports count
            if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
                analysis.exports_count = len(pe.DIRECTORY_ENTRY_EXPORT.symbols)

            # Packer detection (basic)
            for section in pe.sections:
                section_name = section.Name.rstrip(b"\x00").decode("utf-8", errors="replace").lower()
                if "upx" in section_name:
                    analysis.packer_detected = "UPX"
                elif "aspack" in section_name:
                    analysis.packer_detected = "ASPack"
                elif ".nsp" in section_name:
                    analysis.packer_detected = "NSPack"
                elif "mpress" in section_name:
                    analysis.packer_detected = "MPRESS"

            # Signature check (basic)
            if hasattr(pe, "DIRECTORY_ENTRY_SECURITY"):
                analysis.has_signature = True
                # Full signature validation would require pywin32 on Windows

            pe.close()

        except pefile.PEFormatError:
            analysis.is_pe = False
        except Exception as e:
            logger.debug(f"PE analysis error: {e}")

        return analysis

    def _add_pe_findings(self, result: ScanResult) -> None:
        """Add PE analysis findings to result."""
        if not result.pe_analysis:
            return

        pe = result.pe_analysis

        # Suspicious imports
        for imp in pe.suspicious_imports:
            result.findings.append(Finding(
                title=f"Suspicious Import: {imp['function']}",
                detail=f"{imp['description']} (from {imp['dll']})",
                severity=imp["severity"],
                category="pe_imports"
            ))

        # High entropy sections
        for section in pe.high_entropy_sections:
            result.findings.append(Finding(
                title=f"High Entropy Section: {section['name']}",
                detail=f"Entropy {section['entropy']:.2f} (may indicate packed/encrypted code)",
                severity="medium",
                category="pe_structure"
            ))

        # RWX sections
        for section in pe.rwx_sections:
            result.findings.append(Finding(
                title=f"RWX Section: {section}",
                detail="Section with Read/Write/Execute permissions (potential code injection)",
                severity="high",
                category="pe_structure"
            ))

        # Packer detection
        if pe.packer_detected:
            result.findings.append(Finding(
                title=f"Packer Detected: {pe.packer_detected}",
                detail="File appears to be packed (may hide malicious code)",
                severity="medium",
                category="pe_structure"
            ))

    def _analyze_script(self, result: ScanResult, content: bytes) -> None:
        """Analyze script file for suspicious patterns."""
        try:
            text = content.decode("utf-8", errors="replace")
        except Exception:
            text = str(content)

        text_lower = text.lower()

        # PowerShell specific
        if result.extension == ".ps1":
            if "-encodedcommand" in text_lower or "-enc " in text_lower:
                result.findings.append(Finding(
                    title="Encoded PowerShell Command",
                    detail="Script uses encoded command execution",
                    severity="high",
                    category="script"
                ))

            if "invoke-expression" in text_lower or "iex " in text_lower:
                result.findings.append(Finding(
                    title="Dynamic Code Execution",
                    detail="Script uses Invoke-Expression (IEX)",
                    severity="high",
                    category="script"
                ))

        # Check for obfuscation
        char_pattern = text.count("[char]") + text.count("char(")
        if char_pattern > 10:
            result.findings.append(Finding(
                title="Character Obfuscation",
                detail=f"Script contains {char_pattern} char encoding instances",
                severity="medium",
                category="obfuscation"
            ))

    def _extract_iocs(self, content: bytes) -> IOCExtraction:
        """Extract Indicators of Compromise from content."""
        iocs = IOCExtraction()

        try:
            text = content.decode("utf-8", errors="replace")
        except Exception:
            text = str(content)

        # URL extraction
        url_pattern = r'https?://[^\s<>"\'{}|\\^`\[\]]+[^\s<>"\'{}|\\^`\[\].,;:!?\)]'
        iocs.urls = list(set(re.findall(url_pattern, text, re.IGNORECASE)))[:20]

        # IP extraction
        ip_pattern = r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
        potential_ips = list(set(re.findall(ip_pattern, text)))
        # Filter out common non-IOC IPs
        iocs.ips = [ip for ip in potential_ips if not ip.startswith(("0.", "127.", "255."))][:20]

        # Domain extraction (basic)
        domain_pattern = r"\b[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}\b"
        potential_domains = list(set(re.findall(domain_pattern, text)))
        # Filter common extensions
        iocs.domains = [d for d in potential_domains if not d.endswith((".dll", ".exe", ".sys"))][:20]

        # Registry key patterns
        reg_pattern = r"HKLM?\\[A-Za-z0-9\\]+|HKCU?\\[A-Za-z0-9\\]+"
        iocs.registry_keys = list(set(re.findall(reg_pattern, text, re.IGNORECASE)))[:10]

        # File paths (Windows)
        path_pattern = r'[A-Z]:\\[^\s<>"\'|*?]+\.[a-zA-Z]{2,4}'
        iocs.file_paths = list(set(re.findall(path_pattern, text)))[:10]

        # Email addresses
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        iocs.emails = list(set(re.findall(email_pattern, text)))[:10]

        return iocs

    def _calculate_score(self, result: ScanResult) -> int:
        """Calculate overall score from findings."""
        score = 0

        severity_scores = {
            "critical": 25,
            "high": 15,
            "medium": 8,
            "low": 3,
        }

        for finding in result.findings:
            severity = finding.severity.lower()
            score += severity_scores.get(severity, 5)

        # ClamAV detection is definitive
        if result.clamav.get("infected"):
            score = max(score, 80)

        # Cap at 100
        return min(100, score)

    def _determine_verdict(self, score: int) -> str:
        """Determine verdict from score."""
        if score < 20:
            return "Safe"
        if score < 60:
            return "Suspicious"
        return "Malicious"

    def _generate_summary(self, result: ScanResult) -> str:
        """Generate human-readable summary."""
        parts = []

        # Verdict
        parts.append(f"Verdict: {result.verdict} (Score: {result.score}/100)")

        # Key findings
        critical = [f for f in result.findings if f.severity == "critical"]
        high = [f for f in result.findings if f.severity == "high"]

        if critical:
            parts.append(f"Critical findings: {len(critical)}")
        if high:
            parts.append(f"High severity findings: {len(high)}")

        if result.clamav.get("infected"):
            parts.append(f"ClamAV detection: {result.clamav.get('signature', 'Unknown')}")

        if result.pe_analysis and result.pe_analysis.packer_detected:
            parts.append(f"Packer: {result.pe_analysis.packer_detected}")

        return " | ".join(parts)

    def _error_result(self, file_path: str, error: str) -> ScanResult:
        """Create error result."""
        return ScanResult(
            file_path=file_path,
            file_name=os.path.basename(file_path),
            file_size=0,
            sha256="",
            mime_type="",
            extension="",
            verdict="Unknown",
            score=0,
            summary=f"Error: {error}",
            errors=[error]
        )


def get_static_scanner() -> StaticScanner:
    """Get a static scanner instance."""
    return StaticScanner()
