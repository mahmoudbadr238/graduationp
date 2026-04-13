"""Anti-Evasion Human Simulation — honeypots, browser history, mouse presence.

These functions create a realistic human environment inside the sandbox VM
to defeat malware that checks for signs of automated analysis.

Extracted from *agent_payload.py* and *sentinel_agent.py*.
"""

from __future__ import annotations

import logging
import os
import random
import subprocess
import time

import pyautogui

log = logging.getLogger("sentinel_agent")

SCREEN_W, SCREEN_H = pyautogui.size()
EASING = pyautogui.easeInOutQuad


def _safe_move(x: int, y: int, duration: float = 1.4) -> None:
    """Move mouse with human-like easing; clamp to screen bounds."""
    x = max(0, min(x, SCREEN_W - 1))
    y = max(0, min(y, SCREEN_H - 1))
    pyautogui.moveTo(x, y, duration=duration, tween=EASING)


# ---------------------------------------------------------------------------
# 1. Human presence simulation
# ---------------------------------------------------------------------------

def simulate_human_activity() -> None:
    """Realistic human presence: mouse sweeps, start menu, right-click."""
    log.info("=== Human Activity Simulation START ===")

    # Natural mouse sweeps
    for _ in range(random.randint(5, 8)):
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


# ---------------------------------------------------------------------------
# 2. Honeypot files
# ---------------------------------------------------------------------------

def create_honeypot_files() -> None:
    """Seed desktop with decoy files and open passwords.txt in Notepad."""
    log.info("=== Honeypot Setup START ===")
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


# ---------------------------------------------------------------------------
# 3. Browser history generation
# ---------------------------------------------------------------------------

def generate_browser_history() -> None:
    """Open Edge to Wikipedia, scroll around, then close."""
    log.info("=== Browser History Generation START ===")
    try:
        subprocess.Popen(  # noqa: S606
            "start microsoft-edge:https://en.wikipedia.org/wiki/Special:Random",
            shell=True,  # noqa: S602
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
# 4. Archive extraction
# ---------------------------------------------------------------------------

def maybe_extract_archive(target: "Path") -> "Path":  # noqa: F821
    """If target is an archive, extract via 7-Zip and return the payload path."""
    from pathlib import Path as _Path

    ARCHIVE_EXTS = {".zip", ".rar", ".7z"}
    HIGH_RISK_EXTS = {".exe", ".bat", ".cmd", ".vbs", ".ps1", ".js", ".scr"}
    SEVEN_ZIP = r"C:\Program Files\7-Zip\7z.exe"
    EXTRACT_DIR = _Path(r"C:\Sandbox\extracted")

    if target.suffix.lower() not in ARCHIVE_EXTS:
        return target

    log.info("Archive detected: %s", target.suffix)
    if not os.path.exists(SEVEN_ZIP):
        log.error("7z.exe missing — cannot extract")
        return target

    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [SEVEN_ZIP, "x", str(target), f"-o{EXTRACT_DIR}", "-y", "-pinfected"]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)  # noqa: S603
    except subprocess.TimeoutExpired:
        log.warning("7-Zip extraction timed out")
    time.sleep(2.0)

    if not EXTRACT_DIR.exists():
        return target

    # Hunt for high-risk payload
    for dirpath, _, files in os.walk(str(EXTRACT_DIR)):
        for fname in files:
            if _Path(fname).suffix.lower() in HIGH_RISK_EXTS:
                payload = _Path(dirpath) / fname
                log.info("Payload found: %s", payload)
                return payload

    # Fallback to first file
    for dirpath, _, files in os.walk(str(EXTRACT_DIR)):
        if files:
            return _Path(dirpath) / files[0]

    return target
