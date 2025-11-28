"""
Admin privilege utilities for Windows UAC elevation.
Handles checking and requesting administrator privileges.
"""

import ctypes
import os
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
            # Get the script path
            script = os.path.abspath(sys.argv[0])
            params = " ".join(sys.argv[1:])

            # Request elevation via ShellExecute with 'runas' verb
            ret = ctypes.windll.shell32.ShellExecuteW(
                None,  # hwnd
                "runas",  # operation
                sys.executable,  # file (Python interpreter)
                f'"{script}" {params}',  # parameters
                None,  # directory
                1,  # show command (SW_NORMAL)
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


def require_admin(auto_elevate: bool = True) -> bool:
    """
    Require admin privileges, optionally elevating if needed.

    Args:
        auto_elevate: If True, automatically request UAC elevation.

    Returns:
        bool: True if admin privileges are available.
    """
    return AdminPrivileges.request_if_needed(auto_elevate=auto_elevate)
