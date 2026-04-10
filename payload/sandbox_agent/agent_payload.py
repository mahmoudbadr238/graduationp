"""
Sentinel Visual Agent Payload — Human-Simulation Sandbox Agent
==============================================================
Runs INSIDE the sandbox VM to visually interact with a dropped sample
like a real human operator, defeating evasive malware that checks for
mouse movement, open documents, and user activity before executing.

Anti-evasion capabilities:
  - Realistic mouse movement with easeInOutQuad curves
  - Desktop honeypot files (passwords.txt opened in Notepad)
  - Browser history generation (Edge → Wikipedia)
  - Start menu & right-click interactions
  - Intelligent installer/prompt auto-clicking via UIA tree walking
  - Continuous human presence simulation during monitoring

Compiled to sentinel_agent.exe via PyInstaller and deployed by VMwareRunner.

Usage:
    agent.exe <target_file>                    # e.g. agent.exe C:\\Sandbox\\rufus.exe
    agent.exe <target_file> --timeout 90       # custom interaction timeout
    agent.exe <target_file> --no-hud           # disable overlay (headless)
"""

from __future__ import annotations

import argparse
import ctypes
import logging
import os
import queue
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging setup — file + console with detailed formatting
# ---------------------------------------------------------------------------
LOG_DIR = Path(os.environ.get("SENTINEL_LOG_DIR", r"C:\Sandbox"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)-7s] %(funcName)-28s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_DIR / "sentinel_agent.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("sentinel_agent")

# ---------------------------------------------------------------------------
# PyAutoGUI setup — disable fail-safe (no mouse-corner abort in a VM)
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

# Installer button keywords (case-insensitive matching)
CLICK_KEYWORDS = [
    "next >", "next", "i agree", "agree", "accept", "install",
    "finish", "yes", "ok", "run", "continue", "close",
]
# Setup/installer window title keywords
SETUP_TITLE_KEYWORDS = ["setup", "install", "wizard", "update"]
# Window titles belonging to OS chrome — never interact
IGNORED_TITLES = {
    "taskbar", "start", "program manager",
    "windows input experience", "text input application",
    "sentinel agent",  # our own HUD overlay
}

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
    """Push a status message to the overlay HUD and logger."""
    _hud_queue.put(f"Sentinel Agent: {text}")
    log.info("[HUD] %s", text)


# ---------------------------------------------------------------------------
# Automation helpers
# ---------------------------------------------------------------------------


def _safe_move(x: int, y: int, duration: float = MOVE_DURATION) -> None:
    """Move mouse with human-like easing; clamp to screen bounds."""
    x = max(0, min(x, SCREEN_W - 1))
    y = max(0, min(y, SCREEN_H - 1))
    log.debug("Mouse → (%d, %d) over %.2fs", x, y, duration)
    pyautogui.moveTo(x, y, duration=duration, tween=EASING)



def _human_scroll(clicks: int, pause: float = 0.35) -> None:
    """Scroll in small human-like increments."""
    direction = 1 if clicks > 0 else -1
    for _ in range(abs(clicks)):
        pyautogui.scroll(direction * 3)
        time.sleep(pause)


def _dismiss_uac() -> None:
    """Attempt to dismiss UAC or 'Run as Admin' prompts via keyboard."""
    log.info("UAC dismissal attempt")
    hud("Handling UAC / elevation prompt…")
    time.sleep(1.5)
    pyautogui.hotkey("alt", "y")
    time.sleep(1.0)
    pyautogui.press("enter")
    time.sleep(0.5)


# ---------------------------------------------------------------------------
# 1. Human Mouse Movement Simulation (pyautogui)
# ---------------------------------------------------------------------------


