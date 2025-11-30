"""Smoke test for Sentinel application - basic import and diagnostics."""

import json
import subprocess
import sys
from pathlib import Path


def test_import_app():
    """Test that the app module can be imported."""
    import app

    assert app is not None


def test_diagnose_command():
    """Test that --diagnose flag works without errors."""
    result = subprocess.run(
        [sys.executable, "-m", "app", "--diagnose"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Diagnostics failed: {result.stderr}"
    assert "DIAGNOSTICS PASSED" in result.stdout or "Privileges" in result.stdout


def test_export_diagnostics():
    """Test that --export-diagnostics flag works."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        output_file = Path(tmp.name)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "app", "--export-diagnostics", str(output_file)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Export failed: {result.stderr}"
        assert output_file.exists(), "Diagnostics file not created"

        # Validate JSON format
        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)
        assert "system" in data
        assert "dependencies" in data
    finally:
        if output_file.exists():
            output_file.unlink()


def test_reset_settings():
    """Test that --reset-settings flag works."""
    result = subprocess.run(
        [sys.executable, "-m", "app", "--reset-settings"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Reset failed: {result.stderr}"
    assert "reset" in result.stdout.lower() or "OK" in result.stdout
