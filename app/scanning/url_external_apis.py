"""
External Threat Intelligence API integrations (optional).

Provides lookups against:
- Google Safe Browsing API v4  (env: GOOGLE_SAFE_BROWSING_KEY)
- VirusTotal Public API v3     (env: VIRUSTOTAL_API_KEY)

All lookups are **optional** and gracefully degrade when API keys
are not set or the network is unreachable.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Try importing requests — same guard the rest of the project uses
try:
    import requests

    _REQUESTS = True
except ImportError:
    _REQUESTS = False


@dataclass
class ExternalCheckResult:
    """Result from a single external API lookup."""

    source: str  # "google_safe_browsing", "virustotal"
    available: bool = False  # Was the lookup performed?
    flagged: bool = False  # Did the API flag the URL?
    threat_types: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)
    error: str = ""

    def to_evidence_list(self) -> list[dict]:
        """Convert to Evidence-compatible dicts for scoring."""
        if not self.flagged:
            return []
        items = []
        for threat in self.threat_types:
            items.append(
                {
                    "title": f"External API: {self.source}",
                    "severity": "high",
                    "detail": f"{self.source} flagged URL as {threat}",
                    "category": "reputation",
                }
            )
        return items


# ── Google Safe Browsing v4 ──────────────────────────────────────────────────

_GSB_ENDPOINT = "https://safebrowsing.googleapis.com/v4/threatMatches:find"


def google_safe_browsing(url: str) -> ExternalCheckResult:
    """Lookup a URL via Google Safe Browsing API v4."""
    result = ExternalCheckResult(source="Google Safe Browsing")
    api_key = os.environ.get("GOOGLE_SAFE_BROWSING_KEY", "").strip()
    if not api_key or not _REQUESTS:
        return result

    try:
        body = {
            "client": {"clientId": "sentinel", "clientVersion": "1.0"},
            "threatInfo": {
                "threatTypes": [
                    "MALWARE",
                    "SOCIAL_ENGINEERING",
                    "UNWANTED_SOFTWARE",
                    "POTENTIALLY_HARMFUL_APPLICATION",
                ],
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": url}],
            },
        }
        resp = requests.post(
            _GSB_ENDPOINT,
            params={"key": api_key},
            json=body,
            timeout=5,
        )
        result.available = True
        if resp.status_code == 200:
            data = resp.json()
            matches = data.get("matches", [])
            if matches:
                result.flagged = True
                result.threat_types = list(
                    {m.get("threatType", "UNKNOWN") for m in matches}
                )
                result.raw = data
        else:
            result.error = f"HTTP {resp.status_code}"
            logger.warning("Google Safe Browsing API returned %d", resp.status_code)
    except Exception as exc:
        result.error = str(exc)[:200]
        logger.debug("Google Safe Browsing lookup failed: %s", exc)

    return result


# ── VirusTotal v3 ────────────────────────────────────────────────────────────

_VT_URL_ENDPOINT = "https://www.virustotal.com/api/v3/urls"


def virustotal_lookup(url: str) -> ExternalCheckResult:
    """Lookup a URL via VirusTotal Public API v3."""
    import base64

    result = ExternalCheckResult(source="VirusTotal")
    api_key = os.environ.get("VIRUSTOTAL_API_KEY", "").strip()
    if not api_key or not _REQUESTS:
        return result

    try:
        # VT uses base64-encoded URL (no padding) as the resource ID
        url_id = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
        headers = {"x-apikey": api_key, "Accept": "application/json"}

        resp = requests.get(
            f"{_VT_URL_ENDPOINT}/{url_id}",
            headers=headers,
            timeout=8,
        )
        result.available = True

        if resp.status_code == 200:
            data = resp.json()
            attrs = data.get("data", {}).get("attributes", {})
            stats = attrs.get("last_analysis_stats", {})
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)

            if malicious > 0 or suspicious > 0:
                result.flagged = True
                threats = []
                if malicious > 0:
                    threats.append(f"malicious ({malicious} engines)")
                if suspicious > 0:
                    threats.append(f"suspicious ({suspicious} engines)")
                result.threat_types = threats
                result.raw = {
                    "malicious": malicious,
                    "suspicious": suspicious,
                    "harmless": stats.get("harmless", 0),
                    "undetected": stats.get("undetected", 0),
                }
        elif resp.status_code == 404:
            # URL not in VT database — not an error
            result.raw = {"not_found": True}
        else:
            result.error = f"HTTP {resp.status_code}"
            logger.warning("VirusTotal API returned %d", resp.status_code)
    except Exception as exc:
        result.error = str(exc)[:200]
        logger.debug("VirusTotal lookup failed: %s", exc)

    return result


# ── Convenience ──────────────────────────────────────────────────────────────


def run_external_checks(url: str) -> list[ExternalCheckResult]:
    """Run all configured external API checks and return results."""
    results = []

    gsb = google_safe_browsing(url)
    if gsb.available:
        results.append(gsb)

    vt = virustotal_lookup(url)
    if vt.available:
        results.append(vt)

    return results


def has_any_external_api_key() -> bool:
    """Check if any external API key is configured."""
    return bool(
        os.environ.get("GOOGLE_SAFE_BROWSING_KEY", "").strip()
        or os.environ.get("VIRUSTOTAL_API_KEY", "").strip()
    )
