"""
Sentinel Visual Agent — Sandbox Automation Payload
===================================================
Drops into a clean Windows 10 VM guest and visually executes a target
sample with a hacker-style HUD overlay, so users can watch the
automation happen live through the VMware window.

Architecture:
    Main thread  → Tkinter HUD (mainloop)
    Daemon thread → PyAutoGUI automation sequence, updates HUD via root.after()

Compile & deploy:
    pyinstaller --onefile --noconsole --name sentinel_agent sentinel_visual_agent.py
    Copy dist\\sentinel_agent.exe into the VM and run:
        sentinel_agent.exe C:\\Sandbox\\target.exe
"""

from __future__ import annotations

import threading
import time
import tkinter as tk
from pathlib import Path

import pyautogui

# ── PyAutoGUI config ─────────────────────────────────────────────────────────
pyautogui.FAILSAFE = False   # no fail-safe corner abort inside a VM
pyautogui.PAUSE = 0.25       # small implicit pause between calls

# ── Screen metrics ───────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = pyautogui.size()


# ═══════════════════════════════════════════════════════════════════════════════
#  HUD  (Tkinter — runs on the MAIN thread)
# ═══════════════════════════════════════════════════════════════════════════════

class AgentHUD:
    """Always-on-top, borderless, semi-transparent overlay with green-on-black
    cyber-security aesthetic.  Exposes a thread-safe ``set_status()`` that the
    background automation thread can call from any context."""

    WIDTH = 580
    HEIGHT = 44

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Sentinel Agent")
        self.root.overrideredirect(True)                     # borderless
        self.root.attributes("-topmost", True)               # always on top
        self.root.attributes("-alpha", 0.90)                 # semi-transparent
        self.root.configure(bg="#0a0a0a")

        # Center horizontally, pin near top
        x = (SCREEN_W - self.WIDTH) // 2
        y = 16
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

        self._label = tk.Label(
            self.root,
            text="\U0001f916 Sentinel Agent: Initializing\u2026",
            font=("Consolas", 12, "bold"),
            fg="#00ff41",          # terminal green
            bg="#0a0a0a",
            anchor="w",
            padx=14,
        )
        self._label.pack(fill="both", expand=True)

    # ── Thread-safe status update ────────────────────────────────────────────

    def set_status(self, text: str) -> None:
        """Can be called from ANY thread. Schedules the update on the Tk
        main-loop via ``root.after()`` so it is completely thread-safe."""
        self.root.after(0, self._apply, text)

    def _apply(self, text: str) -> None:
        self._label.config(text=f"\U0001f916 Sentinel Agent: {text}")

    # ── Shutdown ─────────────────────────────────────────────────────────────

    def shutdown(self) -> None:
        """Schedule a clean destroy from any thread."""
        self.root.after(0, self.root.destroy)

    def run(self) -> None:
        """Enter the Tk main-loop (blocks — call on the main thread)."""
        self.root.mainloop()


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTOMATION SEQUENCE  (runs on a daemon thread)
# ═══════════════════════════════════════════════════════════════════════════════

