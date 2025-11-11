"""Unit tests for service implementations."""
# nosec B101 - assert statements are expected in pytest test files

import os
import tempfile
from pathlib import Path

import pytest

from app.infra.file_scanner import LocalFileScanner


class TestLocalFileScanner:
    """Test file scanner service."""

    @pytest.fixture
    def temp_file(self):
        """Create a temporary test file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("This is a test file for scanning.")
            temp_path = f.name

        yield temp_path

        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)

    def test_scan_file_calculates_hash(self, temp_file):
        """Test that file scanner calculates SHA256 hash."""
        scanner = LocalFileScanner(vt_client=None)

        result = scanner.scan_file(temp_file)

        assert "error" not in result
        assert "sha256" in result
        assert len(result["sha256"]) == 64  # SHA256 hex length
        assert result["path"] == temp_file
        assert result["size"] > 0

    def test_scan_nonexistent_file(self):
        """Test scanning a file that doesn't exist."""
        scanner = LocalFileScanner(vt_client=None)

        result = scanner.scan_file(str(Path("nonexistent") / "file.txt"))

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_scan_directory_fails(self, tmp_path):
        """Test that scanning a directory fails."""
        scanner = LocalFileScanner(vt_client=None)

        # tmp_path is a directory
        result = scanner.scan_file(str(tmp_path))

        assert "error" in result
        assert "not a file" in result["error"].lower()

    def test_hash_consistency(self, temp_file):
        """Test that same file produces same hash."""
        scanner = LocalFileScanner(vt_client=None)

        result1 = scanner.scan_file(temp_file)
        result2 = scanner.scan_file(temp_file)

        assert result1["sha256"] == result2["sha256"]

    def test_scan_without_vt_client(self, temp_file):
        """Test scanning without VirusTotal client."""
        scanner = LocalFileScanner(vt_client=None)

        result = scanner.scan_file(temp_file)

        assert "error" not in result
        assert result["vt_check"] is False

    def test_file_metadata_extraction(self, temp_file):
        """Test that file metadata is extracted correctly."""
        scanner = LocalFileScanner(vt_client=None)

        result = scanner.scan_file(temp_file)

        assert "name" in result
        assert "size" in result
        assert "path" in result
        assert result["name"] == Path(temp_file).name
        assert result["size"] > 0


class TestFileHashCalculation:
    """Test hash calculation specifically."""

    def test_known_hash(self):
        """Test hash calculation against known value."""
        scanner = LocalFileScanner(vt_client=None)

        # Create file with known content
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test")
            temp_path = f.name

        try:
            result = scanner.scan_file(temp_path)

            # SHA256 of "test" is known
            expected_hash = (
                "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
            )
            assert result["sha256"] == expected_hash
        finally:
            os.remove(temp_path)

    def test_empty_file_hash(self):
        """Test hashing an empty file."""
        scanner = LocalFileScanner(vt_client=None)

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            result = scanner.scan_file(temp_path)

            # SHA256 of empty file
            expected_hash = (
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            )
            assert result["sha256"] == expected_hash
        finally:
            os.remove(temp_path)
