"""Administrative privileges detection - Windows cross-platform"""

import ctypes
import os


def is_admin() -> bool:
    """Check if the current process has administrator privileges.

    Returns:
        True if running as admin on Windows, True on non-Windows platforms
    """
    try:
        # Windows-specific check
        if os.name == "nt":
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        # On Unix-like systems, treat as non-blocking (assume sufficient privileges)
        return True
    except (AttributeError, OSError):
        # If we can't determine, assume no admin privileges
        return os.name != "nt"
