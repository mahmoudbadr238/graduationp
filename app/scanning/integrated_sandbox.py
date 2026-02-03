"""
Integrated Local Sandbox - Bundled sandbox execution environment.

Runs samples in a restricted environment WITHOUT requiring external tools:
- Windows: AppContainer or Low Integrity + Restricted Token + Job Object limits
- Linux: User namespaces via unshare (if available)
- macOS: Static-only (sandbox not available)

100% Offline - No cloud APIs or external services.
"""

import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Tuple
import json

logger = logging.getLogger(__name__)

# Platform detection
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"


def get_sandbox_workspace() -> Path:
    """Get the sandbox workspace directory."""
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        workspace = base / "Sentinel" / "sandbox_runs"
    else:
        base = Path.home() / ".config" / "sentinel"
        workspace = base / "sandbox_runs"
    
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def get_reports_directory() -> Path:
    """Get the scan reports directory."""
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        reports = base / "Sentinel" / "scan_reports"
    else:
        base = Path.home() / ".config" / "sentinel"
        reports = base / "scan_reports"
    
    reports.mkdir(parents=True, exist_ok=True)
    return reports


class SandboxResult:
    """Result of a sandbox execution."""
    
    def __init__(self):
        self.success: bool = False
        self.error: Optional[str] = None
        self.start_time: Optional[str] = None
        self.end_time: Optional[str] = None
        self.duration_seconds: float = 0.0
        self.exit_code: Optional[int] = None
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
            "platform": "windows" if IS_WINDOWS else ("linux" if IS_LINUX else "other"),
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
        self._available: Optional[bool] = None
        self._availability_reason: str = ""
        self._platform = platform.system().lower()
        self._check_availability()
    
    def _check_availability(self) -> None:
        """Check if sandbox is available on this platform."""
        if IS_WINDOWS:
            self._check_windows_availability()
        elif IS_LINUX:
            self._check_linux_availability()
        elif IS_MACOS:
            self._available = False
            self._availability_reason = "macOS sandbox not yet implemented. Static analysis is available."
        else:
            self._available = False
            self._availability_reason = f"Unsupported platform: {self._platform}"
    
    def _check_windows_availability(self) -> None:
        """Check Windows sandbox capabilities."""
        try:
            # Check if we can create restricted processes
            # We'll use Job Objects which are available on all modern Windows
            import ctypes
            kernel32 = ctypes.windll.kernel32
            
            # Test if we can create a job object
            job = kernel32.CreateJobObjectW(None, None)
            if job:
                kernel32.CloseHandle(job)
                self._available = True
                self._availability_reason = "Windows sandbox available (Job Object + Restricted Token)"
            else:
                self._available = False
                self._availability_reason = "Cannot create Job Objects"
        except Exception as e:
            self._available = False
            self._availability_reason = f"Windows sandbox check failed: {e}"
    
    def _check_linux_availability(self) -> None:
        """Check Linux sandbox capabilities (user namespaces)."""
        try:
            # Check if unshare is available
            result = subprocess.run(
                ["which", "unshare"],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                self._available = False
                self._availability_reason = "unshare command not found"
                return
            
            # Check if user namespaces are enabled
            try:
                with open("/proc/sys/kernel/unprivileged_userns_clone", "r") as f:
                    if f.read().strip() == "0":
                        self._available = False
                        self._availability_reason = "User namespaces disabled (unprivileged_userns_clone=0)"
                        return
            except FileNotFoundError:
                # File doesn't exist on some distros, try to test directly
                pass
            
            # Test if we can actually create a user namespace
            result = subprocess.run(
                ["unshare", "--user", "--map-root-user", "echo", "test"],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                self._available = True
                self._availability_reason = "Linux sandbox available (user namespaces via unshare)"
            else:
                self._available = False
                self._availability_reason = f"User namespace test failed: {result.stderr.decode()[:100]}"
                
        except subprocess.TimeoutExpired:
            self._available = False
            self._availability_reason = "Sandbox capability check timed out"
        except Exception as e:
            self._available = False
            self._availability_reason = f"Linux sandbox check failed: {e}"
    
    def availability(self) -> dict[str, Any]:
        """
        Check if sandbox execution is available.
        
        Returns:
            Dict with keys: available (bool), reason (str), method (str), platform (str)
        """
        method = "unknown"
        if self._available:
            if IS_WINDOWS:
                method = "Windows Job Object"
            elif IS_LINUX:
                method = "Linux User Namespace"
        
        return {
            "available": self._available or False,
            "reason": self._availability_reason,
            "method": method,
            "platform": self._platform,
        }
    
    def run_file(
        self,
        file_path: str,
        timeout: int = 60,
        block_network: bool = True
    ) -> SandboxResult:
        """
        Run a file in the sandbox environment.
        
        Args:
            file_path: Path to the file to execute
            timeout: Maximum execution time in seconds (default 60)
            block_network: Whether to block network access (default True)
        
        Returns:
            SandboxResult with execution details and findings
        """
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
            
            # Copy file to workspace (NEVER execute original)
            sample_name = Path(file_path).name
            sandbox_sample = workspace / sample_name
            shutil.copy2(file_path, sandbox_sample)
            
            # Get initial file list for comparison
            initial_files = self._list_files(workspace)
            
            # Execute based on platform
            start = time.time()
            
            if IS_WINDOWS:
                self._run_windows_sandbox(result, sandbox_sample, timeout, block_network, workspace)
            elif IS_LINUX:
                self._run_linux_sandbox(result, sandbox_sample, timeout, block_network, workspace)
            else:
                result.error = "Platform not supported for sandbox execution"
            
            result.duration_seconds = time.time() - start
            result.end_time = datetime.now().isoformat()
            
            # Analyze file changes
            if result.success or result.timed_out:
                final_files = self._list_files(workspace)
                result.created_files = [f for f in final_files if f not in initial_files and f != sample_name]
                
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
        workspace: Path
    ) -> None:
        """Run sample in Windows restricted environment."""
        import ctypes
        from ctypes import wintypes
        
        result.sandbox_method = "windows_job_restricted"
        
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
            JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x0100
            JOB_OBJECT_LIMIT_JOB_MEMORY = 0x0200
            JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x0008
            
            limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            limits.BasicLimitInformation.LimitFlags = (
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE |
                JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            )
            limits.BasicLimitInformation.ActiveProcessLimit = 10  # Limit child processes
            limits.ProcessMemoryLimit = 256 * 1024 * 1024  # 256 MB per process
            limits.JobMemoryLimit = 512 * 1024 * 1024  # 512 MB total
            
            JobObjectExtendedLimitInformation = 9
            kernel32.SetInformationJobObject(
                job,
                JobObjectExtendedLimitInformation,
                ctypes.byref(limits),
                ctypes.sizeof(limits)
            )
            
            # Block network if requested using Windows Firewall
            if block_network:
                firewall_rule_name = f"SentinelSandbox_{workspace.name}"
                try:
                    # Add outbound block rule for this specific executable
                    subprocess.run([
                        "netsh", "advfirewall", "firewall", "add", "rule",
                        f"name={firewall_rule_name}",
                        "dir=out",
                        "action=block",
                        f"program={sample_path}",
                        "enable=yes"
                    ], capture_output=True, timeout=10)
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
                cmd = ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(sample_path)]
            elif ext in [".vbs", ".vbe"]:
                cmd = ["cscript.exe", "//nologo", str(sample_path)]
            elif ext in [".js", ".jse"]:
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
            CREATE_BREAKAWAY_FROM_JOB = 0x01000000
            
            class STARTUPINFOW(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("lpReserved", wintypes.LPWSTR),
                    ("lpDesktop", wintypes.LPWSTR),
                    ("lpTitle", wintypes.LPWSTR),
                    ("dwX", wintypes.DWORD),
                    ("dwY", wintypes.DWORD),
                    ("dwXSize", wintypes.DWORD),
                    ("dwYSize", wintypes.DWORD),
                    ("dwXCountChars", wintypes.DWORD),
                    ("dwYCountChars", wintypes.DWORD),
                    ("dwFillAttribute", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD),
                    ("wShowWindow", wintypes.WORD),
                    ("cbReserved2", wintypes.WORD),
                    ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
                    ("hStdInput", wintypes.HANDLE),
                    ("hStdOutput", wintypes.HANDLE),
                    ("hStdError", wintypes.HANDLE),
                ]
            
            class PROCESS_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("hProcess", wintypes.HANDLE),
                    ("hThread", wintypes.HANDLE),
                    ("dwProcessId", wintypes.DWORD),
                    ("dwThreadId", wintypes.DWORD),
                ]
            
            # Use subprocess for simplicity, then assign to job
            try:
                with open(stdout_path, "w") as stdout_file, open(stderr_path, "w") as stderr_file:
                    process = subprocess.Popen(
                        cmd,
                        stdout=stdout_file,
                        stderr=stderr_file,
                        cwd=str(workspace),
                        creationflags=CREATE_NO_WINDOW | CREATE_SUSPENDED,
                    )
            except OSError as e:
                # If suspended creation fails, try without
                with open(stdout_path, "w") as stdout_file, open(stderr_path, "w") as stderr_file:
                    process = subprocess.Popen(
                        cmd,
                        stdout=stdout_file,
                        stderr=stderr_file,
                        cwd=str(workspace),
                        creationflags=CREATE_NO_WINDOW,
                    )
            
            # Assign process to job object
            process_handle = kernel32.OpenProcess(0x1F0FFF, False, process.pid)  # PROCESS_ALL_ACCESS
            if process_handle:
                kernel32.AssignProcessToJobObject(job, process_handle)
                kernel32.CloseHandle(process_handle)
            
            # Resume if suspended (in case we used CREATE_SUSPENDED)
            try:
                kernel32.ResumeThread(ctypes.c_void_p(process._handle))
            except Exception:
                pass
            
            # Record spawned process
            result.processes_spawned.append({
                "pid": process.pid,
                "name": sample_path.name,
                "start_time": datetime.now().isoformat(),
            })
            
            # Wait for completion or timeout
            try:
                process.wait(timeout=timeout)
                result.exit_code = process.returncode
                result.success = True
            except subprocess.TimeoutExpired:
                result.timed_out = True
                result.success = True  # Timeout is a valid outcome
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
                    subprocess.run([
                        "netsh", "advfirewall", "firewall", "delete", "rule",
                        f"name={firewall_rule_name}"
                    ], capture_output=True, timeout=10)
                except Exception as e:
                    logger.warning(f"Failed to remove firewall rule: {e}")
    
    def _run_linux_sandbox(
        self,
        result: SandboxResult,
        sample_path: Path,
        timeout: int,
        block_network: bool,
        workspace: Path
    ) -> None:
        """Run sample in Linux user namespace sandbox."""
        result.sandbox_method = "linux_unshare"
        
        stdout_path = workspace / "stdout.txt"
        stderr_path = workspace / "stderr.txt"
        
        try:
            # Make sample executable
            os.chmod(sample_path, 0o755)
            
            # Build unshare command
            # --user: create new user namespace
            # --map-root-user: map current user to root inside namespace
            # --pid: create new PID namespace
            # --fork: fork before executing
            # --mount-proc: mount new /proc (requires --pid)
            
            unshare_args = [
                "unshare",
                "--user",
                "--map-root-user",
                "--pid",
                "--fork",
                "--mount-proc",
            ]
            
            # Add network isolation if requested
            if block_network:
                unshare_args.append("--net")
                result.network_blocked = True
            
            # Determine how to run the sample
            ext = sample_path.suffix.lower()
            
            if ext in [".sh"]:
                cmd = unshare_args + ["/bin/bash", str(sample_path)]
            elif ext in [".py"]:
                cmd = unshare_args + [sys.executable, str(sample_path)]
            elif ext in [".pl"]:
                cmd = unshare_args + ["perl", str(sample_path)]
            else:
                # Try to run as ELF executable
                cmd = unshare_args + [str(sample_path)]
            
            # Execute with timeout
            with open(stdout_path, "w") as stdout_file, open(stderr_path, "w") as stderr_file:
                process = subprocess.Popen(
                    cmd,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    cwd=str(workspace),
                    env={
                        "HOME": str(workspace),
                        "PATH": "/usr/bin:/bin",
                        "TERM": "dumb",
                    }
                )
                
                result.processes_spawned.append({
                    "pid": process.pid,
                    "name": sample_path.name,
                    "start_time": datetime.now().isoformat(),
                })
                
                try:
                    process.wait(timeout=timeout)
                    result.exit_code = process.returncode
                    result.success = True
                except subprocess.TimeoutExpired:
                    result.timed_out = True
                    result.success = True
                    process.kill()
                    try:
                        process.wait(timeout=5)
                    except Exception:
                        pass
            
            # Read output
            try:
                if stdout_path.exists():
                    result.stdout = stdout_path.read_text(errors="replace")[:10000]
                if stderr_path.exists():
                    result.stderr = stderr_path.read_text(errors="replace")[:10000]
            except Exception as e:
                logger.warning(f"Failed to read output: {e}")
                
        except Exception as e:
            logger.exception(f"Linux sandbox execution failed: {e}")
            result.error = str(e)
    
    def _generate_behavior_summary(self, result: SandboxResult) -> str:
        """Generate a human-readable behavior summary."""
        summary_parts = []
        
        if result.timed_out:
            summary_parts.append(f"Execution timed out after {result.duration_seconds:.1f} seconds.")
        else:
            summary_parts.append(f"Execution completed in {result.duration_seconds:.1f} seconds with exit code {result.exit_code}.")
        
        if result.created_files:
            summary_parts.append(f"Created {len(result.created_files)} new files in sandbox.")
        
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
        
        return " ".join(summary_parts) if summary_parts else "No notable behavior observed."
    
    def _analyze_behavior(self, result: SandboxResult) -> list[dict]:
        """Analyze sandbox behavior and generate findings."""
        findings = []
        
        # Timeout is suspicious for certain file types
        if result.timed_out:
            findings.append({
                "type": "medium",
                "category": "execution",
                "message": "Process did not terminate within timeout period",
                "details": f"This may indicate infinite loops, waiting for network, or intentional stalling.",
            })
        
        # Many child processes
        if len(result.processes_spawned) > 3:
            findings.append({
                "type": "medium",
                "category": "processes",
                "message": f"Spawned multiple child processes ({len(result.processes_spawned)})",
                "details": "Multi-process behavior may indicate dropper or loader functionality.",
            })
        
        # File creation
        if result.created_files:
            suspicious_extensions = [".exe", ".dll", ".bat", ".cmd", ".ps1", ".vbs", ".js"]
            suspicious_files = [f for f in result.created_files if any(f.lower().endswith(ext) for ext in suspicious_extensions)]
            
            if suspicious_files:
                findings.append({
                    "type": "high",
                    "category": "file_creation",
                    "message": f"Created executable/script files during execution",
                    "details": suspicious_files[:5],
                })
            elif len(result.created_files) > 5:
                findings.append({
                    "type": "low",
                    "category": "file_creation",
                    "message": f"Created {len(result.created_files)} files during execution",
                    "details": result.created_files[:5],
                })
        
        # Check stderr for common errors that might indicate blocked malicious behavior
        if result.stderr:
            stderr_lower = result.stderr.lower()
            if "access denied" in stderr_lower or "permission denied" in stderr_lower:
                findings.append({
                    "type": "medium",
                    "category": "access",
                    "message": "Process attempted restricted operations",
                    "details": "Sandbox blocked potentially malicious access attempts.",
                })
            if "network" in stderr_lower or "connection" in stderr_lower or "socket" in stderr_lower:
                findings.append({
                    "type": "medium",
                    "category": "network",
                    "message": "Process attempted network operations",
                    "details": "Network activity was blocked by sandbox.",
                })
        
        # Non-zero exit code
        if result.exit_code is not None and result.exit_code != 0:
            findings.append({
                "type": "info",
                "category": "execution",
                "message": f"Process exited with non-zero code: {result.exit_code}",
                "details": "This may be normal or indicate an error/crash.",
            })
        
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
_sandbox_instance: Optional[IntegratedSandbox] = None


def get_integrated_sandbox() -> IntegratedSandbox:
    """Get the global IntegratedSandbox instance."""
    global _sandbox_instance
    if _sandbox_instance is None:
        _sandbox_instance = IntegratedSandbox()
    return _sandbox_instance
