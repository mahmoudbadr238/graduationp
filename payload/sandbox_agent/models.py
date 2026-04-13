"""Normalized data models for the Sentinel sandbox agent.

Every layer of the agent pipeline operates on well-defined dataclasses
so that data flows are explicit and inspectable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Observation layer
# ---------------------------------------------------------------------------

@dataclass
class WindowState:
    """Snapshot of a single top-level window's accessible controls."""

    title: str
    buttons: list[str] = field(default_factory=list)
    checkboxes: list[str] = field(default_factory=list)
    text_fields: int = 0
    is_active: bool = False


@dataclass
class Observation:
    """Complete UI observation across all visible windows."""

    windows: list[WindowState] = field(default_factory=list)
    timestamp: float = field(default_factory=time.monotonic)

    @property
    def active_window(self) -> WindowState | None:
        """Return the currently active window, if any."""
        for w in self.windows:
            if w.is_active:
                return w
        return None

    @property
    def has_actionable_ui(self) -> bool:
        """True if any window has buttons or checkboxes."""
        return any(w.buttons or w.checkboxes for w in self.windows)

    def to_json_list(self) -> list[dict[str, Any]]:
        """Serialize to the compact list-of-dicts format expected by the LLM."""
        out: list[dict[str, Any]] = []
        for w in self.windows:
            out.append({
                "window": w.title,
                "buttons": w.buttons,
                "checkboxes": w.checkboxes,
                "text_fields": w.text_fields,
                "active": w.is_active,
            })
        return out


# ---------------------------------------------------------------------------
# State classification
# ---------------------------------------------------------------------------

class ScreenState(str, Enum):
    """Broad categories the current UI can be classified into."""

    IDLE = "idle"
    UNKNOWN = "unknown"
    DIALOG = "dialog"
    INSTALLER_WIZARD = "installer_wizard"
    AGREEMENT = "agreement"
    LOGIN_FORM = "login_form"
    SECURITY_PROMPT = "security_prompt"
    DESKTOP_ONLY = "desktop_only"
    BACKGROUND_ACTIVITY = "background_activity"


@dataclass
class StateClassification:
    """Result of classifying the current screen state."""

    state: ScreenState
    confidence: float  # 0.0 – 1.0
    explanation: str
    # Which window drove the classification (by title)
    source_window: str = ""


# ---------------------------------------------------------------------------
# Action decision
# ---------------------------------------------------------------------------

class ActionType(str, Enum):
    CLICK = "click"
    CHECK = "check"
    TYPE = "type"
    KEY = "key"
    WAIT = "wait"


@dataclass
class ActionDecision:
    """A single proposed action the agent wants to execute."""

    action: ActionType
    target: str = ""
    confidence: float = 0.0
    reason: str = ""

    @staticmethod
    def wait(reason: str = "no actionable UI") -> ActionDecision:
        return ActionDecision(
            action=ActionType.WAIT, confidence=1.0, reason=reason,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "target": self.target,
            "confidence": round(self.confidence, 2),
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Action resolution
# ---------------------------------------------------------------------------

@dataclass
class MatchResult:
    """Result of resolving a target string to a real UI control."""

    control: Any  # pywinauto wrapper element
    control_text: str
    window_title: str
    score: float  # 0.0 – 1.0
    method: str  # "exact", "contains", "fuzzy"


# ---------------------------------------------------------------------------
# Action record (memory / retry guard)
# ---------------------------------------------------------------------------

@dataclass
class ActionRecord:
    """Record of a past action for the memory/retry guard."""

    cycle: int
    timestamp: float
    decision: ActionDecision
    executed: bool
    state_changed: bool
    match_score: float = 0.0
    verification: str = ""  # "changed", "unchanged", "error"


# ---------------------------------------------------------------------------
# UI Fingerprint (verifier)
# ---------------------------------------------------------------------------

@dataclass
class UIFingerprint:
    """Lightweight snapshot of the UI state for before/after comparison."""

    window_titles: frozenset[str] = field(default_factory=frozenset)
    active_title: str = ""
    button_texts: frozenset[str] = field(default_factory=frozenset)
    checkbox_texts: frozenset[str] = field(default_factory=frozenset)
    total_buttons: int = 0
    total_checkboxes: int = 0

    @staticmethod
    def from_observation(obs: Observation) -> UIFingerprint:
        titles: set[str] = set()
        buttons: set[str] = set()
        checkboxes: set[str] = set()
        active = ""
        for w in obs.windows:
            titles.add(w.title)
            if w.is_active:
                active = w.title
            buttons.update(w.buttons)
            checkboxes.update(w.checkboxes)
        return UIFingerprint(
            window_titles=frozenset(titles),
            active_title=active,
            button_texts=frozenset(buttons),
            checkbox_texts=frozenset(checkboxes),
            total_buttons=len(buttons),
            total_checkboxes=len(checkboxes),
        )

    def similarity(self, other: UIFingerprint) -> float:
        """Return 0.0–1.0 similarity score between two fingerprints."""
        if not self.window_titles and not other.window_titles:
            return 1.0

        scores: list[float] = []

        # Window titles overlap
        if self.window_titles or other.window_titles:
            union = self.window_titles | other.window_titles
            inter = self.window_titles & other.window_titles
            scores.append(len(inter) / len(union) if union else 1.0)

        # Same active window?
        scores.append(1.0 if self.active_title == other.active_title else 0.0)

        # Button sets overlap
        if self.button_texts or other.button_texts:
            union = self.button_texts | other.button_texts
            inter = self.button_texts & other.button_texts
            scores.append(len(inter) / len(union) if union else 1.0)

        return sum(scores) / len(scores) if scores else 1.0