def _automation_sequence(hud: AgentHUD, target: str, monitor_seconds: int = 30) -> None:
    """Full visual interaction sequence executed in a background thread."""

    target_path = Path(target)
    target_name = target_path.name

    def status(msg: str) -> None:
        hud.set_status(msg)

    def step_pause(seconds: float = 1.0) -> None:
        time.sleep(seconds)

    try:
        # ── 0. Warm-up ──────────────────────────────────────────────────────
        status("Initiating sequence\u2026")
        step_pause(2.0)

        # ── 1. Verify target exists ─────────────────────────────────────────
        status(f"Locating payload: {target_name}")
        step_pause(1.5)

        if not target_path.exists():
            status(f"ERROR \u2014 payload not found: {target}")
            step_pause(5.0)
            hud.shutdown()
            return

        status("Payload confirmed on disk \u2714")
        step_pause(1.5)

        # ── 2. Launch via Win+R (Run dialog) ────────────────────────────────
        status("Opening Run dialog (Win+R)\u2026")
        step_pause(0.5)
        pyautogui.hotkey("win", "r")
        step_pause(1.5)

        status(f"Typing payload path\u2026")
        # typewrite only handles ASCII; use pyperclip fallback for Unicode paths
        try:
            pyautogui.typewrite(target, interval=0.04)
        except Exception:
            # Fallback: write via clipboard
            import subprocess
            subprocess.run(                                          # noqa: S603
                ["clip"],
                input=target.encode("utf-16le"),
                check=False,
            )
            pyautogui.hotkey("ctrl", "v")
        step_pause(0.8)

        status("Executing payload\u2026")
        pyautogui.press("enter")
        step_pause(3.0)

        # ── 3. Handle UAC / prompts ─────────────────────────────────────────
        status("Executing payload and handling prompts\u2026")
        step_pause(1.5)

        # UAC: arrow Left to "Yes" then Enter
        pyautogui.press("left")
        step_pause(0.4)
        pyautogui.press("enter")
        step_pause(1.5)

        # Backup: Alt+Y (direct UAC accept on many Win10 builds)
        pyautogui.hotkey("alt", "y")
        step_pause(1.0)

        # Extra Enter for any remaining dialog
        pyautogui.press("enter")
        step_pause(2.0)

        # ── 4. Click through installer/license prompts ──────────────────────
        status("Clicking through setup prompts\u2026")
        for cycle in range(3):
            pyautogui.press("enter")
            step_pause(1.0)
            pyautogui.press("tab")
            step_pause(0.4)
            pyautogui.press("enter")
            step_pause(1.5)
            status(f"Prompt cycle {cycle + 1}/3 accepted")
        step_pause(1.0)

        # ── 5. Human-like mouse exploration ─────────────────────────────────
        status("Performing dynamic behavior analysis\u2026")
        step_pause(1.0)

        cx, cy = SCREEN_W // 2, SCREEN_H // 2

        # Move to center like a human
        pyautogui.moveTo(cx, cy, duration=1.5, tween=pyautogui.easeInOutQuad)
        step_pause(1.0)

        # Explore the window
        waypoints = [
            (cx - 200, cy - 150, "Inspecting top-left region\u2026"),
            (cx + 200, cy - 100, "Inspecting top-right region\u2026"),
            (cx + 180, cy + 120, "Inspecting bottom-right region\u2026"),
            (cx - 160, cy + 140, "Inspecting bottom-left region\u2026"),
            (cx, cy, "Returning to center\u2026"),
        ]
        for wx, wy, msg in waypoints:
            status(msg)
            wx = max(0, min(wx, SCREEN_W - 1))
            wy = max(0, min(wy, SCREEN_H - 1))
            pyautogui.moveTo(wx, wy, duration=1.2, tween=pyautogui.easeInOutQuad)
            step_pause(0.8)

        # ── 6. Scroll like a human reading ──────────────────────────────────
        status("Scrolling through application content\u2026")
        for _ in range(5):
            pyautogui.scroll(-3)       # scroll down
            step_pause(0.4)

        step_pause(1.5)
        status("Reading content\u2026")

        for _ in range(5):
            pyautogui.scroll(-3)       # scroll down more
            step_pause(0.4)

        step_pause(2.0)

        for _ in range(8):
            pyautogui.scroll(3)        # scroll back up
            step_pause(0.35)

        step_pause(1.0)

        # ── 7. Idle monitoring with periodic mouse jiggle ───────────────────
        status(f"Monitoring runtime behavior ({monitor_seconds} s)\u2026")
        monitor_end = time.monotonic() + monitor_seconds
        while time.monotonic() < monitor_end:
            remaining = int(monitor_end - time.monotonic())
            status(f"Monitoring\u2026 {remaining}s remaining")
            jx = cx + (int(time.monotonic() * 7) % 50) - 25
            jy = cy + (int(time.monotonic() * 5) % 40) - 20
            jx = max(0, min(jx, SCREEN_W - 1))
            jy = max(0, min(jy, SCREEN_H - 1))
            pyautogui.moveTo(jx, jy, duration=0.6, tween=pyautogui.easeInOutQuad)
            step_pause(5.0)

        # ── 8. Done ─────────────────────────────────────────────────────────
        status("Analysis complete. Terminating Agent.")
        step_pause(3.0)

    except Exception as exc:
        try:
            status(f"Agent error: {exc}")
        except Exception:
            pass
        step_pause(3.0)

    finally:
        hud.shutdown()


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_args() -> tuple[str, int]:
    """Parse CLI arguments: sentinel_agent.exe <target> [--timeout N]."""
    import argparse

    parser = argparse.ArgumentParser(description="Sentinel Visual Agent")
    parser.add_argument("target", nargs="?", default=r"C:\Sandbox\target.exe",
                        help="Path to the sample to detonate")
    parser.add_argument("--timeout", type=int, default=30,
                        help="Monitoring window in seconds (default: 30)")
    args = parser.parse_args()
    return args.target, args.timeout


def main() -> None:
    target, monitor_seconds = _parse_args()

    hud = AgentHUD()

    worker = threading.Thread(
        target=_automation_sequence,
        args=(hud, target, monitor_seconds),
        daemon=True,
    )
    worker.start()

    # Tk mainloop blocks on the main thread — required by Tkinter
    hud.run()


if __name__ == "__main__":
    main()
