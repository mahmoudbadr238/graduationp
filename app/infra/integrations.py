"""Integration availability helpers - Nmap, VirusTotal, etc."""

import os
import shutil


def nmap_available() -> bool:
    """Check if nmap command-line tool is available.

    Returns:
        True if nmap is found in PATH
    """
    return shutil.which("nmap") is not None


def virustotal_enabled() -> bool:
    """Check if VirusTotal API key is configured.

    Returns:
        True if VT_API_KEY environment variable is set and non-empty
    """
    key = os.getenv("VT_API_KEY", "").strip()
    return len(key) > 0


def get_integration_status() -> dict[str, bool]:
    """Get status of all optional integrations.

    Returns:
        Dictionary with integration name as key and availability as boolean
    """
    return {
        "nmap": nmap_available(),
        "virustotal": virustotal_enabled(),
    }


def print_integration_status():
    """Print clean, single-line status for each integration."""
    status = get_integration_status()

    if not status["nmap"]:
        print("[SKIP] Network scanner: nmap not found")

    if not status["virustotal"]:
        print("[SKIP] VirusTotal: VT_API_KEY not set")
