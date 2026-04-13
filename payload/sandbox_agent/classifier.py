"""Screen State Classifier — infers what kind of UI the agent is looking at.

Uses deterministic keyword/heuristic rules to classify the current screen
state from an :class:`Observation`.  No LLM calls — this is fast and
predictable.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .models import Observation, ScreenState, StateClassification

if TYPE_CHECKING:
    from .models import WindowState

log = logging.getLogger("sentinel_agent")

# ---------------------------------------------------------------------------
# Keyword sets (lowered)
# ---------------------------------------------------------------------------

_INSTALLER_TITLE_KW: frozenset[str] = frozenset({
    "setup", "install", "wizard", "update", "installer",
    "uninstall", "package", "deployment",
})

_AGREEMENT_BUTTON_KW: frozenset[str] = frozenset({
    "i agree", "i accept", "accept", "agree",
    "accept the terms", "license agreement", "eula",
})

_SECURITY_TITLE_KW: frozenset[str] = frozenset({
    "smartscreen", "windows security", "user account control",
    "open file - security warning", "security warning",
    "unknown publisher", "windows protected your pc",
    "windows defender",
})

_SECURITY_BUTTON_KW: frozenset[str] = frozenset({
    "run anyway", "more info", "allow", "yes", "allow access",
    "run", "install anyway",
})

_LOGIN_FIELD_KW: frozenset[str] = frozenset({
    "username", "password", "email", "sign in", "log in",
    "user name", "login",
})

_PROGRESS_BUTTON_KW: frozenset[str] = frozenset({
    "next", "next >", "continue", "install", "finish",
    "ok", "close", "done", "yes",
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_screen(obs: Observation) -> StateClassification:
    """Classify the current screen state from observations.

    Returns the highest-confidence classification found.
    """
    if not obs.windows:
        return StateClassification(
            state=ScreenState.DESKTOP_ONLY,
            confidence=0.8,
            explanation="No non-OS windows visible",
        )

    # Try each classifier in priority order; return first high-confidence hit.
    classifiers = [
        _check_security_prompt,
        _check_agreement,
        _check_installer_wizard,
        _check_login_form,
        _check_dialog,
        _check_background_activity,
    ]

    best = StateClassification(
        state=ScreenState.UNKNOWN,
        confidence=0.3,
        explanation="No specific pattern matched",
    )

    for fn in classifiers:
        result = fn(obs)
        if result and result.confidence > best.confidence:
            best = result

    log.info(
        "Classified: %s (%.0f%%) — %s",
        best.state.value,
        best.confidence * 100,
        best.explanation,
    )
    return best


def classify(obs: Observation) -> StateClassification:
    """Backward-compatible alias for older imports."""
    return classify_screen(obs)


# ---------------------------------------------------------------------------
# Individual classifiers
# ---------------------------------------------------------------------------

def _any_kw(text: str, keywords: frozenset[str]) -> bool:
    """True if any keyword appears in the lowered text."""
    low = text.lower()
    return any(kw in low for kw in keywords)


def _check_security_prompt(obs: Observation) -> StateClassification | None:
    for w in obs.windows:
        title_low = w.title.lower()
        # Title matches security keywords
        if any(kw in title_low for kw in _SECURITY_TITLE_KW):
            return StateClassification(
                state=ScreenState.SECURITY_PROMPT,
                confidence=0.95,
                explanation=f"Security prompt detected: '{w.title}'",
                source_window=w.title,
            )
        # Buttons that strongly suggest a security dialog
        for btn in w.buttons:
            if btn.lower() in ("run anyway", "more info", "allow access"):
                return StateClassification(
                    state=ScreenState.SECURITY_PROMPT,
                    confidence=0.90,
                    explanation=f"Security button '{btn}' in '{w.title}'",
                    source_window=w.title,
                )
    return None


def _check_agreement(obs: Observation) -> StateClassification | None:
    for w in obs.windows:
        # Check buttons and checkboxes for agreement keywords
        for text in w.buttons + w.checkboxes:
            if _any_kw(text, _AGREEMENT_BUTTON_KW):
                return StateClassification(
                    state=ScreenState.AGREEMENT,
                    confidence=0.90,
                    explanation=f"Agreement control '{text}' in '{w.title}'",
                    source_window=w.title,
                )
    return None


def _check_installer_wizard(obs: Observation) -> StateClassification | None:
    for w in obs.windows:
        title_low = w.title.lower()
        if any(kw in title_low for kw in _INSTALLER_TITLE_KW):
            conf = 0.85
            # Boost confidence if we also see Next/Install/Continue buttons
            if any(_any_kw(b, _PROGRESS_BUTTON_KW) for b in w.buttons):
                conf = 0.92
            return StateClassification(
                state=ScreenState.INSTALLER_WIZARD,
                confidence=conf,
                explanation=f"Installer window: '{w.title}'",
                source_window=w.title,
            )
        # Even without title match, a window full of progress buttons
        progress_count = sum(1 for b in w.buttons if _any_kw(b, _PROGRESS_BUTTON_KW))
        if progress_count >= 2:
            return StateClassification(
                state=ScreenState.INSTALLER_WIZARD,
                confidence=0.70,
                explanation=f"{progress_count} installer-like buttons in '{w.title}'",
                source_window=w.title,
            )
    return None


def _check_login_form(obs: Observation) -> StateClassification | None:
    for w in obs.windows:
        if w.text_fields >= 2:
            # Check if button/checkbox text hints at login
            all_text = " ".join(w.buttons + w.checkboxes).lower()
            if any(kw in all_text for kw in _LOGIN_FIELD_KW):
                return StateClassification(
                    state=ScreenState.LOGIN_FORM,
                    confidence=0.80,
                    explanation=f"Login form with {w.text_fields} fields in '{w.title}'",
                    source_window=w.title,
                )
            # Multiple text fields without clear login hint
            if w.text_fields >= 3:
                return StateClassification(
                    state=ScreenState.LOGIN_FORM,
                    confidence=0.55,
                    explanation=f"{w.text_fields} text fields in '{w.title}'",
                    source_window=w.title,
                )
    return None


def _check_dialog(obs: Observation) -> StateClassification | None:
    for w in obs.windows:
        # Small number of buttons, no installer keywords, active window
        if w.is_active and 1 <= len(w.buttons) <= 4 and not w.checkboxes:
            return StateClassification(
                state=ScreenState.DIALOG,
                confidence=0.60,
                explanation=f"Simple dialog: '{w.title}' ({len(w.buttons)} buttons)",
                source_window=w.title,
            )
    return None


def _check_background_activity(obs: Observation) -> StateClassification | None:
    # Multiple windows but none active, or all windows have no interactive controls
    if all(not w.is_active for w in obs.windows):
        return StateClassification(
            state=ScreenState.BACKGROUND_ACTIVITY,
            confidence=0.50,
            explanation="No active window — background activity only",
        )
    if obs.windows and not obs.has_actionable_ui:
        return StateClassification(
            state=ScreenState.BACKGROUND_ACTIVITY,
            confidence=0.45,
            explanation="Windows visible but no actionable controls",
        )
    return None
