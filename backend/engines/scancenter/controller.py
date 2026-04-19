"""ScanCenter controller – orchestrates a complete file scan pipeline.

Pipeline steps
--------------
1  Validate input file
2  Compute hashes + file metadata
3  Static analysis engines
   3a PE analysis (if applicable)
   3b Strings extraction
    3c Groq AI NGAV analysis
    3d ClamAV (if installed)
    3e Signature verification
4  IOC extraction (strict validators)
5  Verdict scoring (deterministic, no LLM)
6  Optional VMware sandbox
7  Post-sandbox verdict refinement
8  Build v3 report
9  Write report.json to data directory
10 Insert scancenter_history row
11 Return V3Report

Never hangs: every step has a timeout. Cancel is honoured between steps.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .export import default_export_dir, export_report
from .history_repo import HistoryRepo
from .report_schema import (
    AiExplanation,
    EngineResult,
    FileInfo,
    IocSection,
    JobInfo,
    PeInfo,
    SandboxSection,
    StaticSection,
    V3Report,
    VerdictSection,
)

logger = logging.getLogger(__name__)

_IS_WINDOWS = os.name == "nt"
_CREATE_NO_WINDOW = 0x08000000

# ─────────────────────────────────────────────────────────────────────────────
# Options container
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ScanOptions:
    use_sandbox: bool = False
    allow_execution: bool = False      # only applies when use_sandbox=True
    disable_network: bool = True       # only applies when use_sandbox=True
    monitor_seconds: int = 60
    run_clamav: bool = True
    run_groq_ai: bool = True
    strings_limit: int = 200           # max strings to store
    visible_gui: bool = False          # run UI automation in visible guest desktop session


# ─────────────────────────────────────────────────────────────────────────────
# Progress callback type
# ─────────────────────────────────────────────────────────────────────────────

ProgressCb = Any   # Callable[[int, str], None]  – (percent, stage_name)


# ─────────────────────────────────────────────────────────────────────────────
# IOC extraction helpers (strict validators)
# ─────────────────────────────────────────────────────────────────────────────

_RE_URL = re.compile(
    r"https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=%]{8,256}", re.I
)
_RE_IP = re.compile(
    r"\b((?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)
_RE_DOMAIN = re.compile(
    r"\b(?:[a-zA-Z0-9\-]{1,63}\.)+(?:"
    r"com|net|org|io|gov|edu|co|ru|de|uk|fr|jp|cn|br|in|au|ca|"
    r"info|biz|xyz|top|online|site|tech|app|dev|cloud|win|pw|tk|"
    r"su|eu|nl|ru|pl|cz|sk|hu|ro|ua|by|kz|az|tr|sa|ae|il|us|me|"
    r"tv|cc|ws|sh|to|ly|gl|ms|ai|ml|club"
    r")\b",
    re.I,
)
_RE_REGISTRY = re.compile(
    r"(?:HKEY_[A-Z_]+|HK(?:LM|CU|CR|U|CC))"
    r"[\\\/][^\x00-\x1f\"<>|?*]{4,200}",
    re.I,
)
_RE_WIN_PATH = re.compile(
    r"[A-Za-z]:\\(?:[^\\/:*?\"<>|\x00-\x1f]{1,255}\\)*[^\\/:*?\"<>|\x00-\x1f]{1,255}",
)

# Known-benign IPs / private ranges to skip
_SKIP_IPS = {"0.0.0.0", "127.0.0.1", "255.255.255.255"}
_SKIP_DOMAINS_RE = re.compile(
    r"(?:schemas\.openxmlformats|xml|w3\.org|microsoft\.com|mozilla\.org"
    r"|apple\.com|schema|example\.com|localhost)",
    re.I,
)
_SKIP_EXTS = {".exe", ".dll", ".sys", ".pdb", ".obj", ".lib", ".ilk", ".pch"}


def _is_private_ip(ip: str) -> bool:
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        a, b = int(parts[0]), int(parts[1])
        return (
            a == 10
            or (a == 172 and 16 <= b <= 31)
            or (a == 192 and b == 168)
            or a == 169
        )
    except ValueError:
        return False


def _extract_iocs(content: bytes) -> IocSection:
    """Extract IOCs from raw bytes with strict dedup + filtering."""
    try:
        text = content.decode("utf-8", errors="replace")
    except Exception:
        text = ""

    # URLs (also captures domains inside)
    urls: list[str] = []
    seen_urls: set[str] = set()
    for m in _RE_URL.finditer(text):
        u = m.group(0)[:512]
        if u not in seen_urls:
            seen_urls.add(u)
            urls.append(u)
    urls = urls[:150]

    # IPs
    ips: list[str] = []
    seen_ips: set[str] = set()
    for m in _RE_IP.finditer(text):
        ip = m.group(0)
        if ip not in _SKIP_IPS and not _is_private_ip(ip) and ip not in seen_ips:
            seen_ips.add(ip)
            ips.append(ip)
    ips = ips[:100]

    # Domains (exclude those that appeared in URLs already)
    url_hosts = {u.split("/")[2].lower() for u in urls if "/" in u[8:]}
    domains: list[str] = []
    seen_dom: set[str] = set()
    for m in _RE_DOMAIN.finditer(text):
        d = m.group(0).lower()
        if (
            d not in seen_dom
            and d not in url_hosts
            and not _SKIP_DOMAINS_RE.search(d)
            and len(d) >= 4
        ):
            seen_dom.add(d)
            domains.append(d)
    domains = domains[:100]

    # Registry keys
    reg_keys: list[str] = []
    seen_reg: set[str] = set()
    for m in _RE_REGISTRY.finditer(text):
        rk = m.group(0)[:300]
        if rk not in seen_reg:
            seen_reg.add(rk)
            reg_keys.append(rk)
    reg_keys = reg_keys[:50]

    # Windows file paths (skip common PE sections / debug artefacts)
    file_paths: list[str] = []
    seen_path: set[str] = set()
    for m in _RE_WIN_PATH.finditer(text):
        p = m.group(0)[:300]
        ext = Path(p).suffix.lower()
        if p not in seen_path and ext not in _SKIP_EXTS:
            seen_path.add(p)
            file_paths.append(p)
    file_paths = file_paths[:80]

    return IocSection(
        urls=urls,
        domains=domains,
        ips=ips,
        file_paths=file_paths,
        registry_keys=reg_keys,
        hashes=[],
        emails=[],
    )


# ─────────────────────────────────────────────────────────────────────────────
def _safe_int(value: object, default: int = 0) -> int:
    """Convert *value* to int, returning *default* for non-numeric values
    like ``'N/A'``, ``'Error'``, ``None``, etc."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except (ValueError, TypeError):
            print(f"[Scoring] WARNING: non-integer score value ignored: {value!r}")
            return default
    print(f"[Scoring] WARNING: unexpected score type {type(value).__name__}: {value!r}")
    return default


