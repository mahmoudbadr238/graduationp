"""
Linux-specific chatbot tool implementations.

Replaces Windows-specific tools in security_chatbot_v4.py on Linux.
These are called by the platform dispatcher when running on Linux.
"""

import logging
import os
import pathlib
import shutil
import subprocess

logger = logging.getLogger(__name__)


def get_startup_programs() -> str:
    """List startup programs from XDG autostart directories."""
    logger.info("[LinuxTools] get_startup_programs invoked")
    try:
        autostart_dirs = [
            pathlib.Path.home() / ".config" / "autostart",
            pathlib.Path("/etc/xdg/autostart"),
        ]
        lines = ["Startup Programs (XDG Autostart):", ""]
        total = 0
        for d in autostart_dirs:
            if d.is_dir():
                for f in sorted(d.glob("*.desktop")):
                    name = f.stem
                    exec_line = ""
                    try:
                        for line in f.read_text(errors="ignore").splitlines():
                            if line.startswith("Exec="):
                                exec_line = line[5:]
                                break
                    except OSError:
                        pass
                    lines.append(f"  [{d.name}] {name}")
                    if exec_line:
                        lines.append(f"    → {exec_line}")
                    total += 1

        if total == 0:
            lines.append("  No startup entries found.")
        else:
            lines.append(f"\nTotal: {total} startup entries")

        return "\n".join(lines)

    except Exception as exc:
        logger.exception("[LinuxTools] get_startup_programs failed")
        return f"Failed to get startup programs: {exc}"


def run_system_diagnostics() -> str:
    """Run a Linux system health check."""
    logger.info("[LinuxTools] run_system_diagnostics invoked")

    checks: list[str] = []

    # 1. ClamAV
    if shutil.which("clamscan"):
        checks.append("ClamAV: ✅ Installed")
    else:
        checks.append("ClamAV: ❌ Not found")

    # 2. UFW Firewall
    if shutil.which("ufw"):
        try:
            r = subprocess.run(
                ["ufw", "status"], capture_output=True, text=True, timeout=5,
            )
            active = "Status: active" in (r.stdout or "")
            checks.append(f"UFW Firewall: {'✅ Active' if active else '❌ Inactive'}")
        except Exception:
            checks.append("UFW Firewall: ⚠️ Could not check")
    else:
        checks.append("Firewall: ⚠️ ufw not installed")

    # 3. AI Key
    groq_key = bool(os.environ.get("GROQ_API_KEY", "").strip())
    checks.append(f"GROQ_API_KEY: {'✅ Loaded' if groq_key else '❌ Missing'}")

    # 4. Static Scanner
    try:
        from backend.engines.scanning.static_scanner import StaticScanner
        scanner = StaticScanner()
        checks.append(f"Groq AI Scanner: {'✅ Ready' if scanner else '❌ Unavailable'}")
    except Exception as exc:
        checks.append(f"Groq AI Scanner: ❌ Failed to load ({exc})")

    # 5. RTP
    try:
        from PySide6.QtCore import QSettings
        qs = QSettings("SentinelSecurity", "SentinelApp")
        rtp_on = qs.value("rtpEnabled", True, type=bool)
        checks.append(
            f"Real-Time Protection: {'✅ Enabled' if rtp_on else '⚪ Disabled'}"
        )
    except Exception as exc:
        checks.append(f"Real-Time Protection: ⚠️ Error ({exc})")

    return "System Health Report:\n" + "\n".join(f"  {c}" for c in checks)


def update_software(software_id: str) -> str:
    """Update software via apt."""
    logger.info("[LinuxTools] update_software invoked: %s", software_id)
    try:
        result = subprocess.run(
            ["sudo", "apt", "update", "-y"],
            capture_output=True, text=True, timeout=60,
        )
        result2 = subprocess.run(
            ["sudo", "apt", "upgrade", "-y", software_id],
            capture_output=True, text=True, timeout=120,
        )
        output = (result2.stdout or "") + (result2.stderr or "")
        if result2.returncode == 0:
            return f"Successfully updated '{software_id}'.\nOutput:\n{output.strip()}"
        return (
            f"Update of '{software_id}' finished with exit code "
            f"{result2.returncode}.\nOutput:\n{output.strip()}"
        )
    except FileNotFoundError:
        return "Error: 'apt' is not available on this system."
    except subprocess.TimeoutExpired:
        return f"Error: Update of '{software_id}' timed out."
    except Exception as exc:
        return f"Error updating '{software_id}': {exc}"


def install_software(software_id: str) -> str:
    """Install software via apt."""
    logger.info("[LinuxTools] install_software invoked: %s", software_id)
    try:
        result = subprocess.run(
            ["sudo", "apt", "install", "-y", software_id],
            capture_output=True, text=True, timeout=180,
        )
        output = (result.stdout or "") + (result.stderr or "")
        if result.returncode == 0:
            return f"Successfully installed '{software_id}'.\nOutput:\n{output.strip()}"
        return (
            f"Installation of '{software_id}' finished with exit code "
            f"{result.returncode}.\nOutput:\n{output.strip()}"
        )
    except FileNotFoundError:
        return "Error: 'apt' is not available on this system."
    except subprocess.TimeoutExpired:
        return f"Error: Installation of '{software_id}' timed out."
    except Exception as exc:
        return f"Error installing '{software_id}': {exc}"
