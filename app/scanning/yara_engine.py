"""
YARA Engine - Offline Malware Detection using YARA Rules

Provides local, offline file scanning using YARA rules.
No network dependencies.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Try to import yara - it's optional
try:
    import yara
    YARA_AVAILABLE = True
except (ImportError, OSError) as e:
    YARA_AVAILABLE = False
    # Only log warning for ImportError, suppress DLL errors
    if isinstance(e, ImportError):
        logger.warning("YARA library not installed. Install with: pip install yara-python")
    # Silently skip OSError (DLL not found) since YARA is optional


@dataclass
class YaraMatch:
    """Represents a single YARA rule match."""
    rule_name: str
    description: str
    severity: str  # low, medium, high, critical
    category: str
    matched_strings: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


class YaraEngine:
    """
    YARA scanning engine for offline malware detection.
    
    Features:
    - Loads rules from app/scanning/yara_rules/
    - Supports custom rule additions
    - Returns structured match results with severity
    """
    
    # Severity weights for scoring
    SEVERITY_SCORES = {
        "critical": 25,
        "high": 15,
        "medium": 8,
        "low": 3,
    }
    
    def __init__(self, rules_dir: Optional[Path] = None):
        """
        Initialize the YARA engine.
        
        Args:
            rules_dir: Optional path to YARA rules directory.
                      Defaults to app/scanning/yara_rules/
        """
        self._rules: Optional[Any] = None
        self._rules_loaded = False
        self._rules_dir = rules_dir or self._get_default_rules_dir()
        
        if YARA_AVAILABLE:
            self._load_rules()
        else:
            logger.warning("YARA not available - rule matching disabled")
    
    def _get_default_rules_dir(self) -> Path:
        """Get the default rules directory."""
        # Navigate from this file to the yara_rules directory
        current_dir = Path(__file__).parent
        return current_dir / "yara_rules"
    
    def _load_rules(self) -> bool:
        """Load all YARA rules from the rules directory."""
        if not YARA_AVAILABLE:
            return False
        
        try:
            if not self._rules_dir.exists():
                logger.warning(f"YARA rules directory not found: {self._rules_dir}")
                return False
            
            # Find all .yar and .yara files
            rule_files = list(self._rules_dir.glob("*.yar")) + list(self._rules_dir.glob("*.yara"))
            
            if not rule_files:
                logger.warning(f"No YARA rule files found in {self._rules_dir}")
                return False
            
            # Compile rules from all files
            filepaths = {f"rules_{i}": str(f) for i, f in enumerate(rule_files)}
            self._rules = yara.compile(filepaths=filepaths)
            self._rules_loaded = True
            
            logger.info(f"Loaded YARA rules from {len(rule_files)} file(s)")
            return True
            
        except yara.SyntaxError as e:
            logger.error(f"YARA syntax error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to load YARA rules: {e}")
            return False
    
    @property
    def is_available(self) -> bool:
        """Check if YARA scanning is available."""
        return YARA_AVAILABLE and self._rules_loaded
    
    def scan_file(self, file_path: str) -> List[YaraMatch]:
        """
        Scan a file with YARA rules.
        
        Args:
            file_path: Path to the file to scan
            
        Returns:
            List of YaraMatch objects for each matching rule
        """
        if not self.is_available:
            logger.debug("YARA scanning not available")
            return []
        
        try:
            matches = self._rules.match(file_path, timeout=30)
            return self._process_matches(matches)
        except yara.TimeoutError:
            logger.warning(f"YARA scan timed out for {file_path}")
            return []
        except Exception as e:
            logger.error(f"YARA scan error for {file_path}: {e}")
            return []
    
    def scan_data(self, data: bytes) -> List[YaraMatch]:
        """
        Scan raw bytes with YARA rules.
        
        Args:
            data: Raw bytes to scan
            
        Returns:
            List of YaraMatch objects for each matching rule
        """
        if not self.is_available:
            return []
        
        try:
            matches = self._rules.match(data=data, timeout=30)
            return self._process_matches(matches)
        except yara.TimeoutError:
            logger.warning("YARA scan timed out for data")
            return []
        except Exception as e:
            logger.error(f"YARA scan error: {e}")
            return []
    
    def _process_matches(self, matches) -> List[YaraMatch]:
        """Process raw YARA matches into YaraMatch objects."""
        results = []
        
        for match in matches:
            # Extract metadata
            meta = match.meta if hasattr(match, 'meta') else {}
            
            # Get matched strings
            matched_strings = []
            if hasattr(match, 'strings'):
                for string_match in match.strings:
                    # Handle different yara-python versions
                    if hasattr(string_match, 'instances'):
                        for instance in string_match.instances:
                            try:
                                matched_strings.append(instance.matched_data.decode('utf-8', errors='replace')[:50])
                            except:
                                matched_strings.append(str(instance)[:50])
                    else:
                        # Older format: (offset, identifier, data)
                        if len(string_match) >= 3:
                            try:
                                matched_strings.append(string_match[2].decode('utf-8', errors='replace')[:50])
                            except:
                                matched_strings.append(str(string_match[2])[:50])
            
            yara_match = YaraMatch(
                rule_name=match.rule,
                description=meta.get('description', 'No description'),
                severity=meta.get('severity', 'medium'),
                category=meta.get('category', 'unknown'),
                matched_strings=matched_strings[:5],  # Limit to 5 examples
                tags=list(match.tags) if hasattr(match, 'tags') else []
            )
            results.append(yara_match)
        
        return results
    
    def calculate_score(self, matches: List[YaraMatch]) -> int:
        """
        Calculate a score from YARA matches.
        
        Args:
            matches: List of YaraMatch objects
            
        Returns:
            Score from 0-100 based on match severity
        """
        if not matches:
            return 0
        
        total_score = 0
        for match in matches:
            severity = match.severity.lower()
            total_score += self.SEVERITY_SCORES.get(severity, 5)
        
        # Cap at 100
        return min(100, total_score)
    
    def get_findings(self, matches: List[YaraMatch]) -> List[Dict[str, Any]]:
        """
        Convert YARA matches to finding dictionaries.
        
        Args:
            matches: List of YaraMatch objects
            
        Returns:
            List of finding dictionaries suitable for reports
        """
        findings = []
        
        for match in matches:
            findings.append({
                "title": f"YARA: {match.rule_name}",
                "detail": match.description,
                "severity": match.severity,
                "category": match.category,
                "matched_strings": match.matched_strings,
            })
        
        return findings


# Fallback pattern-based scanner for when YARA is not available
class FallbackPatternScanner:
    """
    Simple pattern-based scanner as fallback when YARA is not installed.
    Uses basic regex matching for common suspicious patterns.
    """
    
    # Patterns with their severity
    PATTERNS = [
        # PowerShell suspicious patterns
        (rb"-EncodedCommand", "PowerShell encoded command", "high"),
        (rb"Invoke-Expression", "PowerShell code execution", "high"),
        (rb"DownloadString", "PowerShell download", "high"),
        (rb"Net\.WebClient", "Network download capability", "medium"),
        
        # Process injection
        (rb"VirtualAllocEx", "Memory allocation (injection)", "critical"),
        (rb"WriteProcessMemory", "Process memory write", "critical"),
        (rb"CreateRemoteThread", "Remote thread creation", "critical"),
        
        # Registry persistence
        (rb"CurrentVersion\\Run", "Registry persistence", "high"),
        (rb"reg add", "Registry modification", "medium"),
        (rb"schtasks", "Scheduled task creation", "high"),
        
        # Credential access
        (rb"mimikatz", "Credential dumping tool", "critical"),
        (rb"sekurlsa", "Credential extraction", "critical"),
        (rb"lsass", "LSASS access", "high"),
        
        # Security bypass
        (rb"DisableRealtimeMonitoring", "Disable antivirus", "critical"),
        (rb"Set-MpPreference", "Defender modification", "high"),
        
        # Ransomware indicators
        (rb"encrypt", "Encryption functionality", "medium"),
        (rb"ransom", "Ransomware indicator", "critical"),
        (rb"bitcoin", "Cryptocurrency reference", "medium"),
        
        # Network
        (rb"TCPClient", "Network connection", "low"),
        (rb"System\.Net\.Sockets", "Socket programming", "low"),
    ]
    
    def scan_data(self, data: bytes) -> List[Dict[str, Any]]:
        """Scan data for suspicious patterns."""
        findings = []
        
        for pattern, description, severity in self.PATTERNS:
            try:
                if pattern.lower() in data.lower():
                    findings.append({
                        "title": f"Pattern: {description}",
                        "detail": f"Found suspicious pattern in file",
                        "severity": severity,
                        "category": "pattern_match",
                    })
            except Exception:
                continue
        
        return findings
    
    def calculate_score(self, findings: List[Dict]) -> int:
        """Calculate score from findings."""
        severity_scores = {"critical": 25, "high": 15, "medium": 8, "low": 3}
        
        total = sum(severity_scores.get(f.get("severity", "low"), 3) for f in findings)
        return min(100, total)


def get_yara_engine() -> YaraEngine:
    """Get a YARA engine instance."""
    return YaraEngine()


def get_pattern_scanner() -> FallbackPatternScanner:
    """Get a fallback pattern scanner instance."""
    return FallbackPatternScanner()