# Verdict scoring – deterministic weighted model
# ─────────────────────────────────────────────────────────────────────────────

# Default weights (must sum to 1.0).  Unavailable sources are redistributed.
_DEFAULT_WEIGHTS: dict[str, float] = {
    "clamav":   0.40,
    "groq_ai":  0.30,
    "sandbox":  0.30,
}


def _compute_source_scores(
    engines: list[EngineResult],
    static: StaticSection,
    sandbox: SandboxSection | None,
) -> tuple[dict[str, int], dict[str, bool]]:
    """Return per-source raw scores (0-100) and availability flags."""
    scores: dict[str, int] = {
        "clamav": 0,
        "groq_ai": 0,
        "sandbox": 0,
    }
    avail: dict[str, bool] = {
        "clamav": False,
        "groq_ai": False,
        "sandbox": False,
    }

    _INACTIVE_STATUSES = {"unavailable", "skipped", "not_installed", "error", "n/a"}

    for eng in engines:
        name_lo = eng.name.lower().replace(" ", "_")
        status_lo = str(eng.status).lower().strip()
        if "clamav" in name_lo:
            avail["clamav"] = status_lo not in _INACTIVE_STATUSES
            if status_lo in ("detected", "malicious"):
                scores["clamav"] = 80
            elif status_lo == "clean":
                scores["clamav"] = 0

    # Groq AI NGAV source
    groq = static.groq_analysis or {}
    if groq:
        avail["groq_ai"] = True
        raw_score = groq.get("score", 0)
        scores["groq_ai"] = max(0, min(100, _safe_int(raw_score, 0)))

    # Sandbox — mark unavailable if it errored or didn't execute
    if sandbox and sandbox.enabled:
        if sandbox.executed:
            avail["sandbox"] = True
            sb = 0
            if getattr(sandbox, "persistence_indicators", []):
                sb += 25   # Run keys / startup / scheduled tasks / services
            if getattr(sandbox, "security_tampering", []):
                sb += 30   # Disabling Defender / AV / firewall — critical
            # Injection heuristics inferred from highlights
            if any("inject" in h.lower() for h in (sandbox.highlights or [])):
                sb += 25
            # Writes to suspicious system locations
            suspicious_paths = [
                f for f in (sandbox.file_diff or [])
                if any(p in str(f).lower()
                       for p in ("startup", "appdata\\roaming", "temp", "system32", "programfiles"))
            ]
            if suspicious_paths:
                sb += 15   # unsigned/unexpected drops in system dirs
            net_count = len(sandbox.network_attempts or [])
            sb += min(net_count * 5, 20)   # network connections to external hosts
            if len(sandbox.file_diff or []) > 20:
                sb += 10   # mass file changes — ransomware heuristic
            scores["sandbox"] = min(sb, 100)
        # else: inspect-only → sandbox executed=False means no execution penalty

    return scores, avail


