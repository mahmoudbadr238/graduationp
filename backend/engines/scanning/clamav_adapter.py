"""
ClamAV Adapter - Optional Local Antivirus Integration

Integrates with ClamAV if installed on the system.
100% local, no network required.
"""

import logging
import subprocess
from dataclasses import dataclass
from typing import Any

from backend.infra.integrations import get_clamav_status

logger = logging.getLogger(__name__)

# Subprocess flags for Windows
_SUBPROCESS_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class ClamAVResult:
    """Result from ClamAV scan."""

    available: bool
    scanned: bool
    infected: bool
    signature_name: str | None
    raw_output: str
    error: str | None


class ClamAVAdapter:
    """
    Adapter for ClamAV command-line scanner.

    Features:
    - Auto-detects clamscan in PATH
    - Runs scans in worker-friendly way
    - Parses results into structured format
    - Gracefully handles missing ClamAV
    """

    def __init__(self):
        """Initialize the ClamAV adapter."""
        self._clamscan_path: str | None = None
        self._available = False
        self._status: dict[str, Any] = {}
        self._detect_clamscan()

    def _detect_clamscan(self) -> None:
        """Detect ClamAV via the shared integration probe."""
        self._status = get_clamav_status()
        self._clamscan_path = self._status.get("scannerPath") or None
        self._available = bool(self._status.get("available"))

        if self._available and self._clamscan_path:
            logger.info("ClamAV detected at: %s", self._clamscan_path)
            return

        logger.warning("ClamAV not detected: %s", self._status.get("detail", "Unavailable"))

    @property
    def is_available(self) -> bool:
        """Check if ClamAV is available."""
        return self._available

    @property
    def clamscan_path(self) -> str | None:
        """Get the path to clamscan executable."""
        return self._clamscan_path

    @property
    def status(self) -> dict[str, Any]:
        """Return the normalized ClamAV availability status."""
        return dict(self._status)

    def scan_file(self, file_path: str, timeout: int = 120) -> ClamAVResult:
        """
        Scan a file with ClamAV.

        Args:
            file_path: Path to file to scan
            timeout: Timeout in seconds

        Returns:
            ClamAVResult with scan results
        """
        if not self._available:
            return ClamAVResult(
                available=False,
                scanned=False,
                infected=False,
                signature_name=None,
                raw_output="",
                error="ClamAV not installed",
            )

        try:
            # Run clamscan with no-summary for cleaner output
            cmd = [self._clamscan_path, "--no-summary", "--infected", file_path]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=_SUBPROCESS_FLAGS,
            )

            output = result.stdout.strip()
            stderr = result.stderr.strip()

            # Parse result
            # Return code: 0 = clean, 1 = infected, 2 = error
            infected = result.returncode == 1
            signature_name = None

            if infected and output:
                # Parse signature name from output
                # Format: "/path/to/file: SignatureName FOUND"
                if "FOUND" in output:
                    parts = output.split(":")
                    if len(parts) >= 2:
                        sig_part = parts[-1].strip()
                        sig_part = sig_part.replace("FOUND", "").strip()
                        signature_name = sig_part

            return ClamAVResult(
                available=True,
                scanned=True,
                infected=infected,
                signature_name=signature_name,
                raw_output=output,
                error=stderr if result.returncode == 2 else None,
            )

        except subprocess.TimeoutExpired:
            logger.warning("ClamAV scan timed out for %s", file_path)
            return ClamAVResult(
                available=True,
                scanned=False,
                infected=False,
                signature_name=None,
                raw_output="",
                error="Scan timed out",
            )
        except Exception as e:
            logger.error("ClamAV scan error: %s", e)
            return ClamAVResult(
                available=True,
                scanned=False,
                infected=False,
                signature_name=None,
                raw_output="",
                error=str(e),
            )

    def get_version(self) -> str | None:
        """Get ClamAV version string."""
        if not self._available:
            return None

        try:
            result = subprocess.run(
                [self._clamscan_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=_SUBPROCESS_FLAGS,
            )
            return result.stdout.strip()
        except Exception:
            return None

    def get_database_info(self) -> dict[str, Any]:
        """Get ClamAV database info."""
        if not self._available:
            return {"available": False}

        try:
            # Try to find database files
            db_paths = []
            if self._status.get("scannerPath", "").lower().endswith(".exe"):
                db_paths = [
                    r"C:\Program Files\ClamAV\database",
                    r"C:\ProgramData\ClamAV\database",
                ]
            else:
                db_paths = [
                    "/var/lib/clamav",
                    "/usr/local/share/clamav",
                ]

            for db_path in db_paths:
                if os.path.exists(db_path):
                    files = os.listdir(db_path)
                    return {
                        "available": True,
                        "path": db_path,
                        "files": [f for f in files if f.endswith((".cvd", ".cld"))],
                    }

            return {"available": True, "path": None, "files": []}

        except Exception as e:
            return {"available": True, "error": str(e)}


# Singleton instance
_adapter: ClamAVAdapter | None = None


def get_clamav_adapter() -> ClamAVAdapter:
    """Get the ClamAV adapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = ClamAVAdapter()
    return _adapter
