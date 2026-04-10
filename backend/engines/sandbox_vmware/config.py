"""Configuration for VMware Sandbox Lab."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_VMRUN = r"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe"
DEFAULT_VMX = r"D:\vm\windows10\Windows 10 x64.vmx"
DEFAULT_SNAPSHOT = "Clean Base"
DEFAULT_GUEST_IN = r"C:\Sandbox\in"
DEFAULT_GUEST_OUT = r"C:\Sandbox\out"
DEFAULT_GUEST_RUNNER = r"C:\Sandbox\run.ps1"
DEFAULT_GUEST_OPEN_URL = r"C:\Sandbox\open_url.ps1"
DEFAULT_HOST_RESULTS = Path(r"C:\SentinelSandbox\results")
DEFAULT_HOST_FRAMES = Path(r"C:\SentinelSandbox\frames")


def _load_dotenv() -> None:
    """Load `.env` if python-dotenv is available."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path, override=False)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(slots=True)
class SandboxConfig:
    """Resolved Sandbox Lab settings."""

    vmrun_path: str
    vmx_path: str
    snapshot_name: str
    guest_user: str
    guest_pass: str
    guest_in_dir: str
    guest_out_dir: str
    guest_runner_path: str
    guest_open_url_path: str
    host_frames_dir: Path
    host_results_dir: Path
    frame_keep_count: int = 12
    capture_interval_ms: int = 500
    capture_enabled: bool = (
        True  # set SANDBOX_CAPTURE=0 to disable screenshots entirely
    )
    report_poll_seconds: int = 90

    @property
    def host_ready(self) -> bool:
        """Whether vmrun and VMX look configured on the host."""
        return Path(self.vmrun_path).exists() and Path(self.vmx_path).exists()

    @property
    def guest_ready(self) -> bool:
        """Whether guest credentials are available."""
        return bool(self.guest_user and self.guest_pass)

    def ensure_directories(self) -> None:
        """Ensure output directories exist."""
        self.host_frames_dir.mkdir(parents=True, exist_ok=True)
        self.host_results_dir.mkdir(parents=True, exist_ok=True)


def load_sandbox_config() -> SandboxConfig:
    """Load VMware sandbox settings from environment with safe defaults."""
    _load_dotenv()

    host_results_dir = Path(
        os.environ.get("SANDBOX_HOST_RESULTS_DIR", str(DEFAULT_HOST_RESULTS))
    )
    host_frames_dir = Path(
        os.environ.get("SANDBOX_HOST_FRAMES_DIR", str(DEFAULT_HOST_FRAMES))
    )

    config = SandboxConfig(
        vmrun_path=os.environ.get("SANDBOX_VMRUN", DEFAULT_VMRUN),
        vmx_path=os.environ.get("SANDBOX_VMX", DEFAULT_VMX),
        snapshot_name=os.environ.get("SANDBOX_SNAPSHOT", DEFAULT_SNAPSHOT),
        guest_user=os.environ.get("SANDBOX_GUEST_USER", "").strip(),
        guest_pass=os.environ.get("SANDBOX_GUEST_PASS", "").strip(),
        guest_in_dir=DEFAULT_GUEST_IN.rstrip("\\/"),
        guest_out_dir=DEFAULT_GUEST_OUT.rstrip("\\/"),
        guest_runner_path=DEFAULT_GUEST_RUNNER,
        guest_open_url_path=DEFAULT_GUEST_OPEN_URL,
        host_frames_dir=host_frames_dir,
        host_results_dir=host_results_dir,
        frame_keep_count=max(2, _env_int("SANDBOX_FRAME_KEEP", 12)),
        capture_interval_ms=max(400, _env_int("SANDBOX_CAPTURE_INTERVAL_MS", 500)),
        capture_enabled=os.environ.get("SANDBOX_CAPTURE", "1").strip()
        not in ("0", "false", "no"),
        report_poll_seconds=max(15, _env_int("SANDBOX_REPORT_POLL_SECONDS", 90)),
    )
    config.ensure_directories()
    return config
