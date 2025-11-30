"""Nmap CLI wrapper for network scanning with async support."""

import asyncio
import logging
import os
import platform
import re
import shutil
import socket
import subprocess  # nosec B404 - subprocess needed for nmap integration with hardcoded path
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Generator, Optional

from ..config.settings import get_settings
from ..core.errors import ExternalToolMissing, IntegrationDisabled
from ..core.interfaces import INetworkScanner

logger = logging.getLogger(__name__)

# Regex pattern for valid nmap targets (IP, hostname, CIDR)
# Prevents shell metacharacter injection
TARGET_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9.\-:\/]*$')
DANGEROUS_CHARS = set(';|&$(){}[]<>`\\!@#%^*=+\'"\'\n\r\t')

# Scan timeout configuration
SCAN_TIMEOUT = 1800  # 30 minutes max
FAST_SCAN_TIMEOUT = 300  # 5 minutes for fast scans
VULN_SCAN_TIMEOUT = 3600  # 1 hour for vulnerability scans
RATE_LIMIT_DELAY = 1  # Delay between scans (seconds)

# Platform detection
_IS_WINDOWS = sys.platform == 'win32'
_SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if _IS_WINDOWS else 0

# Scan type profiles - each maps to specific nmap arguments
# User NEVER provides these flags, only the scan type
SCAN_PROFILES: dict[str, dict[str, Any]] = {
    "host_discovery": {
        "description": "Discover live hosts on network",
        "args": ["-sn"],  # Ping scan
        "requires_host": False,
        "timeout": FAST_SCAN_TIMEOUT,
    },
    "network_map": {
        "description": "Map network structure with traceroute",
        "args": ["-sn", "--traceroute"],
        "requires_host": False,
        "timeout": SCAN_TIMEOUT,
    },
    "port_scan": {
        "description": "Scan open/closed/filtered ports",
        "args": ["-sS", "-sV", "-T4"],  # SYN scan + version detection
        "requires_host": True,
        "timeout": SCAN_TIMEOUT,
    },
    "os_detect": {
        "description": "Detect operating systems",
        "args": ["-O", "-T4"],  # OS detection
        "requires_host": True,
        "timeout": SCAN_TIMEOUT,
    },
    "service_version": {
        "description": "Identify service names and versions",
        "args": ["-sV", "--version-intensity", "5"],
        "requires_host": True,
        "timeout": SCAN_TIMEOUT,
    },
    "firewall_detect": {
        "description": "Detect firewalls and filtering",
        "args": ["-sA", "-T4"],  # ACK scan for firewall detection
        "requires_host": True,
        "timeout": SCAN_TIMEOUT,
    },
    "vuln_scan": {
        "description": "Find known vulnerabilities",
        "args": ["--script", "vuln"],
        "requires_host": True,
        "timeout": VULN_SCAN_TIMEOUT,
    },
    "protocol_scan": {
        "description": "Analyze IP protocols",
        "args": ["-sO", "-T4"],  # IP protocol scan
        "requires_host": True,
        "timeout": SCAN_TIMEOUT,
    },
}


def check_nmap_installed() -> tuple[bool, str]:
    """Check if nmap is installed and return (available, path).
    
    Returns:
        Tuple of (is_available, nmap_path_or_empty)
    """
    # Try shutil.which first (checks PATH)
    nmap_path = shutil.which("nmap")
    if nmap_path:
        return True, nmap_path
    
    # On Windows, check common install paths
    if _IS_WINDOWS:
        common_paths = [
            r"C:\Program Files (x86)\Nmap\nmap.exe",
            r"C:\Program Files\Nmap\nmap.exe",
            os.path.expandvars(r"%PROGRAMFILES%\Nmap\nmap.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Nmap\nmap.exe"),
        ]
        for path in common_paths:
            if os.path.isfile(path):
                return True, path
    
    # On Linux/macOS check common paths
    else:
        common_paths = [
            "/usr/bin/nmap",
            "/usr/local/bin/nmap",
            "/opt/homebrew/bin/nmap",  # macOS Homebrew
        ]
        for path in common_paths:
            if os.path.isfile(path):
                return True, path
    
    return False, ""


