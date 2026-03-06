"""Typed schemas for sandbox job/step data.

These TypedDicts define the contract between analyzer_dynamic, vmware_runner,
and artifacts modules so callers always get predictable keys.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict


class StepDict(TypedDict):
    """A single progress step in the pipeline timeline."""

    time: str  # HH:MM:SS
    status: str  # "Running" | "OK" | "Failed" | "Pending"
    message: str


class ProcessEntry(TypedDict, total=False):
    pid: int
    ppid: int
    name: str
    cmdline: str


class ConnectionEntry(TypedDict, total=False):
    proto: str
    local_addr: str
    remote_addr: str
    state: str
    pid: int


class FileEntry(TypedDict, total=False):
    path: str
    action: str  # "created" | "modified" | "deleted"


class GuestSummary(TypedDict, total=False):
    """summary.json written by guest_agent.ps1."""

    job_id: str
    sample_name: str
    executed: bool
    exit_code: NotRequired[int | None]
    duration_sec: float
    started_at: str
    finished_at: str
    new_processes: list[ProcessEntry]
    new_connections: list[ConnectionEntry]
    new_files: list[FileEntry]
    modified_files: list[FileEntry]
    errors: list[str]
    alerts: list[str]
    process_snapshot_before: list[ProcessEntry]
    process_snapshot_after: list[ProcessEntry]
    connection_snapshot: list[ConnectionEntry]


class StaticAnalysisResult(TypedDict, total=False):
    md5: str
    sha1: str
    sha256: str
    file_size: int
    file_type: str
    magic: str
    entropy: float
    strings_count: int
    strings_sample: list[str]
    defender_detected: bool
    defender_threat: str
    error: str


class SandboxJobResult(TypedDict, total=False):
    """Final structured result returned by analyzer_dynamic."""

    job_id: str
    sample_path: str
    sample_name: str
    success: bool
    error: str
    started_at: str
    finished_at: str
    run_dir: str

    # Analysis results
    static: StaticAnalysisResult
    dynamic: GuestSummary

    # Scoring
    verdict: str  # "Malicious" | "Suspicious" | "Inconclusive" | "Benign"
    score: int  # 0-100
    summary: str
    highlights: list[str]

    # Step log
    steps: list[StepDict]
