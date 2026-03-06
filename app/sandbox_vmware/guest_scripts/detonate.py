#!/usr/bin/env python3
"""
Sentinel – Visible VM Detonation Script
────────────────────────────────────────
Deployed into the guest VM by the host sandbox controller.
Visibly opens the sample file, moves the mouse, clicks through basic
prompts/dialogs, and captures periodic screenshots — all designed to be
visible in the live preview stream.

Requirements (pre-installed in the sandbox VM):
    pip install pyautogui Pillow psutil

Usage:
    python detonate.py --sample C:\\Sandbox\\sample.exe --outdir C:\\Sandbox\\out
                       [--timeout 45] [--jobid sc_xxx]
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Attempt imports (graceful fallback) ──────────────────────────────────────
try:
    import pyautogui

    pyautogui.FAILSAFE = False  # mouse-to-corner won't abort
    pyautogui.PAUSE = 0.08
except ImportError:
    pyautogui = None  # type: ignore[assignment]

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]


IS_WIN = os.name == "nt"

# ── Logging to JSONL ────────────────────────────────────────────────────────


class ActionLog:
    """Append-only JSONL log of every visible action."""

    def __init__(self, path: Path):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, action: str, detail: str = "", status: str = "ok") -> None:
        entry = {
            "ts": datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3],
            "action": action,
            "detail": detail[:300],
            "status": status,
        }
        try:
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except OSError:
            pass
        print(f"[{entry['ts']}] {status.upper():7s} | {action}: {detail}")


# ── Screenshot helper ────────────────────────────────────────────────────────


def take_screenshot(out_dir: Path, label: str = "") -> Optional[str]:
    """Save a full-screen screenshot. Returns saved path or None."""
    shots_dir = out_dir / "shots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    name = f"det_{label + '_' if label else ''}{ts}.png"
    dest = shots_dir / name
    try:
        if pyautogui is not None:
            img = pyautogui.screenshot()
            img.save(str(dest))
            return str(dest)
        # Fallback: PowerShell .NET screen capture (works without pyautogui)
        if IS_WIN:
            ps = (
                "Add-Type -An System.Windows.Forms,System.Drawing;"
                "$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
                "$i=[System.Drawing.Bitmap]::new($b.Width,$b.Height);"
                "$g=[System.Drawing.Graphics]::FromImage($i);"
                "$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);"
                f"$i.Save('{dest}',[System.Drawing.Imaging.ImageFormat]::Png)"
            )
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
                timeout=10, capture_output=True,
            )
            if dest.exists():
                return str(dest)
    except Exception:
        pass
    return None


# ── Mouse movement helpers ───────────────────────────────────────────────────


def smooth_move(x: int, y: int, duration: float = 0.4) -> None:
    """Visibly slide the mouse cursor to (x, y)."""
    if pyautogui is None:
        return
    try:
        pyautogui.moveTo(x, y, duration=duration)
    except Exception:
        pass


def desktop_sweep(w: int, h: int) -> None:
    """Sweep the mouse across the desktop (visible activity)."""
    cx, cy = w // 2, h // 2
    smooth_move(cx, cy, 0.3)
    for tx, ty in [
        (int(w * 0.15), int(h * 0.15)),
        (int(w * 0.85), int(h * 0.15)),
        (int(w * 0.85), int(h * 0.80)),
        (int(w * 0.15), int(h * 0.80)),
        (cx, cy),
    ]:
        smooth_move(tx, ty, 0.25)
        time.sleep(0.1)


def taskbar_hover(w: int, h: int) -> None:
    """Hover over taskbar elements (Start, clock)."""
    smooth_move(w // 2, h - 18, 0.25)
    time.sleep(0.3)
    smooth_move(20, h - 18, 0.2)  # Start area
    time.sleep(0.4)
    smooth_move(w - 60, h - 18, 0.2)  # Clock / tray
    time.sleep(0.3)
    smooth_move(w // 2, h // 2, 0.2)


# ── Dialog / prompt clicker ──────────────────────────────────────────────────

# Common button texts in UAC/installer/security prompts
_DIALOG_BUTTONS: List[str] = [
    "Yes", "Run", "Allow", "Continue", "OK", "Open",
    "Install", "Next", "I Agree", "Accept", "Finish",
    "&Yes", "&Run", "&Allow", "&OK",
]


def click_dialogs(logger: ActionLog, rounds: int = 6, interval: float = 2.0) -> int:
    """Try to locate and click common dialog buttons.

    Uses pyautogui.locateOnScreen with button images if available,
    otherwise falls back to keyboard shortcuts (Alt+Y for UAC, Enter
    for generic dialogs).

    Returns total number of clicks performed.
    """
    clicks = 0
    for _ in range(rounds):
        time.sleep(interval)
        # Strategy 1: Send Alt+Y (common UAC "Yes" accelerator)
        if pyautogui is not None:
            try:
                pyautogui.hotkey("alt", "y")
                clicks += 1
                logger.log("click_dialog", "Sent Alt+Y (UAC / confirm)")
            except Exception:
                pass
            # Strategy 2: Press Enter (catches generic OK/Continue dialogs)
            try:
                time.sleep(0.5)
                pyautogui.press("enter")
                clicks += 1
                logger.log("click_dialog", "Sent Enter (generic confirm)")
            except Exception:
                pass
    return clicks


# ── Open-file strategies ─────────────────────────────────────────────────────


def open_via_startfile(sample: Path, logger: ActionLog) -> bool:
    """Use os.startfile() – the standard Windows shell open."""
    if not IS_WIN:
        return False
    try:
        os.startfile(str(sample))  # type: ignore[attr-defined]
        logger.log("open_file", f"os.startfile({sample.name})")
        return True
    except Exception as exc:
        logger.log("open_file", f"os.startfile failed: {exc}", "warn")
        return False


def open_via_run_dialog(sample: Path, logger: ActionLog) -> bool:
    """Open the file using Win+R Run dialog (visible typing)."""
    if pyautogui is None:
        return False
    try:
        pyautogui.hotkey("win", "r")
        time.sleep(1.5)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.press("delete")
        time.sleep(0.1)
        # Type the path visibly (interval makes each character visible)
        pyautogui.typewrite(str(sample), interval=0.035)
        time.sleep(0.6)
        logger.log("open_file", f"Run dialog filled: {sample.name}")
        pyautogui.press("enter")
        logger.log("open_file", "Run dialog submitted")
        return True
    except Exception as exc:
        logger.log("open_file", f"Run dialog failed: {exc}", "warn")
        return False


def open_via_explorer(sample: Path, logger: ActionLog) -> bool:
    """Open containing folder in Explorer and double-click."""
    if not IS_WIN or pyautogui is None:
        return False
    try:
        subprocess.Popen(["explorer.exe", "/select,", str(sample)])
        time.sleep(3)
        # Attempt double-click in the center of the screen (rough heuristic)
        w, h = pyautogui.size()
        smooth_move(w // 2, h // 2, 0.3)
        time.sleep(0.5)
        pyautogui.doubleClick()
        logger.log("open_file", f"Explorer double-click on {sample.name}")
        return True
    except Exception as exc:
        logger.log("open_file", f"Explorer failed: {exc}", "warn")
        return False


# ── Process monitoring ───────────────────────────────────────────────────────


def snapshot_processes() -> Dict[int, str]:
    """Return dict of {pid: name} for current processes."""
    if psutil is None:
        return {}
    result: Dict[int, str] = {}
    for p in psutil.process_iter(["pid", "name"]):
        try:
            result[p.info["pid"]] = p.info["name"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return result


# ── Periodic screenshot thread ───────────────────────────────────────────────


def _screenshot_loop(
    out_dir: Path, stop_event: threading.Event, interval: float = 2.0
) -> None:
    """Capture screenshots at regular intervals until stopped."""
    idx = 0
    while not stop_event.is_set():
        take_screenshot(out_dir, label=f"tick_{idx:03d}")
        idx += 1
        stop_event.wait(interval)


# ── Main detonation routine ──────────────────────────────────────────────────


def detonate(
    sample_path: str,
    out_dir: str = "C:\\Sandbox\\out",
    timeout_sec: int = 45,
    job_id: str = "unknown",
) -> Dict[str, Any]:
    """
    Run the full visible detonation sequence and return a behavior dict.

    Phases:
        1) Desktop sweep (mouse movement — anti-sandbox evasion)
        2) Taskbar hover
        3) Open sample (visible, multiple strategies)
        4) Click through prompts (UAC / installer dialogs)
        5) Monitor for new processes
        6) Collect periodic screenshots
        7) Final summary
    """
    sample = Path(sample_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "shots").mkdir(parents=True, exist_ok=True)

    logger = ActionLog(out / "detonate_actions.jsonl")
    logger.log("start", f"job={job_id}  sample={sample.name}  timeout={timeout_sec}s")

    result: Dict[str, Any] = {
        "job_id": job_id,
        "sample_name": sample.name,
        "sample_path": str(sample),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "phases": {},
        "new_processes": [],
        "screenshots": [],
        "dialog_clicks": 0,
        "sample_opened": False,
        "open_method": "",
        "errors": [],
    }

    # Detect screen size
    if pyautogui is not None:
        w, h = pyautogui.size()
    else:
        w, h = 1920, 1080
    logger.log("screen", f"{w}x{h}")

    # ── Phase 1: Desktop sweep ───────────────────────────────────────────
    logger.log("phase", "Phase 1: Desktop sweep")
    try:
        desktop_sweep(w, h)
        result["phases"]["desktop_sweep"] = "ok"
    except Exception as exc:
        result["phases"]["desktop_sweep"] = f"error: {exc}"
        result["errors"].append(f"desktop_sweep: {exc}")
    shot = take_screenshot(out, "sweep")
    if shot:
        result["screenshots"].append(shot)

    # ── Phase 2: Taskbar hover ───────────────────────────────────────────
    logger.log("phase", "Phase 2: Taskbar hover")
    try:
        taskbar_hover(w, h)
        result["phases"]["taskbar_hover"] = "ok"
    except Exception as exc:
        result["phases"]["taskbar_hover"] = f"error: {exc}"
        result["errors"].append(f"taskbar_hover: {exc}")
    shot = take_screenshot(out, "taskbar")
    if shot:
        result["screenshots"].append(shot)

    # ── Phase 3: Open the sample ─────────────────────────────────────────
    logger.log("phase", "Phase 3: Open sample")
    baseline_procs = snapshot_processes()

    if not sample.exists():
        logger.log("open_file", f"Sample not found: {sample}", "error")
        result["errors"].append(f"Sample not found: {sample}")
    else:
        # Try multiple strategies
        opened = open_via_run_dialog(sample, logger)
        if not opened:
            opened = open_via_startfile(sample, logger)
        if not opened:
            opened = open_via_explorer(sample, logger)
        result["sample_opened"] = opened
        result["open_method"] = (
            "run_dialog" if opened else "none"
        )

    shot = take_screenshot(out, "after_open")
    if shot:
        result["screenshots"].append(shot)
    time.sleep(2)

    # ── Phase 4: Start periodic screenshots ──────────────────────────────
    stop_shots = threading.Event()
    shot_thread = threading.Thread(
        target=_screenshot_loop,
        args=(out, stop_shots, 2.5),
        daemon=True,
    )
    shot_thread.start()

    # ── Phase 5: Click through dialogs ───────────────────────────────────
    logger.log("phase", "Phase 5: Click dialogs / prompts")
    dialog_rounds = max(3, timeout_sec // 8)
    result["dialog_clicks"] = click_dialogs(
        logger, rounds=dialog_rounds, interval=2.5
    )

    # ── Phase 6: Wait / monitor ──────────────────────────────────────────
    logger.log("phase", "Phase 6: Monitoring")
    remaining = max(0, timeout_sec - dialog_rounds * 3)
    if remaining > 0:
        time.sleep(min(remaining, 20))

    # ── Phase 7: Collect new processes ───────────────────────────────────
    stop_shots.set()
    shot_thread.join(timeout=5)

    current_procs = snapshot_processes()
    new_pids = set(current_procs.keys()) - set(baseline_procs.keys())
    for pid in sorted(new_pids):
        name = current_procs.get(pid, "?")
        result["new_processes"].append({"pid": pid, "name": name})
    logger.log("processes", f"{len(new_pids)} new processes detected")

    # Final screenshot
    shot = take_screenshot(out, "final")
    if shot:
        result["screenshots"].append(shot)

    # Collect all shot files
    shots_dir = out / "shots"
    if shots_dir.is_dir():
        result["screenshots"] = sorted(
            str(p) for p in shots_dir.glob("det_*.png")
        )

    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    result["phases"]["complete"] = "ok"
    logger.log("done", f"Detonation finished — {len(result['screenshots'])} screenshots")

    # Write behavior.json
    behavior_path = out / "detonate_behavior.json"
    try:
        with open(behavior_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, default=str)
        logger.log("save", f"Wrote {behavior_path}")
    except Exception as exc:
        logger.log("save", f"Failed: {exc}", "error")

    return result


# ── CLI entry-point ──────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sentinel visible VM detonation script"
    )
    parser.add_argument("--sample", required=True, help="Path to sample file")
    parser.add_argument("--outdir", default="C:\\Sandbox\\out", help="Output dir")
    parser.add_argument("--timeout", type=int, default=45, help="Timeout in seconds")
    parser.add_argument("--jobid", default="unknown", help="Job ID")
    args = parser.parse_args()

    result = detonate(
        sample_path=args.sample,
        out_dir=args.outdir,
        timeout_sec=args.timeout,
        job_id=args.jobid,
    )
    # Exit 0 for success, 1 for critical failures
    if not result.get("sample_opened") and result.get("errors"):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
