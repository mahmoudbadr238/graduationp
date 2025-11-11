"""Entry point for running Sentinel as a module: python -m app"""

import json
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

# Check for export-diagnostics mode
if "--export-diagnostics" in sys.argv:
    try:
        idx = sys.argv.index("--export-diagnostics")
        output_file = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        if not output_file:
            print("[ERROR] --export-diagnostics requires output file path")
            sys.exit(1)

        from app.utils.diagnostics import collect_diagnostics

        diagnostics = collect_diagnostics()
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(diagnostics, f, indent=2)
        print(f"[OK] Diagnostics exported to {output_file}")
        sys.exit(0)
    except OSError as e:
        print(f"[ERROR] Failed to export diagnostics: {e}")
        sys.exit(1)

# Check for reset-settings mode
if "--reset-settings" in sys.argv:
    try:
        from app.core.config import get_config

        config = get_config()
        config.reset()
        print("[OK] Settings reset to defaults")
        sys.exit(0)
    except OSError as e:
        print(f"[ERROR] Failed to reset settings: {e}")
        sys.exit(1)

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
