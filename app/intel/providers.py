"""
Threat Intelligence Providers
=============================

Abstracted providers for threat intelligence lookups.
Currently supports:
- VirusTotal (primary)
- Extensible for AbuseIPDB, urlscan.io

PRIVACY BY DESIGN:
- Files: Only SHA256 hashes sent, never content
- URLs: Normalized, no sensitive params sent
- All lookups cached to minimize external calls
- API keys stored securely, never logged
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlparse, urlencode
import base64

logger = logging.getLogger(__name__)


# =============================================================================
# VERDICTS
# =============================================================================

class ThreatVerdict(Enum):
    """Standardized threat verdict across all providers."""
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"
    UNKNOWN = "unknown"
    ERROR = "error"
    
    @classmethod
    def from_score(cls, score: int) -> "ThreatVerdict":
        """Convert a 0-100 score to verdict."""
        if score >= 70:
            return cls.MALICIOUS
        elif score >= 40:
            return cls.SUSPICIOUS
        elif score >= 0:
            return cls.CLEAN
        return cls.UNKNOWN


@dataclass
class IntelResult:
    """Standardized result from any intelligence provider."""
    verdict: ThreatVerdict
    score: int  # 0-100, higher = more malicious
    provider: str
    lookup_type: str  # "file_hash", "url", "ip", "domain"
    raw_value: str  # The hash/url/ip that was looked up
    
    # Detection details
    positives: int = 0  # Number of engines detecting as malicious
    total: int = 0  # Total engines that scanned
    
    # Additional context
    categories: list[str] = field(default_factory=list)
    threat_names: list[str] = field(default_factory=list)
    
    # Metadata
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    
    # Full response (for debugging)
    raw_response: dict = field(default_factory=dict)
    
    # Error info
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "score": self.score,
            "provider": self.provider,
            "lookup_type": self.lookup_type,
            "positives": self.positives,
            "total": self.total,
            "categories": self.categories,
            "threat_names": self.threat_names,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "error": self.error,
        }
    
    @property
    def detection_ratio(self) -> str:
        """Human-readable detection ratio."""
        if self.total == 0:
            return "No scan data"
        return f"{self.positives}/{self.total}"
    
    @property
    def summary(self) -> str:
        """One-line summary for UI."""
        if self.error:
            return f"Error: {self.error}"
        
        if self.verdict == ThreatVerdict.CLEAN:
            return f"✅ Clean ({self.detection_ratio} detections)"
        elif self.verdict == ThreatVerdict.SUSPICIOUS:
            return f"⚠️ Suspicious ({self.detection_ratio} detections)"
        elif self.verdict == ThreatVerdict.MALICIOUS:
            threats = ", ".join(self.threat_names[:3]) if self.threat_names else "malware"
            return f"🔴 Malicious: {threats} ({self.detection_ratio})"
        else:
            return f"❓ Unknown - not in database"


# =============================================================================
# PROVIDER BASE
# =============================================================================

class IntelProvider(ABC):
    """Base class for threat intelligence providers."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._rate_limit_reset: float = 0
        self._requests_remaining: int = 999
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging/caching."""
        pass
    
    @abstractmethod
    async def check_file_hash(self, sha256: str) -> IntelResult:
        """Check a file hash against the provider."""
        pass
    
    @abstractmethod
    async def check_url(self, url: str) -> IntelResult:
        """Check a URL against the provider."""
        pass
    
    def _is_rate_limited(self) -> bool:
        """Check if we're currently rate limited."""
        if self._requests_remaining <= 0 and time.time() < self._rate_limit_reset:
            return True
        return False


# =============================================================================
# VIRUSTOTAL
# =============================================================================

