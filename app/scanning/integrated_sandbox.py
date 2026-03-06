"""
Integrated Local Sandbox - Windows-only, Job Object restricted execution.

Runs samples in a restricted Windows environment using:
- Windows Job Object (memory + CPU limits, kill-on-close)
- Optional network blocking via Windows Firewall rule
- File activity monitoring

For full VMware behavioral analysis see app/sandbox_vmware/.
100% Offline - No cloud APIs or external services.
"""

import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_SANDBOX_CPU_CAP_PERCENT = 50
INTERNAL_SANDBOX_ARTIFACTS = {
    "stdout.txt",
    "stderr.txt",
    "preview.mp4",
    "session.json",
}

# Windows-only — this module does not support Linux or macOS
IS_WINDOWS = True


def get_sandbox_workspace() -> Path:
    """Get the sandbox workspace directory (Windows: %APPDATA%/Sentinel/sandbox_runs)."""
    base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    workspace = base / "Sentinel" / "sandbox_runs"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def get_reports_directory() -> Path:
    """Get the scan reports directory (Windows: %APPDATA%/Sentinel/scan_reports)."""
    base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    reports = base / "Sentinel" / "scan_reports"
    reports.mkdir(parents=True, exist_ok=True)
    return reports


class SandboxResult:
    """Result of a sandbox execution."""

    def __init__(self):
        self.success: bool = False
        self.error: str | None = None
        self.start_time: str | None = None
        self.end_time: str | None = None
        self.duration_seconds: float = 0.0
        self.exit_code: int | None = None
        self.timed_out: bool = False
        self.stdout: str = ""
        self.stderr: str = ""
        self.sandbox_method: str = "unknown"
        self.network_blocked: bool = False
        self.workspace_path: str = ""
        self.created_files: list[str] = []
        self.modified_files: list[str] = []
        self.processes_spawned: list[dict] = []
        self.findings: list[dict] = []
        self.behavior_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "error_message": self.error,  # Scoring expects error_message
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "stdout": self.stdout[:5000] if self.stdout else "",
            "stderr": self.stderr[:5000] if self.stderr else "",
            "sandbox_method": self.sandbox_method,
            "network_blocked": self.network_blocked,
            "workspace_path": self.workspace_path,
            "platform": "windows",
            # Scoring module expects these field names
            "files_created": self.created_files[:50],
            "files_modified": self.modified_files[:50],
            "files_deleted": [],  # We don't track deletions yet
            "child_processes": self.processes_spawned[:20],
            "registry_modifications": [],  # Windows-specific, not tracked yet
            "network_connections": [],  # Not tracked in basic sandbox
            "peak_cpu_percent": 0,  # Not tracked yet
            "peak_memory_mb": 0,  # Not tracked yet
            "findings": self.findings,
            "behavior_summary": self.behavior_summary,
        }


