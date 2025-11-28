"""Nmap CLI wrapper for network scanning with async support."""

import asyncio
import logging
import os
import subprocess  # nosec B404 - subprocess needed for nmap integration with hardcoded path
from typing import Any, Callable, Optional

from ..config.settings import get_settings
from ..core.errors import ExternalToolMissing, IntegrationDisabled
from ..core.interfaces import INetworkScanner

logger = logging.getLogger(__name__)

# Scan timeout configuration
SCAN_TIMEOUT = 1800  # 30 minutes max
FAST_SCAN_TIMEOUT = 300  # 5 minutes for fast scans
RATE_LIMIT_DELAY = 1  # Delay between scans (seconds)


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

        # Progress callback and rate limiting
        self._progress_callback: Optional[Callable[[str], None]] = None
        self._last_scan_time = 0

    def set_progress_callback(self, callback: Callable[[str], None]) -> None:
        """Set a callback for progress updates during scanning."""
        self._progress_callback = callback
        logger.debug("Progress callback registered")

    def _report_progress(self, message: str) -> None:
        """Report progress if callback is set."""
        if self._progress_callback:
            self._report_progress(message)
        logger.debug(f"Nmap: {message}")

    async def scan_async(self, target: str, fast: bool = True) -> dict[str, Any]:
        """
        Run nmap scan on target asynchronously (non-blocking).

        Args:
            target: IP address, hostname, or CIDR range
            fast: If True, use quick scan (-F). If False, use comprehensive scan.

        Returns:
            Dict with scan results including hosts, ports, and services
        """
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
