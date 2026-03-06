"""
Sentinel VT-like Unified Report Schema
=======================================
Defines the canonical ``report.json`` structure produced by every analysis
run (static-only OR static + VMware sandbox).  Both the Scan Tool QML page
and the AI explainer consume this schema.

All fields use **snake_case** keys for consistency with the Python codebase.
The schema version is ``"2.0"`` to distinguish from the camelCase ``1.0``
schema in ``app/sandbox/report_schema.py``.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, NotRequired, TypedDict

# ── Sub-structures ────────────────────────────────────────────────────────────


class JobInfo(TypedDict):
    id: str
    started_at: str
    finished_at: str
    duration_sec: float
    mode: str  # "static" | "sandbox" | "url"


class FileInfo(TypedDict):
    path: str
    name: str
    size_bytes: int
    extension: str
    file_type: str  # magic-detected (e.g. "PE32 executable")
    sha256: str
    sha1: str
    md5: str
    signed: bool | None  # True=verified, False=invalid, None=unknown/no signtool
    publisher: NotRequired[str | None]


class EngineResult(TypedDict):
    name: str
    version: NotRequired[str]
    status: str  # "clean" | "suspicious" | "malicious" | "error" | "not_installed"
    details: str
    confidence: int  # 0-100


class StaticSection(TypedDict):
    entropy: float
    top_strings: list[str]
    pe_analyzed: bool
    suspicious_imports: list[str]
    yara_matches: list[str]
    engines: list[EngineResult]


class ProcessEntry(TypedDict, total=False):
    pid: int
    name: str
    cmdline: str
    parent: str


class NetworkAttempt(TypedDict, total=False):
    proto: str
    remote_addr: str
    remote_port: int
    pid: int


class SandboxSection(TypedDict):
    mode: str  # "run" | "inspect" | "extract" | "static_only"
    executed: bool
    duration_sec: NotRequired[float]
    processes_started: list[ProcessEntry]
    files_created: list[str]
    files_modified: list[str]
    registry_modified: list[str]
    network_attempts: list[NetworkAttempt]
    dns_queries: list[str]
    alerts: list[str]
    errors: list[str]
    highlights: list[str]


class IocSection(TypedDict):
    ips: list[str]
    domains: list[str]
    urls: list[str]
    file_paths: list[str]
    registry_keys: list[str]
    hashes: list[str]


class VerdictSection(TypedDict):
    risk: str  # "Low" | "Medium" | "High" | "Critical"
    score: int  # 0-100
    confidence: int  # 0-100
    label: str  # "Clean" | "Suspicious" | "Malicious" | "Inconclusive"
    reasons: list[str]


class SentinelReport(TypedDict):
    """
    Full VirusTotal-style analysis report.

    Saved as ``data/reports/<job_id>/report.json`` on the host.
    """

    schema_version: str  # "2.0"
    job: JobInfo
    file: FileInfo
    static: StaticSection
    sandbox: SandboxSection
    iocs: IocSection
    verdict: VerdictSection
    recommendations: list[str]
    ai_explanation: NotRequired[dict[str, Any] | None]


# ── Risk / label helpers ──────────────────────────────────────────────────────


def score_to_risk(score: int) -> str:
    """Map 0-100 score to Low/Medium/High/Critical."""
    if score >= 80:
        return "Critical"
    if score >= 60:
        return "High"
    if score >= 25:
        return "Medium"
    return "Low"


def score_to_label(score: int) -> str:
    if score >= 60:
        return "Malicious"
    if score >= 25:
        return "Suspicious"
    if score > 0:
        return "Clean"
    return "Clean"


# ── Empty-report factory ──────────────────────────────────────────────────────


def build_empty_report(
    *,
    job_id: str = "",
    mode: str = "static",
) -> SentinelReport:
    """Return a zeroed-out SentinelReport ready to be filled in."""
    now = datetime.datetime.now().isoformat()
    return SentinelReport(
        schema_version="2.0",
        job=JobInfo(
            id=job_id or _new_job_id(),
            started_at=now,
            finished_at=now,
            duration_sec=0.0,
            mode=mode,
        ),
        file=FileInfo(
            path="",
            name="",
            size_bytes=0,
            extension="",
            file_type="",
            sha256="",
            sha1="",
            md5="",
            signed=None,
            publisher=None,
        ),
        static=StaticSection(
            entropy=0.0,
            top_strings=[],
            pe_analyzed=False,
            suspicious_imports=[],
            yara_matches=[],
            engines=[],
        ),
        sandbox=SandboxSection(
            mode="static_only",
            executed=False,
            processes_started=[],
            files_created=[],
            files_modified=[],
            registry_modified=[],
            network_attempts=[],
            dns_queries=[],
            alerts=[],
            errors=[],
            highlights=[],
        ),
        iocs=IocSection(
            ips=[],
            domains=[],
            urls=[],
            file_paths=[],
            registry_keys=[],
            hashes=[],
        ),
        verdict=VerdictSection(
            risk="Low",
            score=0,
            confidence=0,
            label="Clean",
            reasons=[],
        ),
        recommendations=[],
        ai_explanation=None,
    )


def _new_job_id() -> str:
    return datetime.datetime.now().strftime("job_%Y%m%d_%H%M%S")


# ── Report persistence helpers ────────────────────────────────────────────────

_REPORTS_ROOT = Path("data") / "reports"
_LOGS_ROOT = Path("data") / "logs"


def report_dir(job_id: str) -> Path:
    d = _REPORTS_ROOT / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_report(report: SentinelReport, job_id: str | None = None) -> Path:
    """Serialize *report* to ``data/reports/<job_id>/report.json``."""
    import json

    jid = job_id or report["job"]["id"]
    out = report_dir(jid) / "report.json"
    with out.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    return out


def save_log(lines: list[str], job_id: str) -> Path:
    """Append text lines to ``data/logs/<job_id>.log``."""
    _LOGS_ROOT.mkdir(parents=True, exist_ok=True)
    out = _LOGS_ROOT / f"{job_id}.log"
    with out.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return out


def load_report(path: str | Path) -> SentinelReport:
    import json

    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ── Schema validation & normalization ─────────────────────────────────────────

_REQUIRED_TOP_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "job",
        "file",
        "static",
        "sandbox",
        "iocs",
        "verdict",
    }
)
_REQUIRED_STATIC_KEYS: frozenset[str] = frozenset(
    {
        "engines",
        "top_strings",
        "suspicious_imports",
        "yara_matches",
    }
)
_REQUIRED_SANDBOX_KEYS: frozenset[str] = frozenset(
    {
        "processes_started",
        "files_created",
        "files_modified",
        "registry_modified",
        "network_attempts",
        "dns_queries",
        "alerts",
        "errors",
        "highlights",
    }
)
_REQUIRED_IOC_KEYS: frozenset[str] = frozenset(
    {
        "ips",
        "domains",
        "urls",
        "file_paths",
        "registry_keys",
        "hashes",
    }
)
_REQUIRED_VERDICT_KEYS: frozenset[str] = frozenset(
    {
        "risk",
        "score",
        "confidence",
        "label",
        "reasons",
    }
)


def validate_report_v2(report: dict) -> tuple[bool, list[str]]:
    """Validate *report* against the v2 schema contract.

    Returns ``(True, [])`` on success, or ``(False, [error, ...])``
    listing every missing / wrong field.  Does **not** mutate the report.
    """
    errors: list[str] = []
    if not isinstance(report, dict):
        return False, ["report is not a dict"]

    sv = report.get("schema_version")
    if sv != "2.0":
        errors.append(f"schema_version expected '2.0', got {sv!r}")

    for k in _REQUIRED_TOP_KEYS:
        if k not in report:
            errors.append(f"missing top-level key: '{k}'")

    if isinstance(report.get("static"), dict):
        for k in _REQUIRED_STATIC_KEYS:
            if k not in report["static"]:
                errors.append(f"missing static.{k}")

    if isinstance(report.get("sandbox"), dict):
        for k in _REQUIRED_SANDBOX_KEYS:
            if k not in report["sandbox"]:
                errors.append(f"missing sandbox.{k}")

    if isinstance(report.get("iocs"), dict):
        for k in _REQUIRED_IOC_KEYS:
            if k not in report["iocs"]:
                errors.append(f"missing iocs.{k}")

    if isinstance(report.get("verdict"), dict):
        for k in _REQUIRED_VERDICT_KEYS:
            if k not in report["verdict"]:
                errors.append(f"missing verdict.{k}")

    return (len(errors) == 0, errors)


def normalize_report_v2(report: dict) -> dict:
    """Return a copy of *report* with every missing array / scalar key
    filled with safe defaults so QML bindings never hit *undefined*.

    The original dict is **not** mutated.
    If *report* is not a dict, a zeroed ``build_empty_report()`` is returned.
    """
    import copy

    if not isinstance(report, dict):
        return dict(build_empty_report())  # type: ignore[return-value]

    r: dict = copy.deepcopy(report)
    r.setdefault("schema_version", "2.0")
    r.setdefault("job", {})
    r.setdefault("file", {})
    r.setdefault("recommendations", [])
    r.setdefault("ai_explanation", None)

    # ── static ────────────────────────────────────────────────────────────────
    st: dict = r.setdefault("static", {})
    st.setdefault("entropy", 0.0)
    st.setdefault("top_strings", [])
    st.setdefault("pe_analyzed", False)
    st.setdefault("suspicious_imports", [])
    st.setdefault("yara_matches", [])
    st.setdefault("engines", [])

    # ── sandbox ───────────────────────────────────────────────────────────────
    sb: dict = r.setdefault("sandbox", {})
    sb.setdefault("mode", "static_only")
    sb.setdefault("executed", False)
    sb.setdefault("processes_started", [])
    sb.setdefault("files_created", [])
    sb.setdefault("files_modified", [])
    sb.setdefault("registry_modified", [])
    sb.setdefault("network_attempts", [])
    sb.setdefault("dns_queries", [])
    sb.setdefault("alerts", [])
    sb.setdefault("errors", [])
    sb.setdefault("highlights", [])

    # ── iocs ──────────────────────────────────────────────────────────────────
    ioc: dict = r.setdefault("iocs", {})
    ioc.setdefault("ips", [])
    ioc.setdefault("domains", [])
    ioc.setdefault("urls", [])
    ioc.setdefault("file_paths", [])
    ioc.setdefault("registry_keys", [])
    ioc.setdefault("hashes", [])

    # ── verdict ───────────────────────────────────────────────────────────────
    vd: dict = r.setdefault("verdict", {})
    vd.setdefault("risk", "Low")
    vd.setdefault("score", 0)
    vd.setdefault("confidence", 0)
    vd.setdefault("label", "Clean")
    vd.setdefault("reasons", [])

    return r
