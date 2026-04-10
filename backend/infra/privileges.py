"""Administrative privileges detection - Windows only"""

import ctypes


def is_admin() -> bool:
    """Check if the current process has Windows administrator privileges.

    Returns:
        True if running as Administrator on Windows.
    """
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False