class IntegratedSandbox:
    """
    Integrated local sandbox that runs samples in a restricted environment.

    This sandbox is bundled with Sentinel and works immediately after installation.
    No external tools (VirtualBox, firejail, etc.) are required.
    """

    def __init__(self):
        self._available: bool | None = None
        self._availability_reason: str = ""
        self._windows_job_available: bool = False
        self._check_availability()

    def _check_availability(self) -> None:
        """Check if Job Object sandbox is available (Windows-only)."""
        self._check_windows_availability()

    def _check_windows_availability(self) -> None:
        """Check Windows Job Object sandbox availability."""
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            job = kernel32.CreateJobObjectW(None, None)
            if job:
                kernel32.CloseHandle(job)
                self._windows_job_available = True
                self._available = True
                self._availability_reason = (
                    "Windows sandbox available (Job Object + restricted execution)"
                )
            else:
                self._windows_job_available = False
                self._available = False
                self._availability_reason = (
                    "Job Object creation failed — sandbox unavailable"
                )
            logger.info("Integrated sandbox: JobObject=%s", self._windows_job_available)
        except Exception as exc:
            self._available = False
            self._availability_reason = f"Windows sandbox check failed: {exc}"

    def availability(self) -> dict[str, Any]:
        """
        Check if the Job Object sandbox is available.

        Returns:
            Dict with keys: available (bool), reason (str), method (str), platform (str)
        """
        method = "Windows Job Object" if self._available else "unavailable"
        return {
            "available": self._available or False,
            "reason": self._availability_reason,
            "method": method,
            "platform": "windows",
            "selected_engine": "job_object",
            "job_object_available": self._windows_job_available,
        }

    @staticmethod
    def _sandbox_cpu_cap_percent() -> int:
        """
        Return sandbox CPU cap (0 disables cap).

        Controlled by SENTINEL_SANDBOX_CPU_CAP_PERCENT, defaulting to 50.
        """
        raw = os.environ.get(
            "SENTINEL_SANDBOX_CPU_CAP_PERCENT",
            str(DEFAULT_SANDBOX_CPU_CAP_PERCENT),
        ).strip()
        try:
            value = int(raw)
        except ValueError:
            value = DEFAULT_SANDBOX_CPU_CAP_PERCENT
        return max(0, min(100, value))

    @staticmethod
    def _should_use_inplace_execution(original_path: Path) -> bool:
        """
        Heuristic: many desktop apps need adjacent files and fail when exe-only copied.

        When this returns True we execute in-place (still under job object restrictions)
        so GUI apps can launch and preview can attach to their real window.
        """
        if original_path.suffix.lower() not in {".exe", ".com", ".scr", ".msi"}:
            return False

        # Explicit opt-in override for advanced users.
        if os.environ.get("SENTINEL_SANDBOX_INPLACE_COMPAT", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }:
            return True

        parent = original_path.parent
        parent_lower = str(parent).lower()
        trusted_location_tokens = (
            "program files",
            "riot games",
            "steam",
            "epic games",
            "ubisoft",
            "origin games",
            "battle.net",
            "gog galaxy",
        )
        if not any(token in parent_lower for token in trusted_location_tokens):
            return False

        try:
            sibling_files = sum(
                1
                for item in parent.iterdir()
                if item.is_file() and item.name.lower() != original_path.name.lower()
            )
        except OSError:
            return False

        return sibling_files >= 5

    def _emit_event(self, event_type: str, data: dict) -> None:
        """Emit a sandbox event via callback if available."""
        if self._event_callback:
            try:
                self._event_callback(event_type, data)
            except Exception as e:
                logger.warning(f"Event callback error: {e}")

    def _is_cancelled(self) -> bool:
        """Check if sandbox execution was cancelled."""
        try:
            return self._cancel_check()
        except Exception:
            return False

    def run_file(
        self,
        file_path: str,
        timeout: int = 60,
        block_network: bool = True,
        event_callback: callable = None,
        cancel_check: callable = None,
    ) -> SandboxResult:
        """
        Run a file in the sandbox environment.

        Args:
            file_path: Path to the file to execute
            timeout: Maximum execution time in seconds (default 60)
            block_network: Whether to block network access (default True)
            event_callback: Optional callback for live events: fn(event_type, data)
            cancel_check: Optional callable returning True if cancelled

        Returns:
            SandboxResult with execution details and findings
        """
        self._event_callback = (
            event_callback
            if event_callback is not None
            else (lambda *args, **kwargs: None)
        )
        self._cancel_check = (
            cancel_check if cancel_check is not None else (lambda: False)
        )
        result = SandboxResult()
        result.start_time = datetime.now().isoformat()
        result.network_blocked = block_network

        # Validate file exists
        if not os.path.isfile(file_path):
            result.error = f"File not found: {file_path}"
            result.end_time = datetime.now().isoformat()
            return result

        # Check availability
        if not self._available:
            result.error = f"Sandbox not available: {self._availability_reason}"
            result.end_time = datetime.now().isoformat()
            return result

        try:
            # Create sandbox workspace
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            workspace = get_sandbox_workspace() / timestamp
            workspace.mkdir(parents=True, exist_ok=True)
            result.workspace_path = str(workspace)

            # Always keep a workspace copy; may run original in compatibility mode.
            sample_name = Path(file_path).name
            original_sample = Path(file_path)
            sandbox_sample = workspace / sample_name
            shutil.copy2(file_path, sandbox_sample)

            # Compatibility mode: dependency-heavy desktop apps may not run from exe-only copy.
            execution_sample = sandbox_sample
            execution_cwd = workspace
            if self._should_use_inplace_execution(original_sample):
                execution_sample = original_sample
                execution_cwd = original_sample.parent
                logger.info(
                    "Sandbox compatibility mode enabled (in-place execution): %s",
                    original_sample,
                )

            # Get initial file list for comparison
            initial_files = self._list_files(workspace)

            # Execute with Job Object containment
            start = time.time()

            self._run_windows_sandbox(
                result,
                execution_sample,
                timeout,
                block_network,
                workspace,
                execution_cwd=execution_cwd,
                inplace_compat=(execution_sample == original_sample),
            )

            result.duration_seconds = time.time() - start
            result.end_time = datetime.now().isoformat()

            # Analyze file changes
            if result.success or result.timed_out:
                final_files = self._list_files(workspace)
                result.created_files = [
                    f
                    for f in final_files
                    if f not in initial_files
                    and f != sample_name
                    and Path(f).name.lower() not in INTERNAL_SANDBOX_ARTIFACTS
                ]

                # Generate behavior summary
                result.behavior_summary = self._generate_behavior_summary(result)

                # Generate findings
                result.findings = self._analyze_behavior(result)

        except Exception as e:
            logger.exception(f"Sandbox execution failed: {e}")
            result.error = str(e)
            result.end_time = datetime.now().isoformat()

        return result

    def _list_files(self, directory: Path) -> set[str]:
        """List all files in a directory recursively."""
        files = set()
        try:
            for item in directory.rglob("*"):
                if item.is_file():
                    files.add(str(item.relative_to(directory)))
        except Exception:
            pass
        return files

    def _run_windows_sandbox(
        self,
        result: SandboxResult,
        sample_path: Path,
        timeout: int,
        block_network: bool,
        workspace: Path,
        execution_cwd: Path | None = None,
        inplace_compat: bool = False,
    ) -> None:
        """Run sample in Windows restricted environment."""
        import ctypes
        from ctypes import wintypes

        result.sandbox_method = (
            "windows_job_restricted_inplace"
            if inplace_compat
            else "windows_job_restricted"
        )

        stdout_path = workspace / "stdout.txt"
        stderr_path = workspace / "stderr.txt"

        kernel32 = ctypes.windll.kernel32

        # Create a Job Object with restrictions
        job = None
        process = None
        firewall_rule_name = None

        try:
            # Create Job Object
            job = kernel32.CreateJobObjectW(None, None)
            if not job:
                result.error = f"Failed to create Job Object: {ctypes.get_last_error()}"
                return

            # Set Job Object limits
            class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]

            class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("IoInfo", ctypes.c_byte * 24),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]

            # JOB_OBJECT_LIMIT flags
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
            JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x0008

            limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            limits.BasicLimitInformation.LimitFlags = (
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            )
            limits.BasicLimitInformation.ActiveProcessLimit = (
                10  # Limit child processes
            )
            limits.ProcessMemoryLimit = 256 * 1024 * 1024  # 256 MB per process
            limits.JobMemoryLimit = 512 * 1024 * 1024  # 512 MB total

            JobObjectExtendedLimitInformation = 9
            kernel32.SetInformationJobObject(
                job,
                JobObjectExtendedLimitInformation,
                ctypes.byref(limits),
                ctypes.sizeof(limits),
            )

            # Optionally cap CPU usage to reduce host impact during detonation.
            cpu_cap_percent = self._sandbox_cpu_cap_percent()
            if cpu_cap_percent > 0:

                class JOBOBJECT_CPU_RATE_CONTROL_INFORMATION(ctypes.Structure):
                    _fields_ = [
                        ("ControlFlags", wintypes.DWORD),
                        ("CpuRate", wintypes.DWORD),
                    ]

                JOB_OBJECT_CPU_RATE_CONTROL_ENABLE = 0x1
                JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP = 0x4
                JobObjectCpuRateControlInformation = 15

                cpu_limit = JOBOBJECT_CPU_RATE_CONTROL_INFORMATION()
                cpu_limit.ControlFlags = (
                    JOB_OBJECT_CPU_RATE_CONTROL_ENABLE
                    | JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP
                )
                cpu_limit.CpuRate = int(cpu_cap_percent * 100)

                applied = kernel32.SetInformationJobObject(
                    job,
                    JobObjectCpuRateControlInformation,
                    ctypes.byref(cpu_limit),
                    ctypes.sizeof(cpu_limit),
                )
                if applied:
                    logger.info("Sandbox CPU cap applied: %s%%", cpu_cap_percent)
                else:
                    logger.debug(
                        "Could not apply sandbox CPU cap (error=%s)",
                        ctypes.get_last_error(),
                    )

            # Block network if requested using Windows Firewall
            if block_network:
                firewall_rule_name = f"SentinelSandbox_{workspace.name}"
                try:
                    # Add outbound block rule for this specific executable
                    subprocess.run(
                        [
                            "netsh",
                            "advfirewall",
                            "firewall",
                            "add",
                            "rule",
                            f"name={firewall_rule_name}",
                            "dir=out",
                            "action=block",
                            f"program={sample_path}",
                            "enable=yes",
                        ],
                        capture_output=True,
                        timeout=10,
                    )
                except Exception as e:
                    logger.warning(f"Failed to add firewall rule: {e}")
                    firewall_rule_name = None

            # Determine how to run the sample
            ext = sample_path.suffix.lower()

            if ext in [".exe", ".com", ".scr"]:
                cmd = [str(sample_path)]
            elif ext in [".bat", ".cmd"]:
                cmd = ["cmd.exe", "/c", str(sample_path)]
            elif ext in [".ps1"]:
                cmd = [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(sample_path),
                ]
            elif ext in [".vbs", ".vbe"] or ext in [".js", ".jse"]:
                cmd = ["cscript.exe", "//nologo", str(sample_path)]
            elif ext in [".py"]:
                cmd = [sys.executable, str(sample_path)]
            elif ext in [".dll"]:
                # For DLLs, use rundll32 with a common entry point
                cmd = ["rundll32.exe", str(sample_path) + ",DllMain"]
            else:
                # Try to run directly
                cmd = [str(sample_path)]

            # Create process with CREATE_SUSPENDED flag
            CREATE_SUSPENDED = 0x00000004
            CREATE_NO_WINDOW = 0x08000000
            BELOW_NORMAL_PRIORITY_CLASS = 0x00004000

            # Validate flags are integers
            creationflags = 0
            if isinstance(CREATE_NO_WINDOW, int):
                creationflags |= CREATE_NO_WINDOW
            if isinstance(CREATE_SUSPENDED, int):
                creationflags |= CREATE_SUSPENDED
            if isinstance(BELOW_NORMAL_PRIORITY_CLASS, int):
                creationflags |= BELOW_NORMAL_PRIORITY_CLASS

            launch_cwd = execution_cwd or workspace

            try:
                with (
                    open(stdout_path, "w") as stdout_file,
                    open(stderr_path, "w") as stderr_file,
                ):
                    process = subprocess.Popen(
                        cmd,
                        stdout=stdout_file,
                        stderr=stderr_file,
                        cwd=str(launch_cwd),
                        creationflags=creationflags,
                    )
            except OSError:
                # If suspended creation fails, try without
                with (
                    open(stdout_path, "w") as stdout_file,
                    open(stderr_path, "w") as stderr_file,
                ):
                    process = subprocess.Popen(
                        cmd,
                        stdout=stdout_file,
                        stderr=stderr_file,
                        cwd=str(launch_cwd),
                        creationflags=CREATE_NO_WINDOW
                        if isinstance(CREATE_NO_WINDOW, int)
                        else 0,
                    )

            # Assign process to job object
            process_handle = kernel32.OpenProcess(
                0x1F0FFF, False, process.pid
            )  # PROCESS_ALL_ACCESS
            if process_handle:
                kernel32.AssignProcessToJobObject(job, process_handle)
                kernel32.CloseHandle(process_handle)

            # Resume if suspended (in case we used CREATE_SUSPENDED)
            try:
                kernel32.ResumeThread(ctypes.c_void_p(process._handle))
            except Exception:
                pass

            # Record spawned process
            result.processes_spawned.append(
                {
                    "pid": process.pid,
                    "name": sample_path.name,
                    "start_time": datetime.now().isoformat(),
                }
            )

            # Emit process start event
            self._emit_event(
                "process_start",
                {
                    "pid": process.pid,
                    "name": sample_path.name,
                    "path": str(sample_path),
                    "timestamp": datetime.now().isoformat(),
                },
            )

            # Wait for completion or timeout using polling (non-blocking)
            # This allows the UI to remain responsive and supports live events
            poll_interval = 0.5  # Check every 500ms for smoother updates
            elapsed = 0.0
            last_file_check = 0.0
            file_check_interval = 1.0  # Check for new files every 1 second
            known_files = set(self._list_files(workspace))

            while elapsed < timeout:
                # Check for cancellation
                if self._is_cancelled():
                    result.error = "Sandbox execution cancelled by user"
                    kernel32.TerminateJobObject(job, 1)
                    process.kill()
                    try:
                        process.wait(timeout=5)
                    except Exception:
                        pass
                    self._emit_event(
                        "session_cancelled", {"timestamp": datetime.now().isoformat()}
                    )
                    break

                retcode = process.poll()
                if retcode is not None:
                    # Process finished
                    result.exit_code = retcode
                    result.success = True
                    self._emit_event(
                        "process_exit",
                        {
                            "pid": process.pid,
                            "exit_code": retcode,
                            "timestamp": datetime.now().isoformat(),
                        },
                    )
                    break

                # Periodically check for new files (file activity detection)
                if elapsed - last_file_check >= file_check_interval:
                    current_files = set(self._list_files(workspace))
                    new_files = current_files - known_files
                    for new_file in new_files:
                        if Path(new_file).name.lower() in INTERNAL_SANDBOX_ARTIFACTS:
                            continue
                        self._emit_event(
                            "file_create",
                            {
                                "path": str(workspace / new_file),
                                "name": new_file,
                                "timestamp": datetime.now().isoformat(),
                            },
                        )
                        result.created_files.append(new_file)
                    known_files = current_files
                    last_file_check = elapsed

                time.sleep(poll_interval)
                elapsed += poll_interval
            else:
                # Timeout reached
                result.timed_out = True
                result.success = True  # Timeout is a valid outcome
                self._emit_event("timeout", {"timestamp": datetime.now().isoformat()})
                # Kill via job object
                kernel32.TerminateJobObject(job, 1)
                process.kill()
                try:
                    process.wait(timeout=5)
                except Exception:
                    pass

            # Read output files
            try:
                if stdout_path.exists():
                    result.stdout = stdout_path.read_text(errors="replace")[:10000]
                if stderr_path.exists():
                    result.stderr = stderr_path.read_text(errors="replace")[:10000]
            except Exception as e:
                logger.warning(f"Failed to read output: {e}")

        except Exception as e:
            logger.exception(f"Windows sandbox execution failed: {e}")
            result.error = str(e)

        finally:
            # Cleanup
            if job:
                kernel32.CloseHandle(job)

            if firewall_rule_name:
                try:
                    subprocess.run(
                        [
                            "netsh",
                            "advfirewall",
                            "firewall",
                            "delete",
                            "rule",
                            f"name={firewall_rule_name}",
                        ],
                        capture_output=True,
                        timeout=10,
                    )
                except Exception as e:
                    logger.warning(f"Failed to remove firewall rule: {e}")

    def _generate_behavior_summary(self, result: SandboxResult) -> str:
        """Generate a human-readable behavior summary."""
        summary_parts = []

        if result.timed_out:
            summary_parts.append(
                f"Execution timed out after {result.duration_seconds:.1f} seconds."
            )
        else:
            summary_parts.append(
                f"Execution completed in {result.duration_seconds:.1f} seconds with exit code {result.exit_code}."
            )

        if result.created_files:
            summary_parts.append(
                f"Created {len(result.created_files)} new files in sandbox."
            )

        if len(result.processes_spawned) > 1:
            summary_parts.append(f"Spawned {len(result.processes_spawned)} processes.")

        if result.network_blocked:
            summary_parts.append("Network access was blocked during execution.")

        if result.stdout:
            lines = result.stdout.strip().split("\n")
            if lines and lines[0]:
                summary_parts.append(f"Output: {lines[0][:100]}...")

        if result.stderr:
            lines = result.stderr.strip().split("\n")
            if lines and lines[0]:
                summary_parts.append(f"Errors: {lines[0][:100]}...")

        return (
            " ".join(summary_parts)
            if summary_parts
            else "No notable behavior observed."
        )

    def _analyze_behavior(self, result: SandboxResult) -> list[dict]:
        """Analyze sandbox behavior and generate findings."""
        findings = []

        # Timeout is suspicious for certain file types
        if result.timed_out:
            findings.append(
                {
                    "type": "medium",
                    "category": "execution",
                    "message": "Process did not terminate within timeout period",
                    "details": "This may indicate infinite loops, waiting for network, or intentional stalling.",
                }
            )

        # Many child processes
        if len(result.processes_spawned) > 3:
            findings.append(
                {
                    "type": "medium",
                    "category": "processes",
                    "message": f"Spawned multiple child processes ({len(result.processes_spawned)})",
                    "details": "Multi-process behavior may indicate dropper or loader functionality.",
                }
            )

        # File creation
        if result.created_files:
            suspicious_extensions = [
                ".exe",
                ".dll",
                ".bat",
                ".cmd",
                ".ps1",
                ".vbs",
                ".js",
            ]
            suspicious_files = [
                f
                for f in result.created_files
                if any(f.lower().endswith(ext) for ext in suspicious_extensions)
            ]

            if suspicious_files:
                findings.append(
                    {
                        "type": "high",
                        "category": "file_creation",
                        "message": "Created executable/script files during execution",
                        "details": suspicious_files[:5],
                    }
                )
            elif len(result.created_files) > 5:
                findings.append(
                    {
                        "type": "low",
                        "category": "file_creation",
                        "message": f"Created {len(result.created_files)} files during execution",
                        "details": result.created_files[:5],
                    }
                )

        # Check stderr for common errors that might indicate blocked malicious behavior
        if result.stderr:
            stderr_lower = result.stderr.lower()
            if "access denied" in stderr_lower or "permission denied" in stderr_lower:
                findings.append(
                    {
                        "type": "medium",
                        "category": "access",
                        "message": "Process attempted restricted operations",
                        "details": "Sandbox blocked potentially malicious access attempts.",
                    }
                )
            if (
                "network" in stderr_lower
                or "connection" in stderr_lower
                or "socket" in stderr_lower
            ):
                findings.append(
                    {
                        "type": "medium",
                        "category": "network",
                        "message": "Process attempted network operations",
                        "details": "Network activity was blocked by sandbox.",
                    }
                )

        # Non-zero exit code
        if result.exit_code is not None and result.exit_code != 0:
            findings.append(
                {
                    "type": "info",
                    "category": "execution",
                    "message": f"Process exited with non-zero code: {result.exit_code}",
                    "details": "This may be normal or indicate an error/crash.",
                }
            )

        return findings

    def cleanup_old_workspaces(self, max_age_hours: int = 24) -> int:
        """Clean up old sandbox workspaces."""
        cleaned = 0
        workspace_root = get_sandbox_workspace()
        cutoff = time.time() - (max_age_hours * 3600)

        try:
            for item in workspace_root.iterdir():
                if item.is_dir():
                    try:
                        if item.stat().st_mtime < cutoff:
                            shutil.rmtree(item)
                            cleaned += 1
                    except Exception as e:
                        logger.warning(f"Failed to clean {item}: {e}")
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")

        return cleaned


# Global singleton
_sandbox_instance: IntegratedSandbox | None = None


def get_integrated_sandbox() -> IntegratedSandbox:
    """Get the global IntegratedSandbox instance."""
    global _sandbox_instance
    if _sandbox_instance is None:
        _sandbox_instance = IntegratedSandbox()
    return _sandbox_instance
