#!/usr/bin/env python3
import os
import faulthandler
import sys
import traceback
from pathlib import Path

from backend.platform.paths import get_app_paths


def _get_crash_log_path() -> Path:
    """Store crash traces with the rest of the app logs, not in the repo root."""
    crash_dir = get_app_paths().crash_dir
    crash_dir.mkdir(parents=True, exist_ok=True)
    return crash_dir / "crash_traceback.txt"


_CRASH_PATH = _get_crash_log_path()
_crash_file = _CRASH_PATH.open("w", encoding="utf-8")  # noqa: SIM115
faulthandler.enable(file=_crash_file)


def _crash_excepthook(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: object,
) -> None:
    with _CRASH_PATH.open("a", encoding="utf-8") as crash_file:
        crash_file.write("\n=== UNHANDLED EXCEPTION ===\n")
        traceback.print_exception(exc_type, exc_value, exc_tb, file=crash_file)
    _original_excepthook(exc_type, exc_value, exc_tb)


_original_excepthook = sys.excepthook
sys.excepthook = _crash_excepthook

# Platform shim MUST load before any backend module — it patches
# subprocess.CREATE_NO_WINDOW on Linux so Windows-only modules can import.
import backend.platform  # noqa: F401  — side-effect import

# ── GPU / rendering fallback for Linux / WSL ────────────────────────────
# Must be set *before* any Qt module is imported. On WSL, Mesa's software
# rasterizer and missing Vulkan drivers frequently crash the scene graph.
if sys.platform.startswith("linux"):
    os.environ.setdefault("QSG_RHI_BACKEND", "opengl")          # Qt6 scene-graph
    os.environ.setdefault("QT_QUICK_BACKEND", "software")       # fallback renderer
    os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")         # Mesa SW rasterizer
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")             # prefer X11 on Wayland-less WSL

from backend.entrypoint import main

if __name__ == "__main__":
    raise SystemExit(main())
