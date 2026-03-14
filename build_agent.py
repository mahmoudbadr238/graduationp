"""Build sentinel_agent.exe and place it where the backend expects it.

Usage:
    python build_agent.py

What it does:
    1. Runs PyInstaller on tools/sandbox_agent/agent_payload.py
    2. Output name: sentinel_agent.exe  (--onefile --noconsole)
    3. Hidden imports: pyautogui, tkinter
    4. Copies the result to  <project_root>/dist/sentinel_agent.exe
       (both vmware_runner.py and sandbox_controller.py look there)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE = PROJECT_ROOT / "tools" / "sandbox_agent" / "agent_payload.py"
DIST_DIR = PROJECT_ROOT / "dist"
EXE_NAME = "sentinel_agent"
FINAL_EXE = DIST_DIR / f"{EXE_NAME}.exe"


def main() -> int:
    if not SOURCE.exists():
        print(f"[ERROR] Source not found: {SOURCE}")
        return 1

    print(f"[1/3] Building {EXE_NAME}.exe from {SOURCE.relative_to(PROJECT_ROOT)} ...")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name", EXE_NAME,
        "--hidden-import", "pyautogui",
        "--hidden-import", "tkinter",
        "--distpath", str(DIST_DIR),
        "--workpath", str(PROJECT_ROOT / "build" / EXE_NAME),
        "--specpath", str(PROJECT_ROOT),
        str(SOURCE),
    ]

    print(f"    Command: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    if result.returncode != 0:
        print(f"\n[ERROR] PyInstaller exited with code {result.returncode}")
        return result.returncode

    if not FINAL_EXE.exists():
        print(f"[ERROR] Expected output not found: {FINAL_EXE}")
        return 1

    size_mb = FINAL_EXE.stat().st_size / (1024 * 1024)
    print(f"\n[2/3] Built successfully: {FINAL_EXE}")
    print(f"       Size: {size_mb:.1f} MB")

    # Verify the path matches what the backend expects
    runner_expects = PROJECT_ROOT / "dist" / "sentinel_agent.exe"
    if FINAL_EXE.resolve() == runner_expects.resolve():
        print(f"[3/3] Path matches backend expectation: dist/sentinel_agent.exe  ✓")
    else:
        print(f"[WARN] Backend expects: {runner_expects}")
        print(f"       Actual output:   {FINAL_EXE}")

    print("\n[DONE] Ready for VM deployment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
