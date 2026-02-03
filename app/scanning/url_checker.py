"""
URL Checker - Offline URL Security Analysis

Performs local heuristic analysis on URLs:
- Domain/TLD analysis
- Suspicious pattern detection
- Local blocklist checking
- No network required

100% Offline - No external API calls.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


@dataclass
class URLCheckResult:
    """Result from URL analysis."""
    # Input
    original_url: str
    normalized_url: str
    
    # Verdict
    verdict: str  # Safe, Suspicious, Malicious, Unknown
    score: int  # 0-100
    summary: str
    
    # Details
    reasons: List[Dict[str, Any]] = field(default_factory=list)
    
    # Parsed components
    parsed: Dict[str, Any] = field(default_factory=dict)
    
    # Flags
    is_blocked: bool = False
    is_allowlisted: bool = False


class URLChecker:
    """
    Local URL security checker.
    
    Features:
    - Heuristic analysis (no network)
    - Local blocklist/allowlist
    - Suspicious TLD detection
    - Phishing pattern detection
    - Unicode confusable detection
    """
    
    def __init__(self, lists_dir: Optional[Path] = None):
        """
        Initialize the URL checker.
        
        Args:
            lists_dir: Optional path to URL lists directory.
                      Defaults to app/scanning/url_lists/
        """
        self._lists_dir = lists_dir or self._get_default_lists_dir()
        
        # Load lists
        self._blocked_domains: Set[str] = set()
        self._blocked_keywords: Set[str] = set()
        self._allowlist_domains: Set[str] = set()
        self._suspicious_tlds: Set[str] = set()
        
        self._load_lists()
    
    def _get_default_lists_dir(self) -> Path:
        """Get the default lists directory."""
        current_dir = Path(__file__).parent
        return current_dir / "url_lists"
    
    def _load_lists(self) -> None:
        """Load all URL lists from disk."""
        self._blocked_domains = self._load_list("blocked_domains.txt")
        self._blocked_keywords = self._load_list("blocked_keywords.txt")
        self._allowlist_domains = self._load_list("allowlist_domains.txt")
        self._suspicious_tlds = self._load_list("suspicious_tlds.txt")
        
        logger.info(f"Loaded URL lists: {len(self._blocked_domains)} blocked domains, "
                   f"{len(self._allowlist_domains)} allowed domains")
    
    def _load_list(self, filename: str) -> Set[str]:
        """Load a list file, returning a set of entries."""
        items = set()
        filepath = self._lists_dir / filename
        
        if not filepath.exists():
            logger.debug(f"List file not found: {filepath}")
            return items
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if line and not line.startswith("#"):
                        items.add(line.lower())
        except Exception as e:
            logger.error(f"Failed to load {filename}: {e}")
        
        return items
    
    def check_url(self, url: str) -> URLCheckResult:
        """
        Analyze a URL for security concerns.
        
        Args:
            url: The URL to analyze
            
        Returns:
            URLCheckResult with analysis details
        """
        # Normalize URL
        normalized = self._normalize_url(url)
        
        # Initialize result
        result = URLCheckResult(
            original_url=url,
            normalized_url=normalized,
            verdict="Unknown",
            score=0,
            summary="",
        )
        
        # Parse URL
        try:
            parsed = urlparse(normalized)
            result.parsed = {
                "scheme": parsed.scheme,
                "domain": parsed.netloc,
                "path": parsed.path,
                "query": parsed.query,
                "tld": self._extract_tld(parsed.netloc),
            }
        except Exception as e:
            result.summary = f"Invalid URL: {e}"
            result.verdict = "Unknown"
            return result
        
        domain = result.parsed["domain"].lower()
        tld = result.parsed["tld"]
        
        # Check blocklist first
        if self._is_blocked(domain):
            result.is_blocked = True
            result.reasons.append({
                "title": "Domain in blocklist",
                "detail": f"Domain '{domain}' is in the local blocklist",
                "severity": "critical",
                "score": 50
            })
        
        # Check allowlist
        if self._is_allowlisted(domain):
            result.is_allowlisted = True
            result.reasons.append({
                "title": "Domain in allowlist",
                "detail": f"Domain '{domain}' is in the trusted allowlist",
                "severity": "info",
                "score": -20
            })
        
        # Heuristic checks
        self._check_suspicious_tld(result, tld)
        self._check_ip_literal(result, domain)
        self._check_url_length(result, normalized)
        self._check_subdomain_count(result, domain)
        self._check_at_symbol(result, url)
        self._check_unicode_confusables(result, domain)
        self._check_percent_encoding(result, normalized)
        self._check_suspicious_keywords(result, normalized)
        self._check_executable_download(result, result.parsed["path"])
        self._check_typosquatting(result, domain)
        self._check_suspicious_port(result, domain)
        self._check_numeric_domain(result, domain)
        
        # Calculate score
        result.score = self._calculate_score(result)
        result.verdict = self._determine_verdict(result.score)
        result.summary = self._generate_summary(result)
        
        return result
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for analysis."""
        url = url.strip()
        
        # Add scheme if missing
        if not url.startswith(('http://', 'https://', 'ftp://')):
            url = 'https://' + url
        
        # Decode punycode
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            if domain.startswith('xn--') or '.xn--' in domain:
                domain = domain.encode('ascii').decode('idna')
                url = parsed._replace(netloc=domain).geturl()
        except:
            pass
        
        return url
    
    def _extract_tld(self, domain: str) -> str:
        """Extract TLD from domain."""
        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]
        
        parts = domain.split('.')
        if len(parts) >= 2:
            return '.' + parts[-1]
        return ''
    
    def _is_blocked(self, domain: str) -> bool:
        """Check if domain is in blocklist."""
        domain = domain.lower()
        
        # Remove port
        if ':' in domain:
            domain = domain.split(':')[0]
        
        # Check exact match
        if domain in self._blocked_domains:
            return True
        
        # Check parent domains
        parts = domain.split('.')
        for i in range(len(parts)):
            parent = '.'.join(parts[i:])
            if parent in self._blocked_domains:
                return True
        
        return False
    
    def _is_allowlisted(self, domain: str) -> bool:
        """Check if domain is in allowlist."""
        domain = domain.lower()
        
        # Remove port
        if ':' in domain:
            domain = domain.split(':')[0]
        
        # Check exact match
        if domain in self._allowlist_domains:
            return True
        
        # Check parent domains
        parts = domain.split('.')
        for i in range(len(parts)):
            parent = '.'.join(parts[i:])
            if parent in self._allowlist_domains:
                return True
        
        return False
    
    def _check_suspicious_tld(self, result: URLCheckResult, tld: str) -> None:
        """Check for suspicious TLDs."""
        if tld.lower() in self._suspicious_tlds:
            result.reasons.append({
                "title": "Suspicious TLD",
                "detail": f"TLD '{tld}' is commonly used for malicious purposes",
                "severity": "medium",
                "score": 15
            })
    
    def _check_ip_literal(self, result: URLCheckResult, domain: str) -> None:
        """Check if domain is an IP address."""
        # Remove port
        host = domain.split(':')[0]
        
        # IPv4 check
        ipv4_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        if re.match(ipv4_pattern, host):
            result.reasons.append({
                "title": "IP Address URL",
                "detail": "URL uses IP address instead of domain name",
                "severity": "high",
                "score": 20
            })
    
    def _check_url_length(self, result: URLCheckResult, url: str) -> None:
        """Check for excessively long URLs."""
        if len(url) > 200:
            result.reasons.append({
                "title": "Excessively Long URL",
                "detail": f"URL length ({len(url)} chars) may indicate obfuscation",
                "severity": "low",
                "score": 5
            })
    
    def _check_subdomain_count(self, result: URLCheckResult, domain: str) -> None:
        """Check for excessive subdomains."""
        # Remove port
        host = domain.split(':')[0]
        parts = host.split('.')
        
        if len(parts) > 4:
            result.reasons.append({
                "title": "Excessive Subdomains",
                "detail": f"{len(parts)} domain levels may indicate spoofing",
                "severity": "medium",
                "score": 10
            })
    
    def _check_at_symbol(self, result: URLCheckResult, url: str) -> None:
        """Check for @ symbol in URL (credential attack)."""
        parsed = urlparse(url)
        if '@' in parsed.netloc:
            result.reasons.append({
                "title": "@ Symbol in URL",
                "detail": "URL contains @ which may hide true destination",
                "severity": "high",
                "score": 25
            })
    
    def _check_unicode_confusables(self, result: URLCheckResult, domain: str) -> None:
        """Check for Unicode confusable characters."""
        # Common confusables
        confusables = {
            'а': 'a (Cyrillic)',  # Cyrillic а looks like Latin a
            'е': 'e (Cyrillic)',
            'о': 'o (Cyrillic)',
            'р': 'p (Cyrillic)',
            'с': 'c (Cyrillic)',
            'х': 'x (Cyrillic)',
            'і': 'i (Cyrillic)',
            'ј': 'j (Cyrillic)',
            'ѕ': 's (Cyrillic)',
            'ー': '- (Japanese)',
            '。': '. (Japanese)',
            'ο': 'o (Greek)',
            'α': 'a (Greek)',
            'ε': 'e (Greek)',
        }
        
        found = []
        for char in domain:
            if char in confusables:
                found.append(confusables[char])
        
        if found:
            result.reasons.append({
                "title": "Unicode Confusable Characters",
                "detail": f"Domain contains look-alike characters: {', '.join(found[:3])}",
                "severity": "critical",
                "score": 35
            })
    
    def _check_percent_encoding(self, result: URLCheckResult, url: str) -> None:
        """Check for suspicious percent encoding."""
        # Count encoded characters
        encoded_count = url.count('%')
        
        if encoded_count > 10:
            result.reasons.append({
                "title": "Heavy URL Encoding",
                "detail": f"{encoded_count} encoded characters may indicate obfuscation",
                "severity": "medium",
                "score": 12
            })
    
    def _check_suspicious_keywords(self, result: URLCheckResult, url: str) -> None:
        """Check for suspicious keywords in URL."""
        url_lower = url.lower()
        
        found_keywords = []
        for keyword in self._blocked_keywords:
            if keyword in url_lower:
                found_keywords.append(keyword)
        
        if found_keywords:
            result.reasons.append({
                "title": "Suspicious Keywords",
                "detail": f"URL contains suspicious patterns: {', '.join(found_keywords[:3])}",
                "severity": "medium",
                "score": 8 * min(len(found_keywords), 3)
            })
    
    def _check_executable_download(self, result: URLCheckResult, path: str) -> None:
        """Check if URL points to executable download."""
        dangerous_extensions = {
            '.exe': 'Windows executable',
            '.msi': 'Windows installer',
            '.dll': 'Windows library',
            '.scr': 'Screen saver',
            '.bat': 'Batch script',
            '.cmd': 'Command script',
            '.ps1': 'PowerShell script',
            '.vbs': 'VBScript',
            '.js': 'JavaScript file',
            '.hta': 'HTML Application',
            '.iso': 'Disk image',
            '.img': 'Disk image',
        }
        
        path_lower = path.lower()
        for ext, desc in dangerous_extensions.items():
            if path_lower.endswith(ext):
                result.reasons.append({
                    "title": f"Executable Download: {ext}",
                    "detail": f"URL points to {desc} download",
                    "severity": "high",
                    "score": 20
                })
                break
    
    def _check_typosquatting(self, result: URLCheckResult, domain: str) -> None:
        """Check for common typosquatting patterns."""
        # Known brand patterns
        brand_patterns = [
            (r'paypa[l1]', 'PayPal'),
            (r'go+g[l1]e', 'Google'),
            (r'micros[o0]ft', 'Microsoft'),
            (r'app[l1]e', 'Apple'),
            (r'amaz[o0]n', 'Amazon'),
            (r'faceb[o0]{2}k', 'Facebook'),
            (r'netf[l1]ix', 'Netflix'),
            (r'bank.?of.?america', 'Bank of America'),
        ]
        
        domain_lower = domain.lower()
        
        for pattern, brand in brand_patterns:
            # Check if pattern matches but isn't the real domain
            if re.search(pattern, domain_lower):
                real_domain = brand.lower().replace(' ', '') + '.com'
                if real_domain not in domain_lower:
                    result.reasons.append({
                        "title": f"Possible Typosquatting: {brand}",
                        "detail": f"Domain resembles {brand} but isn't official",
                        "severity": "high",
                        "score": 25
                    })
                    break
    
    def _check_suspicious_port(self, result: URLCheckResult, domain: str) -> None:
        """Check for non-standard ports."""
        if ':' in domain:
            try:
                port = int(domain.split(':')[1])
                if port not in [80, 443, 8080, 8443]:
                    result.reasons.append({
                        "title": "Non-Standard Port",
                        "detail": f"URL uses port {port} which is unusual",
                        "severity": "low",
                        "score": 5
                    })
            except:
                pass
    
    def _check_numeric_domain(self, result: URLCheckResult, domain: str) -> None:
        """Check for heavily numeric domains."""
        host = domain.split(':')[0]
        # Remove TLD
        parts = host.split('.')
        if len(parts) > 1:
            main_part = '.'.join(parts[:-1])
            digits = sum(c.isdigit() for c in main_part)
            if len(main_part) > 5 and digits / len(main_part) > 0.5:
                result.reasons.append({
                    "title": "Heavily Numeric Domain",
                    "detail": "Domain contains excessive numbers",
                    "severity": "medium",
                    "score": 10
                })
    
    def _calculate_score(self, result: URLCheckResult) -> int:
        """Calculate overall score from reasons."""
        total = 0
        for reason in result.reasons:
            total += reason.get("score", 0)
        
        # Cap at 100, floor at 0
        return max(0, min(100, total))
    
    def _determine_verdict(self, score: int) -> str:
        """Determine verdict from score."""
        if score < 15:
            return "Safe"
        elif score < 40:
            return "Suspicious"
        else:
            return "Malicious"
    
    def _generate_summary(self, result: URLCheckResult) -> str:
        """Generate human-readable summary."""
        if result.is_blocked:
            return f"⚠️ Domain is blocked | Score: {result.score}/100"
        
        if result.is_allowlisted:
            return f"✅ Trusted domain | Score: {result.score}/100"
        
        issue_count = len([r for r in result.reasons if r.get("score", 0) > 0])
        
        if issue_count == 0:
            return f"No issues detected | Score: {result.score}/100"
        
        return f"{issue_count} potential issue(s) found | Score: {result.score}/100"


def get_url_checker() -> URLChecker:
    """Get a URL checker instance."""
    return URLChecker()
