"""
Sandbox Controller - Automated Dynamic Analysis

Orchestrates sandbox execution for behavioral analysis:
- VirtualBox VM integration (preferred)
- Windows Sandbox (.wsb) support
- Process/file/registry monitoring
- Automated report collection

100% Local - No network required.
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Subprocess flags for Windows
_IS_WINDOWS = os.name == "nt"
_SUBPROCESS_FLAGS = 0x08000000 if _IS_WINDOWS else 0


@dataclass
class SandboxResult:
    """Result from sandbox execution."""
    success: bool
    status: str  # completed, timeout, error, not_available
    duration: int  # seconds
    
    # Behavioral data
    processes: List[Dict[str, Any]] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    files_deleted: List[str] = field(default_factory=list)
    registry_modified: List[str] = field(default_factory=list)
    network_connections: List[str] = field(default_factory=list)
    
    # Raw data
    raw_report: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class SandboxController:
    """
    Controls sandbox execution for dynamic analysis.
    
    Supported methods:
    1. VirtualBox VM (preferred, requires setup)
    2. Windows Sandbox (Windows Pro/Enterprise only)
    
    Security:
    - Samples are NEVER executed on the host
    - All execution happens in isolated environment
    - VM snapshots are restored before each run
    """
    
    # Configuration
    DEFAULT_TIMEOUT = 120  # seconds
    VM_NAME = "Sentinel_Sandbox"
    SNAPSHOT_NAME = "Clean"
    SHARED_FOLDER = "Sentinel_Shared"
    
    def __init__(self):
        """Initialize the sandbox controller."""
        self._vboxmanage_path: Optional[str] = None
        self._vbox_available = False
        self._wsb_available = False
        
        self._detect_capabilities()
    
    def _detect_capabilities(self) -> None:
        """Detect available sandbox methods."""
        # Check VirtualBox
        self._vboxmanage_path = self._find_vboxmanage()
        if self._vboxmanage_path:
            self._vbox_available = self._check_vm_exists()
        
        # Check Windows Sandbox
        if _IS_WINDOWS:
            self._wsb_available = self._check_windows_sandbox()
        
        logger.info(f"Sandbox capabilities: VBox={self._vbox_available}, WSB={self._wsb_available}")
    
    def _find_vboxmanage(self) -> Optional[str]:
        """Find VBoxManage executable."""
        # Check PATH first
        path = shutil.which("VBoxManage") or shutil.which("VBoxManage.exe")
        if path:
            return path
        
        # Common installation paths
        if _IS_WINDOWS:
            common_paths = [
                r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
                r"C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe",
            ]
            for p in common_paths:
                if os.path.exists(p):
                    return p
        else:
            common_paths = [
                "/usr/bin/VBoxManage",
                "/usr/local/bin/VBoxManage",
            ]
            for p in common_paths:
                if os.path.exists(p):
                    return p
        
        return None
    
    def _check_vm_exists(self) -> bool:
        """Check if the Sentinel sandbox VM exists."""
        if not self._vboxmanage_path:
            return False
        
        try:
            result = subprocess.run(
                [self._vboxmanage_path, "list", "vms"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=_SUBPROCESS_FLAGS if _IS_WINDOWS else 0,
            )
            return self.VM_NAME in result.stdout
        except Exception:
            return False
    
    def _check_windows_sandbox(self) -> bool:
        """Check if Windows Sandbox is available."""
        try:
            # Check if Windows Sandbox feature is enabled
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-WindowsOptionalFeature -Online -FeatureName Containers-DisposableClientVM | Select-Object -ExpandProperty State"],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=_SUBPROCESS_FLAGS,
            )
            return "Enabled" in result.stdout
        except Exception:
            return False
    
    @property
    def is_available(self) -> bool:
        """Check if any sandbox method is available."""
        return self._vbox_available or self._wsb_available
    
    @property
    def available_methods(self) -> List[str]:
        """Get list of available sandbox methods."""
        methods = []
        if self._vbox_available:
            methods.append("VirtualBox")
        if self._wsb_available:
            methods.append("Windows Sandbox")
        return methods
    
    def run_sample(self, file_path: str, timeout: int = DEFAULT_TIMEOUT) -> SandboxResult:
        """
        Run a sample in the sandbox and collect behavioral data.
        
        Args:
            file_path: Path to the sample file
            timeout: Maximum execution time in seconds
            
        Returns:
            SandboxResult with behavioral analysis
        """
        if not os.path.exists(file_path):
            return SandboxResult(
                success=False,
                status="error",
                duration=0,
                error="File not found"
            )
        
        if not self.is_available:
            return SandboxResult(
                success=False,
                status="not_available",
                duration=0,
                error="No sandbox method available. Install VirtualBox or enable Windows Sandbox."
            )
        
        # Prefer VirtualBox over Windows Sandbox
        if self._vbox_available:
            return self._run_in_virtualbox(file_path, timeout)
        elif self._wsb_available:
            return self._run_in_windows_sandbox(file_path, timeout)
        
        return SandboxResult(
            success=False,
            status="not_available",
            duration=0,
            error="No sandbox available"
        )
    
    def _run_in_virtualbox(self, file_path: str, timeout: int) -> SandboxResult:
        """
        Run sample in VirtualBox VM.
        
        Prerequisites:
        1. VM named 'Sentinel_Sandbox' must exist
        2. Snapshot named 'Clean' must exist
        3. Guest Additions installed in VM
        4. Sandbox agent script must be in VM
        """
        start_time = time.time()
        
        try:
            # Step 1: Restore snapshot
            logger.info("Restoring VM snapshot...")
            success, error = self._vbox_restore_snapshot()
            if not success:
                return SandboxResult(
                    success=False, status="error", duration=0,
                    error=f"Failed to restore snapshot: {error}"
                )
            
            # Step 2: Start VM (headless)
            logger.info("Starting sandbox VM...")
            success, error = self._vbox_start_vm()
            if not success:
                return SandboxResult(
                    success=False, status="error", duration=0,
                    error=f"Failed to start VM: {error}"
                )
            
            # Wait for VM to boot
            time.sleep(30)
            
            # Step 3: Copy sample to VM
            logger.info("Copying sample to VM...")
            sample_name = os.path.basename(file_path)
            success, error = self._vbox_copy_to_vm(file_path, f"C:\\Sandbox\\{sample_name}")
            if not success:
                self._vbox_stop_vm()
                return SandboxResult(
                    success=False, status="error", duration=0,
                    error=f"Failed to copy sample: {error}"
                )
            
            # Step 4: Run sandbox agent
            logger.info("Running sandbox agent...")
            success, error = self._vbox_run_agent(sample_name, timeout)
            
            # Step 5: Collect results
            results = self._vbox_collect_results()
            
            # Step 6: Stop VM
            logger.info("Stopping sandbox VM...")
            self._vbox_stop_vm()
            
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
                    raw_report=results
                )
            else:
                return SandboxResult(
                    success=True,
                    status="completed",
                    duration=duration,
                    error="No behavioral data collected"
                )
            
        except Exception as e:
            logger.error(f"VirtualBox sandbox error: {e}")
            self._vbox_stop_vm()
            return SandboxResult(
                success=False,
                status="error",
                duration=int(time.time() - start_time),
                error=str(e)
            )
    
    def _vbox_restore_snapshot(self) -> Tuple[bool, str]:
        """Restore VM to clean snapshot."""
        try:
            result = subprocess.run(
                [self._vboxmanage_path, "snapshot", self.VM_NAME, "restore", self.SNAPSHOT_NAME],
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=_SUBPROCESS_FLAGS if _IS_WINDOWS else 0,
            )
            return result.returncode == 0, result.stderr
        except Exception as e:
            return False, str(e)
    
    def _vbox_start_vm(self) -> Tuple[bool, str]:
        """Start VM in headless mode."""
        try:
            result = subprocess.run(
                [self._vboxmanage_path, "startvm", self.VM_NAME, "--type", "headless"],
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=_SUBPROCESS_FLAGS if _IS_WINDOWS else 0,
            )
            return result.returncode == 0, result.stderr
        except Exception as e:
            return False, str(e)
    
    def _vbox_stop_vm(self) -> Tuple[bool, str]:
        """Stop VM (poweroff)."""
        try:
            result = subprocess.run(
                [self._vboxmanage_path, "controlvm", self.VM_NAME, "poweroff"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=_SUBPROCESS_FLAGS if _IS_WINDOWS else 0,
            )
            return result.returncode == 0, result.stderr
        except Exception as e:
            return False, str(e)
    
    def _vbox_copy_to_vm(self, host_path: str, guest_path: str) -> Tuple[bool, str]:
        """Copy file from host to VM."""
        try:
            result = subprocess.run(
                [self._vboxmanage_path, "guestcontrol", self.VM_NAME, "copyto",
                 host_path, guest_path,
                 "--username", "sandbox", "--password", "sandbox"],
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=_SUBPROCESS_FLAGS if _IS_WINDOWS else 0,
            )
            return result.returncode == 0, result.stderr
        except Exception as e:
            return False, str(e)
    
    def _vbox_run_agent(self, sample_name: str, timeout: int) -> Tuple[bool, str]:
        """Run the sandbox agent in VM."""
        try:
            # Run agent script that monitors and executes sample
            agent_cmd = f"C:\\Sandbox\\sandbox_agent.py --sample C:\\Sandbox\\{sample_name} --timeout {timeout}"
            
            result = subprocess.run(
                [self._vboxmanage_path, "guestcontrol", self.VM_NAME, "run",
                 "--exe", "python.exe",
                 "--username", "sandbox", "--password", "sandbox",
                 "--wait-stdout", "--wait-stderr",
                 "--", agent_cmd],
                capture_output=True,
                text=True,
                timeout=timeout + 60,
                creationflags=_SUBPROCESS_FLAGS if _IS_WINDOWS else 0,
            )
            return result.returncode == 0, result.stderr
        except Exception as e:
            return False, str(e)
    
    def _vbox_collect_results(self) -> Optional[Dict[str, Any]]:
        """Collect results from VM shared folder."""
        try:
            # Copy report from VM
            report_path = tempfile.mktemp(suffix=".json")
            
            result = subprocess.run(
                [self._vboxmanage_path, "guestcontrol", self.VM_NAME, "copyfrom",
                 "C:\\Sandbox\\report.json", report_path,
                 "--username", "sandbox", "--password", "sandbox"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=_SUBPROCESS_FLAGS if _IS_WINDOWS else 0,
            )
            
            if result.returncode == 0 and os.path.exists(report_path):
                with open(report_path, "r") as f:
                    data = json.load(f)
                os.unlink(report_path)
                return data
        except Exception as e:
            logger.debug(f"Failed to collect results: {e}")
        
        return None
    
    def _run_in_windows_sandbox(self, file_path: str, timeout: int) -> SandboxResult:
        """
        Run sample in Windows Sandbox.
        
        Creates a .wsb configuration that:
        1. Maps a temp folder as read/write
        2. Copies sample and agent to sandbox
        3. Runs agent via LogonCommand
        4. Collects results from mapped folder
        """
        start_time = time.time()
        
        try:
            # Create temp working directory
            work_dir = Path(tempfile.mkdtemp(prefix="sentinel_sandbox_"))
            sample_name = os.path.basename(file_path)
            
            # Copy sample to work directory
            sample_dest = work_dir / sample_name
            shutil.copy2(file_path, sample_dest)
            
            # Copy agent script
            agent_src = Path(__file__).parent.parent.parent / "tools" / "sandbox_agent" / "agent.py"
            if agent_src.exists():
                shutil.copy2(agent_src, work_dir / "agent.py")
            else:
                # Create minimal agent inline
                self._create_minimal_agent(work_dir / "agent.py")
            
            # Create .wsb configuration
            wsb_config = self._create_wsb_config(work_dir, sample_name, timeout)
            wsb_path = work_dir / "sandbox.wsb"
            
            with open(wsb_path, "w") as f:
                f.write(wsb_config)
            
            # Launch Windows Sandbox
            logger.info("Starting Windows Sandbox...")
            process = subprocess.Popen(
                ["cmd", "/c", str(wsb_path)],
                creationflags=_SUBPROCESS_FLAGS,
            )
            
            # Wait for completion (sandbox should auto-close)
            try:
                process.wait(timeout=timeout + 120)
            except subprocess.TimeoutExpired:
                process.kill()
            
            duration = int(time.time() - start_time)
            
            # Collect results
            report_path = work_dir / "report.json"
            if report_path.exists():
                with open(report_path, "r") as f:
                    results = json.load(f)
                
                # Cleanup
                shutil.rmtree(work_dir, ignore_errors=True)
                
                return SandboxResult(
                    success=True,
                    status="completed",
                    duration=duration,
                    processes=results.get("processes", []),
                    files_created=results.get("files_created", []),
                    files_modified=results.get("files_modified", []),
                    registry_modified=results.get("registry_modified", []),
                    network_connections=results.get("network_connections", []),
                    raw_report=results
                )
            else:
                shutil.rmtree(work_dir, ignore_errors=True)
                return SandboxResult(
                    success=True,
                    status="completed",
                    duration=duration,
                    error="No results collected (sample may not have executed)"
                )
            
        except Exception as e:
            logger.error(f"Windows Sandbox error: {e}")
            return SandboxResult(
                success=False,
                status="error",
                duration=int(time.time() - start_time),
                error=str(e)
            )
    
    def _create_wsb_config(self, work_dir: Path, sample_name: str, timeout: int) -> str:
        """Create Windows Sandbox configuration XML."""
        return f"""<Configuration>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>{work_dir}</HostFolder>
      <SandboxFolder>C:\\Sandbox</SandboxFolder>
      <ReadOnly>false</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>python C:\\Sandbox\\agent.py --sample "C:\\Sandbox\\{sample_name}" --timeout {timeout} --output C:\\Sandbox\\report.json</Command>
  </LogonCommand>
  <Networking>Disable</Networking>
  <vGPU>Disable</vGPU>
  <AudioInput>Disable</AudioInput>
  <VideoInput>Disable</VideoInput>
  <ProtectedClient>Enable</ProtectedClient>
  <PrinterRedirection>Disable</PrinterRedirection>
  <ClipboardRedirection>Disable</ClipboardRedirection>
  <MemoryInMB>2048</MemoryInMB>
