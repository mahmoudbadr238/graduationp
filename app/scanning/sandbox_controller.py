"""
Sandbox Controller - VMware Workstation Dynamic Analysis (Windows-only).

Orchestrates sandbox execution for behavioral analysis using VMware Workstation.
No VirtualBox, no Windows Sandbox, no Linux namespaces.

100% Local - No network required.

Setup:
- Set SANDBOX_VMRUN in .env (path to vmrun.exe)
- Set SANDBOX_VMX  in .env (path to .vmx file)
- See docs/sandbox_vmware.md for full VM and ISO setup guide.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Windows-only: suppress console windows for all subprocesses
_SUBPROCESS_FLAGS = 0x08000000  # CREATE_NO_WINDOW


@dataclass
class SandboxResult:
    """Result from VMware sandbox execution."""

    success: bool
    status: str  # completed | timeout | error | not_available | not_configured
    duration: int  # seconds

    # Behavioral data (populated when results are collected from guest)
    processes: list[dict[str, Any]] = field(default_factory=list)
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    registry_modified: list[str] = field(default_factory=list)
    network_connections: list[str] = field(default_factory=list)

    # Raw data
    raw_report: dict[str, Any] | None = None
    error: str | None = None


class SandboxController:
    """
    Controls dynamic sandbox execution via VMware Workstation.

    The VM must be pre-configured with:
    - A clean snapshot (see SANDBOX_SNAPSHOT env var)
    - A drop folder watched by the guest runner script
    - Guest credentials set via SANDBOX_GUEST_USER / SANDBOX_GUEST_PASS

    All execution happens inside the VM — samples never run on the host.
    Results are collected from SANDBOX_HOST_RESULTS_DIR after each run.
    """

    DEFAULT_TIMEOUT = 120  # seconds

    def __init__(self) -> None:
        from ..sandbox_vmware.config import load_sandbox_config
        from ..sandbox_vmware.vmrun_client import VmrunClient

        self._config = load_sandbox_config()
        self._client = VmrunClient(self._config)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """True when VMware is installed, VMX exists, and guest credentials are set."""
        return self._config.host_ready and self._config.guest_ready

    @property
    def available_methods(self) -> list[str]:
        """List of available sandbox methods for UI display."""
        if self._config.host_ready:
            return ["VMware Workstation"]
        return []

    def run_sample(
        self,
        file_path: str,
        timeout: int = DEFAULT_TIMEOUT,
        progress_cb: Any = None,
    ) -> SandboxResult:
        """
        Run a sample inside the VMware sandbox VM.

        Args:
            file_path: Absolute path to the file on the host.
            timeout:   Maximum execution time in seconds (default 120).
            progress_cb: Optional callable(step: int, message: str) for UI updates.

        Returns:
            SandboxResult with behavioral analysis data.
        """
        def _step(n: int, msg: str) -> None:
            logger.info("[Sandbox step %d/7] %s", n, msg)
            if callable(progress_cb):
                try:
                    progress_cb(n, msg)
                except Exception:
                    pass

        # Step 1 - Validate input
        _step(1, "Input validated")
        if not os.path.exists(file_path):
            return SandboxResult(
                success=False,
                status="error",
                duration=0,
                error=f"File not found: {file_path}",
            )

        # Step 2 - Check VMware availability
        _step(2, "VMware detected" if self._config.host_ready else "VMware NOT configured")
        if not self._config.host_ready:
            return SandboxResult(
                success=False,
                status="not_configured",
                duration=0,
                error=(
                    "VMware sandbox not configured. "
                    "Set SANDBOX_VMRUN and SANDBOX_VMX in your .env file. "
                    "See docs/sandbox_vmware.md for setup instructions."
                ),
            )
        if not self._config.guest_ready:
            return SandboxResult(
                success=False,
                status="not_configured",
                duration=0,
                error="VMware guest credentials not set. Set SANDBOX_GUEST_USER and SANDBOX_GUEST_PASS in .env.",
            )

        start_time = time.time()
        try:
            return self._run_in_vmware(file_path, timeout, _step, start_time)
        except Exception as exc:
            logger.exception("VMware sandbox unexpected error: %s", exc)
            return SandboxResult(
                success=False,
                status="error",
                duration=int(time.time() - start_time),
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Internal VMware execution
    # ------------------------------------------------------------------

    def _run_in_vmware(
        self,
        file_path: str,
        timeout: int,
        step_cb: Any,
        start_time: float,
    ) -> SandboxResult:
        """Run sample: revert snapshot -> start VM -> copy -> run -> collect -> stop."""
        from ..sandbox_vmware.vmrun_client import VmrunError

        # Step 3 - Revert + start VM
        step_cb(3, "VM started (reverting to clean snapshot...)")
        try:
            self._client.revert_to_snapshot()
            self._client.start_vm()
        except VmrunError as exc:
            return SandboxResult(
                success=False,
                status="error",
                duration=int(time.time() - start_time),
                error=f"VM start failed: {exc}",
            )

        boot_wait = min(30, max(10, timeout // 4))
        logger.info("Waiting %ds for VM to boot...", boot_wait)
        time.sleep(boot_wait)

        # Step 4 - Transfer sample to guest
        sample_name = os.path.basename(file_path)
        guest_path = self._config.guest_in_dir.rstrip("\\/") + "\\" + sample_name
        step_cb(4, f"Sample transferred to guest: {guest_path}")
        try:
            self._client.copy_file_to_guest(file_path, guest_path)
        except VmrunError as exc:
            self._safe_stop()
            return SandboxResult(
                success=False,
                status="error",
                duration=int(time.time() - start_time),
                error=f"File copy to guest failed: {exc}",
            )

        # Step 5 - Execute sample via guest runner script
        step_cb(5, "Execution monitored (running guest runner script...)")
        try:
            self._client.run_script_in_guest(
                self._config.guest_runner_path,
                f'-Sample "{guest_path}" -Timeout {timeout}',
                timeout=timeout + 60,
            )
        except VmrunError as exc:
            # Non-fatal: runner may have been killed by timeout or completed already
            logger.warning("Guest runner returned error (non-fatal): %s", exc)

        # Allow guest analysis to complete
        analysis_wait = min(timeout, 30)
        logger.info("Waiting %ds for guest analysis to complete...", analysis_wait)
        time.sleep(analysis_wait)

        # Step 6 - Collect results from host results dir
        step_cb(6, "Results collected from guest output folder")
        results = self._collect_results()

        # Step 7 - Stop VM and generate analysis
        step_cb(7, "Analysis generated - stopping VM")
        self._safe_stop()

        duration = int(time.time() - start_time)

        if results:
            return SandboxResult(
                success=True,
                status="completed",
                duration=duration,
                processes=results.get("processes", []),
                files_created=results.get("files_created", []),
                files_modified=results.get("files_modified", []),
                files_deleted=results.get("files_deleted", []),
                registry_modified=results.get("registry_modified", []),
                network_connections=results.get("network_connections", []),
                raw_report=results,
            )

        return SandboxResult(
            success=True,
            status="completed",
            duration=duration,
            error="No behavioral data collected from guest (check guest runner output).",
        )

    def _collect_results(self) -> dict[str, Any] | None:
        """Read the most recent JSON report from host_results_dir."""
        results_dir = self._config.host_results_dir
        if not results_dir.exists():
            logger.warning("Results directory not found: %s", results_dir)
            return None

        candidates = sorted(
            results_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for candidate in candidates:
            try:
                with open(candidate, encoding="utf-8") as fh:
                    data = json.load(fh)
                logger.info("Loaded sandbox report: %s", candidate.name)
                return data
            except Exception as exc:
                logger.debug("Skipping unreadable report %s: %s", candidate, exc)

        return None

    def _safe_stop(self) -> None:
        """Best-effort VM stop - never raises."""
        try:
            self._client.stop_vm()
        except Exception as exc:
            logger.debug("VM stop error (ignored): %s", exc)

    # ------------------------------------------------------------------
    # Setup guidance
    # ------------------------------------------------------------------

    def get_setup_instructions(self) -> str:
        """Return user-facing VMware sandbox setup instructions."""
        return (
            "# VMware Sandbox Setup\n\n"
            "## Requirements\n"
            "- VMware Workstation Pro/Player installed on Windows\n"
            "- Analysis VM (.vmx) with:\n"
            "  - C:\\Sandbox\\in\\   (sample drop folder)\n"
            "  - C:\\Sandbox\\out\\  (results folder)\n"
            "  - C:\\Sandbox\\run.ps1 (execution script)\n"
            '  - Snapshot named "Clean Base"\n\n'
            "## Configuration (.env)\n"
            "```\n"
            "SANDBOX_VMRUN=C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe\n"
            "SANDBOX_VMX=D:\\vm\\windows10\\Windows 10 x64.vmx\n"
            "SANDBOX_SNAPSHOT=Clean Base\n"
            "SANDBOX_GUEST_USER=sandbox\n"
            "SANDBOX_GUEST_PASS=sandbox\n"
            "SANDBOX_HOST_RESULTS_DIR=C:\\SentinelSandbox\\results\n"
            "SANDBOX_HOST_FRAMES_DIR=C:\\SentinelSandbox\\frames\n"
            "```\n\n"
            "## Full Guide\n"
            "See docs/sandbox_vmware.md\n"
        )


def get_sandbox_controller() -> SandboxController:
    """Get a SandboxController instance."""
    return SandboxController()
