"""
Sentinel Visual Agent Payload
=============================
Runs INSIDE the sandbox VM to visually interact with a dropped sample
like a human operator, with a floating HUD overlay showing status.

Compiled to agent.exe via PyInstaller and deployed by VMwareRunner.

Usage:
    agent.exe <target_file>                    # e.g. agent.exe C:\\Sentinel\\Jobs\\abc123\\rufus.exe
    agent.exe <target_file> --timeout 90       # custom interaction timeout
    agent.exe <target_file> --no-hud           # disable overlay (headless)
"""

from __future__ import annotations

import argparse
import ctypes
import os
import queue
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# PyAutoGUI setup – disable fail-safe (no mouse-corner abort in a VM)
# ---------------------------------------------------------------------------
import pyautogui
from pywinauto import Desktop

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.3  # small delay between pyautogui calls

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCREEN_W, SCREEN_H = pyautogui.size()
HUD_WIDTH = 520
HUD_HEIGHT = 38
HUD_X = (SCREEN_W - HUD_WIDTH) // 2
HUD_Y = 18
MOVE_DURATION = 1.4  # seconds – human-like mouse travel time
EASING = pyautogui.easeInOutQuad

# ---------------------------------------------------------------------------
# HUD (Tkinter overlay running on its own thread)
# ---------------------------------------------------------------------------
_hud_queue: queue.Queue[str | None] = queue.Queue()


def _run_hud() -> None:
    """Tkinter main-loop on a daemon thread. Reads messages from _hud_queue."""
    import tkinter as tk

    root = tk.Tk()
    root.title("Sentinel Agent")
    root.overrideredirect(True)  # borderless
    root.attributes("-topmost", True)  # always on top
    root.attributes("-alpha", 0.88)  # slight transparency
    root.configure(bg="#1a1a2e")
    root.geometry(f"{HUD_WIDTH}x{HUD_HEIGHT}+{HUD_X}+{HUD_Y}")

    label = tk.Label(
        root,
        text="Sentinel Agent: Initializing…",
        font=("Consolas", 11, "bold"),
        fg="#00d2ff",
        bg="#1a1a2e",
        anchor="w",
        padx=12,
    )
    label.pack(fill="both", expand=True)

    def _poll() -> None:
        try:
            while True:
                msg = _hud_queue.get_nowait()
                if msg is None:  # shutdown sentinel
                    root.destroy()
                    return
                label.config(text=msg)
        except queue.Empty:
            pass
        root.after(80, _poll)

    root.after(80, _poll)
    root.mainloop()


def hud(text: str) -> None:
    """Push a status message to the overlay HUD."""
    _hud_queue.put(f"Sentinel Agent: {text}")


# ---------------------------------------------------------------------------
# Automation helpers
# ---------------------------------------------------------------------------


def _safe_move(x: int, y: int, duration: float = MOVE_DURATION) -> None:
    """Move mouse with human-like easing; clamp to screen bounds."""
    x = max(0, min(x, SCREEN_W - 1))
    y = max(0, min(y, SCREEN_H - 1))
    pyautogui.moveTo(x, y, duration=duration, tween=EASING)


def _find_on_screen(image_path: str, confidence: float = 0.7) -> tuple[int, int] | None:
    """Try to locate an image on screen; returns center (x, y) or None."""
    try:
        loc = pyautogui.locateOnScreen(image_path, confidence=confidence)
        if loc:
            return pyautogui.center(loc)
    except Exception:
        pass
    return None


def _human_scroll(clicks: int, pause: float = 0.35) -> None:
    """Scroll in small human-like increments."""
    direction = 1 if clicks > 0 else -1
    for _ in range(abs(clicks)):
        pyautogui.scroll(direction * 3)
        time.sleep(pause)


def _dismiss_uac() -> None:
    """Attempt to dismiss UAC or 'Run as Admin' prompts via keyboard."""
    hud("Handling UAC / elevation prompt…")
    time.sleep(1.5)
    # Alt+Y is the UAC "Yes" shortcut on many Windows 10 builds
    pyautogui.hotkey("alt", "y")
    time.sleep(1.0)
    # Fallback: try pressing Enter and Left+Enter patterns
    pyautogui.press("enter")
    time.sleep(0.5)


