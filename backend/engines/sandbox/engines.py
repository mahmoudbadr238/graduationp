"""Static analysis engine wrappers.

Each engine returns an EngineResult TypedDict:
  { "name": str, "status": "clean|suspicious|malicious|error|not_installed", "details": str }

Engines:
  run_defender(path)  – Windows Defender MpCmdRun.exe
    run_groq_ai(path)   – Groq AI NGAV metadata analysis (for executable samples)
  run_clamav(path)    – ClamAV clamscan.exe (optional)
  run_all(path)       – Run all engines, returns list[EngineResult]
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

from .report_schema import EngineResult
from backend.engines.scanning.static_scanner import StaticScanner

logger = logging.getLogger(__name__)

# Hide console windows on Windows for background subprocess calls
_SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW

# ── Windows Defender ──────────────────────────────────────────────────────────

_MPCMDRUN_CANDIDATES = [
    r"C:\Program Files\Windows Defender\MpCmdRun.exe",
    r"C:\Program Files (x86)\Windows Defender\MpCmdRun.exe",
    r"C:\ProgramData\Microsoft\Windows Defender\Platform",  # latest platform dir
]


def _find_mpcmdrun() -> str | None:
    for c in _MPCMDRUN_CANDIDATES:
        p = Path(c)
        if p.is_file():
            return str(p)
        # Walk platform dir for versioned sub-dirs
        if p.is_dir():
            for sub in sorted(p.iterdir(), reverse=True):  # newest first
                exe = sub / "MpCmdRun.exe"
                if exe.is_file():
                    return str(exe)
    return None


def run_defender(path: Path) -> EngineResult:
    """Run Windows Defender CLI scan."""
    mpcmdrun = _find_mpcmdrun()
    if not mpcmdrun:
        return EngineResult(
            name="WindowsDefender",
            status="not_installed",
            details="MpCmdRun.exe not found",
        )
    try:
        proc = subprocess.run(
            [mpcmdrun, "-Scan", "-ScanType", "3", "-File", str(path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            creationflags=_SUBPROCESS_FLAGS,
        )
        combined = proc.stdout + proc.stderr

        # Returncode is the single source of truth:
        #   0 = clean, 2 = threat found, anything else = error
        if proc.returncode == 0 or "no threats found" in combined.lower():
            return EngineResult(
                name="WindowsDefender", status="clean", details="No threats found"
            )

        if proc.returncode == 2:
            threat = ""
            for line in combined.splitlines():
                if "threat" in line.lower():
                    threat = line.strip()[:300]
                    break
            return EngineResult(
                name="WindowsDefender",
                status="malicious",
                details=threat or "Threat detected",
            )

        # Unknown exit code — error, not detection
        return EngineResult(
            name="WindowsDefender",
            status="error",
            details=f"Exit code {proc.returncode}: {combined[:200]}",
        )
    except subprocess.TimeoutExpired:
        return EngineResult(
            name="WindowsDefender", status="error", details="Scan timed out (120s)"
        )
    except Exception as exc:
        logger.warning("Defender scan error: %s", exc)
        return EngineResult(
            name="WindowsDefender", status="error", details=str(exc)[:200]
        )


# ── Groq AI NGAV ─────────────────────────────────────────────────────────────


def run_groq_ai(path: Path) -> EngineResult:
    """Run Groq AI metadata analysis for executable samples."""
    try:
        scanner = StaticScanner()
        result = scanner.scan_file(str(path))
        groq = result.groq_analysis or {}

        if not groq:
            return EngineResult(
                name="GroqAI",
                status="clean",
                details="No PE metadata AI analysis applicable",
            )

        score = int(groq.get("score", 0) or 0)
        verdict = str(groq.get("verdict", "Unknown")).lower()
        explanation = str(groq.get("explanation", "AI classification completed"))

        if score >= 70 or verdict == "malicious":
            status = "malicious"
        elif score >= 40 or verdict == "suspicious":
            status = "suspicious"
        else:
            status = "clean"

        return EngineResult(
            name="GroqAI",
            status=status,
            details=f"{verdict or 'unknown'} ({score}/100): {explanation[:120]}",
        )
    except Exception as exc:
        logger.warning("Groq AI analysis error: %s", exc)
        return EngineResult(name="GroqAI", status="error", details=str(exc)[:200])


# ── ClamAV ────────────────────────────────────────────────────────────────────


def _vt_clamav_fallback(path: Path) -> EngineResult | None:
    """Query VirusTotal for this file's hash and extract ClamAV's verdict.

    Returns an EngineResult with score 100 (malicious) or 0 (clean),
    or None if the lookup cannot be completed.  Every failure path prints
    a diagnostic line to stdout so silent failures are impossible.
    """
    import hashlib
    import os

    api_key = os.environ.get("VIRUSTOTAL_API_KEY", "").strip()
    if not api_key:
        print("[ClamAV-VT] ERROR: VIRUSTOTAL_API_KEY env var is empty or missing")
        return None

    try:
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception as exc:
        print(f"[ClamAV-VT] ERROR: Could not hash file {path}: {exc}")
        return None

    try:
        import requests
    except ImportError as exc:
        print(f"[ClamAV-VT] ERROR: 'requests' library not installed: {exc}")
        return None

    try:
        resp = requests.get(
            f"https://www.virustotal.com/api/v3/files/{sha256}",
            headers={
                "x-apikey": api_key,
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
            timeout=15,
        )
    except Exception as exc:
        print(f"[ClamAV-VT] ERROR: HTTP request failed: {exc}")
        return None

    if resp.status_code == 404:
        print(f"[ClamAV-VT] File not in VT database (SHA256={sha256[:16]}…)")
        return EngineResult(
            name="ClamAV",
            status="clean",
            details="Not in VirusTotal database (assumed clean)",
            score=0,
        )
    if resp.status_code != 200:
        print(f"[ClamAV-VT] ERROR: VT returned HTTP {resp.status_code}")
        return None

    try:
        body = resp.json()
    except Exception as exc:
        print(f"[ClamAV-VT] ERROR: Failed to parse JSON response: {exc}")
        return None

    data = body.get("data", {})
    attrs = data.get("attributes", {})
    results = attrs.get("last_analysis_results", {})

    if not isinstance(results, dict):
        print(f"[ClamAV-VT] ERROR: last_analysis_results is not a dict: {type(results)}")
        return None

    # Look for ClamAV specifically (exact key first, then case-insensitive)
    clamav_result = results.get("ClamAV")
    if not clamav_result:
        for engine_name, engine_data in results.items():
            if engine_name.lower() == "clamav":
                clamav_result = engine_data
                break

    if not clamav_result:
        # ClamAV not in VT results — use aggregate stats as proxy
        stats = attrs.get("last_analysis_stats", {})
        malicious = stats.get("malicious", 0)
        print(f"[ClamAV-VT] ClamAV engine absent from VT; aggregate malicious={malicious}")
        if isinstance(malicious, int) and malicious >= 5:
            return EngineResult(
                name="ClamAV",
                status="malicious",
                details=f"VirusTotal: {malicious} engines flagged (ClamAV engine N/A)",
                score=100,
            )
        return EngineResult(
            name="ClamAV",
            status="clean",
            details=f"VirusTotal: {malicious} detections (ClamAV engine N/A)",
            score=0,
        )

    # Parse ClamAV's specific result from VT
    if not isinstance(clamav_result, dict):
        print(f"[ClamAV-VT] ERROR: ClamAV result is not a dict: {type(clamav_result)}")
        return None

    category = str(clamav_result.get("category", "")).lower()
    vt_result_str = str(clamav_result.get("result") or "")

    print(f"[ClamAV-VT] ClamAV verdict: category={category!r}, result={vt_result_str!r}")

    if category in ("malicious", "suspicious") or vt_result_str:
        return EngineResult(
            name="ClamAV",
            status="malicious",
            details=f"VirusTotal/ClamAV: {vt_result_str or category}",
            score=100,
        )
    return EngineResult(
        name="ClamAV",
        status="clean",
        details="VirusTotal/ClamAV: No threats found",
        score=0,
    )


def run_clamav(path: Path) -> EngineResult:
    """Run clamscan if ClamAV is installed; fallback to VirusTotal ClamAV result."""
    clamscan = shutil.which("clamscan") or shutil.which("clamdscan")

    # ── Local ClamAV available: run it directly ──────────────────────────
    if clamscan:
        try:
            proc = subprocess.run(
                [clamscan, "--no-summary", str(path)],
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
                creationflags=_SUBPROCESS_FLAGS,
            )
            combined = proc.stdout + proc.stderr
            if proc.returncode == 1:
                threat = ""
                for line in combined.splitlines():
                    if "FOUND" in line:
                        threat = line.strip()[:300]
                        break
                return EngineResult(
                    name="ClamAV",
                    status="malicious",
                    details=threat or "Threat detected",
                )
            if proc.returncode == 2:
                return EngineResult(
                    name="ClamAV",
                    status="error",
                    details=combined.strip()[:200] or "ClamAV error",
                )
            return EngineResult(
                name="ClamAV", status="clean", details="No threats found"
            )
        except subprocess.TimeoutExpired:
            return EngineResult(
                name="ClamAV", status="error", details="Scan timed out (90s)"
            )
        except Exception as exc:
            print(f"[ClamAV] ERROR: Local scan crashed: {exc}")
            logger.warning("ClamAV error: %s", exc)
            return EngineResult(
                name="ClamAV", status="error", details=str(exc)[:200],
            )

    # ── Local ClamAV not installed ────────────────────────────────────────
    print("[ClamAV] clamscan / clamdscan not found on PATH")
    return EngineResult(
        name="ClamAV",
        status="not_installed",
        details="clamscan / clamdscan not found on this system",
    )


# ── Run all ───────────────────────────────────────────────────────────────────


def run_all(path: Path) -> list[EngineResult]:
    """Run all engines sequentially and return their results."""
    return [
        run_defender(path),
        run_groq_ai(path),
        run_clamav(path),
    ]