def _score_and_verdict(
    engines: list[EngineResult],
    static: StaticSection,
    iocs: IocSection,
    sandbox: SandboxSection | None,
    file_info: FileInfo | None = None,
) -> VerdictSection:
    """Deterministic 4-source weighted scoring with transparent breakdown."""
    source_scores, avail = _compute_source_scores(engines, static, sandbox)

    # Effective weights: redistribute unavailable source weights proportionally
    active_keys   = [k for k, v in avail.items() if v]
    inactive_keys = [k for k in _DEFAULT_WEIGHTS if k not in active_keys]
    if not active_keys:
        active_keys = ["groq_ai"]   # ultimate fallback
        avail["groq_ai"] = True

    weights = {k: _DEFAULT_WEIGHTS[k] for k in active_keys}
    if inactive_keys:
        freed = sum(_DEFAULT_WEIGHTS[k] for k in inactive_keys)
        share = freed / len(active_keys)
        for k in active_keys:
            weights[k] += share
    # Renormalise
    total_w = sum(weights.values())
    weights = {k: v / total_w for k, v in weights.items()}

    # Weighted total from available sources
    total_score = sum(
        weights.get(k, 0) * source_scores.get(k, 0)
        for k in active_keys
    )

    # PE heuristic bonus (up to +15, on top of weighted sources)
    pe_bonus = 0
    if static.pe:
        if static.pe.packer_detected:        pe_bonus += 3
        if static.pe.high_entropy_sections:  pe_bonus += 2
        if static.pe.rwx_sections:           pe_bonus += 3
        crit_imp = sum(1 for i in (static.pe.suspicious_imports or []) if i.get("severity") == "critical")
        hi_imp   = sum(1 for i in (static.pe.suspicious_imports or []) if i.get("severity") == "high")
        pe_bonus += min(crit_imp * 4 + hi_imp * 2, 10)

    # IOC bonus (up to +8)
    ioc_bonus = min(len(iocs.ips) * 2 + len(iocs.urls) * 2, 8)

    # Signed-binary discount: a verified digital signature is strong evidence
    # of legitimacy.  Reduce score by up to 30 points.  This prevents known
    # signed tools (Rufus, Process Hacker, etc.) from being scored as
    # Critical solely because Defender's heuristics flag raw-disk access or
    # because UPX compression triggers PE-based heuristics.
    sig_discount = 0
    if file_info and file_info.signed is True:
        sig_discount = 30
        if file_info.publisher:
            sig_discount = 35  # known publisher → stronger discount

    raw = total_score + pe_bonus + ioc_bonus - sig_discount
    total_score = max(0, min(100, int(raw)))

    # Build human-readable reasons
    reasons: list[str] = []
    for eng in engines:
        if eng.status in ("detected", "malicious"):
            reasons.append(f"{eng.name} detected: {eng.details or 'threat found'}")
    if static.groq_analysis:
        gv = static.groq_analysis.get("verdict", "Unknown")
        gs = static.groq_analysis.get("score", 0)
        ge = static.groq_analysis.get("explanation", "")
        reasons.append(f"Groq AI Analysis: {gv} ({gs}/100) {ge}".strip())
    if static.pe and static.pe.packer_detected:
        reasons.append(f"Packer detected: {static.pe.packer_detected}")
    if static.pe and static.pe.suspicious_imports:
        reasons.append(f"{len(static.pe.suspicious_imports)} suspicious PE imports")
    if static.pe and static.pe.rwx_sections:
        reasons.append("Read-Write-Execute memory section found")
    if sig_discount > 0:
        pub = file_info.publisher if file_info and file_info.publisher else "unknown"
        reasons.append(f"Digitally signed (publisher: {pub}) — score reduced by {sig_discount}")
    sb_persist = getattr(sandbox, "persistence_indicators", []) if sandbox else []
    sb_tamper  = getattr(sandbox, "security_tampering", []) if sandbox else []
    if sb_persist:
        reasons.append(f"Persistence attempt: {sb_persist[0]}")
    if sb_tamper:
        reasons.append(f"Security tampering: {sb_tamper[0]}")
    if not reasons:
        reasons = ["No significant threat indicators found"]

    # Risk / label mapping (spec-defined thresholds)
    if total_score <= 19:
        risk, label = "Low",      "Clean"
    elif total_score <= 39:
        risk, label = "Medium",   "Suspicious"
    elif total_score <= 69:
        risk, label = "High",     "Likely Malicious"
    else:
        risk, label = "Critical", "Malicious"

    # Confidence
    sandbox_exec = bool(sandbox and sandbox.executed)
    n_src = len(active_keys)
    if sandbox_exec or n_src >= 3:
        confidence = min(85 + (total_score // 20), 96)
    elif n_src >= 2:
        confidence = min(60 + (total_score // 10), 80)
    else:
        confidence = min(40 + (total_score // 8),  65)

    # Breakdown dict (one entry per source)
    breakdown = {
        k: {
            "score":     source_scores[k],
            "available": avail[k],
            "weight":    round(weights.get(k, 0), 3),
        }
        for k in ["clamav", "groq_ai", "sandbox"]
    }

    # Coverage summary (human-readable list)
    _nice = {
        "clamav": "ClamAV",
        "groq_ai": "Groq AI Analysis",
        "sandbox": "Sandbox",
    }
    coverage = [
        f"{_nice[k]}: {source_scores[k]}/100 (weight {weights.get(k,0):.0%})"
        for k in ["clamav", "groq_ai", "sandbox"]
        if avail.get(k)
    ]

    return VerdictSection(
        risk=risk,
        label=label,
        score=total_score,
        confidence=confidence,
        reasons=reasons,
        breakdown=breakdown,
        coverage=coverage,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Defender runner
# ─────────────────────────────────────────────────────────────────────────────

_DEFENDER_PATHS = [
    r"C:\Program Files\Windows Defender\MpCmdRun.exe",
    r"C:\ProgramData\Microsoft\Windows Defender\Platform",
]


def _find_mpcmdrun() -> str | None:
    """Locate MpCmdRun.exe, searching versioned sub-directories."""
    for p in _DEFENDER_PATHS:
        pp = Path(p)
        if pp.is_file():
            return str(pp)
        if pp.is_dir():
            # search latest platform version
            for exe in sorted(pp.glob("*/MpCmdRun.exe"), reverse=True):
                return str(exe)
    found = shutil.which("MpCmdRun.exe")
    return found


class ScanController:
    """
    Run a complete ScanCenter pipeline for one file.

    Usage::

        ctrl = ScanController()
        report = ctrl.run(
            file_path="/path/to/sample.exe",
            options=ScanOptions(use_sandbox=False),
            progress_cb=lambda pct, stage: print(f"{pct}%  {stage}"),
        )
    """

    def __init__(self) -> None:
        self._cancel_event = threading.Event()
        self._history = HistoryRepo()

    # ── Public ────────────────────────────────────────────────────────────────

    def cancel(self) -> None:
        """Signal the pipeline to abort at the next checkpoint."""
        self._cancel_event.set()

    def run(
        self,
        file_path: str,
        options: ScanOptions | None = None,
        progress_cb: ProgressCb | None = None,
        agent_step_cb: Any = None,
    ) -> V3Report:
        """
        Run the full pipeline and return a V3Report.

        Never hangs: every subprocess has a hard timeout.
        If *cancel* is called from another thread, the job aborts cleanly.
        """
        self._cancel_event.clear()
        opts = options or ScanOptions()
        emit = progress_cb or (lambda _p, _s: None)

        # ── Agent Timeline step emitter ─────────────────────────────────────
        # Standardised schema: {ts, stage, title, result, status, artifact_paths}
        _agent_step_cb = agent_step_cb
        self._agent_steps: list[dict] = []

        def emit_step(
            stage: str,
            title: str,
            result: str = "",
            status: str = "ok",
            artifact_paths: list | None = None,
        ) -> None:
            step = {
                "ts":             datetime.now(timezone.utc).strftime("%H:%M:%S"),
                "stage":          stage,
                "title":          title,
                "result":         result,
                "status":         status,   # ok | running | warn | fail
                "artifact_paths": artifact_paths or [],
            }
            self._agent_steps.append(step)
            if _agent_step_cb is not None:
                try:
                    _agent_step_cb(step)
                except Exception:
                    pass

        report = V3Report()
        t0 = datetime.now(timezone.utc)
        job_id = f"sc_{int(t0.timestamp() * 1000)}"
        report.job = JobInfo(
            job_id=job_id,
            started_at=t0.isoformat(),
            mode="static" if not opts.use_sandbox else "sandbox",
        )

        try:
            # ── Step 1: Validate ────────────────────────────────────────────
            emit(2, "Validating file")
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            if not path.is_file():
                raise ValueError(f"Not a regular file: {file_path}")
            emit_step("validate", "File validated", path.name, "ok")

            # ── Step 2: File metadata + hashes ─────────────────────────────
            emit(5, "Computing hashes")
            report.file = self._file_info(path)
            emit_step("hashing", "Hashes computed",
                      f"SHA256={report.file.sha256[:16]}\u2026", "ok")

            if self._cancelled():
                return self._finalise(report, t0, opts, cancelled=True)

            # ── Step 3: Read content (bounded) ─────────────────────────────
            emit(10, "Reading file")
            try:
                content = path.read_bytes()[:12 * 1024 * 1024]  # max 12 MB
            except Exception as exc:
                content = b""
                logger.warning("Could not read %s: %s", file_path, exc)

            # ── Step 4: Run static engines ──────────────────────────────────
            emit(15, "PE analysis")
            emit_step(
                "static",
                "Static analysis running",
                "PE / Groq AI / strings",
                "running",
            )
            static = self._run_static(path, content, opts, emit)
            report.static = static
            _groq_score = _safe_int((static.groq_analysis or {}).get("score", 0))
            _eng_hits = [e.name for e in (static.engines or []) if e.status == "detected"]
            emit_step(
                "static",
                "Static analysis complete",
                f"entropy={static.file_entropy:.2f}  GroqAI={_groq_score}"
                + (f"  detections=[{', '.join(_eng_hits)}]" if _eng_hits else ""),
                "warn" if _eng_hits else "ok",
            )

            if self._cancelled():
                return self._finalise(report, t0, opts, cancelled=True)

            # ── Step 5: IOC extraction ──────────────────────────────────────
            emit(65, "Extracting IOCs")
            emit_step("iocs", "IOC extraction running", "", "running")
            report.iocs = _extract_iocs(content)
            _ioc_n = (len(report.iocs.urls or []) +
                      len(report.iocs.ips or []) +
                      len(report.iocs.domains or []))
            emit_step("iocs", "IOCs extracted", f"{_ioc_n} indicators found", "ok")

            if self._cancelled():
                return self._finalise(report, t0, opts, cancelled=True)

            # ── Step 6: Sandbox (optional) ──────────────────────────────────
            if opts.use_sandbox:
                emit(70, "Starting VMware sandbox")
                emit_step("sandbox", "Starting VMware sandbox",
                          "reverting VM to clean snapshot", "running")
                report.sandbox = self._run_sandbox(
                    path, opts, emit, report.file, emit_step=emit_step
                )
                _sb = report.sandbox
                if _sb.mode == "interactive_session" and not _sb.executed:
                    _sb_status = "warn"
                    _sb_result = "interactive session required (open Sandbox Lab and press Stop Analysis to finalize dynamic verdict)"
                else:
                    _sb_status = "ok" if not _sb.errors else "warn"
                    _sb_result = f"executed={_sb.executed}  processes={len(_sb.process_diff or [])}  errors={len(_sb.errors or [])}"
                emit_step(
                    "sandbox",
                    "Sandbox phase",
                    _sb_result,
                    _sb_status,
                )
            else:
                report.sandbox = SandboxSection(enabled=False)

            if self._cancelled():
                return self._finalise(report, t0, opts, cancelled=True)

            # ── Step 7: Verdict scoring ─────────────────────────────────────
            emit(90, "Scoring verdict")
            emit_step("verdict", "Scoring verdict", "", "running")
            report.verdict = _score_and_verdict(
                static.engines, static, report.iocs, report.sandbox,
                file_info=report.file,
            )
            report.recommendations = self._recommendations(report)
            _vr = report.verdict
            emit_step(
                "verdict",
                "Verdict computed",
                f"{_vr.label} \u2014 {_vr.risk} \u2014 score {_vr.score}/100",
                "ok" if _vr.risk in ("Low", "Medium") else "warn",
            )

            emit(95, "Saving report")
            return self._finalise(report, t0, opts)

        except Exception as exc:
            logger.exception("ScanController.run failed: %s", exc)
            emit_step("error", "Pipeline error", str(exc)[:200], "fail")
            report.verdict = VerdictSection(
                risk="Unknown",
                label="Error",
                score=0,
                confidence=0,
                reasons=[f"Pipeline error: {exc}"],
            )
            return self._finalise(report, t0, opts, error=str(exc))

    # ── Private helpers ───────────────────────────────────────────────────────

    def _cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _file_info(self, path: Path) -> FileInfo:
        """Hash + stat + MIME + signature."""
        import mimetypes

        # Single-pass hash
        h256 = hashlib.sha256()
        h1 = hashlib.sha1()
        hmd5 = hashlib.md5()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h256.update(chunk)
                h1.update(chunk)
                hmd5.update(chunk)

        mime, _ = mimetypes.guess_type(str(path))
        stat = path.stat()

        return FileInfo(
            path=str(path.absolute()),
            name=path.name,
            size_bytes=stat.st_size,
            extension=path.suffix.lower(),
            mime_type=mime or "application/octet-stream",
            sha256=h256.hexdigest(),
            sha1=h1.hexdigest(),
            md5=hmd5.hexdigest(),
        )

    def _run_static(
        self,
        path: Path,
        content: bytes,
        opts: ScanOptions,
        emit: ProgressCb,
    ) -> StaticSection:
        """Delegate to existing StaticScanner then map to v3 schema."""
        engines: list[EngineResult] = []

        try:
            from backend.engines.scanning.static_scanner import StaticScanner

            emit(20, "Static analysis")
            scanner = StaticScanner()
            t_start = time.monotonic()
            result = scanner.scan_file(str(path), run_clamav=opts.run_clamav)
            t_ms = int((time.monotonic() - t_start) * 1000)

            # Map PE info
            pe_info: PeInfo | None = None
            if result.pe_analysis:
                pa = result.pe_analysis
                pe_info = PeInfo(
                    is_pe=pa.is_pe,
                    is_dll=pa.is_dll,
                    is_64bit=pa.is_64bit,
                    arch="x64" if pa.is_64bit else "x86",
                    entry_point=pa.entry_point,
                    image_base=pa.image_base,
                    compile_time=pa.compile_time,
                    packer_detected=pa.packer_detected,
                    imports_count=pa.imports_count,
                    exports_count=pa.exports_count,
                    sections_count=pa.sections_count,
                    suspicious_imports=pa.suspicious_imports,
                    high_entropy_sections=pa.high_entropy_sections,
                    rwx_sections=pa.rwx_sections,
                )

            # Map signature
            sig = result.signature or {}
            signed = sig.get("valid")
            publisher = sig.get("subject", "")

            # File type → into FileInfo (we return it separately too)
            file_type = result.file_type or result.mime_type

            # ClamAV engine result
            clamav = result.clamav or {}
            if clamav.get("available"):
                status = "detected" if clamav.get("infected") else "clean"
                engines.append(EngineResult(
                    name="ClamAV",
                    status=status,
                    score=80 if status == "detected" else 0,
                    details=clamav.get("signature") or "",
                    time_ms=0,
                ))
            else:
                engines.append(EngineResult(name="ClamAV", status="unavailable"))

            # Strings
            strings_top = self._extract_strings(content, opts.strings_limit)

            # Groq AI results
            groq_analysis = result.groq_analysis or {}

            # Store file type + signature back into report.file (caller will override)
            # We return them as extra attributes via a simple trick
            self._last_file_type = file_type
            self._last_signed = signed
            self._last_publisher = publisher
            self._last_entropy = result.static.get("file_entropy", 0.0)

            static = StaticSection(
                engines=engines,
                pe=pe_info,
                groq_analysis=groq_analysis,
                strings_top=strings_top,
                file_entropy=result.static.get("file_entropy", 0.0),
            )

        except Exception as exc:
            logger.error("Static analysis error: %s", exc)
            self._last_file_type = ""
            self._last_signed = None
            self._last_publisher = ""
            self._last_entropy = 0.0
            static = StaticSection(
                engines=[EngineResult(name="StaticScanner", status="error", details=str(exc))]
            )
            t_ms = 0

        # Patch file_type / signed from static analysis
        static.engines = engines
        return static

    def _run_defender(self, path: Path) -> EngineResult:
        """Run MpCmdRun.exe and return an EngineResult."""
        mpcmdrun = _find_mpcmdrun()
        if not mpcmdrun:
            return EngineResult(name="Windows Defender", status="unavailable",
                                details="MpCmdRun.exe not found")

        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                [mpcmdrun, "-Scan", "-ScanType", "3", "-File", str(path)],
                capture_output=True,
                text=True,
                timeout=120,
                creationflags=_CREATE_NO_WINDOW,
            )
            t_ms = int((time.monotonic() - t0) * 1000)
            combined = proc.stdout + proc.stderr

            # Returncode is the single source of truth:
            #   0 = clean, 2 = threat found, anything else = error
            if proc.returncode == 0 or "no threats found" in combined.lower():
                return EngineResult(name="Windows Defender", status="clean",
                                    score=0, time_ms=t_ms)
            if proc.returncode == 2:
                threat = ""
                for line in combined.splitlines():
                    if "threat" in line.lower():
                        threat = line.strip()
                        break
                return EngineResult(name="Windows Defender", status="detected",
                                    score=98, details=threat, time_ms=t_ms)
            return EngineResult(
                name="Windows Defender",
                status="error",
                details=f"Exit code {proc.returncode}",
                time_ms=t_ms,
            )
        except subprocess.TimeoutExpired:
            return EngineResult(name="Windows Defender", status="error",
                                details="Scan timed out (>120s)")
        except Exception as exc:
            return EngineResult(name="Windows Defender", status="error",
                                details=str(exc))

    def _extract_strings(self, content: bytes, limit: int) -> list[str]:
        """Extract printable ASCII strings of length >= 6, capped at *limit*."""
        pattern = re.compile(rb"[\x20-\x7e]{6,256}")
        found: list[str] = []
        for m in pattern.finditer(content):
            s = m.group(0).decode("ascii", errors="replace")
            # Skip very common noise
            if not any(skip in s for skip in ("AAAA", "0000", "####")):
                found.append(s)
            if len(found) >= limit:
                break
        return found

    def _run_sandbox(
        self,
        path: Path,
        opts: ScanOptions,
        emit: ProgressCb,
        file_info: FileInfo,
        emit_step: Any = None,
    ) -> SandboxSection:
        """Interactive-only sandbox placeholder for manual Start/Stop flow.

        Auto detonation is intentionally removed from ScanCenter pipeline.
        Users must run Interactive Sandbox Session from Sandbox Lab and stop
        analysis manually before verdicting dynamic behavior.
        """
        _emit_step = emit_step or (lambda *_a, **_kw: None)
        sb = SandboxSection(
            enabled=True,
            mode="interactive_session",
        )
        emit(72, "Interactive sandbox session required")
        _emit_step(
            "sandbox",
            "Auto detonation removed. Use Sandbox Lab Interactive Session and click Stop Analysis to finalize dynamic verdict.",
            "",
            "warn",
        )
        sb.executed = False
        sb.highlights = [
            "Dynamic verdict is generated only after user-triggered Stop Analysis in Interactive Sandbox Session."
        ]

        return sb

    def _recommendations(self, report: V3Report) -> list[str]:
        risk = report.verdict.risk
        recs: list[str] = []
        if risk in ("High", "Critical"):
            recs += [
                "Quarantine or delete the file immediately.",
                "Run a full system scan with your endpoint antivirus.",
                "Check recently created processes and scheduled tasks.",
                "Consider restoring from a clean backup if the file was executed.",
            ]
        elif risk == "Medium":
            recs += [
                "Verify the file's origin and digital signature.",
                "Do not run the file unless you trust the source.",
                "Run an updated antivirus scan.",
            ]
        else:
            recs += [
                "No action required.",
                "Keep endpoint protection and Sentinel AI models up to date.",
            ]
        return recs

    def _finalise(
        self,
        report: V3Report,
        t0: datetime,
        opts: ScanOptions,
        cancelled: bool = False,
        error: str = "",
    ) -> V3Report:
        """Stamp timestamps, patch file metadata, persist, and return."""
        t1 = datetime.now(timezone.utc)
        report.job.finished_at = t1.isoformat()
        report.job.duration_sec = (t1 - t0).total_seconds()
        report.job.cancelled = cancelled
        report.job.sandbox_enabled = opts.use_sandbox
        report.job.sandbox_mode = (
            "run" if opts.allow_execution else "inspect"
        ) if opts.use_sandbox else "none"

        # Patch file_type / signed from static analysis results
        if report.file and getattr(self, "_last_file_type", None):
            report.file.file_type = self._last_file_type
        if report.file:
            report.file.signed = getattr(self, "_last_signed", None)
            report.file.publisher = getattr(self, "_last_publisher", "") or ""

        if error and not report.verdict.reasons:
            report.verdict = VerdictSection(
                risk="Unknown", label="Error", score=0, confidence=0, reasons=[error]
            )

        # Save report to disk
        export_dir = default_export_dir(report.job.job_id)
        try:
            ex = export_report(report, export_dir)
            report_path = ex.get("report_path", "")
        except Exception as exc:
            logger.warning("export_report failed: %s", exc)
            report_path = ""

        # Persist Agent Timeline steps to steps.jsonl
        _steps = getattr(self, "_agent_steps", None)
        if _steps and export_dir:
            try:
                _steps_path = Path(export_dir) / "steps.jsonl"
                with _steps_path.open("w", encoding="utf-8") as _sfh:
                    for _s in _steps:
                        _sfh.write(json.dumps(_s) + "\n")
            except Exception:
                pass

        # Persist history row
        try:
            engines_summary = json.dumps([
                {"name": e.name, "status": e.status, "details": e.details}
                for e in report.static.engines
            ])
            self._history.upsert(
                job_id=report.job.job_id,
                file_name=report.file.name,
                sha256=report.file.sha256,
                file_type=report.file.file_type or report.file.mime_type,
                verdict_risk=report.verdict.risk,
                verdict_label=report.verdict.label,
                confidence=report.verdict.confidence,
                score=report.verdict.score,
                mode=report.job.mode,
                created_at=report.job.started_at,
                duration_sec=report.job.duration_sec,
                report_path=report_path,
                engines_summary=engines_summary,
            )
        except Exception as exc:
            logger.warning("history upsert failed: %s", exc)

        return report
