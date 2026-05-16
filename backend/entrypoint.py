"""Shared entrypoint logic for development and frozen builds."""

from __future__ import annotations

# Apply platform shims FIRST (patches subprocess.CREATE_NO_WINDOW on Linux)
import backend.platform  # noqa: F401

import json
import logging
import os
import sys
from pathlib import Path

_log = logging.getLogger(__name__)

# Load .env file early so GROQ_API_KEY and other optional secrets are available.
# In frozen builds, users edit files next to Sentinel.exe; bundled modules live
# under _internal, so check both runtime roots.
try:
    from dotenv import load_dotenv
    from backend.runtime import app_root, bundle_root

    for env_path in (
        app_root() / ".env",
        bundle_root() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ):
        if env_path.exists():
            load_dotenv(env_path, override=False)
except ImportError:
    pass


def _run_cli_command(argv: list[str]) -> int | None:
    """Handle non-GUI command modes that should exit immediately."""
    if "--diagnose" in argv:
        from backend.utils.diagnostics import run_diagnostics

        return run_diagnostics()

    if "--export-diagnostics" in argv:
        idx = argv.index("--export-diagnostics")
        output_file = argv[idx + 1] if idx + 1 < len(argv) else None
        if not output_file:
            print("[ERROR] --export-diagnostics requires an output file path")
            return 1

        from backend.utils.diagnostics import collect_diagnostics

        try:
            diagnostics = collect_diagnostics()
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", encoding="utf-8") as handle:
                json.dump(diagnostics, handle, indent=2)
            print(f"[OK] Diagnostics exported to {output_path}")
            return 0
        except OSError as exc:
            print(f"[ERROR] Failed to export diagnostics: {exc}")
            return 1

    if "--reset-settings" in argv:
        try:
            from backend.core.config import get_config

            config = get_config()
            config.reset()
            print("[OK] Settings reset to defaults")
            return 0
        except OSError as exc:
            print(f"[ERROR] Failed to reset settings: {exc}")
            return 1

    return None


def _run_gui() -> int:
    """Launch the desktop GUI."""
    from backend.__version__ import APP_FULL_NAME, __version__
    from backend.platform import IS_WINDOWS, IS_LINUX

    # On Linux, ensure Qt platform env vars are set before QApplication
    if IS_LINUX:
        # Use software rendering if no GPU driver (common in VMs)
        os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
        # Ensure DISPLAY is set for X11
        if "DISPLAY" not in os.environ and "WAYLAND_DISPLAY" not in os.environ:
            os.environ["DISPLAY"] = ":0"

    from backend.application import run

    # Print version to stdout so it appears in terminal/logs regardless of log level
    print(f"{APP_FULL_NAME} v{__version__}")  # noqa: T201

    skip_uac = os.environ.get("SKIP_UAC", "").lower() in ("1", "true", "yes")

    if IS_WINDOWS:
        from backend.utils.admin import AdminPrivileges
    else:
        from backend.platform.linux.admin import AdminPrivileges

    if not AdminPrivileges.is_admin() and not skip_uac:
        privilege_label = "Administrator" if IS_WINDOWS else "Root"
        _log.warning("%s privileges required for full functionality — requesting elevation", privilege_label)
        AdminPrivileges.elevate()
        _log.warning("Elevation declined or failed — continuing with limited access")
    elif skip_uac:
        _log.debug("Skipping elevation (SKIP_UAC=1)")
    else:
        privilege_label = "administrator" if IS_WINDOWS else "root"
        _log.info("Running with %s privileges", privilege_label)

    return run()


def main(argv: list[str] | None = None) -> int:
    """Run the command-line mode or launch the GUI."""
    args = list(sys.argv[1:] if argv is None else argv)
    cli_result = _run_cli_command(args)
    if cli_result is not None:
        return cli_result
    return _run_gui()
