"""Static analysis for sandbox pipeline.

Computes:
  - MD5 / SHA1 / SHA256 hashes
  - File size
  - Magic bytes (file type) via 'magic' if available, else fallback
  - PE detection (checks MZ header)
  - High-entropy string extraction
  - Optional Windows Defender scan (MpCmdRun.exe)
  - Optional YARA rules scan
  - Optional ClamAV scan

All operations are pure host-side and offline.

Public API:
  analyze_file(path)             -> StaticAnalysisResult  (legacy, Defender only)
  analyze_file_full(path)        -> (StaticAnalysisResult, list[EngineResult])
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import subprocess
from pathlib import Path

from .job_schema import StaticAnalysisResult

logger = logging.getLogger(__name__)

_MPCMDRUN_CANDIDATES = [
    r"C:\Program Files\Windows Defender\MpCmdRun.exe",
    r"C:\Program Files (x86)\Windows Defender\MpCmdRun.exe",
]

_PRINTABLE_PATTERN = re.compile(rb"[ -~]{6,}")


def _compute_hashes(path: Path) -> tuple[str, str, str]:
    """Return (md5, sha1, sha256) for a file."""
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            md5.update(chunk)
            sha1.update(chunk)
            sha256.update(chunk)
    return md5.hexdigest(), sha1.hexdigest(), sha256.hexdigest()


def _file_entropy(path: Path) -> float:
    """Compute Shannon entropy of the file data."""
    counts = [0] * 256
    total = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            for byte in chunk:
                counts[byte] += 1
                total += 1
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in counts:
        if count:
            p = count / total
            entropy -= p * math.log2(p)
    return round(entropy, 4)


def _magic_bytes(path: Path) -> str:
    """
    Detect file type from first 4 bytes (minimal magic detection).
    Falls back to python-magic if installed.
    """
    try:
        import magic  # type: ignore[import]

        return magic.from_file(str(path))
    except ImportError:
        pass

    with path.open("rb") as fh:
        header = fh.read(8)

    if header[:2] == b"MZ":
        return "PE executable (Windows)"
    if header[:4] == b"\x7fELF":
        return "ELF executable (Linux)"
    if header[:4] == b"PK\x03\x04":
        return "ZIP archive"
    if header[:4] in (b"\xd0\xcf\x11\xe0", b"\xd0\xcf"):
        return "Microsoft Office document (OLE)"
    if header[:4] == b"%PDF":
        return "PDF document"
    if header[:2] in (b"MZ", b"ZM"):
        return "DOS/PE executable"
    return "Unknown"


def _extract_strings(path: Path, max_count: int = 200) -> list[str]:
    """Extract printable ASCII strings of 6+ chars."""
    strings: list[str] = []
    try:
        with path.open("rb") as fh:
            data = fh.read(2 * 1024 * 1024)  # first 2 MB
        for match in _PRINTABLE_PATTERN.finditer(data):
            strings.append(match.group().decode("ascii", errors="replace"))
            if len(strings) >= max_count:
                break
    except OSError as exc:
        logger.warning("Could not extract strings from %s: %s", path, exc)
    return strings


def _run_defender_scan(path: Path) -> tuple[bool, str]:
    """
    Run Windows Defender command-line scan if available.
    Returns (detected: bool, threat_name: str).
    """
    mpcmdrun: str | None = None
    for candidate in _MPCMDRUN_CANDIDATES:
        if Path(candidate).exists():
            mpcmdrun = candidate
            break

    if not mpcmdrun:
        return False, ""

    try:
        result = subprocess.run(
            [mpcmdrun, "-Scan", "-ScanType", "3", "-File", str(path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        output = (result.stdout + result.stderr).lower()
        detected = (
            result.returncode == 2
            or "threat" in output
            or "found" in output
            or "detected" in output
        )
        threat = ""
        if detected:
            # Try to extract threat name from output
            for line in (result.stdout + result.stderr).splitlines():
                if "threat" in line.lower() or "found" in line.lower():
                    threat = line.strip()[:200]
                    break
        return detected, threat
    except subprocess.TimeoutExpired:
        logger.warning("Defender scan timed out for %s", path)
        return False, "scan timed out"
    except Exception as exc:
        logger.warning("Defender scan failed: %s", exc)
        return False, ""


def analyze_file(
    path: str | Path,
    *,
    run_defender: bool = True,
    extract_strings: bool = True,
) -> StaticAnalysisResult:
    """
    Perform static analysis on a file.

    Args:
        path: Path to the file.
        run_defender: Whether to invoke Windows Defender (MpCmdRun.exe).
        extract_strings: Whether to extract printable strings.

    Returns:
        StaticAnalysisResult TypedDict.
    """
    p = Path(path)
    result: StaticAnalysisResult = {}

    if not p.exists():
        result["error"] = f"File not found: {path}"
        return result

    try:
        result["file_size"] = p.stat().st_size
    except OSError as exc:
        result["error"] = str(exc)
        return result

    try:
        md5, sha1, sha256 = _compute_hashes(p)
        result["md5"] = md5
        result["sha1"] = sha1
        result["sha256"] = sha256
    except OSError as exc:
        result["error"] = f"Hashing failed: {exc}"
        return result

    try:
        result["magic"] = _magic_bytes(p)
        result["file_type"] = result["magic"]
    except Exception as exc:
        result["magic"] = "unknown"
        result["file_type"] = "unknown"
        logger.warning("Magic detection failed: %s", exc)

    try:
        result["entropy"] = _file_entropy(p)
    except Exception as exc:
        logger.warning("Entropy calculation failed: %s", exc)

    if extract_strings:
        try:
            strings = _extract_strings(p)
            result["strings_count"] = len(strings)
            result["strings_sample"] = strings[:50]
        except Exception as exc:
            logger.warning("String extraction failed: %s", exc)

    if run_defender:
        try:
            detected, threat = _run_defender_scan(p)
            result["defender_detected"] = detected
            result["defender_threat"] = threat
        except Exception as exc:
            logger.warning("Defender scan error: %s", exc)
            result["defender_detected"] = False
            result["defender_threat"] = ""

    return result


def analyze_file_full(
    path: str | Path,
    *,
    extract_strings: bool = True,
) -> tuple[StaticAnalysisResult, list]:
    """
    Full static analysis: hashes + entropy + strings + ALL engines.

    Returns:
        (StaticAnalysisResult, list[EngineResult])

    Engine results come from engines.run_all() which includes
    Windows Defender, YARA, and ClamAV.
    """
    from .engines import run_all as _run_all_engines  # avoid circular at module level

    static = analyze_file(path, run_defender=False, extract_strings=extract_strings)
    engine_results = _run_all_engines(Path(path))
    # Back-fill legacy defensive fields from Defender engine result
    for eng in engine_results:
        if eng["name"] == "WindowsDefender":
            static["defender_detected"] = eng["status"] == "malicious"
            static["defender_threat"] = (
                eng["details"] if eng["status"] == "malicious" else ""
            )
    return static, engine_results
