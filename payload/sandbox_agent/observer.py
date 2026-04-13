"""UI Observer — enumerates visible windows and their controls.

Uses pywinauto's UIA backend to walk the accessibility tree and produce
a normalized :class:`Observation` that the rest of the pipeline consumes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pywinauto import Desktop

from .models import Observation, WindowState

if TYPE_CHECKING:
    pass

log = logging.getLogger("sentinel_agent")

# Window titles belonging to OS chrome — never enumerate
IGNORED_TITLES: frozenset[str] = frozenset({
    "taskbar",
    "start",
    "program manager",
    "windows input experience",
    "text input application",
    "sentinel agent",
})


def observe() -> Observation:
    """Enumerate all visible non-OS windows and return a normalized Observation."""
    windows: list[WindowState] = []

    try:
        top_windows = Desktop(backend="uia").windows()
    except Exception as exc:
        log.warning("Desktop enumeration failed: %s", exc)
        return Observation(windows=[])

    for win in top_windows:
        try:
            title = (win.window_text() or "").strip()
        except Exception:
            continue

        if not title or title.lower() in IGNORED_TITLES:
            continue

        ws = WindowState(title=title[:120])

        try:
            ws.is_active = win.is_active()
        except Exception:
            pass

        # Buttons
        try:
            for ctrl in win.descendants(control_type="Button"):
                try:
                    txt = (ctrl.window_text() or "").strip()
                    if txt and len(txt) < 80:
                        ws.buttons.append(txt)
                except Exception:
                    continue
        except Exception:
            pass

        # Checkboxes
        try:
            for ctrl in win.descendants(control_type="CheckBox"):
                try:
                    txt = (ctrl.window_text() or "").strip()
                    if txt and len(txt) < 120:
                        ws.checkboxes.append(txt)
                except Exception:
                    continue
        except Exception:
            pass

        # Text fields
        try:
            ws.text_fields = len(win.descendants(control_type="Edit"))
        except Exception:
            pass

        windows.append(ws)

    # Sort: active window first, then windows with more buttons
    windows.sort(key=lambda w: (not w.is_active, -len(w.buttons)))

    log.info(
        "Observed %d windows: %s",
        len(windows),
        [w.title[:40] for w in windows],
    )
    return Observation(windows=windows)
