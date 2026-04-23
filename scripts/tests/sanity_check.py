"""
Sentinel Scoring Sanity Checker
================================
Standalone script that validates the core scoring math of:
  1. URL Scanner   – trusted-domain short-circuit & GSB override
  2. Groq NGAV     – JSON response parsing from the AI engine

Run:  python sanity_check.py
"""

from __future__ import annotations

import json
import sys
import traceback

# ── ANSI colours ─────────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


# ── Helpers ──────────────────────────────────────────────────────────────────
_passed = 0
_failed = 0


def _report(label: str, ok: bool, detail: str = "") -> None:
    global _passed, _failed
    if ok:
        _passed += 1
        tag = f"{GREEN}PASS{RESET}"
    else:
        _failed += 1
        tag = f"{RED}FAIL{RESET}"
    print(f"  [{tag}] {label}")
    if not ok and detail:
        print(f"         {RED}↳ {detail}{RESET}")


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  SECTION 1 – URL Scorer Short-Circuit Tests                             ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

def test_url_scoring() -> None:
    print(f"\n{CYAN}{BOLD}▸ URL Scoring Engine{RESET}")
    print(f"  {DIM}(backend.engines.scanning.url_scoring.UrlScorer){RESET}\n")

    from backend.engines.scanning.url_scoring import UrlScorer

    scorer = UrlScorer()

    # ── Test A: The YouTube Test ─────────────────────────────────────────
    # youtube.com is in _TRUSTED_DOMAINS.  Even with noisy heuristic
    # evidence, the trusted-domain cap must keep the final score ≤ 10.
    # A mock GSB result at severity "info" (score 0) means GSB ran clean
    # but did NOT flag the domain.
    scan_result_youtube: dict = {
        "normalized_url": "https://www.youtube.com/watch?v=abc",
        "final_url": "https://www.youtube.com/watch?v=abc",
        "verdict": "",
        "content_type": "text/html",
        "signals": {"is_https": True, "ioc_domains": 0},
        "evidence": [
            # GSB ran and came back clean (score 0 = info severity)
            {
                "title": "Google Safe Browsing",
                "severity": "info",
                "detail": "No threats detected",
                "category": "reputation",
            },
            # Fake heuristic warnings that don't match keyword triggers
            # (simulates low-level noise from the pipeline)
            {
                "title": "Third-party analytics loaded",
                "severity": "info",
                "detail": "Non-threatening tracker script",
                "category": "content",
            },
            {
                "title": "Cookie consent banner",
                "severity": "info",
                "detail": "Standard GDPR banner detected",
                "category": "content",
            },
        ],
    }

    result_a = scorer.score(scan_result_youtube)

    _report(
        "Test A – YouTube trusted-domain → score 0",
        result_a.score == 0,
        f"Expected score=0, got score={result_a.score} "
        f"(breakdown: {result_a.breakdown})",
    )

    # ── Test B: The Phishing Test ────────────────────────────────────────
    # An unknown domain where Google Safe Browsing flags it as HIGH
    # severity.  The GSB supremacy rule must force the score to 100.
    scan_result_evil: dict = {
        "normalized_url": "https://random-evil-site.net/login.php",
        "final_url": "https://random-evil-site.net/login.php",
        "verdict": "",
        "content_type": "text/html",
        "signals": {"is_https": True, "ioc_domains": 2},
        "evidence": [
            {
                "title": "Google Safe Browsing flagged",
                "severity": "high",
                "detail": "URL found in Safe Browsing threat lists",
                "category": "reputation",
            },
        ],
    }

    result_b = scorer.score(scan_result_evil)

    _report(
        "Test B – Phishing GSB override → 100",
        result_b.score == 100,
        f"Expected score=100, got score={result_b.score} "
        f"(verdict: {result_b.verdict})",
    )

    # Also verify the verdict string
    _report(
        "Test B – Verdict is 'malicious'",
        result_b.verdict == "malicious",
        f"Expected verdict='malicious', got '{result_b.verdict}'",
    )


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  SECTION 2 – Groq NGAV JSON Parser Tests                                ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

def _parse_groq_response(raw: str) -> dict:
    """
    Replicates the exact JSON extraction logic from
    StaticScanner._run_groq_ngav so we can test it in isolation
    without calling the Groq API.
    """
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    parsed = json.loads(raw)

    ngav_score = int(parsed.get("score", 0))
    ngav_verdict = str(parsed.get("verdict", "Unknown"))
    ngav_explanation = str(parsed.get("explanation", ""))

    return {
        "score": max(0, min(100, ngav_score)),
        "verdict": ngav_verdict,
        "explanation": ngav_explanation,
    }


