"""
Multi-Engine URL Scanner — Aggregates all URL analysis engines.

Combines:
1. URLChecker   — instant offline heuristics (blocklist, TLD, typosquatting…)
2. UrlScanner   — HTTP fetch and content analysis
3. External APIs — Google Safe Browsing, VirusTotal (optional)
4. UrlScorer    — weighted evidence scoring
5. UrlExplainer — human-readable explanations
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from backend.engines.scanning.url_scanner import Evidence, UrlScanResult

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class EngineResult:
    """Result from a single scan engine."""

    engine_name: str
    available: bool = True
    score: int = 0
    verdict: str = "unknown"
    flagged: bool = False
    evidence: list = field(default_factory=list)
    details: dict = field(default_factory=dict)
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "engine_name": self.engine_name,
            "available": self.available,
            "score": self.score,
            "verdict": self.verdict,
            "flagged": self.flagged,
            "evidence_count": len(self.evidence),
            "evidence": [
                e.to_dict() if hasattr(e, "to_dict") else e for e in self.evidence
            ],
            "details": self.details,
            "duration_ms": self.duration_ms,
        }


# Threat type classification keywords
_THREAT_KEYWORDS = {
    "phishing": [
        "password", "login", "credential", "brand name", "external form",
        "phishing", "social_engineering", "typosquat",
    ],
    "malware": [
        "malware", "download attempt", "download content",
        "executable", "obfuscation",
    ],
    "suspicious_structure": [
        "suspicious tld", "punycode", "homograph", "ip address",
        "ip literal", "subdomain", "long url", "encoding",
    ],
    "redirect_abuse": [
        "redirect", "navigation", "javascript redirect",
    ],
    "download_risk": [
        "download", "executable", "octet-stream",
    ],
}


def _classify_threats(evidence_list: list) -> list[str]:
    """
    Classify detected threats into human-readable categories.
    Returns a de-duplicated list like ["Phishing", "Malware"].
    """
    found: set[str] = set()
    for ev in evidence_list:
        title = (
            ev.title.lower() if hasattr(ev, "title") else
            str(ev.get("title", "")).lower()
        )
        detail = (
            ev.detail.lower() if hasattr(ev, "detail") else
            str(ev.get("detail", "")).lower()
        )
        combined = title + " " + detail

        for category, keywords in _THREAT_KEYWORDS.items():
            for kw in keywords:
                if kw in combined:
                    found.add(category)
                    break

    # Pretty labels
    labels = {
        "phishing": "Phishing",
        "malware": "Malware",
        "suspicious_structure": "Suspicious Structure",
        "redirect_abuse": "Redirect Abuse",
        "download_risk": "Download Risk",
    }
    return [labels.get(f, f) for f in sorted(found)]


# ── Multi-Engine Scanner ─────────────────────────────────────────────────────


class MultiEngineUrlScanner:
    """
    Aggregates URLChecker + UrlScanner + external APIs into one scan.

    Usage::

        scanner = MultiEngineUrlScanner()
        result = scanner.scan("https://example.com")
        print(result["final_score"], result["final_verdict"])
    """

    def __init__(self, *, progress_callback: Callable | None = None):
        """
        Args:
            progress_callback: Optional callable(stage: str, pct: int) for
                               real-time UI progress updates.
        """
        self._progress = progress_callback or (lambda *_: None)

    # ── public API ───────────────────────────────────────────────────────

    def scan(
        self,
        url: str,
        *,
        use_sandbox: bool = False,
        block_private_ips: bool = True,
        block_downloads: bool = True,
        run_external_apis: bool = True,
    ) -> dict[str, Any]:
        """
        Run all engines and return an aggregated result dict.

        The returned dict includes:
            final_score, final_verdict, threat_types,
            engines (per-engine breakdown), merged_evidence,
            plus the original UrlScanResult fields.
        """
        t0 = time.perf_counter()
        engines: dict[str, EngineResult] = {}
        all_evidence: list[Evidence] = []

        # ── 1. URLChecker (instant offline heuristics) ───────────────────
        self._progress("Checking blocklists & heuristics…", 5)
        checker_engine = self._run_checker(url)
        engines["heuristic_checker"] = checker_engine
        all_evidence.extend(checker_engine.evidence)

        # Short-circuit if blocked
        if checker_engine.details.get("is_blocked"):
            return self._build_result(
                url, engines, all_evidence, t0,
                force_verdict="blocked", force_score=100,
            )

        # ── 2. UrlScanner (HTTP fetch, content analysis) ──────────────────
        self._progress("Analyzing URL structure…", 15)
        scanner_engine, scan_result = self._run_scanner(
            url,
            use_sandbox=use_sandbox,
            block_private_ips=block_private_ips,
            block_downloads=block_downloads,
        )
        engines["url_scanner"] = scanner_engine
        # Don't duplicate evidence already inside scan_result
        all_evidence.extend(scanner_engine.evidence)

        # ── 3. External APIs (optional) ──────────────────────────────────
        if run_external_apis:
            self._progress("Checking threat intelligence APIs…", 75)
            ext_engines = self._run_external_apis(url)
            for eng in ext_engines:
                engines[eng.engine_name.lower().replace(" ", "_")] = eng
                all_evidence.extend(eng.evidence)

        # ── 4. Score + verdict ───────────────────────────────────────────
        self._progress("Calculating threat score…", 90)
        return self._build_result(
            url, engines, all_evidence, t0,
            scan_result=scan_result,
        )

    # ── engine runners ───────────────────────────────────────────────────

    def _run_checker(self, url: str) -> EngineResult:
        """Run URLChecker offline heuristics."""
        t = time.perf_counter()
        engine = EngineResult(engine_name="Heuristic Checker")
        try:
            from backend.engines.scanning.url_checker import URLChecker

            checker = URLChecker()
            cr = checker.check_url(url)
            engine.score = cr.score
            engine.verdict = cr.verdict.lower()
            engine.flagged = cr.score > 20
            engine.details = {
                "is_blocked": cr.is_blocked,
                "is_allowlisted": cr.is_allowlisted,
            }

            # Convert URLChecker reasons → Evidence objects
            for r in cr.reasons:
                engine.evidence.append(
                    Evidence(
                        title=r.get("title", ""),
                        severity=r.get("severity", "info"),
                        detail=r.get("detail", ""),
                        category="heuristic",
                    )
                )
        except Exception as exc:
            logger.warning("URLChecker failed: %s", exc)
            engine.available = False
            engine.details["error"] = str(exc)[:200]

        engine.duration_ms = int((time.perf_counter() - t) * 1000)
        return engine

    def _run_scanner(
        self, url: str, **kwargs
    ) -> tuple[EngineResult, UrlScanResult | None]:
        """Run UrlScanner HTTP + content analysis pipeline."""
        t = time.perf_counter()
        engine = EngineResult(engine_name="URL Scanner")
        scan_result: UrlScanResult | None = None

        try:
            from backend.engines.scanning.url_scanner import UrlScanner

            scanner = UrlScanner()

            use_sandbox = kwargs.get("use_sandbox", False)
            block_private_ips = kwargs.get("block_private_ips", True)
            block_downloads = kwargs.get("block_downloads", True)

            self._progress("Fetching URL content…", 30)
            if use_sandbox:
                scan_result = scanner.scan_sandbox(
                    url,
                    block_private_ips=block_private_ips,
                    block_downloads=block_downloads,
                )
            else:
                scan_result = scanner.scan_static(
                    url, block_private_ips=block_private_ips
                )

            self._progress("Running content analysis…", 55)
            engine.score = scan_result.score
            engine.verdict = scan_result.verdict.lower() if scan_result.verdict else "unknown"
            engine.flagged = engine.score > 20

            # Copy evidence from scan_result into engine
            for ev in scan_result.evidence:
                engine.evidence.append(ev)

            engine.details = {
                "http_status": scan_result.http_status,
                "content_type": scan_result.content_type,
                "redirect_count": len(scan_result.redirects),
                "ioc_count": (
                    len(scan_result.iocs.get("domains", []))
                    + len(scan_result.iocs.get("ips", []))
                ),
            }

        except Exception as exc:
            logger.warning("UrlScanner failed: %s", exc)
            engine.available = False
            engine.details["error"] = str(exc)[:200]

        engine.duration_ms = int((time.perf_counter() - t) * 1000)
        return engine, scan_result

    def _run_external_apis(self, url: str) -> list[EngineResult]:
        """Run optional external API checks."""
        results: list[EngineResult] = []
        try:
            from backend.engines.scanning.url_external_apis import run_external_checks

            ext_checks = run_external_checks(url)

            for check in ext_checks:
                eng = EngineResult(engine_name=check.source)
                eng.available = check.available
                eng.flagged = check.flagged
                eng.details = check.raw

                if check.flagged:
                    eng.score = 40  # significant boost from external API
                    eng.verdict = "flagged"
                    for ev_dict in check.to_evidence_list():
                        eng.evidence.append(
                            Evidence(
                                title=ev_dict["title"],
                                severity=ev_dict["severity"],
                                detail=ev_dict["detail"],
                                category=ev_dict["category"],
                            )
                        )
                else:
                    eng.verdict = "clean"

                eng.duration_ms = 0  # already measured inside the check
                results.append(eng)

        except ImportError:
            pass
        except Exception as exc:
            logger.debug("External API checks failed: %s", exc)

        return results

    # ── result building ──────────────────────────────────────────────────

    def _build_result(
        self,
        url: str,
        engines: dict[str, EngineResult],
        all_evidence: list,
        t0: float,
        *,
        scan_result: UrlScanResult | None = None,
        force_verdict: str | None = None,
        force_score: int | None = None,
    ) -> dict[str, Any]:
        """
        Aggregate all engine results into the final dict.
        Also runs UrlScorer on the merged evidence.
        """
        # De-duplicate evidence by title+detail
        seen = set()
        unique_evidence: list[Evidence] = []
        for ev in all_evidence:
            title = ev.title if hasattr(ev, "title") else ev.get("title", "")
            detail = ev.detail if hasattr(ev, "detail") else ev.get("detail", "")
            key = (title, detail)
            if key not in seen:
                seen.add(key)
                unique_evidence.append(ev)

        # Score merged evidence
        final_score = force_score
        final_verdict = force_verdict

        scoring_result = None
        if final_score is None:
            try:
                from backend.engines.scanning.url_scoring import UrlScorer

                scorer = UrlScorer()
                # Build a scan_result-like dict for the scorer
                score_input = {
                    "evidence": unique_evidence,
                    "signals": scan_result.signals if scan_result else {},
                    "redirects": scan_result.redirects if scan_result else [],
                    "verdict": "",
                }
                scoring_result = scorer.score(score_input)
                final_score = scoring_result.score
                final_verdict = scoring_result.verdict
            except Exception as exc:
                logger.warning("Scoring failed: %s", exc)
                # Fallback: use highest engine score
                final_score = max((e.score for e in engines.values()), default=0)
                final_verdict = self._score_to_verdict(final_score)

        if final_verdict is None:
            final_verdict = self._score_to_verdict(final_score)

        # Classify threat types
        threat_types = _classify_threats(unique_evidence)

        # Generate explanation
        explanation_dict = None
        if scan_result:
            try:
                from backend.engines.ai.url_explainer import explain_url_scan, explanation_to_dict

                # Update scan_result with final score/verdict
                scan_result.score = final_score
                scan_result.verdict = final_verdict
                scan_result.evidence = unique_evidence
                expl = explain_url_scan(scan_result)
                explanation_dict = explanation_to_dict(expl)
            except Exception as exc:
                logger.debug("Explanation generation failed: %s", exc)

        scan_duration = time.perf_counter() - t0

        self._progress("Scan complete", 100)

        # Build final result dict (matches what backend_bridge expects)
        result: dict[str, Any] = {
            "success": True,
            "url": url,
            "normalized_url": scan_result.normalized_url if scan_result else url,
            "final_url": scan_result.final_url if scan_result else url,
            # Verdict
            "score": final_score,
            "verdict": final_verdict,
            # HTTP info from scanner
            "http_status": scan_result.http_status if scan_result else None,
            "http_content_type": scan_result.content_type if scan_result else "",
            "http_content_length": scan_result.content_size if scan_result else 0,
            # Redirects
            "redirects": scan_result.redirects if scan_result else [],
            "redirect_count": len(scan_result.redirects) if scan_result else 0,
            # Evidence
            "evidence": [
                e.to_dict() if hasattr(e, "to_dict") else e for e in unique_evidence
            ],
            "evidence_count": len(unique_evidence),
            # IOCs
            "iocs": scan_result.iocs if scan_result else {},
            "has_iocs": bool(scan_result and scan_result.iocs),
            # Signals
            "signals": scan_result.signals if scan_result else {},
            # Sandbox
            "has_sandbox": scan_result.sandbox_used if scan_result else False,
            "sandbox_result": (
                scan_result.sandbox_result
                if scan_result and scan_result.sandbox_result
                else None
            ),
            # Explanation
            "explanation": explanation_dict,
            # ── NEW: multi-engine fields ─────────────────────────────────
            "threat_types": threat_types,
            "engines": {name: eng.to_dict() for name, eng in engines.items()},
            "engine_count": len(engines),
            "engines_flagged": sum(1 for e in engines.values() if e.flagged),
            # Scoring breakdown
            "scoring": scoring_result.to_dict() if scoring_result else {
                "score": final_score,
                "verdict": final_verdict,
                "breakdown": {},
            },
            # Timing
            "scan_duration_sec": round(scan_duration, 2),
        }

        return result

    @staticmethod
    def _score_to_verdict(score: int) -> str:
        if score <= 20:
            return "safe"
        if score <= 50:
            return "suspicious"
        if score <= 80:
            return "likely_malicious"
        return "malicious"
