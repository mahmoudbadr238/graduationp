"""HUD Overlay — Tkinter status display decoupled from agent logic.

Provides a thread-safe message queue interface.  The HUD runs on a
daemon thread so it never blocks the agent's main loop.
"""

from __future__ import annotations

import logging
import queue
import threading

import pyautogui

log = logging.getLogger("sentinel_agent")

SCREEN_W, SCREEN_H = pyautogui.size()
HUD_WIDTH = 520
HUD_HEIGHT = 38
HUD_X = (SCREEN_W - HUD_WIDTH) // 2
HUD_Y = 18


_hud_queue: queue.Queue[str | None] = queue.Queue()
_hud_started = False


def start_hud() -> None:
    """Launch the HUD on a daemon thread.  Safe to call multiple times."""
    global _hud_started
    if _hud_started:
        return
    _hud_started = True
    t = threading.Thread(target=_run_hud, daemon=True)
    t.start()
    # Give Tk a moment to initialise
    import time
    time.sleep(0.6)


def stop_hud() -> None:
    """Request HUD shutdown."""
    _hud_queue.put(None)


def hud(text: str) -> None:
    """Push a status message to the overlay and log it."""
    _hud_queue.put(f"Sentinel Agent: {text}")
    log.info("[HUD] %s", text)


def _run_hud() -> None:
    """Tkinter main loop on a daemon thread."""
    import tkinter as tk

    root = tk.Tk()
    root.title("Sentinel Agent")
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.88)
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
                if msg is None:
                    root.destroy()
                    return
                label.config(text=msg)
        except queue.Empty:
            pass
        root.after(80, _poll)

    root.after(80, _poll)
    root.mainloop()