def get_local_subnet() -> str:
    """Auto-detect local subnet for network-wide scans.
    
    Returns:
        CIDR notation like "192.168.1.0/24" or fallback
    """
    try:
        # Get local IP by connecting to a public address (doesn't send data)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        try:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        finally:
            s.close()
        
        # Convert to /24 subnet
        parts = local_ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
    except Exception as e:
        logger.warning(f"Could not detect local subnet: {e}")
    
    # Fallback to common private ranges
    return "192.168.1.0/24"


def get_reports_dir() -> Path:
    """Get directory for saving scan reports."""
    if _IS_WINDOWS:
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".config"
    
    reports_dir = base / "Sentinel" / "nmap_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


class NmapCli(INetworkScanner):
    """Network scanner using local Nmap CLI with async support and rate limiting."""

    def __init__(self):
        settings = get_settings()

        # Check if offline mode
        if settings.offline_only:
            raise IntegrationDisabled("Network scanning disabled in offline mode")

        # Find nmap executable
        self.nmap_path = settings.nmap_path or self._find_nmap()
        if not self.nmap_path:
            raise ExternalToolMissing("Nmap not found. Install from https://nmap.org/")

        # Progress callback and rate limiting
        self._progress_callback: Optional[Callable[[str], None]] = None
        self._last_scan_time = 0
        
        # Active scan processes for streaming output
        self._active_scans: dict[str, subprocess.Popen] = {}
        
        # Accumulated output per scan
        self._scan_outputs: dict[str, str] = {}

    def set_progress_callback(self, callback: Callable[[str], None]) -> None:
        """Set a callback for progress updates during scanning."""
        self._progress_callback = callback
        logger.debug("Progress callback registered")

    def _report_progress(self, message: str) -> None:
        """Report progress if callback is set."""
        if self._progress_callback:
            self._progress_callback(message)
        logger.debug(f"Nmap: {message}")

    @staticmethod
    def validate_target(target: str) -> tuple[bool, str]:
        """Validate nmap target for safety.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not target or not target.strip():
            return False, "Target cannot be empty"
        
        target = target.strip()
        
        # Check length
        if len(target) > 256:
            return False, "Target too long (max 256 characters)"
        
        # Check for dangerous shell metacharacters
        if any(c in target for c in DANGEROUS_CHARS):
            return False, "Target contains invalid characters"
        
        # Validate against pattern
        if not TARGET_PATTERN.match(target):
            return False, "Target format invalid (use IP, hostname, or CIDR)"
        
        return True, ""

    async def scan_async(self, target: str, fast: bool = True) -> dict[str, Any]:
        """
        Run nmap scan on target asynchronously (non-blocking).

        Args:
            target: IP address, hostname, or CIDR range
            fast: If True, use quick scan (-F). If False, use comprehensive scan.

        Returns:
            Dict with scan results including hosts, ports, and services
        """
        # Validate target to prevent command injection
        is_valid, error_msg = self.validate_target(target)
        if not is_valid:
            logger.warning(f"Invalid scan target rejected: {target[:50]}")
            return {"target": target, "status": "error", "error": error_msg, "hosts": []}
        
        target = target.strip()
        
        try:
            # Rate limiting: wait if needed
            import time
            elapsed = time.time() - self._last_scan_time
            if elapsed < RATE_LIMIT_DELAY:
                await asyncio.sleep(RATE_LIMIT_DELAY - elapsed)
            self._last_scan_time = time.time()

            # Build nmap command
            cmd = [self.nmap_path]

            if fast:
                # Fast scan: top 100 ports
                cmd.extend(["-F", "-T4"])
                timeout = FAST_SCAN_TIMEOUT
                self._report_progress(f"Starting fast scan on {target}")
            else:
                # Comprehensive scan: service detection
                cmd.extend(["-sV", "-T3"])
                timeout = SCAN_TIMEOUT
                self._report_progress(f"Starting comprehensive scan on {target}")

            # Always get XML output for parsing
            cmd.extend(["-oX", "-", target])

            # Run nmap in executor to avoid blocking
            loop = asyncio.get_event_loop()
            self._report_progress(f"Executing nmap command: {' '.join(cmd)}")
            
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: subprocess.run(  # nosec B603 B607
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        check=True,
                    ),
                ),
                timeout=timeout + 10,  # Add 10s buffer
            )

            self._report_progress("Scan completed, parsing results")
            # Parse XML output (simplified - in production use python-nmap)
            parsed = self._parse_output(result.stdout, target)
            parsed["duration_seconds"] = timeout
            return parsed

        except asyncio.TimeoutError:
            logger.error(f"Scan timeout for {target} after {timeout}s")
            return {
                "target": target,
                "status": "timeout",
                "error": f"Scan timed out after {timeout}s",
                "hosts": [],
            }
        except subprocess.TimeoutExpired:
            logger.error(f"Subprocess timeout for {target}")
            return {
                "target": target,
                "status": "timeout",
                "error": "Nmap subprocess timed out",
                "hosts": [],
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"Nmap error for {target}: {e.stderr}")
            return {
                "target": target,
                "status": "error",
                "error": f"Nmap failed: {e.stderr}",
                "hosts": [],
            }
        except (OSError, ValueError) as e:
            logger.error(f"Error scanning {target}: {e}")
            return {"target": target, "status": "error", "error": str(e), "hosts": []}

    def scan(self, target: str, fast: bool = True) -> dict[str, Any]:
        """
        Synchronous wrapper for scan_async (for backwards compatibility).

        Args:
            target: IP address, hostname, or CIDR range
            fast: If True, use quick scan. If False, use comprehensive scan.

        Returns:
            Dict with scan results
        """
        # Validate target to prevent command injection
        is_valid, error_msg = self.validate_target(target)
        if not is_valid:
            logger.warning(f"Invalid scan target rejected: {target[:50]}")
            return {"target": target, "status": "error", "error": error_msg, "hosts": []}
        
        target = target.strip()
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context, use run_in_executor instead
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.scan_async(target, fast))
                    return future.result(timeout=SCAN_TIMEOUT + 60)
            else:
                return asyncio.run(self.scan_async(target, fast))
        except Exception as e:
            logger.error(f"Sync scan failed for {target}: {e}")
            return {"target": target, "status": "error", "error": str(e), "hosts": []}

    def _find_nmap(self) -> str:
        """Try to find nmap in common locations."""
        # Check PATH
        try:
            result = subprocess.run(  # nosec B603 B607 - checking nmap version, fixed command
                ["nmap", "--version"], check=False, capture_output=True, timeout=5
            )
            if result.returncode == 0:
                return "nmap"
        except (OSError, subprocess.TimeoutExpired):
            # Nmap not in PATH or timeout
            pass

        # Check common Windows install locations
        common_paths = [
            r"C:\Program Files (x86)\Nmap\nmap.exe",
            r"C:\Program Files\Nmap\nmap.exe",
        ]

        for path in common_paths:
            if os.path.exists(path):
                return path

        return ""

    def _parse_output(self, xml_output: str, target: str) -> dict[str, Any]:
        """Parse nmap XML output (simplified version)."""
        # In production, use python-nmap or xml.etree for proper parsing
        # This is a simplified version that just checks if scan completed

        hosts = []

        # Simple check for host up
        if "Host is up" in xml_output or '<status state="up"' in xml_output:
            # Extract basic info (this is very simplified)
            ports_found = xml_output.count("<port ")

            hosts.append(
                {
                    "address": target,
                    "status": "up",
                    "ports_found": ports_found,
                }
            )

        return {
            "target": target,
            "status": "completed",
            "hosts": hosts,
            "raw_output": xml_output[:1000],  # First 1000 chars
        }

    def run_scan_streaming(
        self,
        scan_type: str,
        target_host: Optional[str],
        output_callback: Callable[[str], None],
    ) -> Generator[str, None, tuple[bool, int, str]]:
        """
        Run a scan with streaming output.
        
        Args:
            scan_type: One of the SCAN_PROFILES keys
            target_host: Target IP/hostname (None for network-wide scans)
            output_callback: Called with each line of output
            
        Yields:
            Output lines as they arrive
            
        Returns:
            Tuple of (success, exit_code, report_path)
        """
        # Get scan profile
        profile = SCAN_PROFILES.get(scan_type)
        if not profile:
            error_msg = f"Unknown scan type: {scan_type}"
            output_callback(f"[ERROR] {error_msg}\n")
            return False, 1, ""
        
        # Determine target
        if profile["requires_host"]:
            if not target_host:
                error_msg = "This scan type requires a target host"
                output_callback(f"[ERROR] {error_msg}\n")
                return False, 1, ""
            
            # Validate target
            is_valid, error_msg = self.validate_target(target_host)
            if not is_valid:
                output_callback(f"[ERROR] Invalid target: {error_msg}\n")
                return False, 1, ""
            
            target = target_host.strip()
        else:
            # Network-wide scan - auto-detect subnet
            target = get_local_subnet()
            output_callback(f"[INFO] Auto-detected local subnet: {target}\n")
        
        # Generate scan ID and report path
        scan_id = f"{scan_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        report_path = get_reports_dir() / f"nmap_{scan_id}.txt"
        
        # Build command
        cmd = [self.nmap_path] + profile["args"] + [target]
        timeout = profile.get("timeout", SCAN_TIMEOUT)
        
        output_callback(f"[INFO] Starting: {profile['description']}\n")
        output_callback(f"[INFO] Target: {target}\n")
        output_callback(f"[INFO] Command: {' '.join(cmd)}\n")
        output_callback("-" * 60 + "\n\n")
        
        # Accumulate output for report
        full_output = []
        
        try:
            # Start process with streaming
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered
                creationflags=_SUBPROCESS_FLAGS,
            )
            
            # Stream output line by line
            start_time = datetime.now()
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                full_output.append(line)
                output_callback(line)
                
                # Check timeout
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > timeout:
                    process.kill()
                    output_callback(f"\n[ERROR] Scan timed out after {timeout}s\n")
                    return False, -1, ""
            
            process.stdout.close()
            exit_code = process.wait()
            
            # Write report
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"Nmap Scan Report\n")
                f.write(f"================\n")
                f.write(f"Scan Type: {profile['description']}\n")
                f.write(f"Target: {target}\n")
                f.write(f"Date: {datetime.now().isoformat()}\n")
                f.write(f"Command: {' '.join(cmd)}\n")
                f.write("-" * 60 + "\n\n")
                f.writelines(full_output)
            
            success = exit_code == 0
            if success:
                output_callback(f"\n[SUCCESS] Scan completed\n")
                output_callback(f"[INFO] Report saved: {report_path}\n")
            else:
                output_callback(f"\n[WARNING] Scan finished with exit code {exit_code}\n")
            
            return success, exit_code, str(report_path)
            
        except FileNotFoundError:
            output_callback("[ERROR] Nmap executable not found\n")
            return False, 1, ""
        except Exception as e:
            output_callback(f"[ERROR] Scan failed: {e}\n")
            logger.exception(f"Scan error: {e}")
            return False, 1, ""

    def save_scan_output(self, scan_id: str, output: str) -> str:
        """Save accumulated scan output to a report file.
        
        Returns:
            Path to saved report
        """
        report_path = get_reports_dir() / f"nmap_{scan_id}.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"Nmap Scan Report - {scan_id}\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write("=" * 60 + "\n\n")
            f.write(output)
        
        logger.info(f"Scan report saved: {report_path}")
        return str(report_path)
