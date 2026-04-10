"""
URL Scanner Engine — Google Safe Browsing v4 Worker for Sentinel.

Provides a dedicated PySide6 QThread worker that queries the Google Safe
Browsing Lookup API to determine whether a URL is malicious.

Environment
~~~~~~~~~~~
* ``GOOGLE_SAFE_BROWSING_KEY`` — **required**.  Pulled from ``os.environ``
  (loaded via ``dotenv`` as a convenience fallback).

Signals
~~~~~~~
* ``scan_finished(dict)`` — emitted with the scan verdict.
* ``scan_error(str)``     — emitted on network / API failures.

Usage::

    worker = URLScannerWorker("https://example.com")
    worker.scan_finished.connect(handle_result)
    worker.scan_error.connect(handle_error)
    worker.start()
"""

from __future__ import annotations

import logging
import os
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_GSB_ENDPOINT = (
    "https://safebrowsing.googleapis.com/v4/threatMatches:find"
)

_THREAT_TYPES = [
    "MALWARE",
    "SOCIAL_ENGINEERING",
    "UNWANTED_SOFTWARE",
    "POTENTIALLY_HARMFUL_APPLICATION",
]

# Human-readable labels for each threat type
_THREAT_LABELS: dict[str, str] = {
    "MALWARE": "Malware",
    "SOCIAL_ENGINEERING": "Phishing",
    "UNWANTED_SOFTWARE": "Unwanted Software",
    "POTENTIALLY_HARMFUL_APPLICATION": "Potentially Harmful Application",
}

_REQUEST_TIMEOUT = 5  # seconds


# ── Worker ───────────────────────────────────────────────────────────────────


class URLScannerWorker(QThread):
    """Background worker that queries Google Safe Browsing v4 for a URL.

    Signals
    -------
    scan_finished(dict)
        Emitted with a verdict dict containing ``status``, ``score``,
        ``details``, ``threat_types``, and ``url``.
    scan_error(str)
        Emitted with a human-readable error message on failure.
    """

    scan_finished = Signal(dict)
    scan_error = Signal(str)

    def __init__(
        self,
        target_url: str,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._target_url = target_url.strip()

    # ── Core logic ───────────────────────────────────────────────────────

    def run(self) -> None:  # noqa: D401 — QThread override
        """Execute the Safe Browsing lookup off the main thread."""
        try:
            result = self.scan_url(self._target_url)
            self.scan_finished.emit(result)
        except Exception as exc:
            logger.exception("URLScannerWorker failed: %s", exc)
            self.scan_error.emit(str(exc)[:300])

    @staticmethod
    def scan_url(target_url: str) -> dict[str, Any]:
        """Query Google Safe Browsing v4 for *target_url*.

        Returns a dict with:
        * ``status``  – ``"Clean"`` or ``"Malicious"``
        * ``score``   – ``0`` (clean) or ``95`` (malicious)
        * ``details`` – human-readable explanation
        * ``threat_types`` – list of matched threat labels (empty if clean)
        * ``url``     – the URL that was checked

        Raises
        ------
        RuntimeError
            If the API key is missing.
        requests.exceptions.RequestException
            On network / HTTP errors.
        """
        import requests  # local import — mirrors project pattern

        # ── Resolve API key ──────────────────────────────────────────
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        api_key = os.environ.get("GOOGLE_SAFE_BROWSING_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "GOOGLE_SAFE_BROWSING_KEY is not set. "
                "Add it to your .env file or system environment."
            )

        # ── Build payload ────────────────────────────────────────────
        payload = {
            "client": {
                "clientId": "sentinel-endpoint-suite",
                "clientVersion": "1.0.0",
            },
            "threatInfo": {
                "threatTypes": _THREAT_TYPES,
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": target_url}],
            },
        }

        # ── Call API ─────────────────────────────────────────────────
        resp = requests.post(
            _GSB_ENDPOINT,
            params={"key": api_key},
            json=payload,
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()

        data = resp.json()

        # ── Parse response ───────────────────────────────────────────
        matches = data.get("matches")
        if not matches:
            return {
                "status": "Clean",
                "score": 0,
                "details": "No threats detected by Google Safe Browsing.",
                "threat_types": [],
                "url": target_url,
            }

        # Deduplicate threat types and convert to readable labels
        raw_types = list({m.get("threatType", "UNKNOWN") for m in matches})
        labels = [_THREAT_LABELS.get(t, t) for t in raw_types]

        return {
            "status": "Malicious",
            "score": 95,
            "details": (
                f"Google Safe Browsing flagged this URL as: "
                f"{', '.join(labels)}"
            ),
            "threat_types": labels,
            "url": target_url,
        }


# ── Convenience bridge ───────────────────────────────────────────────────────


class URLScannerBridge(QObject):
    """Thin QML-friendly bridge that manages ``URLScannerWorker`` lifecycle.

    Connect the signals to your backend bridge or directly to QML:

    * ``url_scan_finished(dict)``
    * ``url_scan_error(str)``
    """

    url_scan_finished = Signal(dict)
    url_scan_error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._worker: URLScannerWorker | None = None

    @Slot(str)
    def scan(self, url: str) -> None:
        """Start a Safe Browsing scan for *url*.

        If a scan is already in progress the call is silently ignored.
        """
        if self._worker is not None and self._worker.isRunning():
            logger.debug("URLScannerBridge: scan already in progress")
            return

        self._worker = URLScannerWorker(url, parent=self)
        self._worker.scan_finished.connect(self._on_finished)
        self._worker.scan_error.connect(self._on_error)
        self._worker.finished.connect(self._on_thread_done)
        self._worker.start()

    # ── Callbacks ────────────────────────────────────────────────────

    def _on_finished(self, result: dict) -> None:
        self.url_scan_finished.emit(result)

    def _on_error(self, msg: str) -> None:
        self.url_scan_error.emit(msg)

    def _on_thread_done(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
