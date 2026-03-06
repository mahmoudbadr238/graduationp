"""Thin wrapper around VMware vmrun.exe."""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from collections.abc import Iterable
from pathlib import Path

from .config import SandboxConfig

logger = logging.getLogger(__name__)


class VmrunError(RuntimeError):
    """Raised when vmrun returns an error."""


class VmrunClient:
    """Execute VMware Workstation automation commands safely."""

    def __init__(self, config: SandboxConfig):
        self._config = config

    def validate_host_requirements(self) -> None:
        """Validate host-side vmrun and VMX presence."""
        vmrun_path = Path(self._config.vmrun_path)
        if not vmrun_path.exists():
            raise VmrunError(
                "VMware Workstation vmrun.exe was not found. "
                f"Expected: {self._config.vmrun_path}"
            )

        vmx_path = Path(self._config.vmx_path)
        if not vmx_path.exists():
            raise VmrunError(
                f"Sandbox VMX file was not found. Expected: {self._config.vmx_path}"
            )

    def ensure_guest_credentials(self) -> None:
        """Validate guest credentials for guest operations."""
        if not self._config.guest_user or not self._config.guest_pass:
            raise VmrunError(
                "Sandbox guest credentials are missing. "
                "Set SANDBOX_GUEST_USER and SANDBOX_GUEST_PASS in .env."
            )

    def _run(
        self,
        args: list[str],
        *,
        guest_auth: bool = False,
        timeout: int = 120,
    ) -> subprocess.CompletedProcess[str]:
        self.validate_host_requirements()

        cmd = [self._config.vmrun_path, "-T", "ws"]
        if guest_auth:
            self.ensure_guest_credentials()
            cmd.extend(
                [
                    "-gu",
                    self._config.guest_user,
                    "-gp",
                    self._config.guest_pass,
                ]
            )
        cmd.extend(args)

        # Redact credentials for safe logging
        _log_cmd = [c if c not in (self._config.guest_pass,) else "***" for c in cmd]
        logger.debug("vmrun: %s", " ".join(_log_cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise VmrunError(
                "VMware Workstation vmrun.exe could not be launched. "
                f"Expected: {self._config.vmrun_path}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise VmrunError(
                f"vmrun timed out after {timeout}s while running: {args[0]}"
            ) from exc

        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or "").strip()
            message = stderr or f"vmrun failed with exit code {result.returncode}"
            lower_message = message.lower()
            if "authentication" in lower_message or "login" in lower_message:
                message = (
                    f"{message} Check SANDBOX_GUEST_USER / SANDBOX_GUEST_PASS "
                    "and confirm VMware Tools is installed in the guest."
                )
            logger.debug("vmrun failed (rc=%d): %s", result.returncode, message)
            raise VmrunError(message)
        return result

    def list_snapshots(self, timeout: int = 30) -> list[str]:
        """List VM snapshots."""
        result = self._run(["listSnapshots", self._config.vmx_path], timeout=timeout)
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if lines and lines[0].lower().startswith("total snapshots"):
            lines = lines[1:]
        return lines

    def revert_to_snapshot(self, timeout: int = 180) -> None:
        """Revert the VM to the configured snapshot."""
        try:
            self._run(
                [
                    "revertToSnapshot",
                    self._config.vmx_path,
                    self._config.snapshot_name,
                ],
                timeout=timeout,
            )
        except VmrunError as exc:
            suggestions = []
            try:
                snapshots = self.list_snapshots(timeout=45)
            except VmrunError:
                snapshots = []
            if snapshots:
                suggestions.append(f"Available snapshots: {', '.join(snapshots)}")
            suggestion_text = f" {' '.join(suggestions)}" if suggestions else ""
            raise VmrunError(
                f"Could not revert VM to snapshot '{self._config.snapshot_name}': {exc}.{suggestion_text}"
            ) from exc

    def start(self, *, nogui: bool = True, timeout: int = 180) -> None:
        """Start the VM."""
        args = ["start", self._config.vmx_path]
        if nogui:
            args.append("nogui")
        self._run(args, timeout=timeout)

    def stop(self, *, hard: bool = True, timeout: int = 90) -> None:
        """Stop the VM."""
        mode = "hard" if hard else "soft"
        self._run(["stop", self._config.vmx_path, mode], timeout=timeout)

    def copy_file_from_host_to_guest(
        self,
        host_path: str | Path,
        guest_path: str,
        *,
        timeout: int = 120,
    ) -> None:
        """Copy a file into the guest."""
        self._run(
            [
                "copyFileFromHostToGuest",
                self._config.vmx_path,
                str(host_path),
                guest_path,
            ],
            guest_auth=True,
            timeout=timeout,
        )

    def copy_file_from_guest_to_host(
        self,
        guest_path: str,
        host_path: str | Path,
        *,
        timeout: int = 120,
    ) -> None:
        """Copy a file out of the guest."""
        self._run(
            [
                "copyFileFromGuestToHost",
                self._config.vmx_path,
                guest_path,
                str(host_path),
            ],
            guest_auth=True,
            timeout=timeout,
        )

    def run_program_in_guest(
        self,
        program_path: str,
        program_args: Iterable[str] | None = None,
        *,
        wait: bool = True,
        interactive: bool = False,
        timeout: int = 300,
    ) -> None:
        """Run a program inside the guest OS.

        Args:
            program_path: Absolute path to the executable inside the guest.
            program_args: Arguments to pass to the program.
            wait:         If True, block until the program finishes.
            interactive:  If True, use ``-activeWindow -interactive`` flags so the
                          program window is visible on the guest desktop.  Without
                          these flags, ``vmrun runProgramInGuest`` launches the
                          process in Session 0 (invisible service session).
            timeout:      Seconds before giving up.
        """
        args = ["runProgramInGuest", self._config.vmx_path]
        if interactive:
            args.extend(["-activeWindow", "-interactive"])
        if not wait:
            args.append("-noWait")
        args.append(program_path)
        if program_args:
            args.extend(list(program_args))
        self._run(args, guest_auth=True, timeout=timeout)

    def check_tools_state(self, *, timeout: int = 10) -> str:
        """Return the raw VMware Tools state string (e.g. 'running', 'installed',
        'not running').  Raises VmrunError if vmrun itself fails."""
        try:
            result = self._run(
                ["checkToolsState", self._config.vmx_path],
                timeout=timeout,
            )
            return (result.stdout or "").strip().lower()
        except VmrunError:
            raise

    def wait_for_tools(
        self,
        *,
        timeout: int = 180,
        poll_interval: int = 3,
        cancel_event: threading.Event | None = None,
    ) -> None:
        """Block until VMware Tools is RUNNING inside the guest, or raise VmrunError.

        Strategy (tried in order, first success wins):
          1. ``vmrun checkToolsState <vmx>``  – native, lightweight.
          2. ``vmrun runProgramInGuest … cmd /c exit 0``  – probe fallback.

        The *cancel_event* is polled between attempts so the caller can abort.
        """
        deadline = time.monotonic() + timeout
        attempt = 0
        last_error = ""

        # Decide strategy once: probe checkToolsState; if it returns an
        # unrecognised error we fall back to the runProgramInGuest probe.
        use_check_tools = True

        while time.monotonic() < deadline:
            if cancel_event is not None and cancel_event.is_set():
                raise VmrunError("Run cancelled by user.")

            attempt += 1
            remaining = int(deadline - time.monotonic())

            if use_check_tools:
                try:
                    state = self.check_tools_state(timeout=min(10, remaining))
                    logger.debug(
                        "wait_for_tools attempt %d: checkToolsState=%r", attempt, state
                    )
                    if state == "running":
                        logger.info("VMware Tools ready after %d attempt(s).", attempt)
                        return
                    # 'installed' means Tools exists but isn't fully started yet;
                    # any other value means not ready.
                    last_error = f"Tools state: {state!r}"
                except VmrunError as exc:
                    msg = str(exc).lower()
                    # checkToolsState not supported on this vmrun build → switch strategy
                    if "unknown command" in msg or "invalid" in msg:
                        logger.debug(
                            "checkToolsState unsupported, switching to probe strategy."
                        )
                        use_check_tools = False
                    else:
                        last_error = str(exc)
                        logger.debug(
                            "wait_for_tools attempt %d failed: %s", attempt, exc
                        )

            if not use_check_tools:
                # Probe: run a harmless cmd in the guest; success means Tools is alive.
                try:
                    self.run_program_in_guest(
                        "cmd.exe",
                        ["/c", "exit", "0"],
                        wait=True,
                        timeout=min(15, remaining),
                    )
                    logger.info(
                        "VMware Tools ready (probe) after %d attempt(s).", attempt
                    )
                    return
                except VmrunError as exc:
                    last_error = str(exc)
                    logger.debug(
                        "wait_for_tools probe attempt %d failed: %s", attempt, exc
                    )

            # Sleep in 1-second slices so cancel_event is responsive.
            slept = 0
            while slept < poll_interval and time.monotonic() < deadline:
                if cancel_event is not None and cancel_event.is_set():
                    raise VmrunError("Run cancelled by user.")
                time.sleep(1)
                slept += 1

        raise VmrunError(
            f"VMware Tools did not become ready within {timeout}s. "
            "Install VMware Tools inside the guest (VM → Install VMware Tools) "
            f"and ensure they start on boot.  Last status: {last_error or 'unknown'}"
        )

    def capture_screen(self, output_path: str | Path, *, timeout: int = 5) -> None:
        """Capture a VM screenshot to a PNG file (best-effort, short timeout)."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        self._run(
            [
                "captureScreen",
                self._config.vmx_path,
                str(output),
            ],
            guest_auth=True,
            timeout=timeout,
        )
