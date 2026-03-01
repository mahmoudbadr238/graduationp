#!/usr/bin/env python3
"""Sentinel - Endpoint Security Suite v1.0.0"""

import faulthandler
import sys
import traceback
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent

# Enable faulthandler to dump C-level tracebacks on segfault
_crash_path = _APP_DIR / "crash_traceback.txt"
_crash_file = open(_crash_path, "w")  # noqa: SIM115
faulthandler.enable(file=_crash_file)

# Also catch Python-level unhandled exceptions
_original_excepthook = sys.excepthook
def _crash_excepthook(exc_type, exc_value, exc_tb):
    with open(_crash_path, "a") as f:
        f.write("\n=== UNHANDLED EXCEPTION ===\n")
        traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    _original_excepthook(exc_type, exc_value, exc_tb)
sys.excepthook = _crash_excepthook

import os

from app.__version__ import APP_FULL_NAME, __version__
from app.application import run
from app.utils.admin import AdminPrivileges

if __name__ == "__main__":
    print(f"{APP_FULL_NAME} v{__version__}")

    # Check for admin privileges and auto-elevate if needed
    # This ensures full access to Security event logs
    skip_uac = os.environ.get("SKIP_UAC", "").lower() in ("1", "true", "yes")

    if not AdminPrivileges.is_admin() and not skip_uac:
        print("[WARNING] Administrator privileges required for full functionality")
        print("  Requesting UAC elevation...")

        # elevate() will prompt for admin, restart the app, and exit this process
        AdminPrivileges.elevate()

        # If we're still here, user declined or it failed
        print(
            "[WARNING] Elevation declined or failed. Continuing with limited access..."
        )
        print("  Some features may be unavailable.\n")
    elif skip_uac:
        print("[DEBUG] Skipping UAC (SKIP_UAC=1)\n")
    else:
        print("[OK] Running with administrator privileges\n")

    raise SystemExit(run())
