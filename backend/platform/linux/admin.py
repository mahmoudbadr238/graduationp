"""
Linux admin privilege utilities.

Replaces backend/utils/admin.py on Linux.
Uses os.geteuid() for detection and pkexec for graphical elevation.
"""

import logging
import os
import subprocess
import sys

_log = logging.getLogger(__name__)


class AdminPrivileges:
    """Manage Linux root privileges."""

    @staticmethod
    def is_admin() -> bool:
        """Check if the current process has root privileges."""
        return os.geteuid() == 0

    @staticmethod
    def elevate() -> int | None:
        """Request privilege elevation via pkexec (graphical PolicyKit prompt).

        Returns:
            Optional[int]: Return code, or None if failed.
        """
        if AdminPrivileges.is_admin():
            return None  # Already root

        try:
            if getattr(sys, "frozen", False):
                target = sys.executable
                args = sys.argv[1:]
            else:
                script = os.path.abspath(sys.argv[0])
                target = sys.executable
                args = [script, *sys.argv[1:]]

            # Use pkexec for graphical sudo prompt
            cmd = ["pkexec", target, *args]
            proc = subprocess.Popen(cmd)
            proc.wait()

            if proc.returncode == 0:
                sys.exit(0)  # Exit current non-root process

            return proc.returncode

        except FileNotFoundError:
            _log.warning("pkexec not found — cannot elevate privileges; install policykit-1 or run with sudo")
            return None
        except (OSError, ValueError) as e:
            _log.warning("Failed to elevate privileges: %s", e)
            return None

    @staticmethod
    def request_if_needed(auto_elevate: bool = False) -> bool:
        """Check root privileges and optionally request elevation."""
        if AdminPrivileges.is_admin():
            _log.debug("Running with root privileges")
            return True

        _log.warning("Not running with root privileges — some features (firewall, security events) may be limited")

        if auto_elevate:
            _log.info("Requesting privilege elevation")
            result = AdminPrivileges.elevate()
            if result is None:
                return False
            return False

        return False


def check_admin() -> bool:
    """Simple helper to check admin status."""
    return AdminPrivileges.is_admin()
