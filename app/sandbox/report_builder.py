"""Build the canonical SentinelReport from static + dynamic analysis results.

Called at the end of the pipeline:
    report = build_report(
        job_id=...,
        started_at=...,
        finished_at=...,
        sample_path=...,
        static_raw=...,      # StaticAnalysisResult from analyzer_static
        engine_results=...,  # list[EngineResult] from engines.run_all()
        guest_summary=...,   # GuestSummary dict from guest agent (may be None)
        host_job_dir=...,    # Path to local artifact directory
    )

The produced report is ALSO saved as ``<host_job_dir>/report.json`` and
``data/logs/sandbox_<job_id>.log``.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .report_schema import (
    EngineResult,
    FileInfo,
    IocSection,
    JobInfo,
    SandboxSection,
    SentinelReport,
    SignatureInfo,
    StaticSection,
    VerdictSection,
    score_to_risk,
)

logger = logging.getLogger(__name__)

# ── Signature detection (authenticode via signtool/sigcheck -best-effort) ─────


def _detect_signature(path: Path) -> SignatureInfo:
    """Try signtool.exe or PowerShell Get-AuthenticodeSignature."""
    # Approach 1: PowerShell
    try:
        proc = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonI",
                "-Command",
                f"$s=(Get-AuthenticodeSignature '{path}');"
                "$s | Select-Object Status,SignerCertificate | ConvertTo-Json -Compress",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout.strip())
            status = str(data.get("Status", "")).lower()
            cert = data.get("SignerCertificate") or {}
            subject = ""
            if isinstance(cert, dict):
                subject = cert.get("Subject", "") or ""
            publisher = None
            if subject:
                m = re.search(r"CN=([^,]+)", subject)
                publisher = m.group(1).strip() if m else subject[:80]
            present = "valid" in status or "trusted" in status
            return SignatureInfo(present=present, publisher=publisher or None)
    except Exception:
        pass
    return SignatureInfo(present=False, publisher=None)


# ── IOC extraction ────────────────────────────────────────────────────────────

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_DOMAIN_RE = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+(?:com|net|org|io|ru|cn|de|uk|info|biz|xyz|top|club|online|site)\b",
    re.I,
)
_REG_RE = re.compile(r"HKEY_[A-Z_]+\\[^\r\n\"\\<>|]+", re.I)

# IPs that are clearly benign (LAN / loopback / broadcast)
_SKIP_IPS = {"127.0.0.1", "0.0.0.0", "255.255.255.255"}
_SKIP_IP_PREFIXES = (
    "10.",
    "192.168.",
    "169.254.",
    "172.16.",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
    "172.21.",
    "172.22.",
    "172.23.",
    "172.24.",
    "172.25.",
    "172.26.",
    "172.27.",
    "172.28.",
    "172.29.",
    "172.30.",
    "172.31.",
)


def _extract_iocs(
    guest_summary: dict[str, Any] | None,
    engine_results: list[EngineResult],
    strings: list[str],
) -> IocSection:
    paths: set[str] = set()
    domains: set[str] = set()
    ips: set[str] = set()
    registry: set[str] = set()

    # From guest summary
    if guest_summary:
        for fe in guest_summary.get("new_files", []):
            p = fe.get("path") or fe.get("Path", "")
            if p:
                paths.add(p)
        for fe in guest_summary.get("modified_files", []):
            p = fe.get("path") or fe.get("Path", "")
            if p:
                paths.add(p)
        for conn in guest_summary.get("new_connections", []):
            remote = conn.get("remote_addr") or conn.get("RemoteAddress", "")
            if remote and ":" in remote:
                ip_part = remote.rsplit(":", 1)[0].strip("[]")
                if (
                    ip_part
                    and ip_part not in _SKIP_IPS
                    and not any(ip_part.startswith(pfx) for pfx in _SKIP_IP_PREFIXES)
                ):
                    ips.add(ip_part)

    # From strings (top 200 printable strings from the binary)
    blob = "\n".join(strings)
    for m in _IP_RE.finditer(blob):
        ip = m.group()
        if ip not in _SKIP_IPS and not any(
            ip.startswith(pfx) for pfx in _SKIP_IP_PREFIXES
        ):
            ips.add(ip)
    for m in _DOMAIN_RE.finditer(blob):
        domains.add(m.group().lower())
    for m in _REG_RE.finditer(blob):
        registry.add(m.group()[:200])

    return IocSection(
        paths=sorted(paths)[:50],
        domains=sorted(domains)[:50],
        ips=sorted(ips)[:50],
        registry=sorted(registry)[:30],
    )


# ── Verdict scoring ───────────────────────────────────────────────────────────

_ENGINE_WEIGHTS = {
    "malicious": 40,
    "suspicious": 15,
    "clean": 0,
    "error": 0,
    "not_installed": 0,
}


def _compute_verdict(
    engine_results: list[EngineResult],
    guest_summary: dict[str, Any] | None,
    iocs: IocSection,
) -> tuple[VerdictSection, list[str]]:
    score = 0
    reasons: list[str] = []
    recs: list[str] = []

    # Engine contribution
    for eng in engine_results:
        w = _ENGINE_WEIGHTS.get(eng["status"], 0)
        if w:
            score += w
            reasons.append(f"{eng['name']}: {eng['status']} — {eng['details'][:80]}")

    # Dynamic contribution
    if guest_summary:
        new_procs = len(guest_summary.get("new_processes", []))
        new_files = len(guest_summary.get("new_files", []))
        new_conns = len(guest_summary.get("new_connections", []))
        alerts = len(guest_summary.get("alerts", []))
        errors = len(guest_summary.get("errors", []))

        score += min(25, new_procs * 5)
        score += min(15, new_files * 2)
        score += min(20, new_conns * 4)
        score += min(20, alerts * 10)
        score += min(10, errors * 2)

        if new_procs:
            reasons.append(f"{new_procs} new process(es) spawned during detonation")
        if new_conns:
            reasons.append(f"{new_conns} outbound network connection(s) observed")
        if new_files:
            reasons.append(f"{new_files} file(s) created/modified")
        if alerts:
            reasons.append(f"{alerts} behavioral alert(s) from agent")

    # IOC contribution
    if iocs["ips"]:
        score += min(15, len(iocs["ips"]) * 3)
        reasons.append(f"{len(iocs['ips'])} external IP(s) referenced in file")
    if iocs["domains"]:
        score += min(10, len(iocs["domains"]) * 2)

    score = min(100, score)
    risk = score_to_risk(score)

    # Recommendations
    if score >= 60:
        recs = [
            "Do not open or run this file on any production system.",
            "Isolate the machine if the file was already executed.",
            "Submit to your security team for further analysis.",
            "Run a full system scan with an up-to-date antivirus.",
        ]
    elif score >= 25:
        recs = [
            "Be cautious — do not run this file unless you trust its source.",
            "Verify the file's origin and digital signature.",
            "Consider scanning with additional tools before use.",
        ]
    else:
        recs = [
            "No significant threats detected.",
            "Keep your system and antivirus definitions up to date.",
        ]

    if not guest_summary:
        recs.append(
            "Dynamic sandbox analysis was skipped or failed — results are static-only."
        )

    return (
        VerdictSection(risk=risk, confidence=min(score + 20, 100), reasons=reasons[:8]),
        recs,
    )


# ── Main builder ──────────────────────────────────────────────────────────────


def build_report(
    *,
    job_id: str,
    started_at: str,
    finished_at: str,
    sample_path: str,
    static_raw: dict[str, Any] | None,
    engine_results: list[EngineResult],
    guest_summary: dict[str, Any] | None,
    host_job_dir: Path,
    sandbox_mode: str = "run",
) -> SentinelReport:
    """Assemble the full SentinelReport and save report.json."""
    sample = Path(sample_path)
    started_dt = datetime.fromisoformat(started_at) if started_at else datetime.now(UTC)
    finished_dt = (
        datetime.fromisoformat(finished_at) if finished_at else datetime.now(UTC)
    )
    duration = (finished_dt - started_dt).total_seconds()

    static_raw = static_raw or {}
    strings_top: list[str] = static_raw.get("strings_sample", [])[:50]

    # Signature
    sig = _detect_signature(sample)

    # IOCs
    iocs = _extract_iocs(guest_summary, engine_results, strings_top)

    # Verdict
    verdict, recs = _compute_verdict(engine_results, guest_summary, iocs)

    # Sandbox section
    mode = sandbox_mode
    executed = bool(guest_summary and guest_summary.get("executed"))
    exit_code = (
        int(guest_summary["exit_code"])
        if (guest_summary and guest_summary.get("exit_code") is not None)
        else None
    )

    new_procs = guest_summary.get("new_processes", []) if guest_summary else []
    new_files = guest_summary.get("new_files", []) if guest_summary else []
    mod_files = guest_summary.get("modified_files", []) if guest_summary else []
    new_conns = guest_summary.get("new_connections", []) if guest_summary else []
    alerts = guest_summary.get("alerts", []) if guest_summary else []
    errors = guest_summary.get("errors", []) if guest_summary else []
    warnings = guest_summary.get("toolWarnings", []) if guest_summary else []

    report = SentinelReport(
        schemaVersion="1.0",
        job=JobInfo(
            id=job_id,
            startedAt=started_at,
            endedAt=finished_at,
            durationSec=round(duration, 1),
        ),
        file=FileInfo(
            path=str(sample),
            name=sample.name,
            sizeBytes=static_raw.get("file_size", 0),
            extension=sample.suffix.lower(),
            type=static_raw.get("file_type", "Unknown"),
            sha256=static_raw.get("sha256", ""),
            md5=static_raw.get("md5", ""),
            sha1=static_raw.get("sha1", ""),
        ),
        static=StaticSection(
            stringsTop=strings_top,
            entropy=float(static_raw.get("entropy", 0.0)),
            signature=sig,
            engines=engine_results,
        ),
        sandbox=SandboxSection(
            mode=mode,
            executed=executed,
            exitCode=exit_code,
            processes={"started": new_procs, "ended": []},
            files={"created": new_files, "modified": mod_files},
            network={"attempts": new_conns},
            events={"highlights": alerts},
            toolWarnings=warnings,
            errors=errors,
        ),
        iocs=iocs,
        verdict=verdict,
        recommendations=recs,
    )

    # ── Persist report.json ────────────────────────────────────────────────────
    report_path = host_job_dir / "report.json"
    try:
        with report_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, default=str)
        logger.info("report.json saved: %s", report_path)
    except OSError as exc:
        logger.error("Could not save report.json: %s", exc)

    # ── Persist structured log ─────────────────────────────────────────────────
    log_dir = Path("data") / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"sandbox_{job_id}.log"
    try:
        with log_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, default=str)
        logger.info("Sandbox log saved: %s", log_path)
    except OSError:
        pass

    return report
