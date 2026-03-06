"""ScanCenter v3 report schema – single source of truth for all scan data.

All fields carry sensible defaults so partial builds never raise KeyError.
Serialize with V3Report.to_dict() (returns a JSON-safe plain dict).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Sub-schemas
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class JobInfo:
    job_id: str = ""
    started_at: str = ""       # ISO-8601
    finished_at: str = ""      # ISO-8601
    duration_sec: float = 0.0
    mode: str = "static"       # "static" | "sandbox"
    cancelled: bool = False
    sandbox_enabled: bool = False
    sandbox_mode: str = "none"  # "none" | "inspect" | "run"


@dataclass
class FileInfo:
    path: str = ""
    name: str = ""
    size_bytes: int = 0
    extension: str = ""
    file_type: str = ""        # e.g. "PE32+ executable (64-bit)"
    sha256: str = ""
    sha1: str = ""
    md5: str = ""
    mime_type: str = ""
    signed: bool | None = None  # True=verified, False=invalid sig, None=unknown
    publisher: str = ""


@dataclass
class EngineResult:
    name: str = ""
    status: str = "unavailable"  # "clean"|"detected"|"error"|"unavailable"|"skipped"
    score: int = 0               # 0-100 engine-internal
    details: str = ""            # Threat name / error message
    time_ms: int = 0


@dataclass
class PeInfo:
    is_pe: bool = False
    is_dll: bool = False
    is_64bit: bool = False
    arch: str = ""
    entry_point: int = 0
    image_base: int = 0
    compile_time: str | None = None
    packer_detected: str | None = None
    imports_count: int = 0
    exports_count: int = 0
    sections_count: int = 0
    entropy: float = 0.0
    suspicious_imports: list[dict[str, Any]] = field(default_factory=list)
    high_entropy_sections: list[dict[str, Any]] = field(default_factory=list)
    rwx_sections: list[str] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class StaticSection:
    engines: list[EngineResult] = field(default_factory=list)
    pe: PeInfo | None = None
    yara_matches: list[dict[str, Any]] = field(default_factory=list)
    strings_top: list[str] = field(default_factory=list)
    file_entropy: float = 0.0


@dataclass
class SandboxSection:
    enabled: bool = False
    executed: bool = False
    mode: str = "inspect"    # "inspect" | "extract" | "run"
    duration_sec: float = 0.0
    exit_code: int | None = None
    process_diff: list[dict[str, Any]] = field(default_factory=list)
    file_diff: list[dict[str, Any]] = field(default_factory=list)
    registry_diff: list[dict[str, Any]] = field(default_factory=list)
    network_attempts: list[dict[str, Any]] = field(default_factory=list)
    dns_queries: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)
    screenshot_path: str = ""
    # Extended behavioral fields (populated by _run_sandbox)
    persistence_indicators: list[str] = field(default_factory=list)
    security_tampering: list[str] = field(default_factory=list)
    live_metrics: dict[str, Any] = field(default_factory=dict)
    # GUI automation fields
    automation_visible: bool = False
    uac_secure_desktop: int | None = None  # 0=ok, 1=blocker, None=unknown
    frames_dir: str = ""
    frames_paths: list[str] = field(default_factory=list)  # host-side key-frame paths
    ui_transcript_snippet: str = ""


@dataclass
class IocSection:
    urls: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    ips: list[str] = field(default_factory=list)
    file_paths: list[str] = field(default_factory=list)
    registry_keys: list[str] = field(default_factory=list)
    hashes: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (
            len(self.urls)
            + len(self.domains)
            + len(self.ips)
            + len(self.file_paths)
            + len(self.registry_keys)
            + len(self.hashes)
            + len(self.emails)
        )


@dataclass
class VerdictSection:
    risk: str = "Unknown"       # "Low"|"Medium"|"High"|"Critical"|"Unknown"
    confidence: int = 0         # 0-100
    score: int = 0              # 0-100
    label: str = "Unknown"      # "Clean"|"Suspicious"|"Likely Malicious"|"Malicious"
    reasons: list[str] = field(default_factory=list)
    # 4-source scoring breakdown
    breakdown: dict[str, Any] = field(default_factory=dict)
    coverage: list[str] = field(default_factory=list)


@dataclass
class AiExplanation:
    one_line_summary: str = ""
    risk_level: str = ""
    top_reasons: list[str] = field(default_factory=list)
    what_to_do: list[str] = field(default_factory=list)
    false_positive_note: str = ""
    executed_note: str = ""
    raw_response: str = ""      # full LLM output for debugging


# ─────────────────────────────────────────────────────────────────────────────
# Root document
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class V3Report:
    schema_version: str = "3.0"
    job: JobInfo = field(default_factory=JobInfo)
    file: FileInfo = field(default_factory=FileInfo)
    static: StaticSection = field(default_factory=StaticSection)
    sandbox: SandboxSection | None = None
    iocs: IocSection = field(default_factory=IocSection)
    verdict: VerdictSection = field(default_factory=VerdictSection)
    recommendations: list[str] = field(default_factory=list)
    ai_explanation: AiExplanation | None = None

    # ── Serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe plain dictionary (nested dataclasses are expanded)."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "V3Report":
        """Reconstruct from a plain dict (tolerant of missing/extra keys)."""
        report = cls()
        if not isinstance(data, dict):
            return report

        if "job" in data and isinstance(data["job"], dict):
            report.job = JobInfo(**{k: v for k, v in data["job"].items() if hasattr(JobInfo, k)})

        if "file" in data and isinstance(data["file"], dict):
            report.file = FileInfo(**{k: v for k, v in data["file"].items() if hasattr(FileInfo, k)})

        if "static" in data and isinstance(data["static"], dict):
            sd = data["static"]
            engines = [EngineResult(**{k: v for k, v in e.items() if hasattr(EngineResult, k)})
                       for e in sd.get("engines", []) if isinstance(e, dict)]
            pe_data = sd.get("pe")
            pe = None
            if isinstance(pe_data, dict):
                pe = PeInfo(**{k: v for k, v in pe_data.items() if hasattr(PeInfo, k)})
            report.static = StaticSection(
                engines=engines,
                pe=pe,
                yara_matches=sd.get("yara_matches", []),
                strings_top=sd.get("strings_top", []),
                file_entropy=float(sd.get("file_entropy", 0.0)),
            )

        if "sandbox" in data and isinstance(data["sandbox"], dict):
            sb = data["sandbox"]
            report.sandbox = SandboxSection(**{k: v for k, v in sb.items() if hasattr(SandboxSection, k)})

        if "iocs" in data and isinstance(data["iocs"], dict):
            ioc = data["iocs"]
            report.iocs = IocSection(**{k: v for k, v in ioc.items() if hasattr(IocSection, k)})

        if "verdict" in data and isinstance(data["verdict"], dict):
            vd = data["verdict"]
            report.verdict = VerdictSection(**{k: v for k, v in vd.items() if hasattr(VerdictSection, k)})

        report.recommendations = data.get("recommendations", [])
        report.schema_version = data.get("schema_version", "3.0")

        if "ai_explanation" in data and isinstance(data["ai_explanation"], dict):
            ae = data["ai_explanation"]
            report.ai_explanation = AiExplanation(**{k: v for k, v in ae.items() if hasattr(AiExplanation, k)})

        return report

    @classmethod
    def from_json(cls, json_str: str) -> "V3Report":
        try:
            return cls.from_dict(json.loads(json_str))
        except Exception:
            return cls()
