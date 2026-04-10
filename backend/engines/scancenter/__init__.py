"""ScanCenter – market-ready static + optional sandbox file analysis package.

Public API
----------
ScanController   – run a full scan job (static + optional VMware sandbox)
V3Report         – the canonical v3 report data-class
HistoryRepo      – read/write scan history from SQLite
export_report    – write report.json + artifacts.zip to a destination folder
explain_report   – call Groq to generate a plain-language AI explanation
"""

from .controller import ScanController
from .export import export_report
from .groq_explainer import explain_report
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
    VerdictSection,
    V3Report,
)

__all__ = [
    "ScanController",
    "V3Report",
    "JobInfo",
    "FileInfo",
    "EngineResult",
    "PeInfo",
    "StaticSection",
    "SandboxSection",
    "IocSection",
    "VerdictSection",
    "AiExplanation",
    "HistoryRepo",
    "export_report",
    "explain_report",
]
