"""Platform detection and module routing.

Provides IS_WINDOWS, IS_LINUX flags and a get_platform_name() helper
so the application can import the correct platform-specific modules
without modifying any existing Windows code.
"""

import subprocess
import sys

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

# ── Compatibility shim ──────────────────────────────────────────────
# Many Windows-specific modules reference subprocess.CREATE_NO_WINDOW
# at module level.  On Linux this attribute doesn't exist and would
# raise AttributeError on import.  We inject it as 0 here — Popen on
# Linux silently ignores `creationflags`, so 0 is harmless.
if not IS_WINDOWS and not hasattr(subprocess, "CREATE_NO_WINDOW"):
    subprocess.CREATE_NO_WINDOW = 0


def get_platform_name() -> str:
    """Return the current platform as a simple string."""
    if IS_WINDOWS:
        return "windows"
    if IS_LINUX:
        return "linux"
    return "unknown"

