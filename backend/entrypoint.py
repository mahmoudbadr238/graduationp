"""Shared entrypoint logic for development and frozen builds."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


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
    from backend.application import run
    from backend.utils.admin import AdminPrivileges

    print(f"{APP_FULL_NAME} v{__version__}")

    skip_uac = os.environ.get("SKIP_UAC", "").lower() in ("1", "true", "yes")

    if not AdminPrivileges.is_admin() and not skip_uac:
        print("[WARNING] Administrator privileges required for full functionality")
        print("  Requesting UAC elevation...")
        AdminPrivileges.elevate()
        print(
            "[WARNING] Elevation declined or failed. Continuing with limited access..."
        )
        print("  Some features may be unavailable.\n")
    elif skip_uac:
        print("[DEBUG] Skipping UAC (SKIP_UAC=1)\n")
    else:
        print("[OK] Running with administrator privileges\n")

    return run()


def main(argv: list[str] | None = None) -> int:
    """Run the command-line mode or launch the GUI."""
    args = list(sys.argv[1:] if argv is None else argv)
    cli_result = _run_cli_command(args)
    if cli_result is not None:
        return cli_result
    return _run_gui()

