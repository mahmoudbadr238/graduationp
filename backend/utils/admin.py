"""
Admin privilege utilities for Windows UAC elevation.
Handles checking and requesting administrator privileges.
"""

import ctypes
import os
import subprocess
import sys


class AdminPrivileges:
    """Manage Windows administrator privileges."""

    @staticmethod
    def is_admin() -> bool:
        """
        Check if the current process has administrator privileges.

        Returns:
            bool: True if running as administrator, False otherwise.
        """
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except (OSError, AttributeError):
            # Windows API not available or function missing
            return False

    @staticmethod
    def elevate() -> int | None:
        """
        Request UAC elevation to run as administrator.
        This will restart the application with admin privileges if granted.

        Returns:
            Optional[int]: Return code from ShellExecuteW, or None if failed.
        """
        if AdminPrivileges.is_admin():
            return None  # Already admin

        try:
            if getattr(sys, "frozen", False):
                target = sys.executable
                params = subprocess.list2cmdline(sys.argv[1:])
                working_dir = os.path.dirname(sys.executable)
            else:
                script = os.path.abspath(sys.argv[0])
                target = sys.executable
                params = subprocess.list2cmdline([script, *sys.argv[1:]])
                working_dir = os.path.dirname(script)

            ret = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                target,
                params,
                working_dir,
                1 if getattr(sys, "frozen", False) else 0,
            )

            if ret > 32:  # Success
                sys.exit(0)  # Exit current non-admin process

            return ret

        except (OSError, AttributeError, ValueError) as e:
            # Windows API call failed, wrong platform, or invalid parameters
            print(f"Failed to elevate privileges: {e}")
            return None

    @staticmethod
    def request_if_needed(auto_elevate: bool = False) -> bool:
        """
        Check admin privileges and optionally request elevation.

        Args:
            auto_elevate: If True, automatically request elevation if not admin.
                         If False, just check and warn.

        Returns:
            bool: True if admin privileges are available (or obtained).
        """
        if AdminPrivileges.is_admin():
            print("[OK] Running with administrator privileges")
            return True

        print("[WARNING] Not running with administrator privileges")
        print("  Some features (Security event logs) may be limited.")

        if auto_elevate:
            print("  Requesting elevation...")
            result = AdminPrivileges.elevate()
            if result is None:
                return False  # Elevation failed or cancelled
            # If we get here, elevation was requested but we're still running
            # (shouldn't happen normally as elevate() calls sys.exit)
            return False

        return False


def check_admin() -> bool:
    """
    Simple helper to check admin status.

    Returns:
        bool: True if running as administrator.
    """
    return AdminPrivileges.is_admin()
