"""
Linux admin privilege utilities.

Replaces backend/utils/admin.py on Linux.
Uses os.geteuid() for detection and pkexec for graphical elevation.
"""

import os
import subprocess
import sys


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
            print("[WARNING] pkexec not found — cannot elevate privileges")
            print("  Install policykit-1 or run with: sudo python main.py")
            return None
        except (OSError, ValueError) as e:
            print(f"Failed to elevate privileges: {e}")
            return None

    @staticmethod
    def request_if_needed(auto_elevate: bool = False) -> bool:
        """Check root privileges and optionally request elevation."""
        if AdminPrivileges.is_admin():
            print("[OK] Running with root privileges")
            return True

        print("[WARNING] Not running with root privileges")
        print("  Some features (firewall, security events) may be limited.")

        if auto_elevate:
            print("  Requesting elevation...")
            result = AdminPrivileges.elevate()
            if result is None:
                return False
            return False

        return False


def check_admin() -> bool:
    """Simple helper to check admin status."""
    return AdminPrivileges.is_admin()