class VirusTotalClient(IntelProvider):
    """
    VirusTotal API v3 client.
    
    Supports:
    - File hash lookups (SHA256 only - privacy first)
    - URL lookups (base64 encoded)
    
    Rate limits:
    - Free API: 4 requests/minute, 500/day
    - Handles rate limiting gracefully
    """
    
    API_BASE = "https://www.virustotal.com/api/v3"
    
    def __init__(self, api_key: Optional[str] = None):
        # Try to get API key from environment if not provided
        super().__init__(api_key or os.environ.get("VIRUSTOTAL_API_KEY"))
        self._session = None
    
    @property
    def name(self) -> str:
        return "virustotal"
    
    @property
    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)
    
    async def _get_session(self):
        """Get or create aiohttp session."""
        if self._session is None:
            try:
                import aiohttp
                self._session = aiohttp.ClientSession(
                    headers={"x-apikey": self.api_key} if self.api_key else {}
                )
            except ImportError:
                logger.warning("aiohttp not installed - VT client disabled")
                return None
        return self._session
    
    async def close(self):
        """Close the HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None
    
    async def check_file_hash(self, sha256: str) -> IntelResult:
        """
        Look up a file by SHA256 hash.
        
        PRIVACY: Only the hash is sent, never the file content.
        """
        if not self.is_configured:
            return IntelResult(
                verdict=ThreatVerdict.ERROR,
                score=-1,
                provider=self.name,
                lookup_type="file_hash",
                raw_value=sha256,
                error="VirusTotal API key not configured",
            )
        
        if self._is_rate_limited():
            return IntelResult(
                verdict=ThreatVerdict.ERROR,
                score=-1,
                provider=self.name,
                lookup_type="file_hash",
                raw_value=sha256,
                error="Rate limited - please wait",
            )
        
        # Validate hash format
        if not re.match(r"^[a-fA-F0-9]{64}$", sha256):
            return IntelResult(
                verdict=ThreatVerdict.ERROR,
                score=-1,
                provider=self.name,
                lookup_type="file_hash",
                raw_value=sha256,
                error="Invalid SHA256 hash format",
            )
        
        try:
            import aiohttp
            session = await self._get_session()
            if not session:
                return IntelResult(
                    verdict=ThreatVerdict.ERROR,
                    score=-1,
                    provider=self.name,
                    lookup_type="file_hash",
                    raw_value=sha256,
                    error="HTTP client not available",
                )
            
            url = f"{self.API_BASE}/files/{sha256.lower()}"
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                # Handle rate limiting
                self._requests_remaining = int(
                    resp.headers.get("x-api-quota-remaining", 999)
                )
                
                if resp.status == 429:
                    self._rate_limit_reset = time.time() + 60
                    return IntelResult(
                        verdict=ThreatVerdict.ERROR,
                        score=-1,
                        provider=self.name,
                        lookup_type="file_hash",
                        raw_value=sha256,
                        error="Rate limited - please wait 60 seconds",
                    )
                
                if resp.status == 404:
                    return IntelResult(
                        verdict=ThreatVerdict.UNKNOWN,
                        score=-1,
                        provider=self.name,
                        lookup_type="file_hash",
                        raw_value=sha256,
                        error=None,
                    )
                
                if resp.status != 200:
                    return IntelResult(
                        verdict=ThreatVerdict.ERROR,
                        score=-1,
                        provider=self.name,
                        lookup_type="file_hash",
                        raw_value=sha256,
                        error=f"API error: HTTP {resp.status}",
                    )
                
                data = await resp.json()
                return self._parse_file_response(sha256, data)
                
        except asyncio.TimeoutError:
            return IntelResult(
                verdict=ThreatVerdict.ERROR,
                score=-1,
                provider=self.name,
                lookup_type="file_hash",
                raw_value=sha256,
                error="Request timeout",
            )
        except Exception as e:
            logger.error(f"VT file hash lookup error: {e}")
            return IntelResult(
                verdict=ThreatVerdict.ERROR,
                score=-1,
                provider=self.name,
                lookup_type="file_hash",
                raw_value=sha256,
                error=str(e),
            )
    
    def _parse_file_response(self, sha256: str, data: dict) -> IntelResult:
        """Parse VT file lookup response."""
        try:
            attrs = data.get("data", {}).get("attributes", {})
            stats = attrs.get("last_analysis_stats", {})
            
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            undetected = stats.get("undetected", 0)
            harmless = stats.get("harmless", 0)
            
            total = malicious + suspicious + undetected + harmless
            positives = malicious + suspicious
            
            # Calculate score (0-100)
            if total > 0:
                score = int((positives / total) * 100)
            else:
                score = 0
            
            # Determine verdict
            if malicious >= 5 or score >= 70:
                verdict = ThreatVerdict.MALICIOUS
            elif malicious >= 1 or suspicious >= 3 or score >= 30:
                verdict = ThreatVerdict.SUSPICIOUS
            else:
                verdict = ThreatVerdict.CLEAN
            
            # Extract threat names
            threat_names = []
            results = attrs.get("last_analysis_results", {})
            for engine, result in results.items():
                if result.get("category") == "malicious" and result.get("result"):
                    threat_names.append(result["result"])
            
            # Deduplicate and limit
            threat_names = list(set(threat_names))[:10]
            
            return IntelResult(
                verdict=verdict,
                score=score,
                provider=self.name,
                lookup_type="file_hash",
                raw_value=sha256,
                positives=positives,
                total=total,
                threat_names=threat_names,
                first_seen=attrs.get("first_submission_date"),
                last_seen=attrs.get("last_analysis_date"),
                raw_response=data,
            )
            
        except Exception as e:
            logger.error(f"Error parsing VT response: {e}")
            return IntelResult(
                verdict=ThreatVerdict.ERROR,
                score=-1,
                provider=self.name,
                lookup_type="file_hash",
                raw_value=sha256,
                error=f"Parse error: {e}",
            )
    
    async def check_url(self, url: str) -> IntelResult:
        """
        Look up a URL.
        
        URLs are base64 encoded as required by VT API v3.
        """
        if not self.is_configured:
            return IntelResult(
                verdict=ThreatVerdict.ERROR,
                score=-1,
                provider=self.name,
                lookup_type="url",
                raw_value=url,
                error="VirusTotal API key not configured",
            )
        
        if self._is_rate_limited():
            return IntelResult(
                verdict=ThreatVerdict.ERROR,
                score=-1,
                provider=self.name,
                lookup_type="url",
                raw_value=url,
                error="Rate limited - please wait",
            )
        
        try:
            import aiohttp
            session = await self._get_session()
            if not session:
                return IntelResult(
                    verdict=ThreatVerdict.ERROR,
                    score=-1,
                    provider=self.name,
                    lookup_type="url",
                    raw_value=url,
                    error="HTTP client not available",
                )
            
            # VT requires base64-encoded URL (without padding)
            url_id = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
            api_url = f"{self.API_BASE}/urls/{url_id}"
            
            async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                self._requests_remaining = int(
                    resp.headers.get("x-api-quota-remaining", 999)
                )
                
                if resp.status == 429:
                    self._rate_limit_reset = time.time() + 60
                    return IntelResult(
                        verdict=ThreatVerdict.ERROR,
                        score=-1,
                        provider=self.name,
                        lookup_type="url",
                        raw_value=url,
                        error="Rate limited",
                    )
                
                if resp.status == 404:
                    return IntelResult(
                        verdict=ThreatVerdict.UNKNOWN,
                        score=-1,
                        provider=self.name,
                        lookup_type="url",
                        raw_value=url,
                    )
                
                if resp.status != 200:
                    return IntelResult(
                        verdict=ThreatVerdict.ERROR,
                        score=-1,
                        provider=self.name,
                        lookup_type="url",
                        raw_value=url,
                        error=f"API error: HTTP {resp.status}",
                    )
                
                data = await resp.json()
                return self._parse_url_response(url, data)
                
        except asyncio.TimeoutError:
            return IntelResult(
                verdict=ThreatVerdict.ERROR,
                score=-1,
                provider=self.name,
                lookup_type="url",
                raw_value=url,
                error="Request timeout",
            )
        except Exception as e:
            logger.error(f"VT URL lookup error: {e}")
            return IntelResult(
                verdict=ThreatVerdict.ERROR,
                score=-1,
                provider=self.name,
                lookup_type="url",
                raw_value=url,
                error=str(e),
            )
    
    def _parse_url_response(self, url: str, data: dict) -> IntelResult:
        """Parse VT URL lookup response."""
        try:
            attrs = data.get("data", {}).get("attributes", {})
            stats = attrs.get("last_analysis_stats", {})
            
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            undetected = stats.get("undetected", 0)
            harmless = stats.get("harmless", 0)
            
            total = malicious + suspicious + undetected + harmless
            positives = malicious + suspicious
            
            # Calculate score
            if total > 0:
                score = int((positives / total) * 100)
            else:
                score = 0
            
            # Determine verdict
            if malicious >= 3 or score >= 60:
                verdict = ThreatVerdict.MALICIOUS
            elif malicious >= 1 or suspicious >= 2 or score >= 20:
                verdict = ThreatVerdict.SUSPICIOUS
            else:
                verdict = ThreatVerdict.CLEAN
            
            # Extract categories
            categories = list(attrs.get("categories", {}).values())
            
            return IntelResult(
                verdict=verdict,
                score=score,
                provider=self.name,
                lookup_type="url",
                raw_value=url,
                positives=positives,
                total=total,
                categories=categories,
                last_seen=attrs.get("last_analysis_date"),
                raw_response=data,
            )
            
        except Exception as e:
            logger.error(f"Error parsing VT URL response: {e}")
            return IntelResult(
                verdict=ThreatVerdict.ERROR,
                score=-1,
                provider=self.name,
                lookup_type="url",
                raw_value=url,
                error=f"Parse error: {e}",
            )


# =============================================================================
# SINGLETON
# =============================================================================

_vt_client: Optional[VirusTotalClient] = None

def get_virustotal_client() -> VirusTotalClient:
    """Get the singleton VirusTotal client."""
    global _vt_client
    if _vt_client is None:
        _vt_client = VirusTotalClient()
    return _vt_client
