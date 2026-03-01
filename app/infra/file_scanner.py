"""Local file scanner with hash calculation."""

import hashlib
from pathlib import Path
from typing import Any

from ..core.interfaces import IFileScanner


class LocalFileScanner(IFileScanner):
    """Scan files locally with SHA256 hash."""

    def __init__(self):
        """Initialize scanner."""

    def scan_file(self, path: str) -> dict[str, Any]:
        """
        Scan a file and return results.

        Returns:
            Dict with file info and hash
        """
        file_path = Path(path)

        if not file_path.exists():
            return {"error": f"File not found: {path}", "path": path}

        if not file_path.is_file():
            return {"error": f"Not a file: {path}", "path": path}

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
            }

            return result

        except (OSError, PermissionError, ValueError) as e:
            # File access errors, hash calculation failures
            return {"error": f"Scan failed: {e!s}", "path": path}

    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file."""
        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()
