"""
URL Scanner - VirusTotal-like local URL analysis.

Multi-layer URL scanning pipeline:
1. Normalize & validate URL
2. Collect reputation & structure signals
3. Safe fetch & static content analysis (no JS execution)
4. Optional sandbox detonation via WebView2
5. IOC extraction and YARA matching

100% Offline - No external API calls.
"""

import hashlib
import ipaddress
import logging
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse, urlunparse

logger = logging.getLogger(__name__)

# Try importing optional dependencies
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests not installed. URL fetching will be limited.")


# Suspicious TLD list (commonly abused)
SUSPICIOUS_TLDS = {
    '.tk', '.ml', '.ga', '.cf', '.gq',  # Free TLDs often abused
    '.xyz', '.top', '.work', '.date', '.loan', '.win', '.stream',
    '.download', '.racing', '.review', '.click', '.link', '.bid',
    '.trade', '.webcam', '.party', '.cricket', '.science', '.accountant',
    '.zip', '.mov',  # File extension TLDs (phishing confusion)
}

# Suspicious path keywords
SUSPICIOUS_PATH_KEYWORDS = [
    'login', 'signin', 'verify', 'confirm', 'secure', 'update',
    'account', 'banking', 'password', 'credential', 'wallet',
    'paypal', 'apple', 'microsoft', 'google', 'amazon', 'facebook',
    'instagram', 'netflix', 'dropbox', 'onedrive', 'icloud',
    '.exe', '.msi', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.scr',
    '.zip', '.rar', '.7z', '.tar',
]

# Suspicious query parameters
SUSPICIOUS_QUERY_PARAMS = [
    'redirect', 'url', 'goto', 'return', 'redir', 'next', 'dest',
    'destination', 'target', 'link', 'out', 'away',
]

# Private IP ranges
PRIVATE_RANGES = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fc00::/7'),
    ipaddress.ip_network('fe80::/10'),
]


@dataclass
class Evidence:
    """Single evidence item from URL analysis."""
    title: str
    severity: str  # "critical", "high", "medium", "low", "info"
    detail: str
    category: str = "general"  # "structure", "content", "behavior", "reputation"
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "severity": self.severity,
            "detail": self.detail,
            "category": self.category,
        }


@dataclass
class UrlScanResult:
    """Complete URL scan result."""
    # Input/Output URLs
    input_url: str
    normalized_url: str
    final_url: str = ""
    redirects: list = field(default_factory=list)
    
    # HTTP info
    http_status: int = 0
    content_type: str = ""
    content_size: int = 0
    server: str = ""
    
    # Analysis
    signals: dict = field(default_factory=dict)
    evidence: list = field(default_factory=list)  # List of Evidence
    iocs: dict = field(default_factory=lambda: {"urls": [], "domains": [], "ips": []})
    yara_matches: list = field(default_factory=list)
    
    # Sandbox results
    sandbox_used: bool = False
    sandbox_result: dict = field(default_factory=dict)
    
    # Verdict (filled by scoring)
    score: int = 0
    verdict: str = "Unknown"
    verdict_label: str = "Unknown"
    summary: str = ""
    explanation: str = ""
    
    # Metadata
    scan_timestamp: str = ""
    scan_duration: float = 0.0
    errors: list = field(default_factory=list)
    
    @property
    def http(self) -> dict:
        """Return HTTP info as a dictionary for compatibility."""
        return {
            "status_code": self.http_status,
            "content_type": self.content_type,
            "content_length": self.content_size,
            "server": self.server,
        }
    
    def to_dict(self) -> dict:
        return {
            "input_url": self.input_url,
            "normalized_url": self.normalized_url,
            "final_url": self.final_url,
            "redirects": self.redirects,
            "http": {
                "status": self.http_status,
                "content_type": self.content_type,
                "content_size": self.content_size,
                "server": self.server,
            },
            "signals": self.signals,
            "evidence": [e.to_dict() if hasattr(e, 'to_dict') else e for e in self.evidence],
            "iocs": self.iocs,
            "yara_matches": self.yara_matches,
            "sandbox_used": self.sandbox_used,
            "sandbox_result": self.sandbox_result,
            "score": self.score,
            "verdict": self.verdict,
            "verdict_label": self.verdict_label,
            "summary": self.summary,
            "explanation": self.explanation,
            "scan_timestamp": self.scan_timestamp,
            "scan_duration": self.scan_duration,
            "errors": self.errors,
        }