def test_groq_parser() -> None:
    print(f"\n{CYAN}{BOLD}▸ Groq NGAV Response Parser{RESET}")
    print(f"  {DIM}(StaticScanner._run_groq_ngav JSON extraction){RESET}\n")

    # ── Test C: The Rufus Test (clean binary, UPX packed) ────────────────
    raw_clean = json.dumps({
        "score": 0,
        "verdict": "Clean",
        "explanation": "Legitimate UPX packer.",
    })

    result_c = _parse_groq_response(raw_clean)

    _report(
        "Test C – Rufus clean score extraction",
        result_c["score"] == 0,
        f"Expected score=0, got {result_c['score']}",
    )
    _report(
        "Test C – Verdict string preserved",
        result_c["verdict"] == "Clean",
        f"Expected 'Clean', got '{result_c['verdict']}'",
    )
    _report(
        "Test C – Explanation preserved",
        result_c["explanation"] == "Legitimate UPX packer.",
        f"Expected 'Legitimate UPX packer.', got '{result_c['explanation']}'",
    )

    # ── Test D: The Ransomware Test (high-threat binary) ─────────────────
    raw_malicious = json.dumps({
        "score": 99,
        "verdict": "Malicious",
        "explanation": "Ransomware API imports detected.",
    })

    result_d = _parse_groq_response(raw_malicious)

    _report(
        "Test D – Ransomware score extraction",
        result_d["score"] == 99,
        f"Expected score=99, got {result_d['score']}",
    )
    _report(
        "Test D – Verdict string preserved",
        result_d["verdict"] == "Malicious",
        f"Expected 'Malicious', got '{result_d['verdict']}'",
    )

    # ── Test E: Markdown-fenced response ─────────────────────────────────
    # Groq sometimes wraps its JSON in ```json ... ``` fences
    raw_fenced = (
        "Here is my analysis:\n\n"
        "```json\n"
        '{"score": 42, "verdict": "Suspicious", '
        '"explanation": "Unusual entropy in .text section."}\n'
        "```\n"
    )

    result_e = _parse_groq_response(raw_fenced)

    _report(
        "Test E – Markdown-fence extraction",
        result_e["score"] == 42,
        f"Expected score=42, got {result_e['score']}",
    )

    # ── Test F: Score clamping ───────────────────────────────────────────
    raw_overflow = json.dumps({"score": 9999, "verdict": "Malicious", "explanation": ""})

    result_f = _parse_groq_response(raw_overflow)

    _report(
        "Test F – Score clamped to 100",
        result_f["score"] == 100,
        f"Expected score=100, got {result_f['score']}",
    )

    raw_underflow = json.dumps({"score": -50, "verdict": "Clean", "explanation": ""})

    result_g = _parse_groq_response(raw_underflow)

    _report(
        "Test F – Negative score clamped to 0",
        result_g["score"] == 0,
        f"Expected score=0, got {result_g['score']}",
    )

    # ── Test G: Malformed JSON ───────────────────────────────────────────
    try:
        _parse_groq_response("NOT VALID JSON {{{")
        _report("Test G – Malformed JSON raises error", False, "No exception raised")
    except (json.JSONDecodeError, ValueError):
        _report("Test G – Malformed JSON raises error", True)


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  RUNNER                                                                  ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

def main() -> int:
    print(f"\n{BOLD}{'=' * 60}")
    print(f"  SENTINEL – Scoring Sanity Checker")
    print(f"{'=' * 60}{RESET}")

    try:
        test_url_scoring()
        test_groq_parser()
    except Exception:
        print(f"\n{RED}{BOLD}FATAL: Unhandled exception during tests{RESET}")
        traceback.print_exc()
        return 1

    # ── Summary ──────────────────────────────────────────────────────────
    total = _passed + _failed
    print(f"\n{BOLD}{'─' * 60}{RESET}")
    print(f"  Results: {GREEN}{_passed} passed{RESET}, {RED}{_failed} failed{RESET} / {total} total")

    if _failed == 0:
        print(f"\n  {GREEN}{BOLD}ALL SYSTEMS NOMINAL. SCORING MATH IS PERFECT.{RESET}\n")
        return 0
    else:
        print(f"\n  {RED}{BOLD}REGRESSIONS DETECTED — FIX BEFORE SHIPPING.{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
