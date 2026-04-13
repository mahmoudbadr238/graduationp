"""Decision Engine — chooses what action to take next.

Uses deterministic rules when confidence is high, falls back to the LLM
(Groq) only when the rules are not sufficient.  All outputs are structured
:class:`ActionDecision` objects with confidence and reason.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

from .models import (
    ActionDecision,
    ActionType,
    Observation,
    ScreenState,
    StateClassification,
)

if TYPE_CHECKING:
    from .memory import ActionMemory

log = logging.getLogger("sentinel_agent")

# ---------------------------------------------------------------------------
# Groq / LLM configuration
# ---------------------------------------------------------------------------

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("AI_MODEL_AGENT", "llama-3.1-8b-instant")

SYSTEM_PROMPT = (
    "You are an autonomous agent inside a malware sandbox. "
    "Your goal is to act like a gullible human user and interact with "
    "whatever is on screen to make the software fully execute.\n\n"
    "You will receive the current UI state as JSON with window titles "
    "and lists of visible button/checkbox texts.\n\n"
    "Rules:\n"
    "- If you see an installer/setup/license dialog, click the button "
    "that progresses the installation (e.g. 'Next', 'Install', 'I Agree').\n"
    "- If you see a checkbox like 'I accept the terms', check it first.\n"
    "- If you see a security warning or SmartScreen, click the allow button.\n"
    "- If there are no actionable controls, reply with wait.\n"
    "- NEVER invent a button that does not appear in the observation.\n"
    "- Your target MUST be the exact text of a control from the observation.\n\n"
    "Reply ONLY with a single JSON object — no explanation, no markdown.\n"
    "Required fields: action, target, confidence (0.0-1.0), reason.\n"
    "Allowed actions:\n"
    '  {"action":"click","target":"<button_text>","confidence":0.9,"reason":"..."}\n'
    '  {"action":"check","target":"<checkbox_text>","confidence":0.9,"reason":"..."}\n'
    '  {"action":"type","target":"<text>","confidence":0.8,"reason":"..."}\n'
    '  {"action":"key","target":"<key_combo>","confidence":0.8,"reason":"..."}\n'
    '  {"action":"wait","target":"","confidence":1.0,"reason":"..."}\n'
)

# ---------------------------------------------------------------------------
# Deterministic rule tables
# ---------------------------------------------------------------------------

# Buttons to click in security prompts (in priority order)
_SECURITY_BUTTONS: list[str] = [
    "run anyway", "more info", "yes", "allow", "allow access",
    "run", "install anyway", "continue",
]

# Buttons to click in agreement dialogs
_AGREEMENT_BUTTONS: list[str] = [
    "i agree", "i accept", "agree", "accept",
]

# Checkboxes to check in agreement dialogs
_AGREEMENT_CHECKBOXES: list[str] = [
    "i accept", "i agree", "accept the terms", "agree",
]

# Buttons to click in installer wizards (priority order)
_INSTALLER_BUTTONS: list[str] = [
    "install", "next >", "next", "continue", "finish",
    "ok", "close", "done", "yes",
]

# Generic dialog buttons (safe default)
_DIALOG_BUTTONS: list[str] = [
    "ok", "yes", "close", "continue", "retry",
]

# Minimum confidence to accept an LLM decision
LLM_MIN_CONFIDENCE = 0.65

# Keyboard shortcuts are allowed only when explicitly justified by state
ALLOWED_SECURITY_KEYS = {"alt+y"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def decide(
    obs: Observation,
    classification: StateClassification,
    api_key: str = "",
    memory: ActionMemory | None = None,
) -> ActionDecision:
    """Choose the next action based on observation and classification.

    Tries deterministic rules first.  Falls back to LLM when rules
    cannot decide with sufficient confidence.
    """
    # 1. Try deterministic rules
    rule_decision = _decide_by_rules(obs, classification, memory)
    if rule_decision and rule_decision.confidence >= 0.7:
        log.info("Rule decision: %s", rule_decision.to_dict())
        return rule_decision

    # 2. Fall back to LLM
    if api_key:
        llm_decision = _decide_by_llm(obs, api_key)
        if llm_decision and llm_decision.action != ActionType.WAIT:
            if not _is_action_allowed_for_state(llm_decision, classification):
                log.warning(
                    "LLM suggested action '%s' not allowed for state '%s'",
                    llm_decision.action.value,
                    classification.state.value,
                )
                return ActionDecision.wait("LLM action not allowed for current state")

            # Validate: target must exist in observation
            if _target_exists_in_observation(llm_decision, obs):
                # Validate: not a recently-failed action
                if memory and memory.is_suppressed(llm_decision.action.value, llm_decision.target):
                    log.info("LLM suggested suppressed action — falling back to wait")
                    return ActionDecision.wait("LLM action suppressed by retry guard")
                log.info("LLM decision: %s", llm_decision.to_dict())
                return llm_decision
            else:
                log.warning(
                    "LLM suggested target '%s' not found in observation — rejecting",
                    llm_decision.target,
                )

    return ActionDecision.wait("no confident action available")


# ---------------------------------------------------------------------------
# Deterministic rules
# ---------------------------------------------------------------------------

def _decide_by_rules(
    obs: Observation,
    classification: StateClassification,
    memory: ActionMemory | None = None,
) -> ActionDecision | None:
    """Apply deterministic rules based on the screen state classification."""
    state = classification.state
    source = classification.source_window

    # Find the source window in observations
    target_win = None
    for w in obs.windows:
        if w.title == source:
            target_win = w
            break
    if target_win is None and obs.windows:
        target_win = obs.active_window or obs.windows[0]

    if target_win is None:
        return None

    def _pick_button(candidates: list[str], conf: float) -> ActionDecision | None:
        """Find the first matching button from candidates, respecting memory."""
        for candidate in candidates:
            cand_low = candidate.lower()
            for btn in target_win.buttons:
                if btn.lower() == cand_low or cand_low in btn.lower():
                    if memory and memory.is_suppressed("click", btn):
                        continue
                    return ActionDecision(
                        action=ActionType.CLICK,
                        target=btn,
                        confidence=conf,
                        reason=f"Rule: {state.value} → click '{btn}'",
                    )
        return None

    def _pick_checkbox(candidates: list[str], conf: float) -> ActionDecision | None:
        for candidate in candidates:
            cand_low = candidate.lower()
            for cb in target_win.checkboxes:
                if cand_low in cb.lower():
                    if memory and memory.is_suppressed("check", cb):
                        continue
                    return ActionDecision(
                        action=ActionType.CHECK,
                        target=cb,
                        confidence=conf,
                        reason=f"Rule: {state.value} → check '{cb}'",
                    )
        return None

    if state == ScreenState.SECURITY_PROMPT:
        result = _pick_button(_SECURITY_BUTTONS, 0.92)
        if result:
            return result
        return ActionDecision.wait("security prompt seen but no confident allow control")

    if state == ScreenState.AGREEMENT:
        # Check checkbox first, then click button
        cb = _pick_checkbox(_AGREEMENT_CHECKBOXES, 0.90)
        if cb:
            return cb
        return _pick_button(_AGREEMENT_BUTTONS + _INSTALLER_BUTTONS, 0.85)

    if state == ScreenState.INSTALLER_WIZARD:
        return _pick_button(_INSTALLER_BUTTONS, 0.88)

    if state == ScreenState.DIALOG:
        return _pick_button(_DIALOG_BUTTONS, 0.70)

    # For other states (idle, desktop_only, background_activity, unknown)
    return None


# ---------------------------------------------------------------------------
# LLM-based decision (Groq)
# ---------------------------------------------------------------------------

def _decide_by_llm(obs: Observation, api_key: str) -> ActionDecision | None:
    """Send observation to Groq and parse the action response."""
    user_msg = json.dumps(obs.to_json_list(), ensure_ascii=False)
    if len(user_msg) > 3000:
        user_msg = user_msg[:3000] + "...]"

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.1,
        "max_tokens": 150,
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        GROQ_API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        content = data["choices"][0]["message"]["content"]
        log.info("Groq raw: %s", content[:200])

        parsed = _extract_json(content)
        if not parsed or "action" not in parsed:
            log.warning("Groq response not parseable: %s", content[:200])
            return None

        action_str = parsed.get("action", "wait").lower()
        try:
            action_type = ActionType(action_str)
        except ValueError:
            log.warning("Unknown action type from LLM: '%s'", action_str)
            return None

        confidence = float(parsed.get("confidence", 0.5))
        if confidence < LLM_MIN_CONFIDENCE:
            log.info("LLM confidence %.2f below threshold — rejecting", confidence)
            return None

        return ActionDecision(
            action=action_type,
            target=parsed.get("target", ""),
            confidence=confidence,
            reason=parsed.get("reason", "LLM decision"),
        )

    except urllib.error.HTTPError as exc:
        log.warning("Groq HTTP %d: %s", exc.code, exc.reason)
        return None
    except Exception as exc:
        log.warning("Groq request failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict | None:
    """Extract a JSON object from LLM response, handling markdown fences."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{[^{}]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _target_exists_in_observation(decision: ActionDecision, obs: Observation) -> bool:
    """Verify that the LLM's target actually exists in the current observation."""
    if decision.action in (ActionType.WAIT, ActionType.KEY, ActionType.TYPE):
        return True  # these don't require a control match

    target_low = decision.target.lower().strip()
    if not target_low:
        return False

    for w in obs.windows:
        for btn in w.buttons:
            if btn.lower().strip() == target_low:
                return True
        for cb in w.checkboxes:
            if cb.lower().strip() == target_low:
                return True
    return False


def _is_action_allowed_for_state(
    decision: ActionDecision,
    classification: StateClassification,
) -> bool:
    """Enforce state-aware safety for higher-risk action types."""
    if decision.action != ActionType.KEY:
        return True

    key = decision.target.lower().strip()
    if not key:
        return False

    if classification.state == ScreenState.SECURITY_PROMPT and key in ALLOWED_SECURITY_KEYS:
        return True

    return False
