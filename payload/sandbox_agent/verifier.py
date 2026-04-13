"""Action Verifier — determines whether an action changed the UI.

After each action, re-observes the UI and compares a fingerprint of
the before/after states.  Returns a verdict the memory module uses
to decide whether the action was effective.
"""

from __future__ import annotations

import logging

from .models import Observation, UIFingerprint
from .observer import observe

log = logging.getLogger("sentinel_agent")

# Below this similarity threshold, the UI is considered to have changed
CHANGE_THRESHOLD = 0.90


def ui_fingerprint(obs: Observation) -> UIFingerprint:
    """Build a comparable fingerprint from an observation snapshot."""
    return UIFingerprint.from_observation(obs)


def verify(before: Observation) -> tuple[Observation, str]:
    """Re-observe the UI and compare against the *before* snapshot.

    Returns
    -------
    (after_observation, verdict)
        verdict is one of: "changed", "unchanged", "error"
    """
    try:
        after = observe()
    except Exception as exc:
        log.warning("Post-action observation failed: %s", exc)
        return Observation(), "error"

    fp_before = ui_fingerprint(before)
    fp_after = ui_fingerprint(after)
    sim = fp_before.similarity(fp_after)

    if sim < CHANGE_THRESHOLD:
        verdict = "changed"
    else:
        verdict = "unchanged"

    log.info(
        "Verification: similarity=%.2f → %s  "
        "(windows: %d→%d, buttons: %d→%d)",
        sim,
        verdict,
        len(before.windows),
        len(after.windows),
        fp_before.total_buttons,
        fp_after.total_buttons,
    )
    return after, verdict