</Configuration>"""
    
    def _create_minimal_agent(self, path: Path) -> None:
        """Create a minimal sandbox agent script."""
        agent_code = '''#!/usr/bin/env python3
"""Minimal Sandbox Agent for Sentinel"""
import argparse
import json
import os
import subprocess
import sys
import time
import psutil

def monitor_and_run(sample_path, timeout, output_path):
    results = {
        "status": "completed",
        "processes": [],
        "files_created": [],
        "files_modified": [],
        "network_connections": [],
    }
    
    # Get baseline
    baseline_procs = {p.pid for p in psutil.process_iter()}
    
    # Run sample
    try:
        proc = subprocess.Popen(
            sample_path,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        
        start = time.time()
        while time.time() - start < timeout:
            if proc.poll() is not None:
                break
            
            # Collect new processes
            for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                if p.pid not in baseline_procs:
                    try:
                        results["processes"].append({
                            "pid": p.pid,
                            "name": p.info['name'],
                            "cmdline": ' '.join(p.info['cmdline'] or [])
                        })
                    except:
                        pass
            
            time.sleep(2)
        
        proc.terminate()
        
    except Exception as e:
        results["error"] = str(e)
    
    # Write results
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Exit sandbox
    time.sleep(5)
    sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", required=True)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--output", default="report.json")
    args = parser.parse_args()
    
    monitor_and_run(args.sample, args.timeout, args.output)
'''
        with open(path, 'w') as f:
            f.write(agent_code)
    
    def get_setup_instructions(self) -> str:
        """Get instructions for setting up sandbox."""
        return """
# Sentinel Sandbox Setup Instructions

## Option 1: VirtualBox (Recommended)

1. Install VirtualBox: https://www.virtualbox.org/
2. Create a Windows VM named "Sentinel_Sandbox"
3. Install Windows and Guest Additions
4. Create user "sandbox" with password "sandbox"
5. Install Python 3 and psutil in the VM
6. Create folder C:\\Sandbox
7. Copy sandbox_agent.py to C:\\Sandbox\\
8. Take a snapshot named "Clean"

## Option 2: Windows Sandbox (Windows Pro/Enterprise)

1. Enable Windows Sandbox feature:
   - Open Settings > Apps > Optional Features
   - Click "More Windows features"
   - Enable "Windows Sandbox"
   - Restart computer

2. No additional setup required - Sentinel will configure it automatically

## Notes

- VirtualBox provides more isolation and better analysis
- Windows Sandbox is easier to set up but less detailed
- Both methods run samples with network disabled
- Sandbox is optional - static analysis works without it
"""


def get_sandbox_controller() -> SandboxController:
    """Get a sandbox controller instance."""
    return SandboxController()
