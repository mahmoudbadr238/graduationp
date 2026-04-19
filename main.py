#!/usr/bin/env python3
import os
import faulthandler
import sys
import traceback
from pathlib import Path


def _get_crash_log_path() -> Path:
    """Store crash traces with the rest of the app logs, not in the repo root."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        log_dir = Path(appdata) / "Sentinel" / "logs"
    else:
        log_dir = Path.home() / "AppData" / "Roaming" / "Sentinel" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "crash_traceback.txt"


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

from backend.entrypoint import main

if __name__ == "__main__":
    raise SystemExit(main())