class UrlScanner:
    """
    Multi-layer URL scanner with static analysis and optional sandbox detonation.
    
    Features:
    - URL normalization and validation
    - Safe HTTP fetch with redirect tracking
    - HTML/JS content analysis
    - IOC extraction
    - YARA rule matching
    - Sandbox detonation via WebView2 (optional)
    - Result caching (1 hour TTL)
    """
    
    # Fetch limits
    MAX_REDIRECTS = 5
    MAX_CONTENT_SIZE = 2 * 1024 * 1024  # 2MB
    CONNECT_TIMEOUT = 3
    READ_TIMEOUT = 7
    
    # Cache settings
    CACHE_TTL_SECONDS = 3600  # 1 hour
    
    # Shared session for connection pooling
    _session = None
    _session_lock = None
    
    # Result cache (URL hash -> result)
    _cache = {}
    _cache_times = {}
    
    def __init__(self):
        self._yara_engine = None
        self._load_yara()
        self._init_session()
    
    def _init_session(self):
        """Initialize shared requests session with connection pooling."""
        if UrlScanner._session is None and REQUESTS_AVAILABLE:
            import threading
            UrlScanner._session_lock = threading.Lock()
            UrlScanner._session = requests.Session()
            # Configure connection pooling
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=10,
                pool_maxsize=10,
                max_retries=1
            )
            UrlScanner._session.mount('http://', adapter)
            UrlScanner._session.mount('https://', adapter)
            # Set default headers
            UrlScanner._session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            })
    
    def _get_cache_key(self, url: str, use_sandbox: bool = False) -> str:
        """Generate cache key from URL and options."""
        import hashlib
        key_str = f"{url}|sandbox={use_sandbox}"
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]
    
    def _get_cached(self, cache_key: str) -> Optional[UrlScanResult]:
        """Get cached result if valid."""
        if cache_key in UrlScanner._cache:
            cache_time = UrlScanner._cache_times.get(cache_key, 0)
            if time.time() - cache_time < self.CACHE_TTL_SECONDS:
                logger.debug(f"Cache hit for {cache_key}")
                return UrlScanner._cache[cache_key]
            else:
                # Expired, remove
                del UrlScanner._cache[cache_key]
                del UrlScanner._cache_times[cache_key]
        return None
    
    def _set_cached(self, cache_key: str, result: UrlScanResult):
        """Cache a scan result."""
        UrlScanner._cache[cache_key] = result
        UrlScanner._cache_times[cache_key] = time.time()
        # Limit cache size
        if len(UrlScanner._cache) > 100:
            # Remove oldest entries
            oldest = sorted(UrlScanner._cache_times.items(), key=lambda x: x[1])[:20]
            for key, _ in oldest:
                UrlScanner._cache.pop(key, None)
                UrlScanner._cache_times.pop(key, None)
    
    def _load_yara(self):
        """Load YARA rules for web content scanning."""
        try:
            from .yara_engine import get_yara_engine
            self._yara_engine = get_yara_engine()
        except Exception as e:
            logger.debug(f"YARA not available for URL scanning: {e}")
    
    def scan_static(
        self,
        url: str,
        block_private_ips: bool = True,
        block_downloads: bool = True,
        use_cache: bool = True,
    ) -> UrlScanResult:
        """
        Perform static URL analysis (no sandbox).
        
        Args:
            url: URL to scan
            block_private_ips: Reject localhost/private IPs
            block_downloads: Flag download content-types as suspicious
            use_cache: Use cached results if available
        
        Returns:
            UrlScanResult with all analysis data
        """
        # Check cache first
        cache_key = self._get_cache_key(url, use_sandbox=False)
        if use_cache:
            cached = self._get_cached(cache_key)
            if cached:
                logger.info(f"Using cached result for {url}")
                return cached
        
        start_time = time.time()
        result = UrlScanResult(
            input_url=url,
            normalized_url="",
            scan_timestamp=datetime.now().isoformat(),
        )
        
        try:
            # Step 1: Normalize and validate
            normalized, valid, validation_evidence = self._normalize_and_validate(
                url, block_private_ips
            )
            result.normalized_url = normalized
            result.evidence.extend(validation_evidence)
            
            if not valid:
                result.verdict = "blocked"
                result.verdict_label = "Blocked"
                result.summary = "URL was blocked during validation"
                result.scan_duration = time.time() - start_time
                return result
            
            # Step 2: Analyze URL structure
            structure_evidence = self._analyze_url_structure(normalized)
            result.evidence.extend(structure_evidence)
            
            # Step 3: Safe fetch with redirect tracking
            if REQUESTS_AVAILABLE:
                fetch_result = self._safe_fetch(normalized, block_downloads)
                result.final_url = fetch_result.get("final_url", normalized)
                result.redirects = fetch_result.get("redirects", [])
                result.http_status = fetch_result.get("status", 0)
                result.content_type = fetch_result.get("content_type", "")
                result.content_size = fetch_result.get("content_size", 0)
                result.server = fetch_result.get("server", "")
                result.evidence.extend(fetch_result.get("evidence", []))
                
                # Step 4: Analyze content
                content = fetch_result.get("content", "")
                if content:
                    content_evidence = self._analyze_content(content, result.final_url)
                    result.evidence.extend(content_evidence)
                    
                    # Extract IOCs
                    result.iocs = self._extract_iocs(content, result.final_url)
                    
                    # YARA matching
                    if self._yara_engine:
                        result.yara_matches = self._run_yara(content)
                        for match in result.yara_matches:
                            result.evidence.append(Evidence(
                                title=f"YARA Rule Match: {match.get('rule', 'unknown')}",
                                severity="high",
                                detail=match.get('description', 'Matched malicious content pattern'),
                                category="content"
                            ))
            else:
                result.errors.append("requests library not available for HTTP fetching")
            
            # Build signals summary
            result.signals = self._build_signals(result)
            
        except Exception as e:
            logger.error(f"URL scan error: {e}")
            result.errors.append(str(e))
        
        result.scan_duration = time.time() - start_time
        
        # Cache the result
        if use_cache and not result.errors:
            self._set_cached(cache_key, result)
        
        return result
    
    def scan_sandbox(
        self,
        url: str,
        block_private_ips: bool = True,
        block_downloads: bool = True,
        timeout_seconds: int = 30,
    ) -> UrlScanResult:
        """
        Perform URL analysis with sandbox detonation via WebView2.
        
        Args:
            url: URL to scan
            block_private_ips: Reject localhost/private IPs
            block_downloads: Block download attempts in sandbox
            timeout_seconds: Sandbox execution timeout
        
        Returns:
            UrlScanResult with static + sandbox analysis
        """
        # First do static scan
        result = self.scan_static(url, block_private_ips, block_downloads)
        
        if result.verdict == "blocked":
            return result
        
        # Then run sandbox detonation
        try:
            sandbox_result = self._run_sandbox_detonation(
                result.normalized_url,
                block_downloads,
                timeout_seconds
            )
            result.sandbox_used = True
            result.sandbox_result = sandbox_result
            
            # Add sandbox evidence
            sandbox_evidence = self._process_sandbox_result(sandbox_result)
            result.evidence.extend(sandbox_evidence)
            
            # Update final URL if sandbox found JS redirects
            if sandbox_result.get("final_url"):
                if sandbox_result["final_url"] != result.final_url:
                    result.evidence.append(Evidence(
                        title="JavaScript Redirect Detected",
                        severity="medium",
                        detail=f"Page redirected via JavaScript to: {sandbox_result['final_url']}",
                        category="behavior"
                    ))
                    result.final_url = sandbox_result["final_url"]
            
        except Exception as e:
            logger.warning(f"Sandbox detonation failed: {e}")
            result.errors.append(f"Sandbox detonation unavailable: {e}")
            result.evidence.append(Evidence(
                title="Sandbox Detonation Unavailable",
                severity="info",
                detail=str(e),
                category="behavior"
            ))
        
        # Rebuild signals
        result.signals = self._build_signals(result)
        
        return result
    
    def _normalize_and_validate(
        self,
        url: str,
        block_private_ips: bool
    ) -> tuple[str, bool, list]:
        """
        Normalize and validate URL.
        
        Returns:
            (normalized_url, is_valid, evidence_list)
        """
        evidence = []
        
        # Strip whitespace
        url = url.strip()
        
        # Reject empty
        if not url:
            evidence.append(Evidence(
                title="Empty URL",
                severity="critical",
                detail="No URL provided",
                category="structure"
            ))
            return "", False, evidence
        
        # Reject control characters
        if any(ord(c) < 32 for c in url):
            evidence.append(Evidence(
                title="Control Characters in URL",
                severity="critical",
                detail="URL contains invalid control characters",
                category="structure"
            ))
            return url, False, evidence
        
        # Add scheme if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            evidence.append(Evidence(
                title="Invalid URL Format",
                severity="critical",
                detail=f"Could not parse URL: {e}",
                category="structure"
            ))
            return url, False, evidence
        
        # Must have scheme and netloc
        if not parsed.scheme or not parsed.netloc:
            evidence.append(Evidence(
                title="Malformed URL",
                severity="critical",
                detail="URL missing scheme or hostname",
                category="structure"
            ))
            return url, False, evidence
        
        # Only allow http/https
        if parsed.scheme not in ('http', 'https'):
            evidence.append(Evidence(
                title="Non-HTTP Scheme",
                severity="high",
                detail=f"Blocked scheme: {parsed.scheme}",
                category="structure"
            ))
            return url, False, evidence
        
        # Extract hostname
        hostname = parsed.hostname or parsed.netloc
        
        # Check for punycode (IDN homograph attack)
        if hostname.startswith('xn--') or 'xn--' in hostname:
            evidence.append(Evidence(
                title="Punycode/IDN Domain",
                severity="high",
                detail=f"Domain uses punycode encoding which can hide homograph attacks: {hostname}",
                category="structure"
            ))
        
        # Check for IP literal
        is_ip = False
        try:
            ip = ipaddress.ip_address(hostname)
            is_ip = True
            evidence.append(Evidence(
                title="IP Address URL",
                severity="medium",
                detail=f"URL uses IP address instead of domain: {hostname}",
                category="structure"
            ))
            
            # Check private/localhost
            if block_private_ips:
                for private_range in PRIVATE_RANGES:
                    if ip in private_range:
                        evidence.append(Evidence(
                            title="Private/Localhost IP Blocked",
                            severity="critical",
                            detail=f"Blocked private/localhost IP: {hostname}",
                            category="structure"
                        ))
                        return url, False, evidence
        except ValueError:
            pass
        
        # Check for localhost names
        if block_private_ips:
            if hostname.lower() in ('localhost', 'localhost.localdomain'):
                evidence.append(Evidence(
                    title="Localhost Blocked",
                    severity="critical",
                    detail="Blocked localhost hostname",
                    category="structure"
                ))
                return url, False, evidence
        
        # Normalize URL
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path or '/',
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))
        
        return normalized, True, evidence
    
    def _analyze_url_structure(self, url: str) -> list:
        """Analyze URL structure for suspicious patterns."""
        evidence = []
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        path = parsed.path or ""
        query = parsed.query or ""
        
        # Check suspicious TLD
        for tld in SUSPICIOUS_TLDS:
            if hostname.endswith(tld):
                evidence.append(Evidence(
                    title="Suspicious TLD",
                    severity="medium",
                    detail=f"Domain uses commonly abused TLD: {tld}",
                    category="structure"
                ))
                break
        
        # Check path for suspicious keywords
        path_lower = path.lower()
        found_keywords = []
        for keyword in SUSPICIOUS_PATH_KEYWORDS:
            if keyword in path_lower:
                found_keywords.append(keyword)
        
        if found_keywords:
            evidence.append(Evidence(
                title="Suspicious Path Keywords",
                severity="medium" if len(found_keywords) <= 2 else "high",
                detail=f"Path contains suspicious keywords: {', '.join(found_keywords[:5])}",
                category="structure"
            ))
        
        # Check for suspicious query params
        if query:
            params = parse_qs(query)
            suspicious_params = [p for p in params.keys() if p.lower() in SUSPICIOUS_QUERY_PARAMS]
            if suspicious_params:
                evidence.append(Evidence(
                    title="Redirect Parameters",
                    severity="low",
                    detail=f"URL contains redirect-like parameters: {', '.join(suspicious_params)}",
                    category="structure"
                ))
        
        # Check for excessive subdomain depth
        subdomain_count = hostname.count('.')
        if subdomain_count >= 4:
            evidence.append(Evidence(
                title="Excessive Subdomains",
                severity="low",
                detail=f"Domain has {subdomain_count} levels which may be used to hide the real domain",
                category="structure"
            ))
        
        # Check for very long URL
        if len(url) > 500:
            evidence.append(Evidence(
                title="Unusually Long URL",
                severity="low",
                detail=f"URL is {len(url)} characters which may indicate obfuscation",
                category="structure"
            ))
        
        # Check for encoded characters
        if '%' in url:
            # Count encoded chars
            encoded_count = url.count('%')
            if encoded_count > 10:
                evidence.append(Evidence(
                    title="Heavy URL Encoding",
                    severity="low",
                    detail=f"URL contains {encoded_count} encoded characters which may hide content",
                    category="structure"
                ))
        
        return evidence
    
    def _safe_fetch(self, url: str, block_downloads: bool) -> dict:
        """
        Safely fetch URL with redirect tracking.
        
        Returns dict with: final_url, redirects, status, content_type, content, evidence
        """
        result = {
            "final_url": url,
            "redirects": [],
            "status": 0,
            "content_type": "",
            "content_size": 0,
            "content": "",
            "server": "",
            "evidence": [],
        }
        
        if not REQUESTS_AVAILABLE:
            return result
        
        try:
            # Custom redirect handler to track chain
            session = requests.Session()
            session.max_redirects = self.MAX_REDIRECTS
            
            # Make request with stream to check content-type before downloading
            response = session.get(
                url,
                timeout=(self.CONNECT_TIMEOUT, self.READ_TIMEOUT),
                allow_redirects=True,
                stream=True,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,*/*',
                    'Accept-Language': 'en-US,en;q=0.9',
                }
            )
            
            result["status"] = response.status_code
            result["final_url"] = response.url
            result["content_type"] = response.headers.get('Content-Type', '')
            result["server"] = response.headers.get('Server', '')
            
            # Track redirects
            if response.history:
                for r in response.history:
                    result["redirects"].append({
                        "url": r.url,
                        "status": r.status_code,
                    })
                
                if len(response.history) >= 3:
                    result["evidence"].append(Evidence(
                        title="Multiple Redirects",
                        severity="medium" if len(response.history) < 5 else "high",
                        detail=f"URL redirected {len(response.history)} times before reaching final destination",
                        category="behavior"
                    ))
            
            # Check content type
            content_type = result["content_type"].lower()
            
            # Block download content types
            download_types = [
                'application/octet-stream', 'application/x-msdownload',
                'application/x-msdos-program', 'application/exe',
                'application/x-exe', 'application/zip', 'application/x-zip',
                'application/x-rar', 'application/x-7z-compressed',
            ]
            
            is_download = any(dt in content_type for dt in download_types)
            if is_download:
                result["evidence"].append(Evidence(
                    title="Download Content Type",
                    severity="high",
                    detail=f"Server returned download content-type: {result['content_type']}",
                    category="content"
                ))
                if block_downloads:
                    response.close()
                    return result
            
            # Only download text content
            if 'text/' in content_type or 'html' in content_type or 'javascript' in content_type:
                # Read with size limit
                content = b""
                for chunk in response.iter_content(chunk_size=8192):
                    content += chunk
                    if len(content) > self.MAX_CONTENT_SIZE:
                        result["evidence"].append(Evidence(
                            title="Large Content",
                            severity="info",
                            detail=f"Content exceeded {self.MAX_CONTENT_SIZE // 1024}KB limit, truncated",
                            category="content"
                        ))
                        break
                
                result["content_size"] = len(content)
                
                # Decode
                try:
                    result["content"] = content.decode('utf-8', errors='replace')
                except Exception:
                    result["content"] = content.decode('latin-1', errors='replace')
            else:
                result["evidence"].append(Evidence(
                    title="Non-Text Content",
                    severity="info",
                    detail=f"Content-type is not text/html: {result['content_type']}",
                    category="content"
                ))
            
            response.close()
            
        except requests.exceptions.TooManyRedirects:
            result["evidence"].append(Evidence(
                title="Excessive Redirects",
                severity="high",
                detail=f"URL exceeded maximum of {self.MAX_REDIRECTS} redirects",
                category="behavior"
            ))
        except requests.exceptions.Timeout:
            result["evidence"].append(Evidence(
                title="Connection Timeout",
                severity="medium",
                detail="Server did not respond within timeout period",
                category="behavior"
            ))
        except requests.exceptions.SSLError as e:
            result["evidence"].append(Evidence(
                title="SSL/TLS Error",
                severity="high",
                detail=f"SSL certificate error: {str(e)[:100]}",
                category="security"
            ))
        except requests.exceptions.ConnectionError as e:
            result["evidence"].append(Evidence(
                title="Connection Failed",
                severity="info",
                detail=f"Could not connect to server: {str(e)[:100]}",
                category="behavior"
            ))
        except Exception as e:
            result["evidence"].append(Evidence(
                title="Fetch Error",
                severity="info",
                detail=f"Error fetching URL: {str(e)[:100]}",
                category="behavior"
            ))
        
        return result
    
    def _analyze_content(self, content: str, url: str) -> list:
        """Analyze HTML/JS content for suspicious patterns."""
        evidence = []
        
        if not content:
            return evidence
        
        content_lower = content.lower()
        
        # Check for title
        title_match = re.search(r'<title[^>]*>(.*?)</title>', content_lower, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()[:100]
            # Check for brand names in title (potential phishing)
            brands = ['paypal', 'apple', 'microsoft', 'google', 'amazon', 'facebook', 
                     'netflix', 'bank', 'secure', 'verify', 'update']
            for brand in brands:
                if brand in title:
                    evidence.append(Evidence(
                        title="Brand Name in Title",
                        severity="medium",
                        detail=f"Page title contains '{brand}': {title}",
                        category="content"
                    ))
                    break
        
        # Check for password fields
        password_fields = len(re.findall(r'type\s*=\s*["\']?password', content_lower))
        if password_fields > 0:
            evidence.append(Evidence(
                title="Password Input Field",
                severity="medium",
                detail=f"Page contains {password_fields} password input field(s)",
                category="content"
            ))
        
        # Check for suspicious form actions
        form_actions = re.findall(r'<form[^>]*action\s*=\s*["\']([^"\']+)', content_lower)
        for action in form_actions:
            if action.startswith('http') and urlparse(url).hostname not in action:
                evidence.append(Evidence(
                    title="External Form Action",
                    severity="high",
                    detail=f"Form submits data to external domain: {action[:100]}",
                    category="content"
                ))
        
        # Check for suspicious iframes
        iframes = re.findall(r'<iframe[^>]*src\s*=\s*["\']([^"\']+)', content, re.IGNORECASE)
        for iframe in iframes:
            if iframe.startswith('http'):
                iframe_domain = urlparse(iframe).hostname
                if iframe_domain and iframe_domain != urlparse(url).hostname:
                    evidence.append(Evidence(
                        title="External IFrame",
                        severity="medium",
                        detail=f"Page embeds external iframe: {iframe[:100]}",
                        category="content"
                    ))
        
        # Check for data URIs (potential embedded malware)
        data_uris = len(re.findall(r'data:[^;]+;base64,', content_lower))
        if data_uris > 5:
            evidence.append(Evidence(
                title="Multiple Data URIs",
                severity="medium",
                detail=f"Page contains {data_uris} base64 data URIs which may hide content",
                category="content"
            ))
        
        # Check for obfuscated JavaScript
        obfuscation_signals = [
            (r'eval\s*\(', "eval()"),
            (r'document\.write\s*\(', "document.write()"),
            (r'unescape\s*\(', "unescape()"),
            (r'fromCharCode', "fromCharCode()"),
            (r'\\x[0-9a-f]{2}', "hex escapes"),
            (r'\\u[0-9a-f]{4}', "unicode escapes"),
        ]
        
        found_obfuscation = []
        for pattern, name in obfuscation_signals:
            if re.search(pattern, content, re.IGNORECASE):
                found_obfuscation.append(name)
        
        if found_obfuscation:
            evidence.append(Evidence(
                title="JavaScript Obfuscation Signals",
                severity="medium",
                detail=f"Page uses potential obfuscation: {', '.join(found_obfuscation)}",
                category="content"
            ))
        
        # Check for cryptocurrency wallet addresses
        crypto_patterns = [
            (r'\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b', "Bitcoin"),
            (r'\b0x[a-fA-F0-9]{40}\b', "Ethereum"),
            (r'\b[LM][a-km-zA-HJ-NP-Z1-9]{26,33}\b', "Litecoin"),
        ]
        
        for pattern, crypto_type in crypto_patterns:
            if re.search(pattern, content):
                evidence.append(Evidence(
                    title=f"{crypto_type} Address Found",
                    severity="medium",
                    detail=f"Page contains what appears to be a {crypto_type} wallet address",
                    category="content"
                ))
        
        return evidence
    
    def _extract_iocs(self, content: str, base_url: str) -> dict:
        """Extract Indicators of Compromise from content."""
        iocs = {"urls": [], "domains": [], "ips": []}
        
        if not content:
            return iocs
        
        base_domain = urlparse(base_url).hostname or ""
        
        # Extract URLs
        url_pattern = r'https?://[^\s<>"\')\]]+(?=["\'\s<>)\]]|$)'
        found_urls = set(re.findall(url_pattern, content))
        iocs["urls"] = list(found_urls)[:50]  # Limit
        
        # Extract domains from URLs
        domains = set()
        for url in found_urls:
            try:
                domain = urlparse(url).hostname
                if domain and domain != base_domain:
                    domains.add(domain)
            except Exception:
                pass
        
        # Also extract from href/src attributes
        attr_domains = re.findall(r'(?:href|src)\s*=\s*["\']https?://([^/\s"\']+)', content, re.IGNORECASE)
        for d in attr_domains:
            if d and d != base_domain:
                domains.add(d.lower())
        
        iocs["domains"] = list(domains)[:50]
        
        # Extract IPs
        ip_pattern = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        found_ips = set(re.findall(ip_pattern, content))
        # Filter out common false positives (version numbers, etc.)
        valid_ips = []
        for ip in found_ips:
            try:
                ipaddress.ip_address(ip)
                valid_ips.append(ip)
            except ValueError:
                pass
        iocs["ips"] = valid_ips[:20]
        
        return iocs
    
    def _run_yara(self, content: str) -> list:
        """Run YARA rules on content."""
        if not self._yara_engine:
            return []
        
        try:
            # Create temp file for YARA scanning
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(content)
                temp_path = f.name
            
            try:
                matches = self._yara_engine.scan_file(temp_path)
                return matches
            finally:
                os.unlink(temp_path)
        except Exception as e:
            logger.debug(f"YARA scan error: {e}")
            return []
    
    def _run_sandbox_detonation(
        self,
        url: str,
        block_downloads: bool,
        timeout_seconds: int
    ) -> dict:
        """
        Run URL in sandbox via WebView2 detonator.
        
        Returns dict with sandbox execution results.
        """
        # Check if WebView2 detonator exists
        detonator_path = Path(__file__).parent.parent.parent / "tools" / "url_detonator" / "webview2_detonator.py"
        
        if not detonator_path.exists():
            # Try alternative location
            detonator_path = Path(__file__).parent.parent.parent / "tools" / "webview2_detonator.py"
        
        if not detonator_path.exists():
            raise FileNotFoundError("WebView2 detonator script not found")
        
        # Create temp file for results
        result_file = tempfile.mktemp(suffix='.json')
        
        try:
            # Run detonator in sandbox
            from .integrated_sandbox import get_integrated_sandbox
            sandbox = get_integrated_sandbox()
            
            avail = sandbox.availability()
            if not avail.get("available"):
                raise RuntimeError(f"Sandbox not available: {avail.get('reason', 'unknown')}")
            
            # Build command
            cmd = [
                sys.executable,
                str(detonator_path),
                "--url", url,
                "--output", result_file,
                "--timeout", str(timeout_seconds),
            ]
            if block_downloads:
                cmd.append("--block-downloads")
            
            # Run via subprocess with timeout (sandbox will also enforce limits)
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout_seconds + 10,
                text=True,
                cwd=str(detonator_path.parent)
            )
            
            # Read results
            if Path(result_file).exists():
                import json
                with open(result_file, 'r') as f:
                    return json.load(f)
            else:
                return {
                    "success": False,
                    "error": result.stderr[:500] if result.stderr else "No output file generated",
                    "stdout": result.stdout[:500] if result.stdout else "",
                }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Sandbox execution timed out",
                "timed_out": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            if Path(result_file).exists():
                try:
                    os.unlink(result_file)
                except Exception:
                    pass
    
    def _process_sandbox_result(self, sandbox_result: dict) -> list:
        """Process sandbox results into evidence items."""
        evidence = []
        
        if not sandbox_result.get("success"):
            error = sandbox_result.get("error", "Unknown error")
            evidence.append(Evidence(
                title="Sandbox Error",
                severity="info",
                detail=f"Sandbox detonation did not complete: {error[:200]}",
                category="behavior"
            ))
            return evidence
        
        # Check for download attempts
        downloads = sandbox_result.get("download_attempts", [])
        if downloads:
            for dl in downloads[:5]:
                evidence.append(Evidence(
                    title="Download Attempt",
                    severity="high",
                    detail=f"Page attempted to download: {dl.get('url', 'unknown')[:100]}",
                    category="behavior"
                ))
        
        # Check for popups
        popups = sandbox_result.get("popups", [])
        if popups:
            evidence.append(Evidence(
                title="Popup Windows",
                severity="medium",
                detail=f"Page attempted to open {len(popups)} popup window(s)",
                category="behavior"
            ))
        
        # Check for external navigations
        navigations = sandbox_result.get("navigations", [])
        if len(navigations) > 5:
            evidence.append(Evidence(
                title="Excessive Navigation",
                severity="medium",
                detail=f"Page triggered {len(navigations)} navigation events",
                category="behavior"
            ))
        
        # Check for script errors
        errors = sandbox_result.get("script_errors", [])
        if errors:
            evidence.append(Evidence(
                title="Script Errors",
                severity="info",
                detail=f"Page had {len(errors)} JavaScript error(s)",
                category="content"
            ))
        
        return evidence
    
    def _build_signals(self, result: UrlScanResult) -> dict:
        """Build summary signals dict."""
        return {
            "has_redirects": len(result.redirects) > 0,
            "redirect_count": len(result.redirects),
            "is_https": result.normalized_url.startswith('https://'),
            "is_ip_literal": bool(re.match(r'https?://\d+\.\d+\.\d+\.\d+', result.normalized_url)),
            "evidence_count": len(result.evidence),
            "critical_count": sum(1 for e in result.evidence if getattr(e, 'severity', e.get('severity') if isinstance(e, dict) else '') == 'critical'),
            "high_count": sum(1 for e in result.evidence if getattr(e, 'severity', e.get('severity') if isinstance(e, dict) else '') == 'high'),
            "medium_count": sum(1 for e in result.evidence if getattr(e, 'severity', e.get('severity') if isinstance(e, dict) else '') == 'medium'),
            "yara_matches": len(result.yara_matches),
            "ioc_domains": len(result.iocs.get("domains", [])),
            "ioc_ips": len(result.iocs.get("ips", [])),
            "sandbox_used": result.sandbox_used,
        }


def get_url_scanner() -> UrlScanner:
    """Get URL scanner instance."""
    return UrlScanner()
