"""Host-side orchestrator for the Guest UI Runner.

Handles:
  1. **Preflight** – verify an interactive desktop session exists in the guest
     before wasting time launching the UI runner.
  2. **Deploy** – copy ``ui_runner.ps1`` and ``launch_interactive.ps1`` into the
     guest at the canonical per-job path.
  3. **Run** – call ``launch_interactive.ps1`` via ``vmrun runProgramInGuest``
     (which runs in Session 0).  That script creates a scheduled task to run
     ``ui_runner.ps1`` in the user's interactive session (Session 1).
  4. **Collect** – pull frames and ``behavior.json`` back to the host run-dir.
  5. **Select key frames** – choose ≤ ``max_frames`` evenly spaced frames that
     show actual UI changes, for the replay carousel.

This module is intentionally *defensive*: every method catches exceptions and
logs rather than propagating unexpected failures to the caller.  The caller
decides whether to treat a UIRunner failure as fatal or advisory.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .vmrun_client import VmrunClient
    from .config import SandboxConfig

logger = logging.getLogger(__name__)

# Guest paths (relative to job directory)
_GUEST_TOOLS_SUBDIR = r"tools\ui_runner"  # relative to C:\Sandbox\jobs\<job>\
_GUEST_FRAMES_SUBDIR = r"frames"           # relative to C:\Sandbox\out\

# Host: source scripts
_SCRIPTS_DIR = Path(__file__).parent / "guest_scripts" / "ui_runner"


class GuestUIRunnerError(RuntimeError):
    """Raised for non-recoverable Guest UI Runner failures."""


class GuestUIRunner:
    """Orchestrate visible UI automation inside the VMware guest.

    The runner is *optional* — it enhances the sandbox run with a visible
    GUI interaction layer, but its failure should not abort the core pipeline.

    Usage::

        runner = GuestUIRunner(client, config, step_cb=worker.emit_step)
        runner.preflight_check_desktop()       # raises GuestUIRunnerError if no desktop
        runner.deploy(job_id, guest_job_dir)   # copy scripts to guest
        runner.run(job_id, sample_guest_path, monitor_seconds, inspect_only)
        key_frames = runner.collect_output(host_run_dir, job_id)
    """

    def __init__(
        self,
        client: "VmrunClient",
        config: "SandboxConfig",
        *,
        step_cb: Callable[[str, str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        self._client = client
        self._config = config
        self._step = step_cb or (lambda status, msg: logger.debug("[%s] %s", status, msg))
        self._cancel = cancel_check or (lambda: False)
        # Populated by collect_output; read by _run_ui_automation to build payload extras.
        self.last_ui_steps: list[str] = []
        self.last_automation_visible: bool = False
        self.last_frames_dir: str = ""
        self.last_behavior: dict = {}
        self.last_uac_secure_desktop: int | None = None   # 0=ok, 1=secure-desktop-on, None=unknown
        self.last_prereq: dict = {}   # full prereq_results.json parsed dict

    # ──────────────────────────────────────────────────────────────── preflight

    def preflight_check_desktop(self) -> str:
        """Verify the guest has an active interactive desktop session.

        Runs ``query user`` inside the guest (via runProgramInGuest, Session 0),
        captures the output to a temp file, copies it back, and parses it.

        Also checks PromptOnSecureDesktop and explorer.exe. Results are stored
        in ``self.last_prereq`` and ``self.last_uac_secure_desktop``.

        Returns:
            The raw ``query user`` output (informational).

        Raises:
            GuestUIRunnerError: if no Active session is found, or if the
                command cannot be executed.
        """
        self._step("Running", "[UI-preflight] Checking interactive desktop session, explorer, and UAC…")
        guest_out = r"C:\Sandbox\out\session_check.txt"
        host_tmp  = Path(tempfile.mktemp(suffix=".txt"))

        try:
            # Ensure guest out-dir exists
            self._client.run_program_in_guest(
                "cmd.exe",
                ["/c", r"if not exist C:\Sandbox\out mkdir C:\Sandbox\out"],
                wait=True,
                timeout=20,
            )
            # Run query user → file
            self._client.run_program_in_guest(
                "cmd.exe",
                ["/c", f'query user > "{guest_out}" 2>&1'],
                wait=True,
                timeout=20,
            )
            # Copy back
            self._client.copy_file_from_guest_to_host(guest_out, host_tmp, timeout=15)
            content = host_tmp.read_text(errors="replace")
        except Exception as exc:
            raise GuestUIRunnerError(
                f"Desktop preflight failed (could not run 'query user'): {exc}\n"
                "Ensure VMware Tools is running and guest credentials are correct."
            ) from exc
        finally:
            host_tmp.unlink(missing_ok=True)

        # ── Check explorer.exe ────────────────────────────────────────────────
        try:
            self._check_explorer_running()
        except Exception as _e:
            self._step("Running", f"[UI-preflight] Explorer check warning: {_e}")

        # ── Check UAC secure desktop ──────────────────────────────────────────
        try:
            uac_val = self._check_uac_secure_desktop()
            self.last_uac_secure_desktop = uac_val
        except Exception as _e:
            self._step("Running", f"[UI-preflight] UAC check warning: {_e}")

        lower = content.lower()
        if "active" in lower:
            session_line = next((l for l in content.splitlines() if "active" in l.lower()), content[:120])
            self._step("OK", f"[UI-preflight] Interactive session found: {session_line.strip()}")
            return content

        if "disc" in lower or "disconnect" in lower:
            raise GuestUIRunnerError(
                "Guest session is DISCONNECTED — reconnect the desktop and try again.\n"
                "GUI automation requires an active logged-in session.\n"
                f"query user output:\n{content}"
            )

        # No 'Active' found
        raise GuestUIRunnerError(
            "Guest not logged in; enable auto-login to see GUI automation.\n"
            "Fix: In the guest VM, enable automatic logon for the user account "
            "(netplwiz → uncheck 'Users must enter a username and password').\n"
            f"query user output:\n{content}"
        )

    def _check_explorer_running(self) -> bool:
        """Verify explorer.exe is running in the guest; attempt to start it if missing.

        Returns True if explorer was already running or was started; False otherwise.
        """
        guest_out = r"C:\Sandbox\out\explorer_check.txt"
        host_tmp  = Path(tempfile.mktemp(suffix=".txt"))
        try:
            self._client.run_program_in_guest(
                "cmd.exe",
                ["/c", f'tasklist /FI "IMAGENAME eq explorer.exe" /NH > "{guest_out}" 2>&1'],
                wait=True, timeout=15,
            )
            self._client.copy_file_from_guest_to_host(guest_out, host_tmp, timeout=10)
            content = host_tmp.read_text(errors="replace")
            if "explorer.exe" in content.lower():
                self._step("OK", "[UI-preflight] explorer.exe is running")
                return True
            else:
                self._step("Running", "[UI-preflight] explorer.exe not found — starting desktop shell…")
                self._client.run_program_in_guest(
                    r"C:\Windows\explorer.exe", [], wait=False, timeout=5,
                )
                self._step("OK", "[UI-preflight] explorer.exe start requested")
                return False
        except Exception as exc:
            self._step("Running", f"[UI-preflight] explorer check failed (non-fatal): {exc}")
            return False
        finally:
            host_tmp.unlink(missing_ok=True)

    def _check_uac_secure_desktop(self) -> int | None:
        """Read PromptOnSecureDesktop from the guest registry.

        Returns:
            0  – secure desktop disabled (automation can click UAC prompts)  ✅
            1  – secure desktop ENABLED  (UAC prompts invisible to automation) ⚠
            None – could not determine (registry key absent or run failed)
        """
        guest_out = r"C:\Sandbox\out\uac_check.txt"
        host_tmp  = Path(tempfile.mktemp(suffix=".txt"))
        reg_cmd = (
            r'reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" '
            r'/v PromptOnSecureDesktop'
        )
        try:
            self._client.run_program_in_guest(
                "cmd.exe",
                ["/c", f'{reg_cmd} > "{guest_out}" 2>&1'],
                wait=True, timeout=15,
            )
            self._client.copy_file_from_guest_to_host(guest_out, host_tmp, timeout=10)
            content = host_tmp.read_text(errors="replace")
        except Exception as exc:
            self._step("Running", f"[UI-preflight] UAC reg query failed (non-fatal): {exc}")
            return None
        finally:
            host_tmp.unlink(missing_ok=True)

        # Parse output line like:
        #   PromptOnSecureDesktop    REG_DWORD    0x0
        for line in content.splitlines():
            if "PromptOnSecureDesktop" in line:
                parts = line.split()
                if parts:
                    raw = parts[-1].strip().lower().lstrip("0x")
                    try:
                        val = int(raw, 16) if raw else None
                        if val == 0:
                            self._step("OK", "[UI-preflight] UAC PromptOnSecureDesktop=0 — automation can interact with UAC prompts ✅")
                        elif val == 1:
                            self._step(
                                "Running",
                                "[UI-preflight] ⚠ UAC PromptOnSecureDesktop=1 — UAC prompts use secure desktop, "
                                "automation cannot click them. "
                                r"Fix inside VM: reg add \"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System\" "
                                r"/v PromptOnSecureDesktop /t REG_DWORD /d 0 /f",
                            )
                        return val
                    except ValueError:
                        return None
        return None

    # ─────────────────────────────────────────────────────────────────── deploy

    def deploy(self, job_id: str, guest_job_base: str) -> str:
        """Copy UI runner scripts to the per-job guest directory.

        Args:
            job_id:         Unique job identifier (e.g. ``run_20240101_120000``).
            guest_job_base: Guest path to the job's base directory
                            (e.g. ``C:\\Sandbox\\jobs\\run_...``).

        Returns:
            The guest path to the deployed ``ui_runner.ps1``.
        """
        guest_tools_dir = f"{guest_job_base}\\{_GUEST_TOOLS_SUBDIR}"
        guest_runner    = f"{guest_tools_dir}\\ui_runner.ps1"
        guest_launcher  = f"{guest_tools_dir}\\launch_interactive.ps1"

        self._step("Running", f"[UI-runner] Creating guest tools dir: {guest_tools_dir}")
        self._client.run_program_in_guest(
            "cmd.exe",
            ["/c", f'md "{guest_tools_dir}" 2>nul'],
            wait=True,
            timeout=20,
        )

        # Copy both scripts
        for host_name, guest_dest in (
            ("ui_runner.ps1",         guest_runner),
            ("launch_interactive.ps1", guest_launcher),
        ):
            src = _SCRIPTS_DIR / host_name
            if not src.exists():
                raise GuestUIRunnerError(
                    f"Host script not found: {src}\n"
                    "Ensure the guest_scripts/ui_runner/ directory is complete."
                )
            self._step("Running", f"[UI-runner] Deploying {host_name} → {guest_dest}")
            self._client.copy_file_from_host_to_guest(src, guest_dest)
            self._step("OK", f"[UI-runner] Deployed {host_name}")

        return guest_runner

    # ──────────────────────────────────────────────────────────────────── run

    def run(
        self,
        job_id: str,
        guest_job_base: str,
        sample_guest_path: str,
        monitor_seconds: int,
        *,
        inspect_only: bool = False,
    ) -> None:
        """Launch the interactive UI runner inside the guest.

        Calls ``launch_interactive.ps1`` via ``runProgramInGuest`` (Session 0).
        That script creates a scheduled task under the guest user account,
        which runs ``ui_runner.ps1`` in Session 1 (visible desktop).

        The call **blocks** until ``launch_interactive.ps1`` returns (which waits
        for the sentinel file ``ui_runner_done.txt``).

        Args:
            job_id:             Unique job identifier.
            guest_job_base:     Guest base path for this job.
            sample_guest_path:  Full guest path to the sample file.
            monitor_seconds:    Maximum seconds to run UI automation.
            inspect_only:       If True, launch but do NOT click installer buttons.

        Raises:
            GuestUIRunnerError: if launch_interactive.ps1 cannot be found or
                ``runProgramInGuest`` fails.
        """
        guest_launcher = f"{guest_job_base}\\{_GUEST_TOOLS_SUBDIR}\\launch_interactive.ps1"

        inspect_flag  = "-InspectOnly" if inspect_only else ""
        launch_args = [
            "-ExecutionPolicy", "Bypass",
            "-File", guest_launcher,
            "-GuestUser",       self._config.guest_user,
            "-GuestPass",       self._config.guest_pass,
            "-SamplePath",      sample_guest_path,
            "-JobId",           job_id,
            "-MonitorSeconds",  str(monitor_seconds),
        ]
        if inspect_only:
            launch_args.append("-InspectOnly")

        # Total timeout: monitor_seconds + startup overhead + collection overhead
        total_timeout = monitor_seconds + 180

        self._step(
            "Running",
            f"[UI-runner] Launching interactive UI runner (inspect_only={inspect_only})…",
        )
        self._client.run_program_in_guest(
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            launch_args,
            wait=True,
            interactive=True,
            timeout=total_timeout,
        )
        self._step("OK", "[UI-runner] launch_interactive finished")

    # ──────────────────────────────────────────────────────────────── collect

    def collect_output(
        self,
        host_run_dir: Path,
        job_id: str,
        *,
        max_frames: int = 10,
    ) -> list[str]:
        """Copy guest ``frames/`` and ``behavior.json`` to *host_run_dir*.

        Returns:
            List of host-side frame paths (absolute) suitable for the QML
            ``replayFramesModel``.  Limited to *max_frames* for clarity.
            Returns an empty list if collection fails.
        """
        self._step("Running", "[UI-runner] Collecting frames, behavior.json, and prereqs from guest…")
        host_frames_dir = host_run_dir / "ui_frames"
        host_frames_dir.mkdir(parents=True, exist_ok=True)

        # ── Pull prereq_results.json (session/explorer/UAC check) ─────────────
        try:
            host_prereq = host_run_dir / "prereq_results.json"
            self._client.copy_file_from_guest_to_host(
                r"C:\Sandbox\out\prereq_results.json", host_prereq, timeout=15
            )
            prereq_data = json.loads(host_prereq.read_text(encoding="utf-8", errors="replace"))
            self.last_prereq = prereq_data
            uac_val = prereq_data.get("uac_secure_desktop")
            if uac_val is not None:
                self.last_uac_secure_desktop = int(uac_val)
            # Emit UAC warning as a step so it shows in the timeline
            if self.last_uac_secure_desktop == 1:
                self._step(
                    "Running",
                    "[UI-runner] \u26a0 UAC secure desktop is ENABLED in guest VM (PromptOnSecureDesktop=1). "
                    "Automation cannot click UAC prompts; run this command inside the VM to fix: "
                    r"reg add ""HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"" "
                    r"/v PromptOnSecureDesktop /t REG_DWORD /d 0 /f",
                )
            self._step("OK", f"[UI-runner] prereq_results: session_active={prereq_data.get('session_active')}, "
                             f"explorer={prereq_data.get('explorer_running')}, "
                             f"uac_secure_desktop={prereq_data.get('uac_secure_desktop')}")
        except Exception as _pe:
            self._step("Running", f"[UI-runner] prereq_results.json not available (non-fatal): {_pe}")

        # ── Pull behavior.json ────────────────────────────────────────────────
        guest_behav = r"C:\Sandbox\out\behavior.json"
        host_behav  = host_run_dir / "behavior.json"
        try:
            self._client.copy_file_from_guest_to_host(guest_behav, host_behav, timeout=20)
            self._step("OK", f"[UI-runner] behavior.json → {host_behav}")
            self._parse_and_log_behavior(host_behav)
        except Exception as exc:
            self._step("Failed", f"[UI-runner] Could not retrieve behavior.json: {exc}")

        # ── Pull done file ────────────────────────────────────────────────────
        try:
            self._client.copy_file_from_guest_to_host(
                r"C:\Sandbox\out\ui_runner_done.txt",
                host_run_dir / "ui_runner_done.txt",
                timeout=10,
            )
        except Exception:
            pass

        # ── Pull ui_step_*.txt markers ────────────────────────────────────────
        # Enumerate via dir /b, copy each one back to the host run-dir.
        ui_steps: list[str] = []
        try:
            guest_step_listing = r"C:\Sandbox\out\ui_steps_listing.txt"
            host_step_listing  = host_run_dir / "ui_steps_listing.txt"
            self._client.run_program_in_guest(
                "cmd.exe",
                ["/c", r'dir /b /on "C:\Sandbox\out\ui_step_*.txt" > "C:\Sandbox\out\ui_steps_listing.txt" 2>&1'],
                wait=True,
                timeout=15,
            )
            self._client.copy_file_from_guest_to_host(guest_step_listing, host_step_listing, timeout=10)
            step_names = [l.strip() for l in host_step_listing.read_text(errors="replace").splitlines()
                          if l.strip().lower().endswith(".txt")]
            for sname in step_names:
                guest_src = rf"C:\Sandbox\out\{sname}"
                host_dst  = host_run_dir / sname
                try:
                    self._client.copy_file_from_guest_to_host(guest_src, host_dst, timeout=10)
                    ui_steps.append(host_dst.read_text(errors="replace").strip())
                except Exception:
                    pass
            if ui_steps:
                self._step("OK", f"[UI-runner] {len(ui_steps)} ui_step marker(s) collected")
        except Exception as exc:
            self._step("Failed", f"[UI-runner] Could not collect ui_step markers: {exc}")

        # ── Pull launch log ───────────────────────────────────────────────────
        try:
            self._client.copy_file_from_guest_to_host(
                r"C:\Sandbox\out\launch_interactive_log.txt",
                host_run_dir / "launch_interactive_log.txt",
                timeout=10,
            )
        except Exception:
            pass

        # ── Enumerate guest frames via a dir /b listing ───────────────────────
        guest_frames_dir = r"C:\Sandbox\out\frames"
        guest_listing    = r"C:\Sandbox\out\frames_listing.txt"
        host_listing     = host_run_dir / "ui_frames_listing.txt"
        frame_names: list[str] = []

        try:
            self._client.run_program_in_guest(
                "cmd.exe",
                ["/c", f'dir /b /on "{guest_frames_dir}" > "{guest_listing}" 2>&1'],
                wait=True,
                timeout=15,
            )
            self._client.copy_file_from_guest_to_host(guest_listing, host_listing, timeout=15)
            frame_names = [
                l.strip() for l in host_listing.read_text(errors="replace").splitlines()
                if l.strip().lower().endswith(".png")
            ]
            self._step("OK", f"[UI-runner] {len(frame_names)} frame file(s) found in guest")
        except Exception as exc:
            self._step("Failed", f"[UI-runner] Could not enumerate guest frames: {exc}")
            return []

        if not frame_names:
            self._step("Failed", "[UI-runner] No frames captured – check if UI runner ran.")
            return []

        # ── Select key frames (evenly spaced) ────────────────────────────────
        selected = self._select_key_frames(frame_names, max_frames)
        self._step("Running", f"[UI-runner] Copying {len(selected)} key frames to host…")

        host_frame_paths: list[str] = []
        for name in selected:
            if self._cancel():
                self._step("Failed", "[UI-runner] Collection cancelled.")
                break
            guest_src = f"{guest_frames_dir}\\{name}"
            host_dst  = host_frames_dir / name
            try:
                self._client.copy_file_from_guest_to_host(guest_src, host_dst, timeout=30)
                host_frame_paths.append(str(host_dst))
            except Exception as exc:
                self._step("Failed", f"[UI-runner] Could not copy frame {name}: {exc}")

        self._step(
            "OK",
            f"[UI-runner] Collected {len(host_frame_paths)} key frame(s) → {host_frames_dir}",
        )

        # Populate instance state for caller to inspect
        self.last_frames_dir       = str(host_frames_dir)
        # automation_visible = frames exist AND behavior shows frames_changed
        self.last_automation_visible = (
            len(host_frame_paths) > 0 and
            self.last_behavior.get("frames_changed", True) is not False
        )
        self.last_ui_steps = ui_steps

        return host_frame_paths

    # ──────────────────────────────────────────────────────────────── helpers

    def _select_key_frames(self, frame_names: list[str], max_n: int) -> list[str]:
        """Return at most *max_n* evenly spaced names from *frame_names*."""
        if not frame_names:
            return []
        total = len(frame_names)
        if total <= max_n:
            return list(frame_names)
        step = total / max_n
        return [frame_names[int(i * step)] for i in range(max_n)]

    def _parse_and_log_behavior(self, path: Path) -> dict:
        """Read behavior.json and emit key stats as steps."""
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            clicks  = len(data.get("buttons_clicked") or [])
            frames  = int(data.get("frames_captured") or 0)
            runtime = float(data.get("runtime_seconds") or 0)
            changed = bool(data.get("frames_changed", True))
            errors  = list(data.get("errors") or [])
            self._step(
                "OK",
                f"[UI-runner] behavior: {frames} frames, {clicks} button click(s), "
                f"{runtime:.1f}s runtime, frames_changed={changed}",
            )
            if not changed:
                self._step(
                    "Failed",
                    "[UI-runner] No visible frame changes detected — "
                    "automation ran in background / no interactive desktop.",
                )
            for err in errors[:5]:
                self._step("Failed" if "ERROR" in err.upper() else "Running", f"  → {err}")
            # Store parsed data for collect_output to use
            self.last_behavior = data
            return data
        except Exception as exc:
            self._step("Failed", f"[UI-runner] Could not parse behavior.json: {exc}")
            return {}
