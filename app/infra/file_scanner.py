"""Local file scanner with hash calculation and optional VirusTotal check."""
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from ..core.interfaces import IFileScanner
from ..core.errors import IntegrationDisabled


class LocalFileScanner(IFileScanner):
    """Scan files locally with SHA256 hash and optional VirusTotal lookup."""
    
    def __init__(self, vt_client=None):
        """
        Initialize scanner.
        
        Args:
            vt_client: Optional VirusTotalClient for cloud lookups
        """
        self.vt_client = vt_client
    
    def scan_file(self, path: str) -> Dict[str, Any]:
        """
        Scan a file and return results.
        
        Returns:
            Dict with file info, hash, and optional VT results
        """
        file_path = Path(path)
        
        if not file_path.exists():
            return {
                "error": f"File not found: {path}",
                "path": path
            }
        
        if not file_path.is_file():
            return {
                "error": f"Not a file: {path}",
                "path": path
            }
        
        try:
            # Calculate SHA256 hash
            sha256 = self._calculate_hash(file_path)
            
            # Get file metadata
            stat = file_path.stat()
            
            result = {
                "path": str(file_path),
                "name": file_path.name,
                "size": stat.st_size,
                "sha256": sha256,
                "vt_check": False,
            }
            
            # Optional VirusTotal check
            if self.vt_client:
                try:
                    vt_result = self.vt_client.scan_file_hash(sha256)
                    result["vt_check"] = True
                    result["vt_result"] = vt_result
                except IntegrationDisabled:
                    result["vt_check"] = False
                    result["vt_disabled"] = True
                except Exception as e:
                    result["vt_error"] = str(e)
            
            return result
        
        except Exception as e:
            return {
                "error": f"Scan failed: {str(e)}",
                "path": path
            }
    
    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
