#!/usr/bin/env python3
"""
Sentinel Sandbox Agent - VM-Side Behavioral Monitoring

This script runs INSIDE the sandbox VM to:
1. Monitor system activity (processes, files, registry, network)
2. Execute the sample in a controlled manner
3. Collect behavioral data
4. Generate report for host collection

Requirements (install in VM):
- Python 3.8+
- psutil
- wmi (Windows only)

Usage:
  python agent.py --sample C:\Sandbox\malware.exe --timeout 60 --output C:\Sandbox\report.json
"""

import argparse
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    import psutil
except ImportError:
    print("ERROR: psutil not installed. Run: pip install psutil")
    sys.exit(1)

# Windows-specific imports
IS_WINDOWS = os.name == "nt"
if IS_WINDOWS:
    try:
        import wmi
        HAS_WMI = True
    except ImportError:
        HAS_WMI = False
        print("WARNING: wmi not installed, registry monitoring limited")
else:
    HAS_WMI = False


class BehavioralMonitor:
    """
    Monitors system behavior during sample execution.
    
    Collects:
    - Process creation/termination
    - File system changes
    - Registry modifications (Windows)
    - Network connections
    """
    
    def __init__(self):
        self.monitoring = False
        self.start_time: Optional[datetime] = None
        
        # Baseline state (captured before execution)
        self._baseline_procs: Set[int] = set()
        self._baseline_files: Dict[str, float] = {}  # path -> mtime
        self._baseline_connections: Set[tuple] = set()
        
        # Collected events
        self.processes: List[Dict[str, Any]] = []
        self.files_created: List[str] = []
        self.files_modified: List[str] = []
        self.files_deleted: List[str] = []
        self.registry_modified: List[str] = []
        self.network_connections: List[Dict[str, Any]] = []
        
        # Monitoring directories
        self.watch_dirs = [
            os.environ.get("TEMP", "C:\\Temp"),
            os.environ.get("USERPROFILE", "C:\\Users"),
            "C:\\Windows\\System32",
            "C:\\Windows\\SysWOW64",
            "C:\\ProgramData",
        ] if IS_WINDOWS else [
            "/tmp",
            os.path.expanduser("~"),
            "/var",
        ]
        
        # Lock for thread safety
        self._lock = threading.Lock()
    
    def capture_baseline(self) -> None:
        """Capture baseline system state before execution."""
        print("[*] Capturing baseline state...")
        
        # Processes
        for proc in psutil.process_iter(['pid']):
            try:
                self._baseline_procs.add(proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Files in watched directories (limited depth)
        for watch_dir in self.watch_dirs:
            self._scan_directory(watch_dir, self._baseline_files, depth=2)
        
        # Network connections
        for conn in psutil.net_connections(kind='inet'):
            try:
                self._baseline_connections.add((
                    conn.laddr.ip if conn.laddr else None,
                    conn.laddr.port if conn.laddr else None,
                    conn.raddr.ip if conn.raddr else None,
                    conn.raddr.port if conn.raddr else None,
                    conn.status,
                ))
            except:
                pass
        
        print(f"[*] Baseline: {len(self._baseline_procs)} processes, "
              f"{len(self._baseline_files)} files, "
              f"{len(self._baseline_connections)} connections")
    
    def _scan_directory(self, path: str, result: Dict[str, float], depth: int = 2) -> None:
        """Recursively scan directory for files."""
        if depth <= 0:
            return
        
        try:
            for entry in os.scandir(path):
                try:
                    if entry.is_file(follow_symlinks=False):
                        result[entry.path] = entry.stat().st_mtime
                    elif entry.is_dir(follow_symlinks=False):
                        self._scan_directory(entry.path, result, depth - 1)
                except (PermissionError, OSError):
                    pass
        except (PermissionError, OSError):
            pass
    
    def start_monitoring(self) -> None:
        """Start background monitoring threads."""
        self.monitoring = True
        self.start_time = datetime.now()
        
        # Start monitoring threads
        self._process_thread = threading.Thread(target=self._monitor_processes, daemon=True)
        self._file_thread = threading.Thread(target=self._monitor_files, daemon=True)
        self._network_thread = threading.Thread(target=self._monitor_network, daemon=True)
        
        self._process_thread.start()
        self._file_thread.start()
        self._network_thread.start()
        
        if IS_WINDOWS and HAS_WMI:
            self._registry_thread = threading.Thread(target=self._monitor_registry, daemon=True)
            self._registry_thread.start()
        
        print("[*] Monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop all monitoring threads."""
        self.monitoring = False
        time.sleep(1)  # Allow threads to finish
        print("[*] Monitoring stopped")
    
    def _monitor_processes(self) -> None:
        """Monitor for new processes."""
        while self.monitoring:
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'ppid', 'exe', 'create_time']):
                    if proc.pid in self._baseline_procs:
                        continue
                    
                    try:
                        info = proc.info
                        
                        with self._lock:
                            # Check if we already recorded this process
                            if not any(p['pid'] == proc.pid for p in self.processes):
                                self.processes.append({
                                    'pid': proc.pid,
                                    'name': info['name'],
                                    'cmdline': ' '.join(info['cmdline'] or []),
                                    'parent_pid': info['ppid'],
                                    'exe': info['exe'],
                                    'time': datetime.now().isoformat(),
                                })
                                print(f"[+] New process: {info['name']} (PID: {proc.pid})")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except Exception as e:
                print(f"[-] Process monitor error: {e}")
            
            time.sleep(0.5)
    
    def _monitor_files(self) -> None:
        """Monitor for file changes."""
        while self.monitoring:
            try:
                current_files: Dict[str, float] = {}
                for watch_dir in self.watch_dirs:
                    self._scan_directory(watch_dir, current_files, depth=2)
                
                with self._lock:
                    # Check for new files
                    for path, mtime in current_files.items():
                        if path not in self._baseline_files:
                            if path not in self.files_created:
                                self.files_created.append(path)
                                print(f"[+] File created: {path}")
                        elif mtime > self._baseline_files[path]:
                            if path not in self.files_modified:
                                self.files_modified.append(path)
                                print(f"[+] File modified: {path}")
                    
                    # Check for deleted files
                    for path in self._baseline_files:
                        if path not in current_files:
                            if path not in self.files_deleted:
                                self.files_deleted.append(path)
                                print(f"[+] File deleted: {path}")
            except Exception as e:
                print(f"[-] File monitor error: {e}")
            
            time.sleep(2)
    
    def _monitor_network(self) -> None:
        """Monitor for new network connections."""
        while self.monitoring:
            try:
                for conn in psutil.net_connections(kind='inet'):
                    try:
                        key = (
                            conn.laddr.ip if conn.laddr else None,
                            conn.laddr.port if conn.laddr else None,
                            conn.raddr.ip if conn.raddr else None,
                            conn.raddr.port if conn.raddr else None,
                            conn.status,
                        )
                        
                        if key not in self._baseline_connections:
                            with self._lock:
                                # Check if we already recorded this connection
                                conn_dict = {
                                    'local_addr': f"{key[0]}:{key[1]}" if key[0] else None,
                                    'remote_addr': f"{key[2]}:{key[3]}" if key[2] else None,
                                    'status': key[4],
                                    'time': datetime.now().isoformat(),
                                }
                                
                                if not any(c['local_addr'] == conn_dict['local_addr'] and 
                                          c['remote_addr'] == conn_dict['remote_addr'] 
                                          for c in self.network_connections):
                                    self.network_connections.append(conn_dict)
                                    print(f"[+] Network: {conn_dict['local_addr']} -> {conn_dict['remote_addr']}")
                    except:
                        pass
            except Exception as e:
                print(f"[-] Network monitor error: {e}")
            
            time.sleep(1)
    
    def _monitor_registry(self) -> None:
        """Monitor for registry changes (Windows only)."""
        if not IS_WINDOWS or not HAS_WMI:
            return
        
        # Common persistence locations
        registry_keys = [
            r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run",
            r"HKEY_LOCAL_MACHINE\Software\Microsoft\Windows\CurrentVersion\Run",
            r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\RunOnce",
            r"HKEY_LOCAL_MACHINE\Software\Microsoft\Windows\CurrentVersion\RunOnce",
        ]
        
        try:
            c = wmi.WMI()
            
            # Get baseline
            baseline_values = {}
            for key in registry_keys:
                try:
                    hive = key.split("\\")[0]
                    subkey = "\\".join(key.split("\\")[1:])
                    
                    if "CURRENT_USER" in hive:
                        hive_int = 0x80000001
                    else:
                        hive_int = 0x80000002
                    
                    reg = c.StdRegProv
                    result, names = reg.EnumValues(hDefKey=hive_int, sSubKeyName=subkey)
                    if result == 0 and names:
                        baseline_values[key] = set(names)
                except:
                    pass
            
            while self.monitoring:
                try:
                    for key in registry_keys:
                        try:
                            hive = key.split("\\")[0]
                            subkey = "\\".join(key.split("\\")[1:])
                            
                            if "CURRENT_USER" in hive:
                                hive_int = 0x80000001
                            else:
                                hive_int = 0x80000002
                            
                            reg = c.StdRegProv
                            result, names = reg.EnumValues(hDefKey=hive_int, sSubKeyName=subkey)
                            
                            if result == 0 and names:
                                current = set(names)
                                baseline = baseline_values.get(key, set())
                                new_values = current - baseline
                                
                                for val in new_values:
                                    with self._lock:
                                        entry = f"{key}\\{val}"
                                        if entry not in self.registry_modified:
                                            self.registry_modified.append(entry)
                                            print(f"[+] Registry: {entry}")
                        except:
                            pass
                except Exception as e:
                    print(f"[-] Registry monitor error: {e}")
                
                time.sleep(2)
        except Exception as e:
            print(f"[-] WMI init error: {e}")
    
    def get_report(self) -> Dict[str, Any]:
        """Generate the behavioral report."""
        with self._lock:
            return {
                "status": "completed",
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": datetime.now().isoformat(),
                "processes": self.processes,
                "files_created": self.files_created,
                "files_modified": self.files_modified,
                "files_deleted": self.files_deleted,
                "registry_modified": self.registry_modified,
                "network_connections": self.network_connections,
            }


