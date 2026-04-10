"""
URL Scoring Engine - Evidence-based threat scoring.

Calculates threat score (0-100) based on evidence collected during URL analysis.
Maps score to verdict and generates summary.

Score Ranges:
    0-20:   Safe - No significant risk indicators
    21-50:  Suspicious - Some concerning indicators, review recommended
    51-80:  Likely Malicious - Multiple threat indicators detected
    81-100: Malicious - High confidence threat detection

Calibration Rules:
    - Allowlisted domains cap heuristic score at 10 (unless GSB flags them).
    - Google Safe Browsing verdicts override local heuristics.
    - Password fields only penalised on non-allowlisted, non-HTTPS pages.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Top-tier domains that should never score above 10 from heuristics alone ──
_TRUSTED_DOMAINS: frozenset[str] = frozenset({
    "google.com", "facebook.com", "microsoft.com", "apple.com",
    "amazon.com", "twitter.com", "github.com", "gitlab.com",
    "linkedin.com", "youtube.com", "instagram.com", "netflix.com",
    "reddit.com", "wikipedia.org", "stackoverflow.com", "mozilla.org",
    "cloudflare.com", "azure.com", "aws.amazon.com", "paypal.com",
    "whatsapp.com", "zoom.us", "dropbox.com", "spotify.com",
})

# Evidence weight configuration
EVIDENCE_WEIGHTS = {
    # Severity-based base weights
    "severity": {
        "critical": 30,
        "high": 20,
        "medium": 10,
        "low": 5,
        "info": 0,
    },
    # Title-based specific weights (override severity-based)
    "title_keywords": {
        # Structure issues
        "punycode": 25,
        "homograph": 25,
        "ip address url": 15,
        "ip literal": 15,
        "localhost": 30,
        "private": 30,
        "suspicious tld": 12,
        # Redirect issues
        "multiple redirects": 10,
        "excessive redirects": 25,
        "javascript redirect": 15,
        # Content issues
        "download content": 25,
        "download attempt": 35,
        "password input": 12,
        "external form": 20,
        "external iframe": 12,
        "data uri": 10,
        "obfuscation": 15,
        "cryptocurrency": 10,
        "brand name": 15,
        # Security issues
        "ssl": 20,
        "tls": 20,
        "certificate": 20,
        # Behavior issues
        "popup": 12,
        "excessive navigation": 10,
    },
}


@dataclass
class UrlScoringResult:
    """Result of URL threat scoring."""

    score: int  # 0-100
    verdict: str  # "safe", "suspicious", "likely_malicious", "malicious", "blocked"
    verdict_label: str  # Human-readable
    summary: str  # One-line summary
    breakdown: dict = field(default_factory=dict)  # Category -> points

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "verdict": self.verdict,
            "verdict_label": self.verdict_label,
            "summary": self.summary,
            "breakdown": self.breakdown,
        }


class UrlScorer:
    """
    Calculates threat scores for URL scan results.

    Uses evidence items and their severities/categories to compute
    an overall threat score and verdict.
    """

    def __init__(self):
        self._breakdown: dict[str, int] = {}

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _extract_domain(scan_result: dict) -> str:
        """Best-effort domain extraction from scan result URLs."""
        from urllib.parse import urlparse

        for key in ("normalized_url", "url", "final_url"):
            raw = scan_result.get(key, "")
            if raw:
                try:
                    host = urlparse(raw).hostname or ""
                    return host.lower().lstrip("www.")
                except Exception:
                    pass
        return ""

    @staticmethod
    def _is_allowlisted(evidence_list: list) -> bool:
        """Return True if any evidence item says 'Domain in allowlist'."""
        for ev in evidence_list:
            title = ev.title if hasattr(ev, "title") else str(ev.get("title", ""))
            if "allowlist" in title.lower():
                return True
        return False

    @staticmethod
    def _gsb_flagged(evidence_list: list) -> bool:
        """Return True if Google Safe Browsing flagged the URL."""
        for ev in evidence_list:
            title = ev.title if hasattr(ev, "title") else str(ev.get("title", ""))
            detail = ev.detail if hasattr(ev, "detail") else str(ev.get("detail", ""))
            combined = (title + " " + detail).lower()
            if "google safe browsing" in combined or "safe browsing" in combined:
                sev = (ev.severity if hasattr(ev, "severity")
                       else str(ev.get("severity", ""))).lower()
                if sev in ("high", "critical"):
                    return True
        return False

    @staticmethod
    def _is_html_content(scan_result: dict) -> bool:
        """Return True if the fetched content was HTML."""
        ct = str(scan_result.get("content_type", "") or
                 scan_result.get("http_content_type", "")).lower()
        return "html" in ct or "text" in ct

    def _should_skip_evidence(
        self, evidence: dict | Any, *, is_html: bool, is_trusted: bool
    ) -> bool:
        """Return True if this evidence item should be suppressed."""
        title = (evidence.title if hasattr(evidence, "title")
                 else str(evidence.get("title", ""))).lower()

        # Suppress password-field penalty on trusted / HTTPS domains
        if is_trusted and "password" in title:
            return True

        return False

    # ── main scoring entry point ─────────────────────────────────────────

    def score(self, scan_result: dict) -> UrlScoringResult:
        """
        Calculate threat score from URL scan result.

        Args:
            scan_result: Output from UrlScanner.scan_static() or scan_sandbox()

        Returns:
            UrlScoringResult with score, verdict, and breakdown
        """
        self._breakdown = {}
        total = 0

        # Check if blocked during validation
        verdict_raw = scan_result.get("verdict", "")
        if verdict_raw == "blocked":
            return UrlScoringResult(
                score=100,
                verdict="blocked",
                verdict_label="Blocked",
                summary="URL was blocked during validation due to security policy",
                breakdown={"blocked": 100},
            )

        # ── Context flags ────────────────────────────────────────────
        evidence_list = scan_result.get("evidence", [])
        signals = scan_result.get("signals", {})
        domain = self._extract_domain(scan_result)

        is_allowlisted = (
            self._is_allowlisted(evidence_list)
            or domain in _TRUSTED_DOMAINS
        )
        gsb_flagged = self._gsb_flagged(evidence_list)
        is_html = self._is_html_content(scan_result)
        is_https = signals.get("is_https", True)
        is_trusted = is_allowlisted and not gsb_flagged

        # ── Google Safe Browsing supremacy ───────────────────────────
        if gsb_flagged:
            # GSB says malicious → force 100
            self._breakdown["google_safe_browsing"] = 100
            return UrlScoringResult(
                score=100,
                verdict="malicious",
                verdict_label="Malicious",
                summary="Google Safe Browsing flagged this URL as a threat",
                breakdown=self._breakdown.copy(),
            )

        # ── Process evidence ─────────────────────────────────────────
        for evidence in evidence_list:
            if self._should_skip_evidence(
                evidence, is_html=is_html, is_trusted=is_trusted
            ):
                continue
            points = self._score_evidence(evidence)
            total += points

        # Many IOC domains
        ioc_domains = signals.get("ioc_domains", 0)
        if ioc_domains > 10:
            ioc_pts = min((ioc_domains - 10) * 2, 20)
            self._breakdown["many_external_domains"] = ioc_pts
            total += ioc_pts

        # HTTP vs HTTPS (only penalise non-trusted domains)
        if not is_https and not is_trusted:
            self._breakdown["not_https"] = 10
            total += 10

        # ── Apply allowlist cap ──────────────────────────────────────
        # If domain is trusted and GSB didn't flag it, cap at 10
        if is_trusted and total > 10:
            logger.debug(
                "Trusted domain '%s': capping heuristic score %d → 10",
                domain, total,
            )
            self._breakdown["allowlist_cap"] = -(total - 10)
            total = 10

        # ── GSB clean discount ───────────────────────────────────────
        # If any external API ran clean, discount local heuristics by 40%
        gsb_ran_clean = any(
            ("safe browsing" in (
                ev.title if hasattr(ev, "title")
                else str(ev.get("title", ""))
            ).lower())
            and (
                ev.severity if hasattr(ev, "severity")
                else str(ev.get("severity", ""))
            ).lower() in ("info", "low")
            for ev in evidence_list
        )
        if gsb_ran_clean and not is_trusted and total > 0:
            discount = int(total * 0.4)
            if discount > 0:
                self._breakdown["gsb_clean_discount"] = -discount
                total -= discount

        # Cap at 100
        total = min(100, max(0, total))

        # Determine verdict
        verdict, verdict_label = self._get_verdict(total)

        # Build summary
        summary = self._build_summary(scan_result, total, verdict_label)

        return UrlScoringResult(
            score=total,
            verdict=verdict,
            verdict_label=verdict_label,
            summary=summary,
            breakdown=self._breakdown.copy(),
        )

    def _score_evidence(self, evidence: dict | Any) -> int:
        """Score a single evidence item."""
        # Handle both dict and Evidence object
        if hasattr(evidence, "title"):
            title = evidence.title.lower()
            severity = evidence.severity.lower()
            getattr(evidence, "category", "general")
        else:
            title = str(evidence.get("title", "")).lower()
            severity = str(evidence.get("severity", "info")).lower()
            evidence.get("category", "general")

        # Check for keyword-based scoring
        points = 0
        matched_keyword = None

        for keyword, weight in EVIDENCE_WEIGHTS["title_keywords"].items():
            if keyword in title:
                if weight > points:
                    points = weight
                    matched_keyword = keyword

        # If no keyword match, use severity-based scoring
        if points == 0:
            points = EVIDENCE_WEIGHTS["severity"].get(severity, 0)

        # Track in breakdown
        if points > 0:
            key = matched_keyword or severity
            if key not in self._breakdown:
                self._breakdown[key] = 0
            self._breakdown[key] += points

        return points

    def _get_verdict(self, score: int) -> tuple[str, str]:
        """Map score to verdict."""
        if score <= 20:
            return "safe", "Safe"
        if score <= 50:
            return "suspicious", "Suspicious"
        if score <= 80:
            return "likely_malicious", "Likely Malicious"
        return "malicious", "Malicious"

    def _build_summary(self, scan_result: dict, score: int, verdict_label: str) -> str:
        """Build one-line summary."""
        input_url = scan_result.get("input_url", "")
        scan_result.get("final_url", input_url)
        evidence_count = len(scan_result.get("evidence", []))
        redirect_count = len(scan_result.get("redirects", []))
        sandbox_used = scan_result.get("sandbox_used", False)

        # Build summary parts
        parts = []

        if score == 0:
            parts.append("No security concerns detected.")
        elif score <= 20:
            parts.append(f"Low risk (score: {score}/100).")
        elif score <= 50:
            parts.append(f"Moderate risk (score: {score}/100) - Review recommended.")
        elif score <= 80:
            parts.append(f"High risk (score: {score}/100) - Likely malicious.")
        else:
            parts.append(f"Critical risk (score: {score}/100) - Avoid this URL.")

        if evidence_count > 0:
            parts.append(f"{evidence_count} indicator(s) found.")

        if redirect_count > 0:
            parts.append(f"{redirect_count} redirect(s).")

        if sandbox_used:
            parts.append("Sandbox detonation performed.")

        return " ".join(parts)
