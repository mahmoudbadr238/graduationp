"""Action Executor — carries out exactly one action with human-like timing.

Supports click, check, type, key, and wait.  Uses pywinauto's invoke()
first, falling back to click_input() then raw pyautogui coordinates.
Mouse movement uses easeInOutQuad curves for realism.
"""

from __future__ import annotations

import logging
import random
import time

import pyautogui

from .models import ActionDecision, ActionType, MatchResult

log = logging.getLogger("sentinel_agent")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCREEN_W, SCREEN_H = pyautogui.size()
EASING = pyautogui.easeInOutQuad

# Human-like timing ranges (seconds)
PRE_ACTION_PAUSE = (0.3, 0.8)   # thinking pause before acting
POST_ACTION_PAUSE = (0.6, 1.2)  # dwell after action
MOVE_DURATION = (0.3, 0.7)      # mouse travel time


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def execute(decision: ActionDecision, match: MatchResult | None = None) -> bool:
    """Execute a single action.  Returns True if the action was performed.

    Parameters
    ----------
    decision : ActionDecision
        What to do and why.
    match : MatchResult | None
        Resolved control from the resolver (needed for click/check).
    """
    act = decision.action

    # Thinking pause — intentional, not random
    pause = random.uniform(*PRE_ACTION_PAUSE)
    time.sleep(pause)

    if act == ActionType.WAIT:
        log.info("Action: wait — %s", decision.reason)
        return False

    if act == ActionType.KEY:
        return _do_key(decision.target)

    if act == ActionType.TYPE:
        return _do_type(decision.target)

    if act in (ActionType.CLICK, ActionType.CHECK):
        if match is None:
            log.warning("No resolved control for %s '%s'", act.value, decision.target)
            return False
        return _do_click(match)

    log.warning("Unknown action type: %s", act.value)
    return False


# ---------------------------------------------------------------------------
# Key press
# ---------------------------------------------------------------------------

def _do_key(target: str) -> bool:
    """Press a key or key combination."""
    log.info("Key press: '%s'", target)
    try:
        keys = [k.strip() for k in target.split("+")]
        if len(keys) == 1:
            pyautogui.press(keys[0])
        else:
            pyautogui.hotkey(*keys)
        time.sleep(random.uniform(*POST_ACTION_PAUSE))
        return True
    except Exception as exc:
        log.warning("Key press failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Type text
# ---------------------------------------------------------------------------

def _do_type(target: str) -> bool:
    """Type text with natural keystroke intervals."""
    log.info("Type: '%s'", target[:60])
    try:
        pyautogui.typewrite(target, interval=random.uniform(0.04, 0.10))
        time.sleep(random.uniform(*POST_ACTION_PAUSE))
        return True
    except Exception as exc:
        log.warning("Type failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Click / check
# ---------------------------------------------------------------------------

def _do_click(match: MatchResult) -> bool:
    """Click a resolved control using the best available method.

    Strategy:
    1. UIA invoke() — most reliable for buttons
    2. click_input() — moves mouse to control center
    3. pyautogui fallback — direct coordinate click
    """
    ctrl = match.control
    label = match.control_text
    win = match.window_title

    log.info("Clicking '%s' in '%s' (score=%.2f)", label, win[:40], match.score)

    # 1. UIA invoke
    try:
        ctrl.invoke()
        log.info("  → invoke() OK")
        time.sleep(random.uniform(*POST_ACTION_PAUSE))
        return True
    except Exception as exc:
        log.debug("  → invoke() failed: %s", exc)

    # 2. click_input (pywinauto moves mouse naturally)
    try:
        ctrl.click_input()
        log.info("  → click_input() OK")
        time.sleep(random.uniform(*POST_ACTION_PAUSE))
        return True
    except Exception as exc:
        log.debug("  → click_input() failed: %s", exc)

    # 3. Coordinate fallback
    try:
        rect = ctrl.rectangle()
        cx = (rect.left + rect.right) // 2
        cy = (rect.top + rect.bottom) // 2
        cx = max(0, min(cx, SCREEN_W - 1))
        cy = max(0, min(cy, SCREEN_H - 1))

        # Smooth mouse movement to target
        duration = random.uniform(*MOVE_DURATION)
        pyautogui.moveTo(cx, cy, duration=duration, tween=EASING)
        time.sleep(0.1)
        pyautogui.click(cx, cy)
        log.info("  → pyautogui click at (%d, %d) OK", cx, cy)
        time.sleep(random.uniform(*POST_ACTION_PAUSE))
        return True
    except Exception as exc:
        log.warning("  → All click methods failed for '%s': %s", label, exc)
        return False
