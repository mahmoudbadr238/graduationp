"""VirusTotal-style final report schema.

Single canonical report.json produced by every analysis run.
Both the UI and AI explainer consume this schema.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict

# ── Sub-structures ─────────────────────────────────────────────────────────────


class JobInfo(TypedDict):
    id: str
    startedAt: str
    endedAt: str
    durationSec: float


class FileInfo(TypedDict):
    path: str
    name: str
    sizeBytes: int
    extension: str
    type: str  # magic-detected file type
    sha256: str
    md5: str
    sha1: str


class SignatureInfo(TypedDict):
    present: bool
    publisher: NotRequired[str | None]


class EngineResult(TypedDict):
    name: str
    status: str  # "clean" | "suspicious" | "malicious" | "error" | "not_installed"
    details: str


class StaticSection(TypedDict):
    stringsTop: list[str]  # top 50 printable strings
    entropy: float  # Shannon entropy
    signature: SignatureInfo
    engines: list[EngineResult]


class ProcessEntry(TypedDict, total=False):
    pid: int
    ppid: int
    name: str
    cmdline: str


class FileEventEntry(TypedDict, total=False):
    path: str
    action: str  # "created" | "modified" | "deleted"


class NetworkAttempt(TypedDict, total=False):
    proto: str
    localAddr: str
    remoteAddr: str
    state: str
    pid: int


class SandboxSection(TypedDict):
    mode: str  # "run" | "inspect" | "extract" | "skipped"
    executed: bool
    exitCode: NotRequired[int | None]
    processes: dict  # {"started": [...], "ended": [...]}
    files: dict  # {"created": [...], "modified": [...]}
    network: dict  # {"attempts": [...]}
    events: dict  # {"highlights": [...]}
    toolWarnings: list[str]
    errors: list[str]


class IocSection(TypedDict):
    paths: list[str]
    domains: list[str]
    ips: list[str]
    registry: list[str]


class VerdictSection(TypedDict):
    risk: str  # "Low" | "Medium" | "High"
    confidence: int  # 0-100
    reasons: list[str]


class SentinelReport(TypedDict):
    """Full VirusTotal-style analysis report.

    Saved as ``report.json`` in the job artifacts directory.
    """

    schemaVersion: str  # "1.0"
    job: JobInfo
    file: FileInfo
    static: StaticSection
    sandbox: SandboxSection
    iocs: IocSection
    verdict: VerdictSection
    recommendations: list[str]


# ── Risk mapping ───────────────────────────────────────────────────────────────


def score_to_risk(score: int) -> str:
    """Convert a 0-100 score to Low/Medium/High."""
    if score >= 60:
        return "High"
    if score >= 25:
        return "Medium"
    return "Low"


def build_empty_report() -> SentinelReport:
    """Return a zeroed-out report shell (useful for error paths)."""
    return SentinelReport(
        schemaVersion="1.0",
        job=JobInfo(id="", startedAt="", endedAt="", durationSec=0.0),
        file=FileInfo(
            path="",
            name="",
            sizeBytes=0,
            extension="",
            type="",
            sha256="",
            md5="",
            sha1="",
        ),
        static=StaticSection(
            stringsTop=[],
            entropy=0.0,
            signature=SignatureInfo(present=False, publisher=None),
            engines=[],
        ),
        sandbox=SandboxSection(
            mode="skipped",
            executed=False,
            exitCode=None,
            processes={"started": [], "ended": []},
            files={"created": [], "modified": []},
            network={"attempts": []},
            events={"highlights": []},
            toolWarnings=[],
            errors=[],
        ),
        iocs=IocSection(paths=[], domains=[], ips=[], registry=[]),
        verdict=VerdictSection(risk="Low", confidence=0, reasons=[]),
        recommendations=[],
    )