def execute_sample(sample_path: str, timeout: int) -> int:
    """
    Execute the sample and wait for completion or timeout.
    
    Args:
        sample_path: Path to the sample file
        timeout: Maximum execution time in seconds
        
    Returns:
        Exit code or -1 if timeout
    """
    print(f"[*] Executing sample: {sample_path}")
    
    # Determine how to execute based on extension
    ext = os.path.splitext(sample_path)[1].lower()
    
    if ext in ['.exe', '.scr', '.com']:
        # Execute directly
        cmd = [sample_path]
    elif ext in ['.bat', '.cmd']:
        cmd = ['cmd', '/c', sample_path]
    elif ext in ['.ps1']:
        cmd = ['powershell', '-ExecutionPolicy', 'Bypass', '-File', sample_path]
    elif ext in ['.vbs', '.vbe']:
        cmd = ['cscript', '//nologo', sample_path]
    elif ext in ['.js', '.jse']:
        cmd = ['cscript', '//nologo', sample_path]
    elif ext in ['.py']:
        cmd = ['python', sample_path]
    elif ext in ['.dll']:
        # Use rundll32 for DLLs
        cmd = ['rundll32.exe', sample_path]
    else:
        # Try to execute directly
        cmd = [sample_path]
    
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE if IS_WINDOWS else 0,
        )
        
        try:
            return_code = proc.wait(timeout=timeout)
            print(f"[*] Sample exited with code: {return_code}")
            return return_code
        except subprocess.TimeoutExpired:
            print("[*] Sample execution timed out, terminating...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            return -1
            
    except FileNotFoundError:
        print(f"[-] Sample not found: {sample_path}")
        return -2
    except Exception as e:
        print(f"[-] Execution error: {e}")
        return -3


def main():
    """Main entry point for sandbox agent."""
    parser = argparse.ArgumentParser(
        description="Sentinel Sandbox Agent - Behavioral Analysis"
    )
    parser.add_argument(
        "--sample",
        required=True,
        help="Path to the sample file to execute"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Maximum execution time in seconds (default: 60)"
    )
    parser.add_argument(
        "--output",
        default="report.json",
        help="Path to output report file (default: report.json)"
    )
    
    args = parser.parse_args()
    
    # Validate sample exists
    if not os.path.exists(args.sample):
        print(f"[-] Sample not found: {args.sample}")
        sys.exit(1)
    
    print("=" * 60)
    print("SENTINEL SANDBOX AGENT")
    print("=" * 60)
    print(f"Sample:  {args.sample}")
    print(f"Timeout: {args.timeout}s")
    print(f"Output:  {args.output}")
    print("=" * 60)
    
    # Initialize monitor
    monitor = BehavioralMonitor()
    
    # Capture baseline
    monitor.capture_baseline()
    
    # Start monitoring
    monitor.start_monitoring()
    
    # Execute sample
    time.sleep(1)  # Let monitoring threads stabilize
    exit_code = execute_sample(args.sample, args.timeout)
    
    # Wait a bit more to catch delayed behavior
    print("[*] Waiting for delayed activity...")
    time.sleep(10)
    
    # Stop monitoring
    monitor.stop_monitoring()
    
    # Generate report
    report = monitor.get_report()
    report["sample_path"] = args.sample
    report["sample_exit_code"] = exit_code
    report["timeout_seconds"] = args.timeout
    
    # Write report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"[*] Report written to: {output_path}")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Processes:       {len(report['processes'])}")
    print(f"Files created:   {len(report['files_created'])}")
    print(f"Files modified:  {len(report['files_modified'])}")
    print(f"Files deleted:   {len(report['files_deleted'])}")
    print(f"Registry:        {len(report['registry_modified'])}")
    print(f"Network:         {len(report['network_connections'])}")
    print("=" * 60)
    
    # Exit cleanly for Windows Sandbox to close
    time.sleep(3)
    sys.exit(0)


if __name__ == "__main__":
    main()
