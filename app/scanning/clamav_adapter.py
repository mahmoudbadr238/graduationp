"""
ClamAV Adapter - Optional Local Antivirus Integration

Integrates with ClamAV if installed on the system.
100% local, no network required.
"""

import logging
import os
import subprocess
import shutil
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Subprocess flags for Windows
_IS_WINDOWS = os.name == "nt"
_SUBPROCESS_FLAGS = 0x08000000 if _IS_WINDOWS else 0  # CREATE_NO_WINDOW


@dataclass
class ClamAVResult:
    """Result from ClamAV scan."""
    available: bool
    scanned: bool
    infected: bool
    signature_name: Optional[str]
    raw_output: str
    error: Optional[str]


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
        self._clamscan_path: Optional[str] = None
        self._available = False
        self._detect_clamscan()
    
    def _detect_clamscan(self) -> None:
        """Detect clamscan executable in PATH."""
        # Common names for clamscan
        executables = ["clamscan", "clamscan.exe", "clamdscan", "clamdscan.exe"]
        
        for exe in executables:
            path = shutil.which(exe)
            if path:
                self._clamscan_path = path
                self._available = True
                logger.info(f"ClamAV detected at: {path}")
                return
        
        # Check common installation paths on Windows
        if _IS_WINDOWS:
            common_paths = [
                r"C:\Program Files\ClamAV\clamscan.exe",
                r"C:\Program Files (x86)\ClamAV\clamscan.exe",
                r"C:\ClamAV\clamscan.exe",
            ]
            for path in common_paths:
                if os.path.exists(path):
                    self._clamscan_path = path
                    self._available = True
                    logger.info(f"ClamAV detected at: {path}")
                    return
        
        logger.debug("ClamAV not detected - optional integration disabled")
    
    @property
    def is_available(self) -> bool:
        """Check if ClamAV is available."""
        return self._available
    
    @property
    def clamscan_path(self) -> Optional[str]:
        """Get the path to clamscan executable."""
        return self._clamscan_path
    
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
                error="ClamAV not installed"
            )
        
        try:
            # Run clamscan with no-summary for cleaner output
            cmd = [
                self._clamscan_path,
                "--no-summary",
                "--infected",
                file_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=_SUBPROCESS_FLAGS if _IS_WINDOWS else 0,
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
                error=stderr if result.returncode == 2 else None
            )
            
        except subprocess.TimeoutExpired:
            logger.warning(f"ClamAV scan timed out for {file_path}")
            return ClamAVResult(
                available=True,
                scanned=False,
                infected=False,
                signature_name=None,
                raw_output="",
                error="Scan timed out"
            )
        except Exception as e:
            logger.error(f"ClamAV scan error: {e}")
            return ClamAVResult(
                available=True,
                scanned=False,
                infected=False,
                signature_name=None,
                raw_output="",
                error=str(e)
            )
    
    def get_version(self) -> Optional[str]:
        """Get ClamAV version string."""
        if not self._available:
            return None
        
        try:
            result = subprocess.run(
                [self._clamscan_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=_SUBPROCESS_FLAGS if _IS_WINDOWS else 0,
            )
            return result.stdout.strip()
        except Exception:
            return None
    
    def get_database_info(self) -> Dict[str, Any]:
        """Get ClamAV database info."""
        if not self._available:
            return {"available": False}
        
        try:
            # Try to find database files
            db_paths = []
            if _IS_WINDOWS:
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
                        "files": [f for f in files if f.endswith(('.cvd', '.cld'))],
                    }
            
            return {"available": True, "path": None, "files": []}
            
        except Exception as e:
            return {"available": True, "error": str(e)}


# Singleton instance
_adapter: Optional[ClamAVAdapter] = None


def get_clamav_adapter() -> ClamAVAdapter:
    """Get the ClamAV adapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = ClamAVAdapter()
    return _adapter
