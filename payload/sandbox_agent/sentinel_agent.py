"""
Sentinel Autonomous UI Agent — Groq-Powered Sandbox Payload
============================================================
Runs INSIDE the sandbox VM. Uses an Observation-Action Loop (ReAct)
to autonomously interact with whatever malware puts on screen.

Architecture:
  1. OBSERVE  → pywinauto dumps the active window's title + button text
  2. THINK    → Groq LLM decides what to click (JSON response)
  3. ACT      → pywinauto/pyautogui executes the click
  4. LOOP     → repeat every 3-5 seconds until timeout

Anti-evasion capabilities retained from the original agent:
  - Realistic mouse movement with easeInOutQuad curves
  - Desktop honeypot files (passwords.txt opened in Notepad)
  - Browser history generation (Edge → Wikipedia)
  - Start menu & right-click interactions

Compiled to sentinel_agent.exe via PyInstaller and deployed by VMwareRunner.

Usage:
    agent.exe <target_file>                    # e.g. agent.exe C:\\Sandbox\\rufus.exe
    agent.exe <target_file> --timeout 90       # custom interaction timeout
    agent.exe <target_file> --no-hud           # disable overlay (headless)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import random
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging setup — file + console
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
# PyAutoGUI + pywinauto setup
# ---------------------------------------------------------------------------
import pyautogui
from pywinauto import Desktop

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.3

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCREEN_W, SCREEN_H = pyautogui.size()
HUD_WIDTH, HUD_HEIGHT = 520, 38
HUD_X = (SCREEN_W - HUD_WIDTH) // 2
HUD_Y = 18
MOVE_DURATION = 1.4
EASING = pyautogui.easeInOutQuad

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("AI_MODEL_AGENT", "llama-3.1-8b-instant")

SYSTEM_PROMPT = (
    "You are an autonomous agent inside a malware sandbox. "
    "Your goal is to act like a gullible human and install whatever is on "
    "the screen to force the malware to execute and unpack itself fully. "
    "You will receive the current UI state as JSON with the active window "
    "title and a list of visible button/checkbox texts.\n\n"
    "Rules:\n"
    "- If you see an installer, setup wizard, license agreement, or any "
    "dialog: click the button that progresses the installation "
    '(e.g. "Next", "I Agree", "Accept", "Install", "Yes", "OK", "Run", '
    '"Finish", "Continue", "Close", "Allow").\n'
    "- If you see a checkbox like 'I accept the terms', click it FIRST, "
    "then on the next cycle click 'Next' or 'Install'.\n"
    "- If there are no actionable buttons or the window is just a desktop "
    'with no dialogs, reply with the wait action.\n'
    "- If you see a security warning or SmartScreen, click the button that "
    'allows execution (e.g. "Run anyway", "More info", "Yes").\n\n'
    "Reply ONLY with a single JSON object. No explanation, no markdown.\n"
    "Allowed formats:\n"
    '  {"action": "click", "target": "<exact_button_text>"}\n'
    '  {"action": "check", "target": "<exact_checkbox_text>"}\n'
    '  {"action": "type", "target": "<text_to_type>"}\n'
    '  {"action": "key", "target": "<key_combo>"} '
    '(e.g. "enter", "alt+y", "tab")\n'
    '  {"action": "wait"}\n'
)

# Window titles belonging to OS chrome — skip observation
IGNORED_TITLES = frozenset({
    "taskbar", "start", "program manager",
    "windows input experience", "text input application",
    "sentinel agent",
})

# ---------------------------------------------------------------------------
# HUD (Tkinter overlay on daemon thread)
# ---------------------------------------------------------------------------
_hud_queue: queue.Queue[str | None] = queue.Queue()


def _run_hud() -> None:
    """Tkinter main-loop on a daemon thread."""
    import tkinter as tk

    root = tk.Tk()
    root.title("Sentinel Agent")
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.88)
    root.configure(bg="#1a1a2e")
    root.geometry(f"{HUD_WIDTH}x{HUD_HEIGHT}+{HUD_X}+{HUD_Y}")

    label = tk.Label(
        root, text="Sentinel Agent: Initializing…",
        font=("Consolas", 11, "bold"), fg="#00d2ff", bg="#1a1a2e",
        anchor="w", padx=12,
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


def hud(text: str) -> None:
    """Push a status message to the overlay HUD and logger."""
    _hud_queue.put(f"Sentinel Agent: {text}")
    log.info("[HUD] %s", text)


# ---------------------------------------------------------------------------
# Mouse / keyboard helpers
# ---------------------------------------------------------------------------


def _safe_move(x: int, y: int, duration: float = MOVE_DURATION) -> None:
    """Move mouse with human-like easing; clamp to screen bounds."""
    x = max(0, min(x, SCREEN_W - 1))
    y = max(0, min(y, SCREEN_H - 1))
    log.debug("Mouse → (%d, %d) over %.2fs", x, y, duration)
    pyautogui.moveTo(x, y, duration=duration, tween=EASING)


def _human_scroll(clicks: int, pause: float = 0.35) -> None:
    direction = 1 if clicks > 0 else -1
    for _ in range(abs(clicks)):
        pyautogui.scroll(direction * 3)
        time.sleep(pause)


def _dismiss_uac() -> None:
    """Attempt to dismiss UAC prompts via keyboard."""
    log.info("UAC dismissal attempt")
    hud("Handling UAC / elevation prompt…")
    time.sleep(1.5)
    pyautogui.hotkey("alt", "y")
    time.sleep(1.0)
    pyautogui.press("enter")
    time.sleep(0.5)


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: OBSERVATION — dump active window UI state via pywinauto UIA
# ═══════════════════════════════════════════════════════════════════════════


def observe_ui_state() -> list[dict]:
    """Return a list of window state dicts for all visible non-OS windows.

    Each dict: {"window": "<title>", "buttons": [...], "checkboxes": [...],
                "text_fields": <count>, "active": <bool>}
    """
    observations = []
    try:
        windows = Desktop(backend="uia").windows()
    except Exception as exc:
        log.warning("Desktop enumeration failed: %s", exc)
        return observations

    for win in windows:
        try:
            title = (win.window_text() or "").strip()
        except Exception:
            continue

        if not title or title.lower() in IGNORED_TITLES:
            continue

        state: dict = {
            "window": title[:120],
            "buttons": [],
            "checkboxes": [],
            "text_fields": 0,
            "active": False,
        }

        try:
            state["active"] = win.is_active()
        except Exception:
            pass

        # Enumerate clickable controls
        try:
            for ctrl in win.descendants(control_type="Button"):
                try:
                    txt = (ctrl.window_text() or "").strip()
                    if txt and len(txt) < 80:
                        state["buttons"].append(txt)
                except Exception:
                    continue
        except Exception:
            pass

        try:
            for ctrl in win.descendants(control_type="CheckBox"):
                try:
                    txt = (ctrl.window_text() or "").strip()
                    if txt and len(txt) < 120:
                        state["checkboxes"].append(txt)
                except Exception:
                    continue
        except Exception:
            pass

        try:
            edits = win.descendants(control_type="Edit")
            state["text_fields"] = len(edits)
        except Exception:
            pass

        observations.append(state)

    # Sort: active window first, then windows with more buttons
    observations.sort(
        key=lambda s: (not s.get("active"), -len(s.get("buttons", []))),
    )

    log.info("Observed %d windows: %s",
             len(observations),
             [o["window"][:40] for o in observations])
    return observations


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: BRAIN — send UI state to Groq, get action decision
# ═══════════════════════════════════════════════════════════════════════════

def _extract_json(text: str) -> dict | None:
    """Extract a JSON object from LLM response text, handling markdown fences."""
    text = text.strip()
    # Strip ```json ... ``` fences
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    # If text starts with {, try parsing directly
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    # Last resort: find first { ... } block
    m = re.search(r"\{[^{}]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def ask_groq(observations: list[dict], api_key: str) -> dict:
    """Send UI observations to Groq and return the parsed action dict.

    Returns: {"action": "click"|"check"|"type"|"key"|"wait", "target": "..."}
    Falls back to {"action": "wait"} on any failure.
    """
    fallback = {"action": "wait"}

    if not api_key:
        log.warning("No GROQ_API_KEY — falling back to wait")
        return fallback

    # Build the user message with compact JSON
    user_msg = json.dumps(observations, ensure_ascii=False)
    if len(user_msg) > 3000:
        # Truncate to keep prompt small for fast inference
        user_msg = user_msg[:3000] + "...]"

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.1,
        "max_tokens": 120,
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        GROQ_API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        content = data["choices"][0]["message"]["content"]
        log.info("Groq raw response: %s", content[:200])

        result = _extract_json(content)
        if result and "action" in result:
            return result

        log.warning("Groq response not parseable as action JSON: %s", content[:200])
        return fallback

    except urllib.error.HTTPError as exc:
        log.warning("Groq HTTP %d: %s", exc.code, exc.reason)
        return fallback
    except Exception as exc:
        log.warning("Groq request failed: %s", exc)
        return fallback


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3: ACTION — execute Groq's decision via pywinauto / pyautogui
# ═══════════════════════════════════════════════════════════════════════════


def execute_action(action: dict) -> bool:
    """Execute the action dict from Groq. Returns True if something was done."""
    act = action.get("action", "wait").lower()
    target = action.get("target", "").strip()

    if act == "wait":
        log.info("Action: wait (no interaction needed)")
        return False

    if act == "key":
        log.info("Action: key press '%s'", target)
        hud(f"⌨ Pressing: {target}")
        try:
            keys = [k.strip() for k in target.split("+")]
            if len(keys) == 1:
                pyautogui.press(keys[0])
            else:
                pyautogui.hotkey(*keys)
            return True
        except Exception as exc:
            log.warning("Key press failed: %s", exc)
            return False

    if act == "type":
        log.info("Action: type text '%s'", target[:60])
        hud(f"⌨ Typing: {target[:30]}…")
        try:
            pyautogui.typewrite(target, interval=random.uniform(0.04, 0.10))
            return True
        except Exception as exc:
            log.warning("Type failed: %s", exc)
            return False

    if act in ("click", "check"):
        log.info("Action: %s target '%s'", act, target)
        hud(f"🖱 {act.title()}: {target[:40]}")
        return _click_target(target, is_checkbox=(act == "check"))

    log.warning("Unknown action type: '%s'", act)
    return False


def _click_target(target_text: str, *, is_checkbox: bool = False) -> bool:
    """Locate and click a control matching target_text using pywinauto.

    Searches all visible windows. Falls back to pyautogui coordinate click.
    """
    target_lower = target_text.lower().strip()

    try:
        windows = Desktop(backend="uia").windows()
    except Exception as exc:
        log.warning("Desktop enum failed during click: %s", exc)
        return False

    for win in windows:
        try:
            title = (win.window_text() or "").strip()
        except Exception:
            continue
        if not title or title.lower() in IGNORED_TITLES:
            continue

        # Determine which control types to search
        control_types = ["CheckBox"] if is_checkbox else ["Button", "CheckBox"]

        for ctype in control_types:
            try:
                controls = win.descendants(control_type=ctype)
            except Exception:
                continue

            for ctrl in controls:
                try:
                    ctrl_text = (ctrl.window_text() or "").strip()
                except Exception:
                    continue

                if ctrl_text.lower().strip() == target_lower:
                    return _do_click(ctrl, ctrl_text, title)

        # Fuzzy match: target is a substring of control text or vice versa
        try:
            all_controls = (
                win.descendants(control_type="Button")
                + win.descendants(control_type="CheckBox")
            )
        except Exception:
            continue

        for ctrl in all_controls:
            try:
                ctrl_text = (ctrl.window_text() or "").strip()
            except Exception:
                continue
            ctrl_lower = ctrl_text.lower().strip()
            if target_lower in ctrl_lower or ctrl_lower in target_lower:
                log.info("Fuzzy match: '%s' ≈ '%s'", target_text, ctrl_text)
                return _do_click(ctrl, ctrl_text, title)

    log.warning("Target '%s' not found in any window", target_text)
    return False


def _do_click(ctrl, ctrl_text: str, win_title: str) -> bool:
    """Click a pywinauto control using invoke(), then click_input() fallback."""
    log.info("  CLICKING: '%s' in '%s'", ctrl_text, win_title[:40])

    # Try UIA Invoke first (most reliable for buttons)
    try:
        ctrl.invoke()
        log.info("  → invoke() succeeded")
        time.sleep(0.8)
        return True
    except Exception as exc:
        log.debug("  → invoke() failed: %s", exc)

    # Fallback: click_input() (moves mouse to control center)
    try:
        ctrl.click_input()
        log.info("  → click_input() succeeded")
        time.sleep(0.8)
        return True
    except Exception as exc:
        log.debug("  → click_input() failed: %s", exc)

    # Last resort: get coordinates and use pyautogui
    try:
        rect = ctrl.rectangle()
        cx = (rect.left + rect.right) // 2
        cy = (rect.top + rect.bottom) // 2
        _safe_move(cx, cy, duration=0.4)
        time.sleep(0.1)
        pyautogui.click(cx, cy)
        log.info("  → pyautogui click at (%d, %d) succeeded", cx, cy)
        time.sleep(0.8)
        return True
    except Exception as exc:
        log.warning("  → All click methods failed for '%s': %s", ctrl_text, exc)
        return False


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4: EXECUTION LOOP — Observe → Think → Act → Repeat
# ═══════════════════════════════════════════════════════════════════════════


def react_loop(api_key: str, duration: int = 120) -> None:
    """Main ReAct loop: observe UI, ask Groq, execute action, repeat."""
    log.info("=== ReAct Loop START (duration=%ds, model=%s) ===", duration, GROQ_MODEL)
    hud(f"ReAct loop active — {GROQ_MODEL}")

    cx, cy = SCREEN_W // 2, SCREEN_H // 2
    start = time.monotonic()
    cycle = 0
    consecutive_waits = 0

    while (time.monotonic() - start) < duration:
        cycle += 1
        remaining = int(duration - (time.monotonic() - start))
        hud(f"Cycle {cycle} — {remaining}s left")
        log.info("─── Cycle %d (remaining: %ds) ───", cycle, remaining)

        # ── OBSERVE ──
        observations = observe_ui_state()

        if not observations:
            log.info("No observable windows — waiting")
            consecutive_waits += 1
        else:
            # ── THINK ──
            action = ask_groq(observations, api_key)
            log.info("Groq decision: %s", json.dumps(action))

            # ── ACT ──
            try:
                did_something = execute_action(action)
                if did_something:
                    consecutive_waits = 0
                else:
                    consecutive_waits += 1
            except Exception as exc:
                log.error("Action execution crashed: %s", exc, exc_info=True)
                consecutive_waits += 1

        # Human-like mouse jiggle between cycles
        jx = cx + random.randint(-60, 60)
        jy = cy + random.randint(-40, 40)
        _safe_move(jx, jy, duration=random.uniform(0.3, 0.7))

        # Dynamic interval: shorter when interacting, longer when idle
        if consecutive_waits > 5:
            interval = random.uniform(4.0, 6.0)
        else:
            interval = random.uniform(2.5, 4.0)
        time.sleep(interval)

    log.info("=== ReAct Loop END (%d cycles) ===", cycle)


# ---------------------------------------------------------------------------
# Anti-evasion: Human simulation, honeypots, browser history
# ---------------------------------------------------------------------------


def simulate_human_activity() -> None:
    """Realistic human presence: mouse sweeps, start menu, right-click."""
    log.info("=== Human Activity Simulation START ===")
    hud("Simulating human presence…")

    for i in range(random.randint(5, 8)):
        _safe_move(
            random.randint(80, SCREEN_W - 80),
            random.randint(80, SCREEN_H - 80),
            duration=random.uniform(0.5, 1.5),
        )
        time.sleep(random.uniform(0.3, 1.0))

    # Start menu search
    pyautogui.press("win")
    time.sleep(random.uniform(1.5, 2.5))
    search = random.choice(["notepad", "calc", "paint", "settings"])
    pyautogui.typewrite(search, interval=random.uniform(0.08, 0.15))
    time.sleep(random.uniform(1.0, 2.0))
    pyautogui.press("escape")
    time.sleep(0.5)

    # Right-click desktop
    pyautogui.hotkey("win", "d")
    time.sleep(1.0)
    pyautogui.rightClick(
        random.randint(SCREEN_W // 3, 2 * SCREEN_W // 3),
        random.randint(SCREEN_H // 3, 2 * SCREEN_H // 3),
    )
    time.sleep(random.uniform(1.0, 1.8))
    pyautogui.press("escape")
    time.sleep(random.uniform(1.0, 3.0))
    log.info("=== Human Activity Simulation END ===")


def create_honeypot_files() -> None:
    """Seed desktop with decoy files and open passwords.txt in Notepad."""
    log.info("=== Honeypot Setup START ===")
    hud("Seeding desktop with honeypot files…")
    desktop = os.path.join(
        os.environ.get("USERPROFILE", r"C:\Users\user"), "Desktop",
    )
    os.makedirs(desktop, exist_ok=True)

    decoys = {
        "Passwords_2026.txt": (
            "=== Personal Password Vault ===\n"
            "Gmail: kR#92xLp!q7\nVPN Corp: Z!tm4Qr@8801\n"
            "Banking: j3Fk$9sPvW\nUpdated: 2026-03-01\n"
        ),
        "Q3_Financial_Report.docx": (
            "Quarterly Financial Summary - CONFIDENTIAL\n"
            "Revenue: $4,812,300   Expenses: $3,207,500\n"
        ),
        "VPN_Config.ini": (
            "[vpn]\nserver = vpn-corp.internal.local\nport = 1194\n"
        ),
        "crypto_wallet_seed.txt": (
            "BIP39 Recovery Seed (DO NOT SHARE)\n"
            "abandon ability able about above absent absorb abstract\n"
        ),
    }

    for filename, content in decoys.items():
        filepath = os.path.join(desktop, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as fh:
                fh.write(content)
        except OSError as exc:
            log.warning("Failed to create decoy %s: %s", filename, exc)

    # Open passwords.txt in Notepad + type extra credentials
    passwords_path = os.path.join(desktop, "Passwords_2026.txt")
    hud("Opening password file in Notepad…")
    try:
        subprocess.Popen(["notepad.exe", passwords_path])  # noqa: S603
        time.sleep(3.0)
        for line in ["", "# Added just now:", "AWS: admin / Tr0ub4dor&3",
                      "SSH: r00t_P@ss!2026"]:
            pyautogui.hotkey("ctrl", "End")
            pyautogui.press("enter")
            pyautogui.typewrite(line, interval=random.uniform(0.04, 0.10))
            time.sleep(random.uniform(0.3, 0.8))
        pyautogui.hotkey("ctrl", "s")
        time.sleep(0.5)
    except Exception as exc:
        log.warning("Notepad honeypot failed: %s", exc)

    log.info("=== Honeypot Setup END ===")


def generate_browser_history() -> None:
    """Open Edge to Wikipedia, scroll around, then close."""
    log.info("=== Browser History Generation START ===")
    hud("Generating browser traffic…")
    try:
        subprocess.Popen(  # noqa: S606
            "start microsoft-edge:https://en.wikipedia.org/wiki/Special:Random",
            shell=True,  # noqa: S602 — intentional sandbox automation
        )
        time.sleep(5.0)
        for _ in range(random.randint(3, 6)):
            pyautogui.scroll(-random.randint(2, 5))
            time.sleep(random.uniform(0.6, 1.4))
        time.sleep(1.0)
        pyautogui.hotkey("alt", "F4")
        time.sleep(1.5)
    except Exception as exc:
        log.warning("Browser history generation failed: %s", exc)
    log.info("=== Browser History Generation END ===")


# ---------------------------------------------------------------------------
# Main agent orchestrator
# ---------------------------------------------------------------------------


def run_agent(target: Path, *, timeout: int = 120, enable_hud: bool = True) -> None:
    """Execute the full autonomous agent sequence."""
    # Load API key from environment
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        log.warning("GROQ_API_KEY not set — agent will use rule-based fallback")

    # Start HUD
    if enable_hud:
        hud_thread = threading.Thread(target=_run_hud, daemon=True)
        hud_thread.start()
        time.sleep(0.6)

    log.info("=" * 60)
    log.info("SENTINEL AUTONOMOUS AGENT STARTED")
    log.info("Target: %s", target)
    log.info("Timeout: %ds | Model: %s", timeout, GROQ_MODEL)
    log.info("Screen: %dx%d | API key: %s",
             SCREEN_W, SCREEN_H, "present" if api_key else "MISSING")
    log.info("=" * 60)

    hud("Initializing…")
    time.sleep(1.0)

    target_dir = str(target.parent)
    filename = target.name

    # --- Verify target exists ---
    if not target.exists():
        log.error("TARGET NOT FOUND: %s", target)
        hud(f"ERROR — target not found: {target}")
        time.sleep(3)
        return
    log.info("Target confirmed: %s (%.1f KB)", target, target.stat().st_size / 1024)

    # --- Anti-evasion: seed human environment ---
    create_honeypot_files()
    generate_browser_history()
    simulate_human_activity()

    # --- Archive extraction ---
    target = _maybe_extract_archive(target)
    target_dir = str(target.parent)
    filename = target.name

    # --- Open Explorer at target folder ---
    log.info("Opening Explorer at: %s", target_dir)
    hud(f"Opening folder: {target_dir}")
    try:
        os.startfile(target_dir)  # noqa: S606
    except Exception as exc:
        log.error("Explorer launch failed: %s", exc)
    time.sleep(2.5)

    # --- Detonate payload ---
    log.info("DETONATING PAYLOAD: %s", target)
    hud(f"Executing payload: {filename}")
    try:
        os.startfile(str(target))  # noqa: S606
    except AttributeError:
        subprocess.Popen([str(target)], shell=True)  # noqa: S603
    time.sleep(4.0)

    # --- Dismiss UAC ---
    _dismiss_uac()

    # --- Autonomous ReAct Loop (the Groq-powered brain) ---
    react_loop(api_key, duration=timeout)

    # --- Wrap up ---
    log.info("=" * 60)
    log.info("SENTINEL AGENT FINISHED — analysis window complete")
    log.info("=" * 60)
    hud("Analysis complete. Shutting down.")
    time.sleep(2.0)
    _hud_queue.put(None)
    time.sleep(0.5)


def _maybe_extract_archive(target: Path) -> Path:
    """If target is an archive, extract via 7-Zip and return the payload path."""
    ARCHIVE_EXTS = {".zip", ".rar", ".7z"}
    HIGH_RISK_EXTS = {".exe", ".bat", ".cmd", ".vbs", ".ps1", ".js", ".scr"}
    SEVEN_ZIP = r"C:\Program Files\7-Zip\7z.exe"
    EXTRACT_DIR = Path(r"C:\Sandbox\extracted")

    if target.suffix.lower() not in ARCHIVE_EXTS:
        return target

    log.info("Archive detected: %s", target.suffix)
    if not os.path.exists(SEVEN_ZIP):
        log.error("7z.exe missing — cannot extract")
        hud("ERROR: 7z.exe missing!")
        return target

    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    hud("Extracting archive…")
    cmd = [SEVEN_ZIP, "x", str(target), f"-o{EXTRACT_DIR}", "-y", "-pinfected"]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        log.warning("7-Zip extraction timed out")
    time.sleep(2.0)

    if not EXTRACT_DIR.exists():
        return target

    # Hunt for high-risk payload
    for dirpath, _, files in os.walk(str(EXTRACT_DIR)):
        for fname in files:
            if Path(fname).suffix.lower() in HIGH_RISK_EXTS:
                payload = Path(dirpath) / fname
                log.info("Payload found: %s", payload)
                hud(f"Payload: {payload.name}")
                return payload

    # Fallback to first file
    for dirpath, _, files in os.walk(str(EXTRACT_DIR)):
        if files:
            return Path(dirpath) / files[0]

    return target


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sentinel Autonomous Agent — Groq-powered sandbox payload",
    )
    parser.add_argument(
        "target", type=Path,
        help="Path to sample file (e.g. C:\\Sandbox\\malware.exe)",
    )
    parser.add_argument(
        "--timeout", type=int, default=120,
        help="Seconds to keep sample alive and monitored (default: 120)",
    )
    parser.add_argument(
        "--no-hud", action="store_true",
        help="Disable floating status overlay",
    )
    args = parser.parse_args()

    if not args.target.exists():
        print(f"[!] Target not found: {args.target}", file=sys.stderr)
        sys.exit(1)

    run_agent(args.target, timeout=args.timeout, enable_hud=not args.no_hud)


if __name__ == "__main__":
    main()
