"""ScanCenter – 6-phase interactive scanner orchestrator (QThread).

Runs an analyst-driven malware analysis pipeline in a background thread
so the PySide6 UI never freezes:

    Phase 1  Static ClamAV scan + SHA-256 hash
    Phase 2  VM setup, behavioral monitor script, payload delivery,
             VMware HWND discovery → QML WindowContainer embedding
    Phase 3  Interactive pause — waits for analyst to click "Finish Session"
    Phase 4  Pull behavior.log, release embed, teardown KVM + revert VM
    Phase 5  Groq AI summary via REST API
    Phase 6  Deterministic scoring, emit scan_complete, redirect to scan page

Signals
-------
progress_updated(int, str)
    Emitted after every meaningful milestone.  ``int`` is 0-100,
    ``str`` is a human-readable status line.

scan_complete(dict)
    Emitted exactly once when the pipeline finishes (success or failure).
    The dict is the ``V3Report.to_dict()`` payload so QML can consume it
    directly via JSON.

request_ui_change(str)
    Emitted to ask main.qml to switch the visible route (e.g.
    ``"sandbox-lab"`` or ``"scan-tool"``).

vmware_window_ready(int)
    Emitted with the VMware HWND so the main thread can create a
    ``QWindow.fromWinId()`` for QML's ``WindowContainer``.

request_release_embed()
    Asks the main thread to release the embedded QWindow before
    the VM is reverted.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal, Slot

from backend.engines.sandbox_vmware.config import SandboxConfig, load_sandbox_config
from backend.engines.sandbox_vmware.vmrun_client import VmrunClient, VmrunError
from backend.engines.sandbox_vmware.window_embedder import find_kvm_hwnd
from backend.engines.scancenter.report_schema import (
    AiExplanation,
    EngineResult,
    FileInfo,
    SandboxSection,
    StaticSection,
    V3Report,
    VerdictSection,
)

logger = logging.getLogger(__name__)

# ── Guest constants ───────────────────────────────────────────────────────────
_GUEST_PAYLOAD = r"C:\Users\Public\Downloads\payload.exe"
_GUEST_MONITOR = r"C:\Users\Public\Downloads\monitor.ps1"
_GUEST_BEHAVIOR_LOG = r"C:\Users\Public\Downloads\behavior.log"
_GUEST_BEHAVIOR_REPORT = r"C:\Users\Public\Downloads\behavior_report.json"

# ── VMware KVM executable (lightweight, borderless console window) ────────────
_VMWARE_KVM_EXE = r"C:\Program Files (x86)\VMware\VMware Workstation\vmware-kvm.exe"

# ── Subprocess creation flags (hide console on Windows) ───────────────────────
_SUBPROCESS_FLAGS = 0
if os.name == "nt":
    _SUBPROCESS_FLAGS = (
        subprocess.CREATE_NO_WINDOW | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    )


def _safe_int(value: object, default: int = 0) -> int:
    """Convert *value* to int, returning *default* for non-numeric strings."""
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(value)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return default


# ══════════════════════════════════════════════════════════════════════════════
# Orchestrator
# ══════════════════════════════════════════════════════════════════════════════


class ScannerOrchestrator(QThread):
    """6-phase interactive scan pipeline executed on a background thread."""

    # ── Signals ───────────────────────────────────────────────────────────
    progress_updated      = Signal(int, str)        # (0-100, status_text)
    scan_complete         = Signal(dict, str, str)  # (V3Report, brief, detailed)
    request_ui_change     = Signal(str)             # route name for main.qml
    vmware_window_ready   = Signal(int)             # HWND of the VMware window
    request_release_embed = Signal()                # ask main thread to release embed

    def __init__(
        self,
        file_path: str,
        *,
        monitor_seconds: int = 30,
        parent: Any | None = None,
    ) -> None:
        super().__init__(parent)
        self._file_path = Path(file_path)
        self._monitor_seconds = monitor_seconds
        self.interactive_event = threading.Event()
        self._kvm_process: subprocess.Popen | None = None
        self._monitor_started_at: float | None = None

    # ── Public Slots ──────────────────────────────────────────────────────

    @Slot()
    def finish_interactive_session(self) -> None:
        """Called from QML when the analyst clicks 'Finish Interactive Session'."""
        logger.info("Analyst triggered finish_interactive_session — unblocking Phase 3")
        self.interactive_event.set()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _emit(self, pct: int, msg: str) -> None:
        print(f"[Orchestrator] {pct}% — {msg}")
        self.progress_updated.emit(pct, msg)

    @staticmethod
    def _generate_monitor_ps1(monitor_seconds: int) -> str:
        """Return a PowerShell script that detonates the payload and logs behaviour."""
        return (
            "# monitor.ps1 — auto-generated by ScannerOrchestrator\n"
            "Set-StrictMode -Version Latest\n"
            "$ErrorActionPreference = 'Continue'\n"
            "$payloadPath = 'C:\\Users\\Public\\Downloads\\payload.exe'\n"
            "$workingDir = 'C:\\Users\\Public\\Downloads'\n"
            "$logFile = 'C:\\Users\\Public\\Downloads\\behavior.log'\n"
            "$reportFile = 'C:\\Users\\Public\\Downloads\\behavior_report.json'\n"
            "$startedAt = Get-Date\n"
            "$errors = New-Object System.Collections.Generic.List[string]\n"
            "$processes = @()\n"
            "$netstatLines = @()\n"
            "$payloadProc = $null\n"
            "'Sentinel behavioral monitor' | Out-File -FilePath $logFile -Encoding utf8\n"
            "\"Started: $($startedAt.ToString('o'))\" | Out-File -FilePath $logFile -Append -Encoding utf8\n"
            "\"Target : $payloadPath\" | Out-File -FilePath $logFile -Append -Encoding utf8\n"
            "'' | Out-File -FilePath $logFile -Append -Encoding utf8\n"
            "\n"
            "# 1. Execute the payload\n"
            "try {\n"
            "    $payloadProc = Start-Process -FilePath $payloadPath -WorkingDirectory $workingDir -PassThru -ErrorAction Stop\n"
            "    \"Started payload PID: $($payloadProc.Id)\" | Out-File -FilePath $logFile -Append -Encoding utf8\n"
            "} catch {\n"
            "    $errText = \"Payload launch failed: $($_.Exception.Message)\"\n"
            "    $errors.Add($errText)\n"
            "    $errText | Out-File -FilePath $logFile -Append -Encoding utf8\n"
            "}\n"
            "'' | Out-File -FilePath $logFile -Append -Encoding utf8\n"
            "\n"
            f"# 2. Let the payload run for {monitor_seconds} seconds\n"
            f"Start-Sleep -Seconds {monitor_seconds}\n"
            "\n"
            "# 3. Capture process information\n"
            "try {\n"
            "    $processes = @(\n"
            "        Get-CimInstance Win32_Process | Where-Object {\n"
            "            ($_.ExecutablePath -like 'C:\\Users\\Public\\Downloads\\*') -or\n"
            "            ($payloadProc -and ($_.ProcessId -eq $payloadProc.Id -or $_.ParentProcessId -eq $payloadProc.Id))\n"
            "        } | Select-Object \n"
            "            @{Name='name';Expression={$_.Name}},\n"
            "            @{Name='pid';Expression={$_.ProcessId}},\n"
            "            @{Name='parent_pid';Expression={$_.ParentProcessId}},\n"
            "            @{Name='path';Expression={$_.ExecutablePath}},\n"
            "            @{Name='command_line';Expression={$_.CommandLine}}\n"
            "    )\n"
            "} catch {\n"
            "    $errText = \"Process capture failed: $($_.Exception.Message)\"\n"
            "    $errors.Add($errText)\n"
            "}\n"
            "'=== PROCESSES ===' | Out-File -FilePath $logFile -Append -Encoding utf8\n"
            "if ($processes.Count -gt 0) {\n"
            "    $processes | Format-Table -AutoSize | Out-String | Out-File -FilePath $logFile -Append -Encoding utf8\n"
            "} else {\n"
            "    'No matching processes captured.' | Out-File -FilePath $logFile -Append -Encoding utf8\n"
            "}\n"
            "'' | Out-File -FilePath $logFile -Append -Encoding utf8\n"
            "\n"
            "# 4. Capture network connections\n"
            "'=== NETWORK ===' | Out-File -FilePath $logFile -Append -Encoding utf8\n"
            "try {\n"
            "    $netstatLines = @(netstat -ano 2>$null | Where-Object { $_ -match '^\\s*(TCP|UDP)\\s+' })\n"
            "} catch {\n"
            "    $errText = \"Network capture failed: $($_.Exception.Message)\"\n"
            "    $errors.Add($errText)\n"
            "}\n"
            "if ($netstatLines.Count -gt 0) {\n"
            "    $netstatLines | Out-File -FilePath $logFile -Append -Encoding utf8\n"
            "} else {\n"
            "    'No active network connections captured.' | Out-File -FilePath $logFile -Append -Encoding utf8\n"
            "}\n"
            "'' | Out-File -FilePath $logFile -Append -Encoding utf8\n"
            "\n"
            "# 5. Write a machine-readable summary for the host pipeline\n"
            "$payloadExitCode = $null\n"
            "if ($payloadProc) {\n"
            "    try {\n"
            "        if ($payloadProc.HasExited) {\n"
            "            $payloadExitCode = $payloadProc.ExitCode\n"
            "        }\n"
            "    } catch {\n"
            "        $payloadExitCode = $null\n"
            "    }\n"
            "}\n"
            "$report = [ordered]@{\n"
            "    status = 'completed'\n"
            "    start_time = $startedAt.ToString('o')\n"
            "    end_time = (Get-Date).ToString('o')\n"
            "    executed = $true\n"
            "    sample_path = $payloadPath\n"
            "    sample_pid = $(if ($payloadProc) { $payloadProc.Id } else { $null })\n"
            "    sample_exit_code = $payloadExitCode\n"
            "    processes = @($processes)\n"
            "    network_connections = @($netstatLines)\n"
            "    errors = @($errors)\n"
            "    summary = [ordered]@{\n"
            "        new_processes = @($processes).Count\n"
            "        network_connections = @($netstatLines).Count\n"
            "        errors = @($errors).Count\n"
            "    }\n"
            "}\n"
            "$report | ConvertTo-Json -Depth 6 | Out-File -FilePath $reportFile -Encoding utf8\n"
        )

    # ── Phase 1: Static ClamAV ───────────────────────────────────────────

    def _phase1_clamav(self) -> EngineResult:
        """Run local clamscan and return an EngineResult with score 0 or 100."""
        self._emit(5, "Phase 1 — Running ClamAV static scan …")

        # Normalize the target path to an absolute Windows path so ClamAV
        # doesn't choke on relative paths or forward-slash separators.
        abs_target = os.path.abspath(str(self._file_path))
        print(f"[Orchestrator] Phase 1 — Target (abs): {abs_target}")

        # 1. Try PATH first
        clamscan = shutil.which("clamscan") or shutil.which("clamdscan")

        # 2. Probe well-known installation directories
        if not clamscan:
            _CLAMAV_CANDIDATES = [
                r"C:\Program Files\ClamAV\clamscan.exe",
                r"C:\Program Files (x86)\ClamAV\clamscan.exe",
                r"C:\ClamAV\clamscan.exe",
                r"C:\Program Files\ClamAV\clamdscan.exe",
                r"C:\Program Files (x86)\ClamAV\clamdscan.exe",
                r"C:\ClamAV\clamdscan.exe",
            ]
            for candidate in _CLAMAV_CANDIDATES:
                if os.path.isfile(candidate):
                    clamscan = candidate
                    print(f"[Orchestrator] Phase 1 — Found ClamAV at hardcoded path: {candidate}")
                    break

        if not clamscan:
            env_path = os.environ.get("PATH", "<not set>")
            print(f"[Orchestrator] Phase 1 — ClamAV NOT FOUND. System PATH:\n{env_path}")
            self._emit(15, "Phase 1 — ClamAV not installed (clamscan not found)")
            return EngineResult(
                name="ClamAV", status="not_installed", score=0,
                details="clamscan / clamdscan not found on this system or common install paths",
            )

        cmd = [clamscan, "--no-summary", abs_target]
        print(f"[Orchestrator] Phase 1 — ClamAV command: {cmd}")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=90, check=False,
                creationflags=_SUBPROCESS_FLAGS,
            )
        except subprocess.TimeoutExpired:
            self._emit(15, "Phase 1 — ClamAV timed out")
            return EngineResult(
                name="ClamAV", status="error", score=0,
                details="clamscan timed out (90 s)",
            )
        except FileNotFoundError as exc:
            print(f"[Orchestrator] Phase 1 — ClamAV binary vanished: {exc}")
            self._emit(15, f"Phase 1 — ClamAV binary not found: {exc}")
            return EngineResult(
                name="ClamAV", status="error", score=0,
                details=f"Binary not found: {exc}",
            )
        except Exception as exc:
            print(f"[Orchestrator] Phase 1 ClamAV crash: {exc}")
            self._emit(15, f"Phase 1 — ClamAV error: {exc}")
            return EngineResult(
                name="ClamAV", status="error", score=0,
                details=str(exc)[:200],
            )

        # ── Aggressive output logging for every exit code ─────────────
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        print(
            f"[Orchestrator] Phase 1 — ClamAV rc={proc.returncode}\n"
            f"  STDOUT: {stdout[:500] or '(empty)'}\n"
            f"  STDERR: {stderr[:500] or '(empty)'}"
        )

        combined = f"{stdout}\n{stderr}".strip()

        if proc.returncode == 1:
            # Threat detected
            threat = ""
            for line in combined.splitlines():
                if "FOUND" in line:
                    threat = line.strip()[:300]
                    break
            self._emit(15, f"Phase 1 — ClamAV DETECTED: {threat[:80]}")
            return EngineResult(
                name="ClamAV", status="malicious", score=100,
                details=threat or "Threat detected",
            )

        if proc.returncode == 2:
            # ClamAV error — surface the exact reason (missing db, perms, etc.)
            error_detail = stderr or stdout or "ClamAV returned exit code 2 (unknown error)"
            print(f"[Orchestrator] Phase 1 — ClamAV ERROR detail:\n{error_detail}")
            self._emit(15, f"Phase 1 — ClamAV error: {error_detail[:80]}")
            return EngineResult(
                name="ClamAV", status="error", score=0,
                details=error_detail[:300],
            )

        if proc.returncode != 0:
            # Unexpected exit code — still surface it
            error_detail = combined or f"ClamAV exited with rc={proc.returncode}"
            print(f"[Orchestrator] Phase 1 — ClamAV unexpected rc={proc.returncode}: {error_detail}")
            self._emit(15, f"Phase 1 — ClamAV rc={proc.returncode}")
            return EngineResult(
                name="ClamAV", status="error", score=0,
                details=error_detail[:300],
            )

        self._emit(15, "Phase 1 — ClamAV clean")
        return EngineResult(
            name="ClamAV", status="clean", score=0, details="No threats found",
        )

    # ── Phase 2: VM Setup + KVM Launch + Embed + Payload Delivery ───────

    def _phase2_prepare_sandbox(
        self, config: SandboxConfig, client: VmrunClient,
    ) -> None:
        """Revert, boot VM headless, launch KVM viewer, embed, wait for tools, deliver payload."""

        # 2a — Revert to clean snapshot
        self._emit(20, "Phase 2 — Reverting VM to clean snapshot …")
        client.revert_to_snapshot(timeout=180)

        # 2b — Start VM headless via vmrun (KVM will provide the display)
        self._emit(25, "Phase 2 — Starting VM (headless via vmrun) …")
        client.start(nogui=True, timeout=180)

        # 2c — Redirect analyst to Detonation Theater so the QML
        #       WindowContainer is visible and ready to adopt the HWND.
        self._emit(28, "Phase 2 — Switching to Detonation Theater …")
        self.request_ui_change.emit("sandbox-lab")
        time.sleep(0.5)   # let QML process the route change and render

        # 2d — Launch vmware-kvm.exe (lightweight, borderless console)
        #       This gives us a clean render surface that's trivial to embed.
        kvm_exe = _VMWARE_KVM_EXE
        vmx_path = config.vmx_path
        self._emit(30, "Phase 2 — Launching vmware-kvm.exe …")
        print(f"[Orchestrator] Launching KVM: {kvm_exe!r} {vmx_path!r}")
        try:
            self._kvm_process = subprocess.Popen(
                [kvm_exe, vmx_path],
                creationflags=_SUBPROCESS_FLAGS,
            )
            print(f"[Orchestrator] KVM process started, PID={self._kvm_process.pid}")
        except FileNotFoundError:
            print(f"[Orchestrator] ERROR: vmware-kvm.exe not found at {kvm_exe}")
            logger.warning("vmware-kvm.exe not found at %s — embedding skipped", kvm_exe)
            self._kvm_process = None
        except OSError as exc:
            print(f"[Orchestrator] ERROR launching vmware-kvm.exe: {exc}")
            logger.warning("Failed to launch vmware-kvm.exe: %s", exc)
            self._kvm_process = None

        # 2e — Poll for the KVM window HWND (20 s, 1 s interval).
        #       Extract the VM name from the VMX path for title matching.
        vm_name = Path(vmx_path).stem  # e.g. "Windows 10 x64"
        if self._kvm_process is not None:
            self._emit(32, "Phase 2 — Polling for KVM window HWND …")
            hwnd = find_kvm_hwnd(timeout=20, poll_interval=1, vm_name=vm_name)
            if hwnd:
                logger.info("Found KVM window HWND=%#x — requesting embed", hwnd)
                self.vmware_window_ready.emit(hwnd)
            else:
                logger.warning("KVM window not found after 20 s — embedding skipped")
        else:
            logger.warning("KVM process was not started — embedding skipped")

        # 2f — Wait for VMware Tools (checkToolsState polling, 2 s interval)
        #       Do NOT copy files or execute anything until tools are running.
        self._emit(33, "Phase 2 — Waiting for VMware Tools in guest …")
        client.wait_for_tools(timeout=180, poll_interval=2)
        self._emit(38, "Phase 2 — VMware Tools running ✓")

        # 2f — Push payload to guest
        self._emit(40, f"Phase 2 — Copying payload to {_GUEST_PAYLOAD} …")
        client.copy_file_from_host_to_guest(
            self._file_path, _GUEST_PAYLOAD, timeout=120,
        )

        # 2g — Generate and push the behavioral monitor script
        self._emit(43, "Phase 2 — Generating monitor.ps1 …")
        ps1_content = self._generate_monitor_ps1(self._monitor_seconds)
        host_ps1 = Path(tempfile.gettempdir()) / "sentinel_monitor.ps1"
        host_ps1.write_text(ps1_content, encoding="utf-8")

        self._emit(45, f"Phase 2 — Copying monitor script to {_GUEST_MONITOR} …")
        client.copy_file_from_host_to_guest(
            host_ps1, _GUEST_MONITOR, timeout=60,
        )

        # 2h — Execute the monitor script inside the guest
        self._emit(48, "Phase 2 — Executing monitor.ps1 in guest …")
        try:
            client.run_program_in_guest(
                r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
                ["-ExecutionPolicy", "Bypass", "-File", _GUEST_MONITOR],
                wait=False,
                interactive=True,
                timeout=30,
            )
        except VmrunError as exc:
            logger.warning("Could not launch monitor.ps1 in guest: %s", exc)
        self._monitor_started_at = time.monotonic()

        self._emit(50, "Phase 2 — Sandbox ready, payload executing in guest")

    # ── Phase 3: Interactive Pause ──────────────────────────────────────

    def _phase3_interactive_wait(self) -> SandboxSection:
        """Block the background thread until the analyst clicks Finish.

        The ``interactive_event`` is set by ``finish_interactive_session()``.
        This never freezes the UI because we are on a QThread.
        """
        sb = SandboxSection(enabled=True, executed=False, mode="interactive")

        self._emit(55, "Phase 3 — Awaiting analyst interaction (click Finish when done) …")
        self.interactive_event.wait()  # blocks thread safely

        # Analyst finished — mark sandbox as executed
        sb.executed = True
        sb.exit_code = 0
        sb.highlights.append("Analyst completed interactive session")
        self._emit(65, "Phase 3 — Analyst session finished")
        return sb

    # ── Phase 4: Log Retrieval + Groq AI + VM Revert + Scoring ───────

    def _teardown_kvm(self, client: VmrunClient | None) -> None:
        """Gracefully terminate the vmware-kvm.exe process and stop the VM.

        Called during Phase 4 cleanup to ensure no ghost VMs are left
        running.  Belt-and-suspenders: kill the KVM viewer first, then
        ask vmrun to soft-stop the guest, then hard-stop as fallback.
        """
        # 1. Terminate the KVM viewer process
        if self._kvm_process is not None:
            pid = self._kvm_process.pid
            try:
                self._kvm_process.terminate()
                self._kvm_process.wait(timeout=5)
                print(f"[Orchestrator] KVM process PID={pid} terminated cleanly")
            except subprocess.TimeoutExpired:
                self._kvm_process.kill()
                print(f"[Orchestrator] KVM process PID={pid} force-killed")
            except OSError as exc:
                print(f"[Orchestrator] KVM teardown error: {exc}")
            finally:
                self._kvm_process = None

        # 2. Stop the guest VM via vmrun (soft first, then hard)
        if client is not None:
            try:
                client.stop(hard=False, timeout=30)
                print("[Orchestrator] VM soft-stopped via vmrun")
            except VmrunError:
                try:
                    client.stop(hard=True, timeout=15)
                    print("[Orchestrator] VM hard-stopped via vmrun (fallback)")
                except VmrunError as exc:
                    logger.warning("VM stop failed during teardown: %s", exc)

    @staticmethod
    def _pull_guest_text_file(
        client: VmrunClient,
        guest_path: str,
        host_name: str,
        *,
        timeout_sec: float,
        poll_interval: float = 2.0,
    ) -> str:
        """Poll for a guest text artifact and return its decoded contents."""
        host_path = Path(tempfile.gettempdir()) / host_name
        try:
            host_path.unlink(missing_ok=True)
        except OSError:
            pass

        deadline = time.monotonic() + max(timeout_sec, 1.0)
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                client.copy_file_from_guest_to_host(guest_path, host_path, timeout=60)
                text = host_path.read_text(encoding="utf-8-sig", errors="replace").strip()
                if text:
                    return text
            except (VmrunError, OSError) as exc:
                last_error = exc
            time.sleep(min(poll_interval, max(0.25, deadline - time.monotonic())))

        if last_error is not None:
            logger.warning("Could not pull %s: %s", guest_path, last_error)
        return ""

    def _pull_behavior_log(
        self,
        client: VmrunClient,
        *,
        timeout_sec: float,
    ) -> str:
        """Copy behavior.log from guest to a temp file and return its contents."""
        return self._pull_guest_text_file(
            client,
            _GUEST_BEHAVIOR_LOG,
            "sentinel_behavior.log",
            timeout_sec=timeout_sec,
        )

    def _pull_behavior_report(
        self,
        client: VmrunClient,
        *,
        timeout_sec: float,
    ) -> dict[str, Any] | None:
        """Copy the JSON behavior summary from the guest and parse it."""
        text = self._pull_guest_text_file(
            client,
            _GUEST_BEHAVIOR_REPORT,
            "sentinel_behavior_report.json",
            timeout_sec=timeout_sec,
        )
        if not text:
            return None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning("Behavior report JSON was invalid: %s", exc)
            return None
        if not isinstance(payload, dict):
            logger.warning("Behavior report must be a JSON object, got %s", type(payload).__name__)
            return None
        return payload

    @staticmethod
    def _apply_behavior_log(sandbox: SandboxSection, behavior_log: str) -> None:
        """Parse legacy behavior.log sections into sandbox fields."""
        if not behavior_log:
            return

        section = ""
        processes: list[dict[str, Any]] = []
        network: list[dict[str, Any]] = []
        for raw_line in behavior_log.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            upper = line.upper()
            if upper.startswith("=== PROCESSES"):
                section = "processes"
                continue
            if upper.startswith("=== NETWORK"):
                section = "network"
                continue

            if section == "processes":
                if line.lower() in {"no matching processes captured."}:
                    continue
                if line.lower().startswith(("name", "active")):
                    continue
                processes.append({"raw": line})
            elif section == "network":
                if line.lower() in {"no active network connections captured."}:
                    continue
                if line.lower().startswith("active connections"):
                    continue
                network.append({"raw": line})

        if processes and not sandbox.process_diff:
            sandbox.process_diff = processes[:30]
        if network and not sandbox.network_attempts:
            sandbox.network_attempts = network[:30]

    @staticmethod
    def _apply_behavior_report(
        sandbox: SandboxSection,
        behavior_report: dict[str, Any],
    ) -> None:
        """Map the guest JSON behavior summary into the ScanCenter sandbox schema."""
        processes = behavior_report.get("processes") or []
        if isinstance(processes, list):
            sandbox.process_diff = [
                entry for entry in processes[:30] if isinstance(entry, dict)
            ] or sandbox.process_diff

        network = behavior_report.get("network_connections") or []
        if isinstance(network, list):
            normalized_network: list[dict[str, Any]] = []
            for entry in network[:30]:
                if isinstance(entry, dict):
                    normalized_network.append(entry)
                elif entry:
                    normalized_network.append({"raw": str(entry)})
            if normalized_network:
                sandbox.network_attempts = normalized_network

        errors = behavior_report.get("errors") or []
        if isinstance(errors, list):
            for entry in errors:
                err = str(entry).strip()
                if err and err not in sandbox.errors:
                    sandbox.errors.append(err[:300])

        summary = behavior_report.get("summary") or {}
        if isinstance(summary, dict):
            proc_count = int(summary.get("new_processes") or len(sandbox.process_diff or []))
            net_count = int(summary.get("network_connections") or len(sandbox.network_attempts or []))
            if proc_count:
                sandbox.highlights.append(f"Processes observed: {proc_count}")
            if net_count:
                sandbox.highlights.append(f"Network events observed: {net_count}")
            if summary.get("errors"):
                sandbox.warnings.append(f"Monitor reported {int(summary['errors'])} collection error(s)")

        exit_code = behavior_report.get("sample_exit_code")
        if isinstance(exit_code, int):
            sandbox.exit_code = exit_code

    def _behavior_collection_timeout(self) -> float:
        """Return how long Phase 4 should wait for guest behavior artifacts."""
        if self._monitor_started_at is None:
            return 8.0
        elapsed = max(0.0, time.monotonic() - self._monitor_started_at)
        remaining = max(0.0, float(self._monitor_seconds) - elapsed)
        return max(6.0, min(35.0, remaining + 6.0))

    @staticmethod
    def _build_scan_log(
        clamav: EngineResult,
        sandbox: SandboxSection,
        behavior_log: str,
    ) -> str:
        """Build a comprehensive log string from ClamAV + Sandbox data for the AI."""
        parts: list[str] = []

        # ── ClamAV static scan ───────────────────────────────────────────
        parts.append("== ClamAV Static Scan ==")
        parts.append(f"Status : {clamav.status}")
        parts.append(f"Score  : {clamav.score}/100")
        parts.append(f"Details: {clamav.details or '(none)'}")
        parts.append("")

        # ── Sandbox structured data ──────────────────────────────────────
        parts.append("== Sandbox Dynamic Analysis ==")
        parts.append(f"Enabled  : {sandbox.enabled}")
        parts.append(f"Executed : {sandbox.executed}")
        parts.append(f"Mode     : {sandbox.mode}")
        if sandbox.duration_sec:
            parts.append(f"Duration : {sandbox.duration_sec:.1f}s")
        if sandbox.exit_code is not None:
            parts.append(f"Exit code: {sandbox.exit_code}")
        parts.append("")

        if sandbox.process_diff:
            parts.append("-- New / Modified Processes --")
            for p in sandbox.process_diff[:30]:
                parts.append(f"  {p}")
            parts.append("")

        if sandbox.file_diff:
            parts.append("-- File-System Changes --")
            for f in sandbox.file_diff[:30]:
                parts.append(f"  {f}")
            parts.append("")

        if sandbox.registry_diff:
            parts.append("-- Registry Changes --")
            for r in sandbox.registry_diff[:30]:
                parts.append(f"  {r}")
            parts.append("")

        if sandbox.network_attempts:
            parts.append("-- Network Connections --")
            for n in sandbox.network_attempts[:20]:
                parts.append(f"  {n}")
            parts.append("")

        if sandbox.dns_queries:
            parts.append("-- DNS Queries --")
            for d in sandbox.dns_queries[:20]:
                parts.append(f"  {d}")
            parts.append("")

        if sandbox.persistence_indicators:
            parts.append("-- Persistence Indicators --")
            for pi in sandbox.persistence_indicators[:20]:
                parts.append(f"  {pi}")
            parts.append("")

        if sandbox.security_tampering:
            parts.append("-- Security Tampering --")
            for st in sandbox.security_tampering[:20]:
                parts.append(f"  {st}")
            parts.append("")

        if sandbox.live_metrics:
            parts.append("-- Resource Usage (live_metrics) --")
            for k, v in sandbox.live_metrics.items():
                parts.append(f"  {k}: {v}")
            parts.append("")

        if sandbox.highlights:
            parts.append("-- Highlights --")
            for h in sandbox.highlights:
                parts.append(f"  • {h}")
            parts.append("")

        if sandbox.warnings:
            parts.append("-- Warnings --")
            for w in sandbox.warnings:
                parts.append(f"  ⚠ {w}")
            parts.append("")

        if sandbox.errors:
            parts.append("-- Errors --")
            for e in sandbox.errors:
                parts.append(f"  ✖ {e}")
            parts.append("")

        # ── Raw behavior.log (if pulled from guest) ──────────────────────
        if behavior_log:
            parts.append("== Raw Behavior Log (from guest VM) ==")
            parts.append(behavior_log[:3000])
            parts.append("")

        return "\n".join(parts)

    @staticmethod
    def _deterministic_summary(
        clamav: EngineResult,
        sandbox: SandboxSection,
        scan_log: str,
    ) -> tuple[str, str]:
        """Build a brief + detailed summary without calling an LLM."""
        # ── Brief ────────────────────────────────────────────────────────
        clam_status = clamav.status or "unavailable"
        threat = clamav.details or ""
        sb_status = "completed" if sandbox.executed else ("enabled" if sandbox.enabled else "skipped")

        if clam_status in ("malicious", "detected"):
            brief = f"ClamAV flagged this file as malicious ({threat}). Exercise extreme caution."
        elif clam_status == "clean" and sb_status == "completed":
            brief = "ClamAV found no threats and the sandbox session completed. The file appears safe."
        elif clam_status == "clean":
            brief = "ClamAV found no threats. No dynamic sandbox data was collected."
        else:
            brief = f"ClamAV returned '{clam_status}'. Review the detailed findings below."

        # ── Detailed ─────────────────────────────────────────────────────
        paras: list[str] = []

        # Paragraph 1 — Static
        paras.append(
            f"Static Analysis (ClamAV): The ClamAV engine returned status "
            f"'{clam_status}' with a score of {clamav.score}/100. "
            f"{'Detected threat: ' + threat + '.' if threat and clam_status != 'clean' else 'No signature-based threats were identified.'}"
        )

        # Paragraph 2 — Dynamic
        dyn_parts: list[str] = []
        if sandbox.executed:
            dyn_parts.append(f"The sandbox session ran in '{sandbox.mode}' mode.")
            if sandbox.process_diff:
                dyn_parts.append(f"{len(sandbox.process_diff)} new/modified processes were observed.")
            if sandbox.file_diff:
                dyn_parts.append(f"{len(sandbox.file_diff)} file-system changes recorded.")
            if sandbox.registry_diff:
                dyn_parts.append(f"{len(sandbox.registry_diff)} registry modifications detected.")
            if sandbox.network_attempts:
                dyn_parts.append(f"{len(sandbox.network_attempts)} network connection attempts.")
            if sandbox.dns_queries:
                dyn_parts.append(f"{len(sandbox.dns_queries)} DNS queries issued.")
            if sandbox.persistence_indicators:
                dyn_parts.append(f"Persistence mechanisms detected: {', '.join(sandbox.persistence_indicators[:5])}.")
            if sandbox.security_tampering:
                dyn_parts.append(f"Security tampering observed: {', '.join(sandbox.security_tampering[:5])}.")
            if sandbox.live_metrics:
                cpu = sandbox.live_metrics.get("cpu_percent")
                mem = sandbox.live_metrics.get("mem_mb")
                if cpu is not None or mem is not None:
                    dyn_parts.append(f"Resource usage — CPU: {cpu}%, Memory: {mem} MB." if cpu and mem else "")
            if not dyn_parts[1:]:
                dyn_parts.append("No suspicious behavioral indicators were recorded during the session.")
        else:
            dyn_parts.append("Dynamic analysis was not performed (sandbox was not executed).")
        paras.append("Dynamic Analysis (Sandbox): " + " ".join(dyn_parts))

        # Paragraph 3 — Assessment
        if clam_status in ("malicious", "detected"):
            paras.append(
                "Assessment: This file is flagged as malicious. Quarantine or delete it immediately. "
                "Do not execute it. Run a full system scan if it was already opened."
            )
        elif sandbox.persistence_indicators or sandbox.security_tampering:
            paras.append(
                "Assessment: While ClamAV did not flag the file, the sandbox detected suspicious "
                "behavioral indicators. Treat this file with caution and consider uploading it to "
                "VirusTotal for a second opinion."
            )
        elif clam_status == "clean" and sandbox.executed:
            paras.append(
                "Assessment: Based on both static and dynamic analysis, this file appears safe. "
                "No malicious signatures or suspicious behaviors were detected."
            )
        else:
            paras.append(
                "Assessment: Limited data is available. Only static analysis was performed. "
                "For a more thorough evaluation, re-scan with the sandbox enabled."
            )

        detailed = "\n\n".join(paras)
        return brief, detailed

    @staticmethod
    def _groq_analyze(
        scan_log: str,
        clamav: EngineResult,
        sandbox: SandboxSection,
    ) -> AiExplanation | None:
        """Call Groq REST API to generate a human-readable threat summary.

        Uses ``requests`` directly against the Groq OpenAI-compatible
        endpoint.  Returns an ``AiExplanation`` on success, or ``None``
        if the API key is missing or the network call fails.
        """
        import requests as _req  # local import — only used in this method

        # Ensure .env is loaded (GROQ_API_KEY may live there)
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            print("[Orchestrator] Groq — GROQ_API_KEY not set, skipping AI summary")
            logger.warning("GROQ_API_KEY not set — Groq AI summary skipped")
            return None

        system_prompt = (
            "You are an AI Security Analyst for an EDR (Endpoint Detection & Response) tool. "
            "You receive ClamAV static scan results and sandbox dynamic analysis logs "
            "(process activity, file changes, registry modifications, network connections, "
            "DNS queries, persistence indicators, security tampering, and resource usage). "
            "Based on ALL available evidence, classify the file and explain the risk.\n\n"
            "You must return EXACTLY two sections separated by '|||'.\n"
            "Section 1 (Brief): A 1–2 sentence plain-language summary of what this file does "
            "and whether it is safe, suspicious, or malicious. Mention the malware family/type "
            "if detected (e.g. ransomware, trojan, worm, adware, PUP, cryptominer, RAT, etc.).\n"
            "Section 2 (Detailed): A technical 3-paragraph report covering:\n"
            "  Paragraph 1 — Static analysis findings (ClamAV verdict, signature matches).\n"
            "  Paragraph 2 — Dynamic/behavioral findings (what the file did at runtime: "
            "processes spawned, files written, registry keys set, network calls, persistence "
            "mechanisms, resource usage anomalies).\n"
            "  Paragraph 3 — Overall threat assessment, malware classification, and "
            "recommended actions for the user.\n\n"
            "If no sandbox data is available, base your analysis on ClamAV results only "
            "and note the limitation."
        )

        user_prompt = scan_log[:6000]

        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 800,
            "temperature": 0.3,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        url = "https://api.groq.com/openai/v1/chat/completions"
        print(f"[Orchestrator] Groq — POST {url}  model={payload['model']}")

        try:
            resp = _req.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
        except _req.exceptions.Timeout:
            print("[Orchestrator] Groq — request timed out (30 s)")
            logger.warning("Groq API timed out")
            return None
        except _req.exceptions.HTTPError as exc:
            print(f"[Orchestrator] Groq — HTTP {resp.status_code}: {resp.text[:300]}")
            logger.warning("Groq API HTTP error: %s", exc)
            return None
        except _req.exceptions.RequestException as exc:
            print(f"[Orchestrator] Groq — network error: {exc}")
            logger.warning("Groq API request failed: %s", exc)
            return None

        # Extract the message content
        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            print(f"[Orchestrator] Groq — unexpected response shape: {exc}")
            logger.warning("Groq response parsing failed: %s", exc)
            return None

        print(f"[Orchestrator] Groq — raw response ({len(content)} chars): {content[:200]}")

        # Parse brief ||| detailed sections
        if "|||" in content:
            brief, detailed = content.split("|||", 1)
            brief = brief.strip()
            detailed = detailed.strip()
        else:
            # Fallback: first sentence = brief, rest = detailed
            brief = content.strip().split(".")[0] + "."
            detailed = content.strip()

        # Derive risk_level from brief text
        risk_level = "Unknown"
        brief_upper = brief.upper()
        if any(w in brief_upper for w in ("MALICIOUS", "DANGEROUS", "THREAT", "MALWARE")):
            risk_level = "Critical"
        elif any(w in brief_upper for w in ("SUSPICIOUS", "CAUTION", "UNUSUAL")):
            risk_level = "Medium"
        elif any(w in brief_upper for w in ("SAFE", "CLEAN", "BENIGN", "HARMLESS")):
            risk_level = "Low"

        return AiExplanation(
            one_line_summary=brief,
            risk_level=risk_level,
            top_reasons=[brief],
            what_to_do=["See the full AI report for detailed analysis."],
            raw_response=content,
        )

    # Known-safe tool names (lowercase) — cap score at 60 even if flagged.
    _KNOWN_SAFE_TOOLS: set[str] = {
        "rufus.exe", "7z.exe", "putty.exe", "winscp.exe",
        "sysinternals", "procmon.exe", "autoruns.exe",
        "wireshark.exe", "nmap.exe", "wget.exe", "curl.exe",
    }

    @staticmethod
    def _compute_weighted_score(
        clamav: EngineResult,
        sandbox: SandboxSection,
        file_info: FileInfo | None = None,
    ) -> tuple[int, str, str]:
        """Return (score, risk, label) using strict weighted average.

        Weights — ClamAV 50 %, Sandbox 50 %.  Unavailable sources are
        dropped and remaining weights are redistributed so they still
        sum to 1.0.  Signed binaries / known-safe tools are capped at 60.
        """
        sources: dict[str, tuple[float, int]] = {}  # name -> (weight, score)

        # ClamAV
        clam_score = _safe_int(clamav.score, 0)
        if clamav.status not in ("unavailable", "error", "n/a"):
            sources["clamav"] = (0.50, clam_score)

        # Sandbox
        if sandbox.enabled and sandbox.executed:
            sb_score = 0
            if sandbox.exit_code and sandbox.exit_code != 0:
                sb_score = 60
            if sandbox.errors:
                sb_score = max(sb_score, 70)
            if not sandbox.errors and sandbox.exit_code == 0:
                sb_score = 20  # ran fine, didn't crash — mild suspicion
            sources["sandbox"] = (0.50, sb_score)

        if not sources:
            return (0, "Unknown", "Inconclusive")

        # Strict weighted average with proportional redistribution
        total_w = sum(w for w, _ in sources.values())
        weighted = sum((w / total_w) * s for w, s in sources.values())
        score = max(0, min(100, round(weighted)))

        # ── Signed-binary / known-tool cap ────────────────────────────
        _MAX_SIGNED = 60
        if file_info is not None:
            fname = (file_info.name or "").lower()
            is_known = fname in ScannerOrchestrator._KNOWN_SAFE_TOOLS
            if file_info.signed or is_known:
                if score > _MAX_SIGNED:
                    score = _MAX_SIGNED

        if score <= 19:
            risk, label = "Low", "Clean"
        elif score <= 39:
            risk, label = "Medium", "Suspicious"
        elif score <= 69:
            risk, label = "High", "Likely Malicious"
        else:
            risk, label = "Critical", "Malicious"

        return score, risk, label

    @staticmethod
    def _build_explanation(
        clamav: EngineResult,
        sandbox: SandboxSection,
        score: int,
        risk: str,
    ) -> AiExplanation:
        """Deterministic template-based explanation (no external AI)."""
        if risk in ("High", "Critical"):
            summary = "This file appears dangerous. Do not open or run it."
            actions = [
                "Quarantine or delete the file immediately.",
                "Run a full system scan with your antivirus.",
                "If you already ran it, disconnect from the internet and seek help.",
            ]
        elif risk == "Medium":
            summary = "This file has suspicious characteristics."
            actions = [
                "Avoid running this file until you can verify its source.",
                "Upload it to VirusTotal.com for a second opinion.",
            ]
        else:
            summary = "This file appears safe based on our analysis."
            actions = ["No action needed. The file looks clean."]

        reasons = []
        if clamav.status in ("malicious", "detected"):
            reasons.append(f"ClamAV detected: {clamav.details}")
        elif clamav.status == "clean":
            reasons.append("ClamAV found no threats.")
        if sandbox.executed:
            if sandbox.errors:
                reasons.append("Sandbox execution encountered errors.")
            else:
                reasons.append("Interactive sandbox session completed by analyst.")

        return AiExplanation(
            one_line_summary=summary,
            risk_level=risk,
            top_reasons=reasons or ["Automated analysis completed."],
            what_to_do=actions,
        )

    def _phase4_teardown(
        self,
        client: VmrunClient | None,
        sandbox: SandboxSection,
    ) -> str:
        """Phase 4 — pull behavior log, release embed, teardown KVM, revert VM.

        Returns the raw behavior log text (may be empty).
        """
        behavior_log = ""

        # 4a — Pull behavior.log from guest (before revert!)
        if client is not None:
            self._emit(66, "Phase 4 — Pulling behavior.log from guest …")
            wait_timeout = self._behavior_collection_timeout()
            behavior_report = self._pull_behavior_report(client, timeout_sec=wait_timeout)
            behavior_log = self._pull_behavior_log(
                client,
                timeout_sec=4.0 if behavior_report else wait_timeout,
            )
            if behavior_report:
                self._apply_behavior_report(sandbox, behavior_report)
                sandbox.highlights.append("Structured behavior report collected")
            if behavior_log:
                self._apply_behavior_log(sandbox, behavior_log)
                sandbox.highlights.append(f"Behavior log: {len(behavior_log)} chars")
            if not behavior_report and not behavior_log:
                sandbox.warnings.append("Behavior artifacts were not produced before teardown")

        # 4b — Release embedded VMware window
        self._emit(68, "Phase 4 — Releasing embedded VMware window …")
        self.request_release_embed.emit()
        time.sleep(1)  # allow main thread to process release

        # 4c — Terminate KVM viewer + stop guest VM
        self._emit(70, "Phase 4 — Tearing down KVM process + stopping VM …")
        self._teardown_kvm(client)

        # 4d — Revert VM to clean snapshot
        if client is not None:
            self._emit(72, "Phase 4 — Reverting VM to clean snapshot …")
            try:
                client.revert_to_snapshot(timeout=180)
            except VmrunError as exc:
                logger.warning("VM revert during teardown failed: %s", exc)

        return behavior_log

    def _phase5_groq_summary(
        self,
        behavior_log: str,
        clamav: EngineResult,
        sandbox: SandboxSection,
    ) -> tuple[AiExplanation | None, str, str]:
        """Phase 5 — call Groq REST API for an AI-generated threat summary.

        Returns (AiExplanation | None, brief_text, detailed_text).
        """
        ai: AiExplanation | None = None
        brief = ""
        detailed = ""

        self._emit(75, "Phase 5 — Building scan log for Groq AI …")
        scan_log = self._build_scan_log(clamav, sandbox, behavior_log)

        self._emit(76, "Phase 5 — Sending scan data to Groq AI …")
        ai = self._groq_analyze(scan_log, clamav, sandbox)
        if ai and ai.raw_response:
            self._emit(80, f"Phase 5 — Groq verdict: {ai.risk_level}")
            raw = ai.raw_response
            if "|||" in raw:
                brief, detailed = raw.split("|||", 1)
                brief = brief.strip()
                detailed = detailed.strip()
            else:
                brief = ai.one_line_summary
                detailed = raw
        elif ai:
            self._emit(80, f"Phase 5 — Groq verdict: {ai.risk_level}")
            brief = ai.one_line_summary
        else:
            self._emit(80, "Phase 5 — Groq unavailable, building deterministic summary")
            # Deterministic fallback so the UI always shows something
            brief, detailed = self._deterministic_summary(clamav, sandbox, scan_log)
        return ai, brief, detailed

    def _phase6_score_and_finalize(
        self,
        clamav: EngineResult,
        sandbox: SandboxSection,
        file_info: FileInfo | None,
        ai: AiExplanation | None,
    ) -> tuple[VerdictSection, AiExplanation]:
        """Phase 6 — deterministic scoring, redirect back to File Scanner."""

        # 6a — Redirect analyst back to File Scanner
        self._emit(82, "Phase 6 — Redirecting to File Scanner …")
        self.request_ui_change.emit("scan-tool")

        # 6b — Compute deterministic score
        self._emit(85, "Phase 6 — Computing weighted score …")
        score, risk, label = self._compute_weighted_score(
            clamav, sandbox, file_info=file_info,
        )

        verdict = VerdictSection(
            score=score,
            risk=risk,
            label=label,
            confidence=70 if sandbox.executed else 45,
            reasons=[
                f"ClamAV: {clamav.status}",
                f"Sandbox: {'analyst session completed' if sandbox.executed else 'not executed'}",
            ],
            breakdown={
                "clamav":  {"score": clamav.score, "available": clamav.status != "unavailable"},
                "sandbox": {"score": score, "available": sandbox.enabled},
            },
        )

        if ai is None:
            ai = self._build_explanation(clamav, sandbox, score, risk)
        return verdict, ai

    # ── QThread entry point ──────────────────────────────────────────────

    def run(self) -> None:  # noqa: C901  (pipeline is inherently sequential)
        """Execute the full 6-phase interactive pipeline.

        Phase 1: ClamAV + SHA-256
        Phase 2: VM setup, payload delivery, UI redirect to Theater
        Phase 3: interactive_event.wait() — analyst works in VM
        Phase 4: Pull behavior.log, release embed, teardown KVM, revert VM
        Phase 5: Groq AI summary via REST API
        Phase 6: Deterministic scoring, emit scan_complete
        """
        report = V3Report()
        report.file = FileInfo(
            path=str(self._file_path),
            name=self._file_path.name,
        )

        try:
            # Validate input
            if not self._file_path.exists():
                raise FileNotFoundError(f"File not found: {self._file_path}")
            report.file.size_bytes = self._file_path.stat().st_size
            sha256 = hashlib.sha256(self._file_path.read_bytes()).hexdigest()
            report.file.sha256 = sha256

            # ── Phase 1: ClamAV ──────────────────────────────────────────
            clamav_result = self._phase1_clamav()
            report.static.engines.append(clamav_result)

            # ── Phase 2 + 3: Interactive Sandbox ─────────────────────────
            sandbox = SandboxSection(enabled=False)
            client = None
            try:
                config = load_sandbox_config()
                if config.host_ready and config.guest_ready:
                    client = VmrunClient(config)
                    self._phase2_prepare_sandbox(config, client)
                    sandbox = self._phase3_interactive_wait()
                else:
                    self._emit(65, "Sandbox skipped — VMware not configured")
                    sandbox.warnings.append(
                        "Sandbox skipped: vmrun or guest credentials not configured"
                    )
            except VmrunError as exc:
                print(f"[Orchestrator] Sandbox pipeline error: {exc}")
                self._emit(65, f"Sandbox error: {str(exc)[:80]}")
                sandbox.enabled = True
                sandbox.errors.append(str(exc)[:300])
            except Exception as exc:
                print(f"[Orchestrator] Sandbox unexpected error: {exc}")
                self._emit(65, f"Sandbox error: {exc}")
                sandbox.errors.append(str(exc)[:300])

            report.sandbox = sandbox

            # ── Phase 4: Teardown ─────────────────────────────────────
            behavior_log = self._phase4_teardown(client, sandbox)

            # ── Phase 5: Groq AI Summary ─────────────────────────────────
            ai = None
            brief_text = ""
            detailed_text = ""
            try:
                ai, brief_text, detailed_text = self._phase5_groq_summary(
                    behavior_log, clamav_result, sandbox,
                )
            except Exception as phase5_exc:
                print(f"[Orchestrator] Phase 5 error (non-fatal): {phase5_exc}")
                self._emit(80, "Phase 5 — AI summary failed, using fallback")
                brief_text, detailed_text = self._deterministic_summary(
                    clamav_result, sandbox,
                    self._build_scan_log(clamav_result, sandbox, behavior_log),
                )

            # ── Phase 6: Score + Finalize ────────────────────────────────
            verdict, ai = self._phase6_score_and_finalize(
                clamav_result, sandbox, file_info=report.file, ai=ai,
            )
            report.verdict = verdict
            report.ai_explanation = ai

            self._emit(100, f"Scan complete — {verdict.risk} ({verdict.score}/100)")
            self.scan_complete.emit(report.to_dict(), brief_text, detailed_text)

        except FileNotFoundError as exc:
            self._emit(100, f"Error: {exc}")
            report.verdict.risk = "Unknown"
            report.verdict.label = str(exc)
            self.scan_complete.emit(report.to_dict(), "", "")

        except Exception as exc:
            print(f"[Orchestrator] FATAL: {exc}")
            self._emit(100, f"Fatal error: {exc}")
            report.verdict.risk = "Unknown"
            report.verdict.label = f"Pipeline error: {str(exc)[:120]}"
            self.scan_complete.emit(report.to_dict(), "", "")
