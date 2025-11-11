"""Entry point for running Sentinel as a module: python -m app"""

import logging
import os
import sys

# Set up basic logging before any imports
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# Check for diagnostic mode
if "--diagnose" in sys.argv:
    from app.utils.diagnostics import run_diagnostics

    sys.exit(run_diagnostics())

# Normal application launch - imports after diagnostic check
from app.__version__ import APP_FULL_NAME, __version__  # noqa: E402
from app.application import run  # noqa: E402
from app.utils.admin import AdminPrivileges  # noqa: E402

print(f"{APP_FULL_NAME} v{__version__}")

# Check for admin privileges (can be skipped with SKIP_UAC=1)
skip_uac = os.environ.get("SKIP_UAC", "").lower() in ("1", "true", "yes")

if not AdminPrivileges.is_admin() and not skip_uac:
    print("[WARNING] Administrator privileges required for full functionality")
    print("  Requesting UAC elevation...")
    AdminPrivileges.elevate()
    print("[WARNING] Elevation declined or failed. Continuing with limited access...")
    print("  Some features may be unavailable.\n")
elif skip_uac:
    print("[DEBUG] Skipping UAC (SKIP_UAC=1)\n")
else:
    print("[OK] Running with administrator privileges\n")

raise SystemExit(run())