# ---------------------------------------------------------------------------
# Anti-Evasion: Human Environment Simulator
# ---------------------------------------------------------------------------


def simulate_human_environment() -> None:
    """Create desktop decoys, generate browser history, and perform organic
    mouse movement so evasive malware believes it is on a real user's machine."""

    # --- 1. Desktop Decoys (Bait Files) ------------------------------------
    hud("Seeding desktop with decoy files\u2026")
    desktop = os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\user"), "Desktop")
    os.makedirs(desktop, exist_ok=True)

    decoys = {
        "Passwords_2026.txt": (
            "=== Personal Password Vault ===\n"
            "Gmail: kR#92xLp!q7\n"
            "VPN Corp: Z!tm4Qr@8801\n"
            "Banking: j3Fk$9sPvW\n"
            "Updated: 2026-03-01\n"
        ),
        "Q3_Financial_Report.docx": (
            "Quarterly Financial Summary - CONFIDENTIAL\n"
            "Revenue: $4,812,300   Expenses: $3,207,500\n"
            "Net Profit: $1,604,800\n"
            "Prepared by: Finance Dept.\n"
        ),
        "VPN_Config.ini": (
            "[vpn]\n"
            "server = vpn-corp.internal.local\n"
            "port = 1194\n"
            "protocol = udp\n"
            "auth = sha256\n"
            "ca = /etc/openvpn/ca.crt\n"
        ),
        "Meeting_Notes_March.txt": (
            "Team Sync - March 10 2026\n"
            "Attendees: Sarah, Mike, Dev-Ops\n"
            "Action items:\n"
            " - Migrate staging to new cluster\n"
            " - Review Q2 budget proposal\n"
        ),
    }

    for filename, content in decoys.items():
        filepath = os.path.join(desktop, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as fh:
                fh.write(content)
        except OSError:
            pass  # non-fatal; continue with remaining decoys

    hud(f"Placed {len(decoys)} decoy files on Desktop")
    time.sleep(0.5)

    # --- 2. Browser History Generation -------------------------------------
    hud("Generating realistic browser traffic\u2026")
    try:
        subprocess.Popen(                          # noqa: S606
            "start microsoft-edge:https://en.wikipedia.org/wiki/Special:Random",
            shell=True,                            # noqa: S602 — intentional sandbox automation
        )
        time.sleep(5.0)  # let Edge render the page

        # Organic scrolling on the wiki page
        for _ in range(random.randint(3, 5)):
            pyautogui.scroll(-random.randint(2, 5))
            time.sleep(random.uniform(0.6, 1.4))

        time.sleep(1.0)
        pyautogui.hotkey("alt", "F4")  # close browser, leaving history/cache
        time.sleep(1.5)
        hud("Browser session closed — cache resident")
    except Exception:
        hud("Browser decoy skipped (Edge unavailable)")
        time.sleep(0.5)

    # --- 3. Organic Mouse Jiggle (The Pulse) -------------------------------
    hud("Simulating human presence\u2026")
    num_points = random.randint(4, 6)
    for _ in range(num_points):
        rx = random.randint(100, SCREEN_W - 100)
        ry = random.randint(100, SCREEN_H - 100)
        dur = random.uniform(0.5, 1.5)
        _safe_move(rx, ry, duration=dur)
        time.sleep(random.uniform(0.3, 0.8))

    hud("Anti-evasion environment ready")
    time.sleep(0.5)


# ---------------------------------------------------------------------------
# Main automation sequence
# ---------------------------------------------------------------------------


def run_agent(target: Path, *, timeout: int = 120, enable_hud: bool = True) -> None:
    """Execute the full visual agent sequence."""

    # --- Start HUD ----------------------------------------------------------
    if enable_hud:
        hud_thread = threading.Thread(target=_run_hud, daemon=True)
        hud_thread.start()
        time.sleep(0.6)  # let Tk initialise

    hud("Initializing…")
    time.sleep(1.0)

    target_dir = str(target.parent)   # e.g. C:\Sandbox
    filename = target.name            # e.g. rufus.exe

    cx, cy = SCREEN_W // 2, SCREEN_H // 2

    # --- 1. Verify target exists --------------------------------------------
    hud(f"Checking target: {filename}")
    if not target.exists():
        hud(f"ERROR — target not found: {target}")
        time.sleep(3)
        return

    hud(f"Target confirmed: {filename}")
    time.sleep(1.0)

    # --- 1a. Anti-Evasion: seed environment before payload execution --------
    simulate_human_environment()

    # --- 1b. Archive extraction via 7-Zip -----------------------------------
    ARCHIVE_EXTS = {".zip", ".rar", ".7z"}
    HIGH_RISK_EXTS = {".exe", ".bat", ".cmd", ".vbs", ".ps1", ".js", ".scr"}
    SEVEN_ZIP = r"C:\Program Files\7-Zip\7z.exe"
    EXTRACT_DIR = Path(r"C:\Sandbox\extracted")

    if target.suffix.lower() in ARCHIVE_EXTS:
        if not os.path.exists(SEVEN_ZIP):
            hud("ERROR: 7z.exe missing! Check VM Snapshot.")
            time.sleep(4)
            # Fall through to native execution of the archive itself
        else:
            EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
            hud("Extracting archive using 7-Zip...")

            cmd = [SEVEN_ZIP, "x", str(target), f"-o{EXTRACT_DIR}", "-y", "-pinfected"]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    hud("Extraction OK")
                else:
                    hud(f"7-Zip exit code {result.returncode} — checking contents")
            except subprocess.TimeoutExpired:
                hud("WARNING — 7-Zip extraction timed out")

            time.sleep(2.0)  # let filesystem settle

            # Payload hunting — find the real executable inside
            if EXTRACT_DIR.exists() and any(EXTRACT_DIR.iterdir()):
                hud("Scanning extracted files for payload…")
                payload_found = None
                for dirpath, _dirs, files in os.walk(str(EXTRACT_DIR)):
                    for fname in files:
                        if Path(fname).suffix.lower() in HIGH_RISK_EXTS:
                            payload_found = Path(dirpath) / fname
                            break
                    if payload_found:
                        break

                if payload_found:
                    hud(f"Payload found: {payload_found.name}")
                    target = payload_found
                    target_dir = str(target.parent)
                    filename = target.name
                else:
                    hud("No high-risk payload — detonating first file")
                    for dirpath, _dirs, files in os.walk(str(EXTRACT_DIR)):
                        if files:
                            target = Path(dirpath) / files[0]
                            target_dir = str(target.parent)
                            filename = target.name
                            break

            time.sleep(1.0)

    # --- 2. Open Explorer natively at target folder -------------------------
    hud(f"Opening folder: {target_dir}")
    try:
        os.startfile(target_dir)  # noqa: S606 – intentional sandbox automation
    except Exception as exc:
        hud(f"Explorer failed: {exc}")
        time.sleep(3)
        return
    time.sleep(2.5)  # wait for Explorer to fully render

    # --- 3. Execute payload natively (bypasses hidden-extension issue) ------
    hud(f"Executing payload natively: {filename}")
    try:
        os.startfile(str(target))  # noqa: S606 – intentional sandbox automation
    except AttributeError:
        subprocess.Popen([str(target)], shell=True)  # noqa: S603
    time.sleep(4.0)  # wait for app / installer / viewer to load

    # --- 4. Intelligent Installer / Prompt Bypass (pywinauto) ---------------
    hud("Starting context-aware UI interaction (45s)…")

    # Keywords that indicate an actionable button in installers / prompts
    _CLICK_KEYWORDS = [
        "next", "agree", "accept", "install", "finish",
        "yes", "ok", "run", "continue",
    ]
    # Window titles belonging to the OS chrome – never interact with these
    _IGNORED_TITLES = {
        "taskbar", "start", "program manager",
        "windows input experience", "text input application",
        "sentinel agent",  # our own HUD overlay
    }

    interaction_start = time.monotonic()
    INTERACTION_DURATION = 45  # seconds

    while (time.monotonic() - interaction_start) < INTERACTION_DURATION:
        remaining = int(INTERACTION_DURATION - (time.monotonic() - interaction_start))
        hud(f"UI scan… {remaining}s left")

        try:
            windows = Desktop(backend="uia").windows()
        except Exception:
            time.sleep(2)
            continue

        for win in windows:
            # --- Target Identification ---
            try:
                title = (win.window_text() or "").strip()
            except Exception:
                continue

            if not title or title.lower() in _IGNORED_TITLES:
                continue

            hud(f"Inspecting: {title[:40]}")

            clicked = False
            try:
                # Walk the control tree looking for Buttons / CheckBoxes
                controls = win.descendants(control_type="Button") + \
                           win.descendants(control_type="CheckBox")
            except Exception:
                # Window disappeared or access denied mid-scan
                controls = []

            for ctrl in controls:
                try:
                    ctrl_text = (ctrl.window_text() or "").strip().lower()
                except Exception:
                    continue

                if any(kw in ctrl_text for kw in _CLICK_KEYWORDS):
                    try:
                        hud(f"Clicking: '{ctrl.window_text()}'")
                        ctrl.invoke()  # native UIA Invoke – no coordinates needed
                        clicked = True
                        time.sleep(1.0)
                    except Exception:
                        # Control might have gone stale; try click_input fallback
                        try:
                            ctrl.click_input()
                            clicked = True
                            time.sleep(1.0)
                        except Exception:
                            pass

            # --- Graceful Fallback ---
            # Active window with no recognisable buttons → send Enter
            if not clicked and controls is not None:
                try:
                    if win.is_active():
                        hud(f"No buttons found in '{title[:30]}' — sending Enter")
                        pyautogui.press("enter")
                        time.sleep(0.8)
                except Exception:
                    pass

        # --- Human-like mouse movement between scans ---
        jx = random.randint(int(cx * 0.6), int(cx * 1.4))
        jy = random.randint(int(cy * 0.6), int(cy * 1.4))
        _safe_move(jx, jy, duration=random.uniform(0.4, 1.2))
        time.sleep(random.uniform(1.5, 3.0))

    # --- 6. Human-like scrolling --------------------------------------------
    hud("Scrolling through application content…")
    _safe_move(cx, cy, duration=0.6)
    time.sleep(0.5)

    _human_scroll(-5)   # scroll down
    time.sleep(1.5)
    hud("Reading content…")
    _human_scroll(-5)   # scroll down more
    time.sleep(2.0)
    _human_scroll(8)    # scroll back up
    time.sleep(1.0)

    # --- 7. Mouse exploration -----------------------------------------------
    hud("Exploring UI elements…")
    explore_points = [
        (cx - 180, cy - 120),
        (cx + 160, cy - 80),
        (cx + 200, cy + 100),
        (cx - 150, cy + 130),
        (cx, cy),
    ]
    for px, py in explore_points:
        _safe_move(px, py, duration=1.0)
        time.sleep(0.8)

    # --- 8. Monitor for remaining timeout -----------------------------------
    poll_interval = 10
    hud(f"Monitoring for {timeout}s (sample is running)…")
    start = time.monotonic()

    while (time.monotonic() - start) < timeout:
        remaining = int(timeout - (time.monotonic() - start))
        hud(f"Monitoring… {remaining}s remaining")
        time.sleep(poll_interval)
        # Occasional human-like mouse jiggle
        jx = cx + (int(time.monotonic()) % 60) - 30
        jy = cy + (int(time.monotonic()) % 40) - 20
        _safe_move(jx, jy, duration=0.6)

    # --- 9. Wrap up ---------------------------------------------------------
    hud("Analysis window complete. Shutting down agent.")
    time.sleep(2.0)

    # Signal HUD to close
    _hud_queue.put(None)
    time.sleep(0.5)


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sentinel Visual Agent – sandbox automation payload",
    )
    parser.add_argument(
        "target",
        type=Path,
        help="Full path to the sample file inside the VM (e.g. C:\\Sentinel\\Jobs\\abc\\malware.exe)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Seconds to keep the sample alive and monitored (default: 120)",
    )
    parser.add_argument(
        "--no-hud",
        action="store_true",
        help="Disable the floating status overlay",
    )
    args = parser.parse_args()

    if not args.target.exists():
        print(f"[!] Target file not found: {args.target}", file=sys.stderr)
        sys.exit(1)

    run_agent(args.target, timeout=args.timeout, enable_hud=not args.no_hud)


if __name__ == "__main__":
    main()
