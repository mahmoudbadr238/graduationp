"""Integration availability helpers - Nmap, etc."""

import shutil


def nmap_available() -> bool:
    """Check if nmap command-line tool is available.

    Returns:
        True if nmap is found in PATH
    """
    return shutil.which("nmap") is not None


def get_integration_status() -> dict[str, bool]:
    """Get status of all optional integrations.

    Returns:
        Dictionary with integration name as key and availability as boolean
    """
    return {
        "nmap": nmap_available(),
    }


def print_integration_status():
    """Print clean, single-line status for each integration."""
    status = get_integration_status()

    if not status["nmap"]:
        print("[SKIP] Network scanner: nmap not found")
