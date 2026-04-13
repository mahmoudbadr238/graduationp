"""Action Resolver — maps a target string to a real pywinauto control.

Uses strict scored matching: exact > contains > fuzzy.  Enforces a
minimum match threshold and prioritizes the active window.
"""

from __future__ import annotations

import logging
from difflib import SequenceMatcher
from typing import Any

from pywinauto import Desktop

from .models import ActionDecision, ActionType, MatchResult
from .observer import IGNORED_TITLES

log = logging.getLogger("sentinel_agent")

# Minimum match score to accept a control as a valid target
MATCH_THRESHOLD = 0.68


def resolve(decision: ActionDecision) -> MatchResult | None:
    """Resolve an ActionDecision's target to a pywinauto control.

    Returns None if no control meets the match threshold, or if the
    action type does not require a control (key, type, wait).
    """
    if decision.action in (ActionType.WAIT, ActionType.KEY, ActionType.TYPE):
        return None  # these don't need a resolved control

    target = decision.target.strip()
    if not target:
        log.warning("Resolve called with empty target")
        return None

    target_lower = target.lower()
    is_checkbox = decision.action == ActionType.CHECK

    try:
        windows = Desktop(backend="uia").windows()
    except Exception as exc:
        log.warning("Desktop enumeration failed during resolve: %s", exc)
        return None

    # Collect all candidates with scores
    candidates: list[MatchResult] = []

    # Sort: active windows first
    sorted_windows = sorted(windows, key=lambda w: not _is_active(w))

    for win in sorted_windows:
        try:
            title = (win.window_text() or "").strip()
        except Exception:
            continue
        if not title or title.lower() in IGNORED_TITLES:
            continue

        is_active_win = _is_active(win)

        # Determine control types to search
        if is_checkbox:
            control_types = ["CheckBox"]
        else:
            control_types = ["Button", "CheckBox"]

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

                if not ctrl_text:
                    continue

                score, method = _score_match(target_lower, ctrl_text.lower())

                # Boost score for active window controls
                if is_active_win:
                    score = min(1.0, score + 0.10)

                if score >= MATCH_THRESHOLD:
                    candidates.append(MatchResult(
                        control=ctrl,
                        control_text=ctrl_text,
                        window_title=title,
                        score=score,
                        method=method,
                    ))

    if not candidates:
        log.warning(
            "No control matched '%s' above threshold %.2f",
            target, MATCH_THRESHOLD,
        )
        return None

    # Pick best match
    best = max(candidates, key=lambda c: c.score)
    log.info(
        "Resolved '%s' → '%s' in '%s' (score=%.2f, method=%s)",
        target, best.control_text, best.window_title[:40],
        best.score, best.method,
    )
    return best


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_match(target: str, control: str) -> tuple[float, str]:
    """Score how well a target matches a control text.

    Returns (score, method) where score is 0.0–1.0.
    """
    # Exact match
    if target == control:
        return 1.0, "exact"

    # Contains: target is a substring of control or vice versa
    if target in control:
        # Longer overlap = better score
        ratio = len(target) / len(control) if control else 0
        return 0.70 + ratio * 0.20, "contains"

    if control in target:
        ratio = len(control) / len(target) if target else 0
        return 0.65 + ratio * 0.15, "contains_reverse"

    # Fuzzy: SequenceMatcher
    ratio = SequenceMatcher(None, target, control).ratio()
    if ratio >= 0.72:
        return 0.40 + ratio * 0.40, "fuzzy"

    return ratio * 0.40, "fuzzy_low"


def _is_active(win: Any) -> bool:
    """Safely check if a window is active."""
    try:
        return win.is_active()
    except Exception:
        return False
