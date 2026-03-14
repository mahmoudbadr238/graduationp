"""High-level VMware automation facade.

Wraps app.sandbox_vmware.VmrunClient with:
- Auto-detection of vmrun.exe
- Retry-backed ensure_guest_ready()
- run_diagnostics() with PASS/FAIL per check
- All operations are synchronous/blocking (call from a worker thread)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

from ..sandbox_vmware.config import SandboxConfig, load_sandbox_config
from ..sandbox_vmware.vmrun_client import VmrunClient, VmrunError

logger = logging.getLogger(__name__)

_VMRUN_CANDIDATES = [
    r"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe",
    r"C:\Program Files\VMware\VMware Workstation\vmrun.exe",
]
_PS = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"


# ── Config loading with vmware.json support ──────────────────────────────────


def _load_vmware_json() -> dict:
    """Load config/vmware.json if present (env vars override)."""
    for candidate in [
        Path("config/vmware.json"),
        Path(__file__).parent.parent.parent / "config" / "vmware.json",
    ]:
        if candidate.exists():
            try:
                with candidate.open(encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    return data
            except Exception as exc:
                logger.warning("Could not load vmware.json: %s", exc)
    return {}


def _autodetect_vmrun() -> str:
    """Return first vmrun.exe that exists, or empty string."""
    found = shutil.which("vmrun")
    if found:
        return found
    for path in _VMRUN_CANDIDATES:
        if Path(path).exists():
            return path
    return ""


def load_runner_config() -> tuple[SandboxConfig, dict]:
    """
    Load SandboxConfig with env-var priority, then vmware.json fallback,
    then autodetect vmrun.

    Returns:
        (SandboxConfig, extras) where extras contains:
            - guest_workdir: str
            - host_artifacts_dir: str
            - boot_wait_seconds: int
    """
    json_cfg = _load_vmware_json()

    def _env_or_json(env_key: str, json_key: str, default: str = "") -> str:
        val = os.environ.get(env_key, "").strip()
        if val:
            return val
        json_val = str(json_cfg.get(json_key, default))
        # Ignore template placeholders
        if json_val.startswith("__USE_ENV_") and json_val.endswith("__"):
            return default
        return json_val or default

    # Use the existing loader (handles .env), then override with JSON where env is empty
    cfg = load_sandbox_config()

    # Always apply JSON/autodetect overrides for all key fields
    vmrun_path = _env_or_json("SANDBOX_VMRUN", "vmrun_path", cfg.vmrun_path)
    if not vmrun_path or not Path(vmrun_path).exists():
        vmrun_path = _autodetect_vmrun() or vmrun_path

    cfg = SandboxConfig(
        vmrun_path=vmrun_path,
        vmx_path=_env_or_json("SANDBOX_VMX", "vmx_path", cfg.vmx_path),
        snapshot_name=_env_or_json(
            "SANDBOX_SNAPSHOT", "snapshot_name", cfg.snapshot_name
        ),
        guest_user=_env_or_json("SANDBOX_GUEST_USER", "guest_username", cfg.guest_user),
        guest_pass=_env_or_json("SANDBOX_GUEST_PASS", "guest_password", cfg.guest_pass),
        guest_in_dir=cfg.guest_in_dir,
        guest_out_dir=cfg.guest_out_dir,
        guest_runner_path=cfg.guest_runner_path,
        guest_open_url_path=cfg.guest_open_url_path,
        host_frames_dir=cfg.host_frames_dir,
        host_results_dir=cfg.host_results_dir,
        frame_keep_count=cfg.frame_keep_count,
        capture_interval_ms=cfg.capture_interval_ms,
        report_poll_seconds=cfg.report_poll_seconds,
    )
    cfg.ensure_directories()

    extras = {
        "guest_workdir": (
            os.environ.get("SANDBOX_GUEST_WORKDIR", "").strip()
            or str(json_cfg.get("guest_workdir", r"C:\Sentinel\Jobs"))
        ),
        "host_artifacts_dir": (
            os.environ.get("SANDBOX_HOST_ARTIFACTS", "").strip()
            or str(json_cfg.get("host_artifacts_dir", r"data\artifacts"))
        ),
        "boot_wait_seconds": int(json_cfg.get("boot_wait_seconds", 25)),
        "report_poll_seconds": int(
            json_cfg.get("report_poll_seconds", cfg.report_poll_seconds)
        ),
    }
    return cfg, extras


# ── VMwareRunner ─────────────────────────────────────────────────────────────


class VMwareRunner:
    """
    High-level VMware Workstation automation for defensive malware analysis.

    All methods are blocking; call from a background thread.
    Uses vmrun Guest Operations (CopyFileFromHostToGuest, RunProgramInGuest, etc.)
    – NO shared folders required.
    """

    def __init__(
        self,
        config: SandboxConfig | None = None,
        extras: dict | None = None,
        step_cb: Callable[[str, str], None] | None = None,
    ):
        """
        Args:
            config: Pre-built SandboxConfig. If None, loads from env/JSON.
            extras: Dict from load_runner_config() with guest_workdir,
                    host_artifacts_dir, boot_wait_seconds. If None, loads.
            step_cb: Callback(status, message) for live step streaming.
                     status is "Running", "OK", or "Failed".
        """
        if config is None:
            config, extras = load_runner_config()
        extras = extras or {}
        self._cfg = config
        self._client = VmrunClient(self._cfg)
        self._step_cb = step_cb or (lambda s, m: None)
        self._guest_workdir: str = extras.get("guest_workdir", r"C:\Sentinel\Jobs")
        self._boot_wait: int = int(extras.get("boot_wait_seconds", 25))

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def config(self) -> SandboxConfig:
        return self._cfg

    @property
    def guest_workdir(self) -> str:
        return self._guest_workdir

    # ── Step helpers ─────────────────────────────────────────────────────────

    def _ok(self, msg: str) -> None:
        self._step_cb("OK", msg)

    def _running(self, msg: str) -> None:
        self._step_cb("Running", msg)

    def _fail(self, msg: str) -> None:
        self._step_cb("Failed", msg)

    # ── High-level operations ─────────────────────────────────────────────────

    def start_vm(self, *, nogui: bool = True, timeout: int = 180) -> None:
        """Start the VM. Idempotent: if already running ignores the error."""
        self._running("Starting VM (headless)")
        try:
            self._client.start(nogui=nogui, timeout=timeout)
        except VmrunError as exc:
            lower = str(exc).lower()
            if "already" in lower or "running" in lower:
                self._ok("VM was already running")
                return
            raise
        self._ok("VM started")

    def revert_snapshot(self, timeout: int = 180) -> None:
        """Stop VM if running, then revert to the configured clean snapshot."""
        self._running(f"Reverting to snapshot '{self._cfg.snapshot_name}'")
        try:
            self._client.stop(hard=True, timeout=60)
        except VmrunError:
            pass  # not running – that's fine
        self._client.revert_to_snapshot(timeout=timeout)
        self._ok(f"Snapshot '{self._cfg.snapshot_name}' restored")

    def ensure_guest_ready(
        self,
        *,
        retries: int = 10,
        retry_delay: float = 6.0,
        test_cmd: str = "echo sentinel_ready",
    ) -> None:
        """
        Wait until VMware Tools + guest auth is responsive.
        Polls by running a no-op command in the guest.
        Raises VmrunError after all retries are exhausted.
        """
        self._running("Waiting for guest OS + VMware Tools to become ready")
        time.sleep(self._boot_wait)
        last_exc: Exception = VmrunError("Guest never became ready")
        for attempt in range(1, retries + 1):
            try:
                self._client.run_program_in_guest(
                    _PS,
                    ["-Command", test_cmd],
                    wait=True,
                    timeout=30,
                )
                self._ok(f"Guest ready (attempt {attempt}/{retries})")
                return
            except VmrunError as exc:
                last_exc = exc
                self._running(
                    f"Guest not responsive yet ({attempt}/{retries}): {str(exc)[:80]}"
                )
                if attempt < retries:
                    time.sleep(retry_delay)
        raise VmrunError(
            f"Guest did not become ready after {retries} attempts. "
            f"Last error: {last_exc}. "
            "Check: VMware Tools installed? Guest auto-login configured? "
            "Correct SANDBOX_GUEST_USER + SANDBOX_GUEST_PASS?"
        )

    def ensure_guest_workdir(self, job_id: str) -> str:
        """
        Create C:\\Sentinel\\Jobs\\<job_id>\\ in the guest.
        Returns the full guest job path.
        """
        job_path = self._guest_workdir.rstrip("\\") + "\\" + job_id
        self._running(f"Creating guest job folder: {job_path}")
        self._client.run_program_in_guest(
            _PS,
            [
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                f"New-Item -ItemType Directory -Force -Path '{job_path}' | Out-Null",
            ],
            wait=True,
            timeout=60,
        )
        self._ok(f"Guest job folder created: {job_path}")
        return job_path

    def copy_to_guest(
        self,
        host_path: str | Path,
        guest_path: str,
        *,
        timeout: int = 120,
    ) -> None:
        """Copy a file from host into the guest VM."""
        name = Path(host_path).name
        self._running(f"Copying {name} → guest {guest_path}")
        self._client.copy_file_from_host_to_guest(
            host_path, guest_path, timeout=timeout
        )
        self._ok(f"Copied {name} to guest")

    def run_in_guest(
        self,
        program: str,
        args: list[str],
        *,
        wait: bool = True,
        timeout: int = 300,
    ) -> None:
        """Run a program inside the guest OS."""
        label = Path(program).name
        mode = "waiting" if wait else "no-wait"
        self._running(f"Running in guest ({mode}): {label}")
        self._client.run_program_in_guest(program, args, wait=wait, timeout=timeout)
        if wait:
            self._ok(f"Guest program finished: {label}")
        else:
            self._ok(f"Guest program launched: {label}")

    def copy_from_guest(
        self,
        guest_path: str,
        host_path: str | Path,
        *,
        timeout: int = 120,
        skip_missing: bool = False,
    ) -> bool:
        """
        Copy a file/folder FROM guest to host.
        Returns True on success, False if file missing and skip_missing=True.
        """
        name = Path(guest_path).name
        self._running(f"Fetching artifact: {name}")
        try:
            self._client.copy_file_from_guest_to_host(
                guest_path, host_path, timeout=timeout
            )
            self._ok(f"Artifact retrieved: {name}")
            return True
        except VmrunError as exc:
            msg = str(exc).lower()
            if skip_missing and (
                "not found" in msg or "no such" in msg or "error" in msg
            ):
                self._fail(f"Artifact not found (non-fatal): {name}")
                return False
            raise

    # ── Persistent-agent helpers ─────────────────────────────────────────────

    def write_job_file(
        self,
        job_dict: dict,
        guest_dest: str = r"C:\Sandbox\job.json",
        *,
        timeout: int = 30,
    ) -> None:
        """Serialise *job_dict* as JSON and copy it to *guest_dest*.

        The agent (C:\\Sandbox\\agent\\agent.ps1) reads this file on each
        scheduled-task trigger and processes it, then deletes it when done.
        """
        import tempfile

        tmp_fd, tmp_name = tempfile.mkstemp(suffix=".json")
        try:
            import os

            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(job_dict, fh)
            self.copy_to_guest(tmp_name, guest_dest, timeout=timeout)
        finally:
            Path(tmp_name).unlink(missing_ok=True)

    def ensure_sandbox_agent(
        self,
        *,
        agent_ps1: Path,
        ui_ahk: Path | None,
        install_ps1: Path,
        guest_agent_dir: str = r"C:\Sandbox\agent",
        guest_agent_ps1: str = r"C:\Sandbox\agent\agent.ps1",
        timeout: int = 120,
    ) -> None:
        """Deploy the persistent sandbox agent to the guest if not already installed.

        Detection: tries to copy *guest_agent_ps1* to a temp host path; if that
        succeeds the agent is already present.  Otherwise copies all scripts and
        runs *install_ps1* to create the scheduled task.
        """
        import tempfile

        # ── Quick presence check ─────────────────────────────────────────────
        self._running(f"Checking for persistent agent at {guest_agent_ps1}")
        with tempfile.NamedTemporaryFile(suffix=".ps1", delete=False) as tf:
            probe = tf.name
        try:
            self._client.copy_file_from_guest_to_host(
                guest_agent_ps1, probe, timeout=15
            )
            present = Path(probe).exists() and Path(probe).stat().st_size > 0
        except Exception:
            present = False
        finally:
            Path(probe).unlink(missing_ok=True)

        if present:
            self._ok("Persistent sandbox agent already installed in guest")
            return

        # ── First-time deploy ────────────────────────────────────────────────
        self._running(
            "First run — deploying persistent sandbox agent to guest "
            f"({guest_agent_dir})"
        )

        # Ensure agent dir exists via PowerShell
        self.run_in_guest(
            _PS,
            [
                "-Command",
                f"New-Item -ItemType Directory -Force -Path '{guest_agent_dir}' | Out-Null",
            ],
            wait=True,
            timeout=30,
        )

        # Copy agent.ps1
        dest_ps1 = guest_agent_dir.rstrip("\\") + "\\agent.ps1"
        self.copy_to_guest(agent_ps1, dest_ps1, timeout=60)

        # Copy ui.ahk if present
        if ui_ahk and ui_ahk.exists():
            dest_ahk = guest_agent_dir.rstrip("\\") + "\\ui.ahk"
            self.copy_to_guest(ui_ahk, dest_ahk, timeout=30)
        else:
            self._running("ui.ahk not found — AHK automation will be skipped in guest")

        # Copy install_agent.ps1
        guest_install = guest_agent_dir.rstrip("\\") + "\\install_agent.ps1"
        self.copy_to_guest(install_ps1, guest_install, timeout=30)

        # Run install_agent.ps1 (registers the SentinelSandboxAgent scheduled task)
        self.run_in_guest(
            _PS,
            [
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-File",
                guest_install,
                "-SourceDir",
                guest_agent_dir,
            ],
            wait=True,
            timeout=timeout,
        )
        self._ok("Persistent sandbox agent installed and task registered")

    def stop_vm(self, *, hard: bool = True, timeout: int = 90) -> None:
        """Stop the VM. Does not raise if VM is already stopped."""
        self._running("Stopping VM")
        try:
            self._client.stop(hard=hard, timeout=timeout)
            self._ok("VM stopped")
        except VmrunError as exc:
            lower = str(exc).lower()
            if "not running" in lower or "not found" in lower:
                self._ok("VM was already stopped")
            else:
                self._fail(f"Stop VM warning (continuing): {exc}")

    # ── Visual-agent execution ───────────────────────────────────────────────

    def execute_with_visual_agent(
        self,
        host_malware_path: str | Path,
        *,
        host_agent_path: str | Path | None = None,
        guest_sandbox_dir: str = r"C:\Sandbox",
        agent_timeout: int = 120,
        cancel_event: threading.Event | None = None,
    ) -> dict:
        """Deploy the visual-agent payload + sample into the guest and execute.

        This copies BOTH the compiled agent EXE and the target sample into the
        guest VM, then launches the agent **interactively** so it appears on the
        guest desktop (Session 1) — not hidden in Session 0.

        vmrun flags used:
            -activeWindow   → attach the process to the foreground window station
            -interactive    → run in the interactive desktop session (Session 1)

        Args:
            host_malware_path:  Absolute or relative path to the sample on the host.
            host_agent_path:    Path to the compiled agent EXE on the host.
                                Defaults to ``<project_root>/dist/sentinel_agent.exe``.
            guest_sandbox_dir:  Working directory inside the guest VM.
            agent_timeout:      Seconds to let the agent run before the host
                                considers it "done" (the agent has its own internal
                                timeout as well).
            cancel_event:       Optional threading.Event for cancellation.

        Returns:
            dict with keys: executed, errors, screenshot_path, duration_sec
        """
        _cancel = cancel_event or threading.Event()
        t_start = time.monotonic()

        result: dict = {
            "executed": False,
            "errors": [],
            "screenshot_path": "",
            "duration_sec": 0.0,
        }

        # ── Resolve host paths ───────────────────────────────────────────────
        malware_path = Path(host_malware_path)
        if not malware_path.exists():
            result["errors"].append(f"Sample not found on host: {malware_path}")
            return result

        if host_agent_path is None:
            # Default: dist/sentinel_agent.exe relative to project root
            host_agent_path = (
                Path(__file__).parent.parent.parent / "dist" / "sentinel_agent.exe"
            )
        agent_path = Path(host_agent_path)
        if not agent_path.exists():
            result["errors"].append(
                f"Visual-agent EXE not found: {agent_path}. "
                "Build it first: python build_agent.py"
            )
            return result

        sample_name = malware_path.name
        guest_sample = guest_sandbox_dir.rstrip("\\") + "\\" + sample_name
        guest_agent = guest_sandbox_dir.rstrip("\\") + "\\sentinel_agent.exe"

        try:
            # 1. Revert to clean snapshot
            if _cancel.is_set():
                result["errors"].append("Cancelled before start")
                return result
            self.revert_snapshot()

            # 2. Start VM headless (preview stream captures the frame buffer)
            if _cancel.is_set():
                return result
            self._running("Starting VM (headless — preview via frame capture)")
            try:
                self._client.start(nogui=True, timeout=180)
            except VmrunError as exc:
                if "already" not in str(exc).lower():
                    raise
            self._ok("VM started (headless)")

            # 3. Wait for guest OS + VMware Tools
            if _cancel.is_set():
                self.stop_vm()
                return result
            self.ensure_guest_ready()

            # 4. Create guest sandbox directory
            if _cancel.is_set():
                self.stop_vm()
                return result
            self._running(f"Creating guest directory: {guest_sandbox_dir}")
            self._client.run_program_in_guest(
                _PS,
                [
                    "-ExecutionPolicy", "Bypass", "-Command",
                    f"New-Item -ItemType Directory -Force -Path '{guest_sandbox_dir}' | Out-Null",
                ],
                wait=True,
                timeout=60,
            )
            self._ok("Guest sandbox directory ready")

            # 5. Copy malware sample to guest
            if _cancel.is_set():
                self.stop_vm()
                return result
            self.copy_to_guest(str(malware_path), guest_sample, timeout=120)

            # 6. Copy visual-agent EXE to guest
            if _cancel.is_set():
                self.stop_vm()
                return result
            self.copy_to_guest(str(agent_path), guest_agent, timeout=120)

            # 7. Execute the agent INTERACTIVELY on the guest desktop
            #    vmrun flags: -activeWindow -interactive → visible in Session 1
            if _cancel.is_set():
                self.stop_vm()
                return result
            self._running(f"Launching visual agent → {sample_name}")
            self._client.run_program_in_guest(
                guest_agent,
                [guest_sample, "--timeout", str(agent_timeout)],
                wait=False,          # don't block the host
                interactive=True,    # -activeWindow -interactive → Session 1
                timeout=30,
            )
            self._ok("Visual agent launched on guest desktop (interactive)")
            result["executed"] = True

            # 8. Wait for the agent's analysis window to complete
            self._running(
                f"Agent running on guest desktop ({agent_timeout}s window)"
            )
            waited = 0
            poll = 5
            while waited < agent_timeout + 30:
                if _cancel.is_set():
                    result["errors"].append("Cancelled during agent execution")
                    break
                time.sleep(poll)
                waited += poll

            # 9. Capture a final screenshot
            try:
                frames_dir = Path(
                    str(self._cfg.host_frames_dir) or "data/artifacts"
                )
                frames_dir.mkdir(parents=True, exist_ok=True)
                scrn_file = str(
                    frames_dir / f"agent_{int(time.time())}.png"
                )
                self._client.capture_screen(scrn_file, timeout=30)
                result["screenshot_path"] = scrn_file
                self._ok("Final screenshot captured")
            except Exception as exc:
                self._running(f"Screenshot unavailable: {exc}")

            # 10. Stop VM
            self.stop_vm()

        except VmrunError as exc:
            logger.error("execute_with_visual_agent VmrunError: %s", exc)
            result["errors"].append(f"VMware error: {exc}")
        except Exception as exc:
            logger.exception("execute_with_visual_agent error: %s", exc)
            result["errors"].append(f"Unexpected error: {exc}")

        result["duration_sec"] = round(time.monotonic() - t_start, 1)
        return result

    # ── Automated file analysis pipeline ─────────────────────────────────────

    def run_file(
        self,
        host_file: str,
        *,
        monitor_seconds: int = 60,
        disable_network: bool = True,
        allow_execution: bool = False,
        step_cb: Callable[[str, str], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> dict:
        """Full automated sandbox pipeline for a single file.

        Sequence:
          1. Revert VM to clean snapshot
          2. Start VM and wait for guest OS + Tools ready
          3. Copy sample to guest input directory
          4. Deploy run.ps1 analysis script to guest
          5. Launch run.ps1 in guest (no-wait mode)
          6. Poll guest for report.json (cancel-safe)
          7. Capture screenshot
          8. Stop VM
          9. Parse and return normalized result dict

        Returns a dict compatible with ScanController._run_sandbox:
          executed, duration_sec, exit_code, new_processes, new_files,
          modified_files, new_connections, errors, alerts,
          screenshot_path, registry_changes
        """
        if step_cb:
            self._step_cb = step_cb

        _cancel: threading.Event = cancel_event or threading.Event()
        t_start = time.monotonic()

        result: dict = {
            "executed": False,
            "duration_sec": 0.0,
            "exit_code": None,
            "new_processes": [],
            "new_files": [],
            "modified_files": [],
            "new_connections": [],
            "errors": [],
            "alerts": [],
            "screenshot_path": "",
            "registry_changes": [],
        }

        host_path = Path(host_file)
        if not host_path.exists():
            result["errors"].append(f"Sample not found: {host_file}")
            return result

        sample_name = host_path.name
        guest_in = (self._cfg.guest_in_dir or r"C:\Sandbox\in").rstrip("\\/")
        guest_out = r"C:\Sandbox\out"
        guest_sample = f"{guest_in}\\{sample_name}"
        guest_script = f"{guest_in}\\run.ps1"

        # Locate host-side run.ps1
        _local_script = (
            Path(__file__).parent.parent
            / "sandbox_vmware"
            / "guest_scripts"
            / "run.ps1"
        )

        try:
            # ── 1. Revert to clean snapshot ───────────────────────────────────
            if _cancel.is_set():
                result["errors"].append("Cancelled before sandbox start")
                return result
            self.revert_snapshot()

            # ── 2. Start VM ───────────────────────────────────────────────────
            if _cancel.is_set():
                return result
            self.start_vm()

            # ── 3. Wait for guest OS + VMware Tools ───────────────────────────
            if _cancel.is_set():
                self.stop_vm()
                return result
            self.ensure_guest_ready()

            # ── 4. Create guest working directories ───────────────────────────
            if _cancel.is_set():
                self.stop_vm()
                return result
            self._running("Preparing guest analysis directories")
            try:
                self._client.run_program_in_guest(
                    _PS,
                    [
                        "-ExecutionPolicy", "Bypass",
                        "-Command",
                        (
                            f"New-Item -ItemType Directory -Force "
                            f"-Path '{guest_in}' | Out-Null; "
                            f"New-Item -ItemType Directory -Force "
                            f"-Path '{guest_out}' | Out-Null"
                        ),
                    ],
                    wait=True,
                    timeout=60,
                )
                self._ok("Guest directories ready")
            except VmrunError as exc:
                result["errors"].append(f"Guest dir setup failed: {exc}")

            # ── 5. Copy sample to guest ───────────────────────────────────────
            if _cancel.is_set():
                self.stop_vm()
                return result
            self.copy_to_guest(str(host_path), guest_sample, timeout=120)

            # ── 6. Deploy analysis script ─────────────────────────────────────
            if _cancel.is_set():
                self.stop_vm()
                return result
            if _local_script.exists():
                self.copy_to_guest(str(_local_script), guest_script, timeout=60)
                self._ok("Analysis script deployed to guest")
            else:
                result["errors"].append(
                    f"run.ps1 not found at {_local_script} — inspect-only fallback"
                )

            # ── 7. Execute analysis script (no-wait) ──────────────────────────
            if _cancel.is_set():
                self.stop_vm()
                return result
            mode_label = "execute" if allow_execution else "inspect"
            self._running(
                f"Analysing {sample_name} ({mode_label} mode, "
                f"{monitor_seconds}s monitor)"
            )
            ps_args = [
                "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Normal",
                "-File", guest_script,
                "-SamplePath", guest_sample,
                "-MonitorSeconds", str(min(monitor_seconds, 300)),
            ]
            if disable_network:
                ps_args.append("-DisableNetwork")
            if allow_execution:
                ps_args.append("-AllowRun")
            try:
                self._client.run_program_in_guest(
                    _PS, ps_args, wait=False, interactive=True, timeout=30
                )
                self._ok("Analysis script launched in guest (interactive)")
            except VmrunError as exc:
                result["errors"].append(f"Failed to launch analysis script: {exc}")

            # ── 8. Poll for report.json ───────────────────────────────────────
            guest_report_path = f"{guest_out}\\report.json"
            max_wait = monitor_seconds + 90
            poll_start = time.monotonic()
            report_raw: dict = {}
            got_report = False
            self._running(f"Polling for report (max {max_wait}s)")

            with tempfile.TemporaryDirectory() as tmpdir:
                local_report = Path(tmpdir) / "report.json"
                while (time.monotonic() - poll_start) < max_wait:
                    if _cancel.is_set():
                        result["errors"].append("Cancelled during analysis")
                        result["duration_sec"] = round(
                            time.monotonic() - t_start, 1
                        )
                        self.stop_vm()
                        return result
                    time.sleep(8.0)
                    try:
                        self._client.copy_file_from_guest_to_host(
                            guest_report_path,
                            str(local_report),
                            timeout=20,
                        )
                        if (
                            local_report.exists()
                            and local_report.stat().st_size > 10
                        ):
                            with local_report.open(
                                "r", encoding="utf-8-sig"
                            ) as fh:
                                report_raw = json.load(fh)
                            got_report = True
                            self._ok("Analysis report received from guest")
                            break
                    except Exception:
                        pass  # still running

            if not got_report:
                result["errors"].append(
                    f"Report not received after {max_wait}s — "
                    "analysis may be incomplete"
                )

            # ── 9. Capture screenshot ─────────────────────────────────────────
            screenshot_path = ""
            if getattr(self._cfg, "capture_enabled", True):
                try:
                    frames_dir = Path(
                        str(self._cfg.host_frames_dir) or "data/artifacts"
                    )
                    frames_dir.mkdir(parents=True, exist_ok=True)
                    scrn_file = str(
                        frames_dir / f"sandbox_{int(time.time())}.png"
                    )
                    self._client.capture_screen(scrn_file, timeout=30)
                    screenshot_path = scrn_file
                    self._ok("Screenshot captured")
                except Exception as exc:
                    self._running(f"Screenshot unavailable: {exc}")

            # ── 10. Stop VM ───────────────────────────────────────────────────
            self.stop_vm()

            # ── 11. Map guest report → result dict ────────────────────────────
            result["duration_sec"] = round(time.monotonic() - t_start, 1)
            result["screenshot_path"] = screenshot_path

            if got_report and isinstance(report_raw, dict):
                result["executed"] = bool(
                    report_raw.get("executed", allow_execution)
                )
                result["exit_code"] = report_raw.get("exit_code")
                result["new_processes"] = [
                    str(p) if not isinstance(p, str) else p
                    for p in report_raw.get("spawned_processes", [])
                ]
                result["new_files"] = [
                    str(f) if not isinstance(f, str) else f
                    for f in report_raw.get("files_created", [])
                ]
                result["new_connections"] = [
                    str(c) if not isinstance(c, str) else c
                    for c in report_raw.get("network_connections", [])
                ]
                result["registry_changes"] = [
                    str(r) if not isinstance(r, str) else r
                    for r in report_raw.get("registry_modified", [])
                ]
                result["errors"] += [
                    str(e) for e in report_raw.get("errors", [])
                ]
                # Merge alerts + highlights into a single alerts list
                alerts = [str(a) for a in report_raw.get("alerts", [])]
                alerts += [str(h) for h in report_raw.get("highlights", [])]
                result["alerts"] = alerts

        except VmrunError as exc:
            logger.error("VMwareRunner.run_file VmrunError: %s", exc)
            result["errors"].append(f"VMware error: {exc}")
            result["duration_sec"] = round(time.monotonic() - t_start, 1)
        except Exception as exc:
            logger.exception("VMwareRunner.run_file unexpected error: %s", exc)
            result["errors"].append(f"Unexpected error: {exc}")
            result["duration_sec"] = round(time.monotonic() - t_start, 1)

        return result

    # ── Diagnostics ──────────────────────────────────────────────────────────

    def run_diagnostics(self) -> list[dict]:
        """
        Run all prerequisite checks and return a list of check results.

        Each entry is:
          { "check": str, "passed": bool, "message": str, "fix": str | None }
        """
        results: list[dict] = []

        def _check(name: str, passed: bool, msg: str, fix: str | None = None) -> None:
            results.append(
                {"check": name, "passed": passed, "message": msg, "fix": fix}
            )

        # 1) vmrun.exe exists
        vmrun = Path(self._cfg.vmrun_path)
        if not self._cfg.vmrun_path:
            _check(
                "vmrun.exe present",
                False,
                "vmrun_path is empty.",
                "Set SANDBOX_VMRUN env var or vmrun_path in config/vmware.json.",
            )
        elif vmrun.exists():
            _check("vmrun.exe present", True, f"Found: {vmrun}")
        else:
            _check(
                "vmrun.exe present",
                False,
                f"Not found: {vmrun}",
                "Install VMware Workstation and set vmrun_path in config/vmware.json "
                f"or SANDBOX_VMRUN env var. Common location: {_VMRUN_CANDIDATES[0]}",
            )

        # 2) VMX file exists
        vmx = Path(self._cfg.vmx_path)
        if not self._cfg.vmx_path:
            _check(
                "VMX file present",
                False,
                "vmx_path is empty.",
                "Set SANDBOX_VMX env var or vmx_path in config/vmware.json.",
            )
        elif vmx.exists():
            _check("VMX file present", True, f"Found: {vmx}")
        else:
            _check(
                "VMX file present",
                False,
                f"Not found: {vmx}",
                "Set SANDBOX_VMX env var or vmx_path in config/vmware.json "
                "to the full path of your Windows 10/11 sandbox .vmx file.",
            )

        # 3) Guest credentials configured
        if self._cfg.guest_user and self._cfg.guest_pass:
            _check(
                "Guest credentials", True, f"User '{self._cfg.guest_user}' configured"
            )
        else:
            missing = []
            if not self._cfg.guest_user:
                missing.append("SANDBOX_GUEST_USER")
            if not self._cfg.guest_pass:
                missing.append("SANDBOX_GUEST_PASS")
            _check(
                "Guest credentials",
                False,
                f"Missing: {', '.join(missing)}",
                "Set the missing env vars or add guest_username/guest_password "
                "to config/vmware.json. The guest account must have auto-login "
                "and 'Allow connection without password prompt' in VMware.",
            )

        # Only continue with live checks if host reqs pass
        host_ok = all(r["passed"] for r in results)

        if not host_ok:
            results.append(
                {
                    "check": "Live VM checks",
                    "passed": False,
                    "message": "Skipped – fix above issues first.",
                    "fix": None,
                }
            )
            return results

        # 4) Can list snapshots (proves vmrun works against the VMX)
        try:
            snapshots = self._client.list_snapshots(timeout=30)
            if self._cfg.snapshot_name in snapshots:
                _check(
                    "Clean snapshot exists",
                    True,
                    f"Snapshot '{self._cfg.snapshot_name}' found ({len(snapshots)} total).",
                )
            else:
                _check(
                    "Clean snapshot exists",
                    False,
                    f"Snapshot '{self._cfg.snapshot_name}' not found. "
                    f"Available: {', '.join(snapshots) if snapshots else '(none)'}",
                    f"Open the VM in VMware Workstation, get to a clean Windows desktop, "
                    f"then: VM → Snapshot → Take Snapshot → name it exactly "
                    f'"{self._cfg.snapshot_name}".',
                )
        except VmrunError as exc:
            _check(
                "Clean snapshot exists",
                False,
                f"Could not query snapshots: {exc}",
                "Ensure the VMX path is correct and VMware Workstation is installed.",
            )

        # 5) Can revert to snapshot (proves start is possible)
        try:
            self._client.revert_to_snapshot(timeout=120)
            _check(
                "Can revert to snapshot",
                True,
                f"Reverted to '{self._cfg.snapshot_name}' successfully.",
            )
        except VmrunError as exc:
            _check(
                "Can revert to snapshot",
                False,
                str(exc),
                "Check snapshot name spelling and that the VM is not locked by another process.",
            )
            return results  # Skip guest checks if we can't revert

        # 6) Can start VM
        try:
            self._client.start(nogui=True, timeout=120)
            _check("Can start VM", True, "VM started in headless mode.")
        except VmrunError as exc:
            _check(
                "Can start VM",
                False,
                str(exc),
                "Check that no other VMware instance is running this VM.",
            )
            return results

        # 7) VMware Tools ready (explicit wait, proves guest ops will work)
        try:
            self._client.wait_for_tools(timeout=self._boot_wait + 60, poll_interval=3)
            _check(
                "VMware Tools ready",
                True,
                "VMware Tools is RUNNING in the guest (probed via checkToolsState / runProgramInGuest).",
            )
        except VmrunError as exc:
            _check(
                "VMware Tools ready",
                False,
                str(exc),
                "Install VMware Tools inside the guest: VM menu → Install VMware Tools, "
                "run the installer, reboot the guest, retake the snapshot.  "
                "Guest operations (mkdir, copy, run) will NOT work without Tools.",
            )
            # No point testing workdir if Tools isn't up
            try:
                self._client.stop(hard=True, timeout=60)
            except VmrunError:
                pass
            return results

        # 8) Can create guest workdir
        try:
            self._client.run_program_in_guest(
                _PS,
                [
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    f"New-Item -ItemType Directory -Force -Path '{self._guest_workdir}' | Out-Null ; "
                    f"if (Test-Path '{self._guest_workdir}') {{ exit 0 }} else {{ exit 1 }}",
                ],
                wait=True,
                timeout=60,
            )
            _check(
                "Can create guest workdir",
                True,
                f"Created '{self._guest_workdir}' in guest.",
            )
        except VmrunError as exc:
            _check(
                "Can create guest workdir",
                False,
                str(exc),
                f"Ensure the guest account has write access to {self._guest_workdir}. "
                "Run PowerShell as admin in the guest: "
                f"New-Item -ItemType Directory -Force -Path '{self._guest_workdir}'",
            )
        finally:
            try:
                self._client.stop(hard=True, timeout=60)
            except VmrunError:
                pass

        return results