def simulate_human_activity() -> None:
    """Simulate realistic human presence: mouse sweeps, start menu,
    right-click desktop, random pauses — all with natural easing."""

    log.info("=== Human Activity Simulation START ===")
    hud("Simulating human presence…")

    # --- Natural mouse sweeps across the screen ---
    num_sweeps = random.randint(5, 8)
    log.info("Performing %d mouse sweeps", num_sweeps)
    for i in range(num_sweeps):
        rx = random.randint(80, SCREEN_W - 80)
        ry = random.randint(80, SCREEN_H - 80)
        dur = random.uniform(0.5, 1.5)
        log.debug("Sweep %d/%d → (%d, %d) in %.2fs", i + 1, num_sweeps, rx, ry, dur)
        _safe_move(rx, ry, duration=dur)
        time.sleep(random.uniform(0.3, 1.0))

    # --- Open and close the Start Menu ---
    log.info("Opening Start Menu")
    hud("Opening Start Menu…")
    pyautogui.press("win")
    time.sleep(random.uniform(1.5, 2.5))
    # Type something as if searching
    search_term = random.choice(["notepad", "calc", "paint", "settings"])
    log.info("Typing search: '%s'", search_term)
    pyautogui.typewrite(search_term, interval=random.uniform(0.08, 0.15))
    time.sleep(random.uniform(1.0, 2.0))
    pyautogui.press("escape")  # close start menu
    time.sleep(0.5)

    # --- Right-click on the desktop ---
    log.info("Right-clicking desktop for context menu")
    hud("Right-clicking desktop…")
    # Move to a clear area of the desktop
    _safe_move(SCREEN_W // 2, SCREEN_H // 2, duration=random.uniform(0.6, 1.2))
    time.sleep(0.3)
    # Minimize all windows first so desktop is visible
    pyautogui.hotkey("win", "d")
    time.sleep(1.0)
    pyautogui.rightClick(
        random.randint(SCREEN_W // 3, 2 * SCREEN_W // 3),
        random.randint(SCREEN_H // 3, 2 * SCREEN_H // 3),
    )
    time.sleep(random.uniform(1.0, 1.8))
    pyautogui.press("escape")  # dismiss context menu
    time.sleep(0.5)

    # --- Random idle pauses (simulates reading/thinking) ---
    idle_duration = random.uniform(1.0, 3.0)
    log.info("Idle pause: %.1fs", idle_duration)
    time.sleep(idle_duration)

    log.info("=== Human Activity Simulation END ===")


# ---------------------------------------------------------------------------
# 2. Intelligent Installer Hunting (pywinauto UIA)
# ---------------------------------------------------------------------------


def hunt_and_click_installers(duration: int = 45) -> None:
    """Continuously scan all visible windows for installer/setup dialogs
    and auto-click through them using the UIA accessibility backend.

    Runs for *duration* seconds, scanning every ~5 seconds.
    """
    log.info("=== Installer Hunter START (duration=%ds) ===", duration)
    hud(f"Installer hunter active ({duration}s)…")

    cx, cy = SCREEN_W // 2, SCREEN_H // 2
    start = time.monotonic()

    while (time.monotonic() - start) < duration:
        remaining = int(duration - (time.monotonic() - start))
        hud(f"Scanning windows… {remaining}s left")

        # --- Enumerate all top-level windows ---
        try:
            windows = Desktop(backend="uia").windows()
            log.debug("Found %d top-level windows", len(windows))
        except Exception as exc:
            log.warning("Desktop enumeration failed: %s", exc)
            time.sleep(5)
            continue

        for win in windows:
            try:
                title = (win.window_text() or "").strip()
            except Exception:
                continue

            if not title or title.lower() in IGNORED_TITLES:
                continue

            # Check if this looks like an installer/setup window
            title_lower = title.lower()
            is_setup = any(kw in title_lower for kw in SETUP_TITLE_KEYWORDS)

            if is_setup:
                log.info(">>> SETUP WINDOW DETECTED: '%s'", title)
            else:
                log.debug("Inspecting window: '%s'", title[:50])

            # --- Walk the control tree for clickable elements ---
            clicked = False
            try:
                controls = (
                    win.descendants(control_type="Button")
                    + win.descendants(control_type="CheckBox")
                )
                log.debug("  %d clickable controls in '%s'", len(controls), title[:40])
            except Exception as exc:
                log.debug("  Control enumeration failed for '%s': %s", title[:40], exc)
                controls = []

            for ctrl in controls:
                try:
                    ctrl_text = (ctrl.window_text() or "").strip()
                except Exception:
                    continue

                ctrl_lower = ctrl_text.lower()
                if any(kw in ctrl_lower for kw in CLICK_KEYWORDS):
                    # Found a matching button — click it
                    log.info("  CLICKING: '%s' in window '%s'", ctrl_text, title[:40])
                    try:
                        ctrl.invoke()  # native UIA Invoke
                        clicked = True
                        log.info("  → invoke() succeeded")
                        time.sleep(1.0)
                    except Exception as exc1:
                        log.debug("  → invoke() failed (%s), trying click_input()", exc1)
                        try:
                            ctrl.click_input()
                            clicked = True
                            log.info("  → click_input() succeeded")
                            time.sleep(1.0)
                        except Exception as exc2:
                            log.warning("  → click_input() also failed: %s", exc2)

            # If this is an active setup window with no recognized buttons, press Enter
            if not clicked and is_setup:
                try:
                    if win.is_active():
                        log.info("  No buttons matched in '%s' — sending Enter", title[:40])
                        pyautogui.press("enter")
                        time.sleep(0.8)
                except Exception:
                    pass

        # --- Human-like mouse movement between scan cycles ---
        jx = random.randint(int(cx * 0.6), int(cx * 1.4))
        jy = random.randint(int(cy * 0.6), int(cy * 1.4))
        _safe_move(jx, jy, duration=random.uniform(0.4, 1.0))
        time.sleep(random.uniform(3.5, 5.5))  # ~5s between scans

    log.info("=== Installer Hunter END ===")


# ---------------------------------------------------------------------------
# 3. Honeypot Interaction — bait ransomware into encrypting
# ---------------------------------------------------------------------------


def create_honeypot_files() -> None:
    """Create decoy files on the Desktop, open passwords.txt in Notepad,
    and type fake credentials to trigger keyloggers and ransomware."""

    log.info("=== Honeypot Setup START ===")
    hud("Seeding desktop with honeypot files…")
    desktop = os.path.join(os.environ.get("USERPROFILE", r"C:\Users\user"), "Desktop")
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
        "crypto_wallet_seed.txt": (
            "BIP39 Recovery Seed (DO NOT SHARE)\n"
            "abandon ability able about above absent absorb abstract absurd abuse access accident\n"
            "Wallet: bc1q42lja79elem0anu8q860g3ez7jp8kq5nly5k\n"
        ),
    }

    for filename, content in decoys.items():
        filepath = os.path.join(desktop, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as fh:
                fh.write(content)
            log.info("Created decoy: %s", filepath)
        except OSError as exc:
            log.warning("Failed to create decoy %s: %s", filename, exc)

    hud(f"Placed {len(decoys)} honeypot files on Desktop")
    time.sleep(0.8)

    # --- Open passwords.txt in Notepad and type live credentials ---
    passwords_path = os.path.join(desktop, "Passwords_2026.txt")
    log.info("Opening Notepad with honeypot: %s", passwords_path)
    hud("Opening password file in Notepad…")

    try:
        subprocess.Popen(["notepad.exe", passwords_path])  # noqa: S603
        time.sleep(3.0)  # wait for Notepad to render

        # Type additional fake passwords to trigger keyloggers
        hud("Typing fake credentials…")
        log.info("Typing additional honeypot credentials into Notepad")
        extra_lines = [
            "",
            "# Added just now:",
            "AWS Console: admin@corp / Tr0ub4dor&3",
            "SSH root: r00t_P@ss!2026",
            "Azure AD: sysadmin / G7k#mQ9$zW",
        ]
        for line in extra_lines:
            pyautogui.hotkey("ctrl", "End")  # go to end of file
            pyautogui.press("enter")
            pyautogui.typewrite(line, interval=random.uniform(0.04, 0.10))
            time.sleep(random.uniform(0.3, 0.8))
            log.debug("Typed: %s", line)

        # Save but leave open (honeypot stays visible)
        pyautogui.hotkey("ctrl", "s")
        time.sleep(0.5)
        log.info("Notepad saved — honeypot active and visible")
        hud("Honeypot file open — bait active")

    except Exception as exc:
        log.warning("Notepad honeypot failed: %s", exc)
        hud("Honeypot Notepad failed — continuing")

    time.sleep(1.0)
    log.info("=== Honeypot Setup END ===")


# ---------------------------------------------------------------------------
# 4. Browser History Generation — defeat VM-detection via empty profile
# ---------------------------------------------------------------------------


def generate_browser_history() -> None:
    """Open Edge to a random Wikipedia page, scroll around, then close.
    Leaves cache/history/cookies behind so malware sees a used browser."""

    log.info("=== Browser History Generation START ===")
    hud("Generating realistic browser traffic…")

    try:
        subprocess.Popen(  # noqa: S606
            "start microsoft-edge:https://en.wikipedia.org/wiki/Special:Random",
            shell=True,  # noqa: S602 — intentional sandbox automation
        )
        time.sleep(5.0)  # let Edge render the page

        # Organic scrolling on the wiki page
        scroll_count = random.randint(3, 6)
        log.info("Scrolling %d times on Wikipedia", scroll_count)
        for i in range(scroll_count):
            amount = -random.randint(2, 5)
            pyautogui.scroll(amount)
            log.debug("Scroll %d/%d: %d clicks", i + 1, scroll_count, amount)
            time.sleep(random.uniform(0.6, 1.4))

        time.sleep(1.0)
        pyautogui.hotkey("alt", "F4")  # close browser
        time.sleep(1.5)
        log.info("Browser closed — cache/history resident")
        hud("Browser session closed — cache resident")

    except Exception as exc:
        log.warning("Browser history generation failed: %s", exc)
        hud("Browser decoy skipped (Edge unavailable)")

    log.info("=== Browser History Generation END ===")


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

    log.info("=" * 60)
    log.info("SENTINEL AGENT STARTED")
    log.info("Target: %s", target)
    log.info("Timeout: %ds", timeout)
    log.info("Screen: %dx%d", SCREEN_W, SCREEN_H)
    log.info("=" * 60)

    hud("Initializing…")
    time.sleep(1.0)

    target_dir = str(target.parent)
    filename = target.name
    cx, cy = SCREEN_W // 2, SCREEN_H // 2

    # --- 1. Verify target exists -------------------------------------------
    hud(f"Checking target: {filename}")
    if not target.exists():
        log.error("TARGET NOT FOUND: %s", target)
        hud(f"ERROR — target not found: {target}")
        time.sleep(3)
        return

    log.info("Target confirmed: %s (%.1f KB)", target, target.stat().st_size / 1024)
    hud(f"Target confirmed: {filename}")
    time.sleep(1.0)

    # --- 2. Anti-Evasion Phase 1: Seed human environment -------------------
    create_honeypot_files()
    generate_browser_history()
    simulate_human_activity()

    # --- 3. Archive extraction via 7-Zip -----------------------------------
    ARCHIVE_EXTS = {".zip", ".rar", ".7z"}
    HIGH_RISK_EXTS = {".exe", ".bat", ".cmd", ".vbs", ".ps1", ".js", ".scr"}
    SEVEN_ZIP = r"C:\Program Files\7-Zip\7z.exe"
    EXTRACT_DIR = Path(r"C:\Sandbox\extracted")

    if target.suffix.lower() in ARCHIVE_EXTS:
        log.info("Archive detected: %s — attempting extraction", target.suffix)
        if not os.path.exists(SEVEN_ZIP):
            log.error("7z.exe missing at %s — cannot extract", SEVEN_ZIP)
            hud("ERROR: 7z.exe missing! Check VM Snapshot.")
            time.sleep(4)
        else:
            EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
            hud("Extracting archive using 7-Zip...")

            cmd = [SEVEN_ZIP, "x", str(target), f"-o{EXTRACT_DIR}", "-y", "-pinfected"]
            log.info("Extraction command: %s", " ".join(cmd))
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                log.info("7-Zip exit code: %d", result.returncode)
                if result.returncode == 0:
                    hud("Extraction OK")
                else:
                    hud(f"7-Zip exit code {result.returncode} — checking contents")
            except subprocess.TimeoutExpired:
                log.warning("7-Zip extraction timed out")
                hud("WARNING — 7-Zip extraction timed out")

            time.sleep(2.0)

            # Payload hunting
            if EXTRACT_DIR.exists() and any(EXTRACT_DIR.iterdir()):
                log.info("Scanning extracted files for high-risk payload…")
                hud("Scanning extracted files for payload…")
                payload_found = None
                for dirpath, _dirs, files in os.walk(str(EXTRACT_DIR)):
                    for fname in files:
                        log.debug("  Found: %s", fname)
                        if Path(fname).suffix.lower() in HIGH_RISK_EXTS:
                            payload_found = Path(dirpath) / fname
                            break
                    if payload_found:
                        break

                if payload_found:
                    log.info("Payload selected: %s", payload_found)
                    hud(f"Payload found: {payload_found.name}")
                    target = payload_found
                    target_dir = str(target.parent)
                    filename = target.name
                else:
                    log.info("No high-risk file — using first extracted file")
                    hud("No high-risk payload — detonating first file")
                    for dirpath, _dirs, files in os.walk(str(EXTRACT_DIR)):
                        if files:
                            target = Path(dirpath) / files[0]
                            target_dir = str(target.parent)
                            filename = target.name
                            break

            time.sleep(1.0)

    # --- 4. Open Explorer at target folder ---------------------------------
    log.info("Opening Explorer at: %s", target_dir)
    hud(f"Opening folder: {target_dir}")
    try:
        os.startfile(target_dir)  # noqa: S606 — intentional sandbox automation
    except Exception as exc:
        log.error("Explorer launch failed: %s", exc)
        hud(f"Explorer failed: {exc}")
        time.sleep(3)
        return
    time.sleep(2.5)

    # --- 5. Execute payload ------------------------------------------------
    log.info("DETONATING PAYLOAD: %s", target)
    hud(f"Executing payload: {filename}")
    try:
        os.startfile(str(target))  # noqa: S606 — intentional sandbox automation
    except AttributeError:
        subprocess.Popen([str(target)], shell=True)  # noqa: S603
    time.sleep(4.0)

    # --- 6. Dismiss potential UAC prompt -----------------------------------
    _dismiss_uac()

    # --- 7. Installer/Prompt Auto-Click Phase (pywinauto) ------------------
    hunt_and_click_installers(duration=45)

    # --- 8. Human-like scrolling & UI exploration --------------------------
    log.info("Post-detonation UI exploration")
    hud("Scrolling through application content…")
    _safe_move(cx, cy, duration=0.6)
    time.sleep(0.5)

    _human_scroll(-5)
    time.sleep(1.5)
    hud("Reading content…")
    _human_scroll(-5)
    time.sleep(2.0)
    _human_scroll(8)
    time.sleep(1.0)

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

    # --- 9. Monitor for remaining timeout ----------------------------------
    poll_interval = 10
    log.info("Entering monitoring phase (%ds)", timeout)
    hud(f"Monitoring for {timeout}s (sample is running)…")
    mon_start = time.monotonic()

    while (time.monotonic() - mon_start) < timeout:
        remaining = int(timeout - (time.monotonic() - mon_start))
        hud(f"Monitoring… {remaining}s remaining")

        # Periodic installer re-scan (catches delayed popups)
        try:
            windows = Desktop(backend="uia").windows()
            for win in windows:
                try:
                    title = (win.window_text() or "").strip().lower()
                except Exception:
                    continue
                if any(kw in title for kw in SETUP_TITLE_KEYWORDS):
                    log.info("Late popup detected: '%s' — re-running installer hunter", title)
                    hunt_and_click_installers(duration=10)
                    break
        except Exception:
            pass

        # Human-like mouse jiggle
        jx = cx + random.randint(-40, 40)
        jy = cy + random.randint(-30, 30)
        _safe_move(jx, jy, duration=0.6)
        time.sleep(poll_interval)

    # --- 10. Wrap up -------------------------------------------------------
    log.info("=" * 60)
    log.info("SENTINEL AGENT FINISHED — analysis window complete")
    log.info("=" * 60)
    hud("Analysis window complete. Shutting down agent.")
    time.sleep(2.0)

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
