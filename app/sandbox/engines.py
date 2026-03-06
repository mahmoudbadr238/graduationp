"""Static analysis engine wrappers.

Each engine returns an EngineResult TypedDict:
  { "name": str, "status": "clean|suspicious|malicious|error|not_installed", "details": str }

Engines:
  run_defender(path)  – Windows Defender MpCmdRun.exe
  run_yara(path)      – YARA rules folder (optional; silently returns not_installed if absent)
  run_clamav(path)    – ClamAV clamscan.exe (optional)
  run_all(path)       – Run all engines, returns list[EngineResult]
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from .report_schema import EngineResult

logger = logging.getLogger(__name__)

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
        )
        combined = proc.stdout + proc.stderr
        lower = combined.lower()
        if (
            proc.returncode == 2
            or "threat" in lower
            or "found" in lower
            or "detected" in lower
        ):
            threat = ""
            for line in combined.splitlines():
                if any(w in line.lower() for w in ("threat", "found", "detected")):
                    threat = line.strip()[:300]
                    break
            return EngineResult(
                name="WindowsDefender",
                status="malicious",
                details=threat or "Threat detected",
            )
        return EngineResult(
            name="WindowsDefender", status="clean", details="No threats found"
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


# ── YARA ──────────────────────────────────────────────────────────────────────

_YARA_RULES_CANDIDATES = [
    Path(__file__).parent.parent.parent / "rules",  # <repo>/rules/
    Path(__file__).parent.parent.parent / "data" / "yara",
]


def _find_yara_rules() -> Path | None:
    for d in _YARA_RULES_CANDIDATES:
        if d.is_dir():
            return d
    return None


def run_yara(path: Path) -> EngineResult:
    """Run YARA rules if yara-python is installed and rules folder exists."""
    rules_dir = _find_yara_rules()
    if not rules_dir:
        return EngineResult(
            name="YARA",
            status="not_installed",
            details="No rules folder found (place .yar files in <repo>/rules/)",
        )
    try:
        import yara  # type: ignore[import]
    except ImportError:
        return EngineResult(
            name="YARA", status="not_installed", details="yara-python not installed"
        )

    rule_files = list(rules_dir.glob("*.yar")) + list(rules_dir.glob("*.yara"))
    if not rule_files:
        return EngineResult(
            name="YARA",
            status="not_installed",
            details="No .yar rule files in rules folder",
        )

    try:
        filepaths = {rf.stem: str(rf) for rf in rule_files}
        compiled = yara.compile(filepaths=filepaths)
        matches = compiled.match(str(path), timeout=30)
        if matches:
            names = ", ".join(m.rule for m in matches[:10])
            return EngineResult(
                name="YARA",
                status="suspicious",
                details=f"Matched: {names}",
            )
        return EngineResult(
            name="YARA",
            status="clean",
            details=f"No match across {len(rule_files)} rule(s)",
        )
    except yara.TimeoutError:
        return EngineResult(name="YARA", status="error", details="YARA scan timed out")
    except Exception as exc:
        logger.warning("YARA error: %s", exc)
        return EngineResult(name="YARA", status="error", details=str(exc)[:200])


# ── ClamAV ────────────────────────────────────────────────────────────────────


def run_clamav(path: Path) -> EngineResult:
    """Run clamscan if ClamAV is installed."""
    clamscan = shutil.which("clamscan") or shutil.which("clamdscan")
    if not clamscan:
        return EngineResult(
            name="ClamAV", status="not_installed", details="clamscan not found in PATH"
        )
    try:
        proc = subprocess.run(
            [clamscan, "--no-summary", str(path)],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
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
        return EngineResult(name="ClamAV", status="clean", details="No threats found")
    except subprocess.TimeoutExpired:
        return EngineResult(
            name="ClamAV", status="error", details="Scan timed out (90s)"
        )
    except Exception as exc:
        logger.warning("ClamAV error: %s", exc)
        return EngineResult(name="ClamAV", status="error", details=str(exc)[:200])


# ── Run all ───────────────────────────────────────────────────────────────────


def run_all(path: Path) -> list[EngineResult]:
    """Run all engines sequentially and return their results."""
    return [
        run_defender(path),
        run_yara(path),
        run_clamav(path),
    ]
