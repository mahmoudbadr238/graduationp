"""
Sentinel Static Scan Engine (VT-style)
=====================================
Unified static analysis pipeline.  Wraps the existing ``StaticScanner`` for
PE / ClamAV work, adds Windows Defender (MpCmdRun) and Groq AI NGAV support,
and produces ``FileInfo``, ``StaticSection``, and ``IocSection`` dicts ready to
be merged into a ``SentinelReport``.

Returns are plain TypedDicts — no PySide6 or Qt imports.
All operations are Windows-only; Linux/macOS paths are never tried.
"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .report_schema import EngineResult, FileInfo, IocSection, StaticSection

logger = logging.getLogger(__name__)

# Hide console windows on Windows for background subprocess calls
_SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW

# ── Helpers ───────────────────────────────────────────────────────────────────


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _detect_filetype(path: Path) -> str:
    """Best-effort file-type string without heavy dependencies."""
    header = b""
    try:
        with path.open("rb") as fh:
            header = fh.read(8)
    except OSError:
        return "unknown"

    sigs: list[tuple[bytes, str]] = [
        (b"MZ", "PE32 executable"),
        (b"\x7fELF", "ELF executable"),
        (b"PK\x03\x04", "ZIP archive"),
        (b"PK\x05\x06", "ZIP archive (empty)"),
        (b"Rar!", "RAR archive"),
        (b"7z\xbc\xaf", "7-Zip archive"),
        (b"%PDF", "PDF document"),
        (b"\xd0\xcf\x11\xe0", "OLE2 compound (Office/MSI)"),
        (b"\x89PNG", "PNG image"),
        (b"GIF8", "GIF image"),
        (b"\xff\xd8\xff", "JPEG image"),
    ]
    for sig, label in sigs:
        if header[: len(sig)] == sig:
            return label

    # Try python-magic if available
    try:
        import magic  # type: ignore[import]

        return magic.from_file(str(path))
    except Exception:
        pass

    return path.suffix.lstrip(".").upper() + " file" if path.suffix else "unknown"


def _file_signature(path: Path) -> tuple[bool, str | None]:
    """Return (is_signed, publisher) using PowerShell Get-AuthenticodeSignature."""
    if sys.platform != "win32":
        return False, None
    try:
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"$s=Get-AuthenticodeSignature '{path}'; "
            "$s.Status.ToString() + '|' + ($s.SignerCertificate.Subject ?? '')",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False,
                          creationflags=_SUBPROCESS_FLAGS)
        out = r.stdout.strip()
        if "|" in out:
            status, subject = out.split("|", 1)
            if status.strip().lower() == "valid":
                cn = re.search(r"CN=([^,]+)", subject)
                return True, cn.group(1) if cn else subject[:80]
    except Exception:
        pass
    return False, None


# ── Engine runners ─────────────────────────────────────────────────────────────


def _find_mpcmdrun() -> str | None:
    """Locate MpCmdRun.exe in the versioned Defender Platform directory."""
    base = Path(r"C:\ProgramData\Microsoft\Windows Defender\Platform")
    if not base.exists():
        return None
    for d in sorted(base.iterdir(), reverse=True):
        candidate = d / "MpCmdRun.exe"
        if candidate.exists():
            return str(candidate)
    # Fallback locations
    for fb in (
        r"C:\Program Files\Windows Defender\MpCmdRun.exe",
        r"C:\Program Files (x86)\Microsoft Security Client\MpCmdRun.exe",
    ):
        if Path(fb).exists():
            return fb
    return None


def run_defender(path: Path) -> EngineResult:
    """Scan with Windows Defender MpCmdRun. Returns EngineResult."""
    mpcmd = _find_mpcmdrun()
    if not mpcmd:
        return EngineResult(
            name="Windows Defender",
            status="not_installed",
            details="MpCmdRun.exe not found",
            confidence=0,
        )
    try:
        r = subprocess.run(
            [
                mpcmd,
                "-Scan",
                "-ScanType",
                "3",
                "-File",
                str(path),
                "-DisableRemediation",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            creationflags=_SUBPROCESS_FLAGS,
        )
        output = (r.stdout + r.stderr).strip()

        # Returncode is the single source of truth:
        #   0 = clean, 2 = threat found, anything else = error
        if r.returncode == 0 or "no threats found" in output.lower():
            return EngineResult(
                name="Windows Defender",
                status="clean",
                details="No threats found",
                confidence=95,
            )
        if r.returncode == 2:
            m = re.search(r"Threat\s+Name\s*:\s*(.+)", output, re.IGNORECASE)
            threat = m.group(1).strip() if m else "Threat detected"
            return EngineResult(
                name="Windows Defender",
                status="malicious",
                details=threat[:200],
                confidence=90,
            )
        return EngineResult(
            name="Windows Defender",
            status="error",
            details=output[:200] or f"exit {r.returncode}",
            confidence=0,
        )
    except subprocess.TimeoutExpired:
        return EngineResult(
            name="Windows Defender",
            status="error",
            details="Scan timed out (120 s)",
            confidence=0,
        )
    except Exception as exc:
        return EngineResult(
            name="Windows Defender",
            status="error",
            details=str(exc)[:200],
            confidence=0,
        )


def run_groq_ngav(path: Path) -> EngineResult:
    """Run Groq AI NGAV analysis on a PE file."""
    # Only meaningful if the file is a PE
    try:
        with path.open("rb") as fh:
            header = fh.read(2)
        if header != b"MZ":
            return EngineResult(
                name="Groq AI",
                status="clean",
                details="Not a PE file — skipped",
                confidence=0,
            )
    except Exception:
        return EngineResult(
            name="Groq AI", status="error", details="Cannot read file", confidence=0
        )

    try:
        from .static_scanner import StaticScanner

        scanner = StaticScanner()
        # Reuse the PE analysis + Groq NGAV from the static scanner
        pe_analysis = scanner._analyze_pe(path, path.read_bytes()[:10 * 1024 * 1024])
        ngav = scanner._run_groq_ngav(pe_analysis)

        if not ngav:
            return EngineResult(
                name="Groq AI",
                status="clean",
                details="NGAV unavailable (no API key or error)",
                confidence=0,
            )

        ngav_score = ngav.get("score", 0)
        ngav_verdict = ngav.get("verdict", "Unknown")
        ngav_explanation = ngav.get("explanation", "")

        if ngav_score >= 70:
            status = "suspicious"
        elif ngav_score >= 50:
            status = "suspicious"
        else:
            status = "clean"

        return EngineResult(
            name="Groq AI",
            status=status,
            details=f"{ngav_verdict}: {ngav_explanation}"[:200],
            confidence=ngav_score,
        )
    except ImportError:
        return EngineResult(
            name="Groq AI",
            status="not_installed",
            details="pefile or groq not installed",
            confidence=0,
        )
    except Exception as exc:
        return EngineResult(
            name="Groq AI", status="error", details=str(exc)[:200], confidence=0
        )


def run_clamav(path: Path) -> EngineResult:
    """Scan with ClamAV clamscan if present."""
    clamscan = shutil.which("clamscan") or shutil.which("clamdscan")
    if not clamscan:
        return EngineResult(
            name="ClamAV",
            status="not_installed",
            details="clamscan not in PATH",
            confidence=0,
        )
    try:
        r = subprocess.run(
            [clamscan, "--no-summary", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            creationflags=_SUBPROCESS_FLAGS,
        )
        output = (r.stdout + r.stderr).strip()
        if r.returncode == 1:
            m = re.search(r": (.+) FOUND", output)
            threat = m.group(1) if m else "Threat found"
            return EngineResult(
                name="ClamAV", status="malicious", details=threat[:200], confidence=85
            )
        if r.returncode == 0:
            return EngineResult(
                name="ClamAV", status="clean", details="OK", confidence=80
            )
        return EngineResult(
            name="ClamAV", status="error", details=output[:200], confidence=0
        )
    except subprocess.TimeoutExpired:
        return EngineResult(
            name="ClamAV", status="error", details="Scan timed out (60 s)", confidence=0
        )
    except Exception as exc:
        return EngineResult(
            name="ClamAV", status="error", details=str(exc)[:200], confidence=0
        )


def run_all_engines(path: Path) -> list[EngineResult]:
    """Run Defender, Groq AI, ClamAV in sequence. Never raises."""
    results: list[EngineResult] = []
    for runner in (run_defender, run_groq_ngav, run_clamav):
        try:
            results.append(runner(path))
        except Exception as exc:
            results.append(
                EngineResult(
                    name=runner.__name__,
                    status="error",
                    details=str(exc)[:200],
                    confidence=0,
                )
            )
    return results


# ── IOC extraction ────────────────────────────────────────────────────────────

_IP_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)
_DOMAIN_RE = re.compile(
    r"\b(?:[a-zA-Z0-9-]{1,63}\.)+(?:com|net|org|info|io|ru|cn|de|uk|fr|biz|xyz|top|tk|ml)\b",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s\"'<>]{4,200}", re.IGNORECASE)
_REG_RE = re.compile(
    r"(HKEY_[A-Z_]+|HKCU|HKLM|HKU|HKCC|HKCR)\\[^\x00-\x1f\"'\\<>|]{1,200}",
    re.IGNORECASE,
)

_PRIVATE_IP = re.compile(
    r"^(10\.|127\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|0\.0\.0\.0|255\.)"
)


def _extract_iocs(path: Path, strings: list[str]) -> IocSection:
    blob = " ".join(strings)
    ips = [ip for ip in set(_IP_RE.findall(blob)) if not _PRIVATE_IP.match(ip)][:30]
    domains = [
        d
        for d in set(_DOMAIN_RE.findall(blob))
        if not any(c.isdigit() for c in d.split(".")[0])
    ][:30]
    urls = list({m.group() for m in _URL_RE.finditer(blob)})[:20]
    registry = list({m.group() for m in _REG_RE.finditer(blob)})[:30]
    return IocSection(
        ips=sorted(ips),
        domains=sorted(domains),
        urls=sorted(urls),
        file_paths=[],
        registry_keys=sorted(registry),
        hashes=[],
    )


# ── Main entry point ──────────────────────────────────────────────────────────


def scan_file(
    file_path: str | Path,
    *,
    run_engines: bool = True,
    extract_strings: bool = True,
    top_strings: int = 50,
) -> tuple[FileInfo, StaticSection, IocSection, list[EngineResult]]:
    """
    Run the full static analysis on *file_path*.

    Returns
    -------
    (file_info, static_section, ioc_section, engine_results)

    All return types are plain dicts compatible with ``SentinelReport``.
    Raises ``FileNotFoundError`` if the file does not exist.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # ── Hashes & file metadata ────────────────────────────────────────────
    file_type = _detect_filetype(path)
    signed, publisher = _file_signature(path)
    file_info = FileInfo(
        path=str(path),
        name=path.name,
        size_bytes=path.stat().st_size,
        extension=path.suffix.lower().lstrip("."),
        file_type=file_type,
        sha256=_sha256(path),
        sha1=_sha1(path),
        md5=_md5(path),
        signed=signed,
        publisher=publisher,
    )

    # ── Delegate heavy analysis to existing StaticScanner ─────────────────
    raw_static: dict[str, Any] = {}
    top_str_list: list[str] = []
    entropy_val: float = 0.0
    pe_analyzed = False
    suspicious_imports: list[str] = []
    groq_analysis: dict[str, Any] = {}

    try:
        from .static_scanner import StaticScanner

        scanner = StaticScanner()
        result = scanner.scan_file(str(path), run_clamav=False)
        raw_static = (
            result.to_dict()
            if hasattr(result, "to_dict")
            else (asdict(result) if is_dataclass(result) else {})
        )
        # Strings
        str_list: list[str] = (
            raw_static.get("strings")
            or (raw_static.get("static") or {}).get("printable_strings")
            or []
        )
        top_str_list = [s for s in str_list if isinstance(s, str)][:top_strings]
        # Entropy
        entropy_val = float(
            (raw_static.get("static") or {}).get("entropy")
            or raw_static.get("entropy")
            or 0
        )
        # PE
        pe_data = raw_static.get("pe_analysis") or {}
        pe_analyzed = bool(pe_data)
        suspicious_imports = list(pe_data.get("suspicious_imports") or [])
        # Groq NGAV from scanner
        groq_analysis = raw_static.get("groq_analysis") or {}
    except Exception as exc:
        logger.warning("StaticScanner failed (continuing): %s", exc)

    # ── Additional engine runs ─────────────────────────────────────────────
    engine_results: list[EngineResult] = []
    if run_engines:
        engine_results = run_all_engines(path)

    # ── IOC extraction from strings ────────────────────────────────────────
    ioc_section = _extract_iocs(path, top_str_list)

    static_section = StaticSection(
        entropy=round(entropy_val, 4),
        top_strings=top_str_list[:top_strings],
        pe_analyzed=pe_analyzed,
        suspicious_imports=suspicious_imports[:50],
        groq_analysis=groq_analysis,
        engines=engine_results,
    )

    return file_info, static_section, ioc_section, engine_results
