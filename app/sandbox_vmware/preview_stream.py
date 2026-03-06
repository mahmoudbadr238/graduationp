"""Periodic vmrun captureScreen preview stream for Sandbox Live Preview.

Runs a daemon thread that calls:
    vmrun -T ws captureScreen <vmx_path> <out_png>
every <interval_sec> seconds while active.

Thread-safe. Start/stop can be called any number of times.
Failures are suppressed after the first N consecutive errors so the
background thread never spams the log while the VM is powering on.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# After this many consecutive failures, suppress individual debug lines.
_SUPPRESS_AFTER: int = 5
# After suppression, emit at most one WARNING per this many seconds.
_SUPPRESSED_WARN_INTERVAL: float = 30.0


class SandboxPreviewStream:
    """Capture sandbox VM screenshots periodically via ``vmrun captureScreen``.

    Usage::

        stream = SandboxPreviewStream(
            vmrun_path=cfg.vmrun_path,
            vmx_path=cfg.vmx_path,
            out_path="data/artifacts/sandbox_preview.png",
            interval_sec=0.7,
            on_update=lambda path, ts_ms: signal.emit(f"file:///{path}?ts={ts_ms}"),
        )
        stream.start()
        # … scan runs …
        stream.stop()

    The ``on_update`` callback is invoked from the background thread whenever
    a screenshot is written successfully.  Callers that need to propagate the
    update to Qt (e.g. emit a PySide6 Signal) can do so safely — PySide6 will
    queue the delivery to the main thread automatically.
    """

    def __init__(
        self,
        vmrun_path: str,
        vmx_path: str,
        out_path: str,
        interval_sec: float = 0.7,
        on_update: "Callable[[str, int], None] | None" = None,
        guest_user: str = "",
        guest_pass: str = "",
    ) -> None:
        """
        Args:
            vmrun_path:   Absolute path to vmrun.exe.
            vmx_path:     Absolute path to the sandbox .vmx file.
            out_path:     Destination PNG path.  Parent directory is created
                          automatically if it does not exist.
            interval_sec: Capture interval in seconds (0.4 – 1.0 recommended).
            on_update:    Optional callback ``(file_path: str, ts_ms: int)``.
                          Invoked after each *successful* capture.
            guest_user:   VMware guest username (passed as -gu to vmrun).
            guest_pass:   VMware guest password (passed as -gp to vmrun).
        """
        self._vmrun = vmrun_path
        self._vmx = vmx_path
        self._out_path = str(Path(out_path).resolve())
        self._interval = max(0.2, float(interval_sec))
        self._on_update = on_update
        self._guest_user = guest_user
        self._guest_pass = guest_pass

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._consec_failures: int = 0
        self._last_warn_at: float = 0.0

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start (or restart) the background capture thread."""
        if self._thread and self._thread.is_alive():
            return  # already running
        self._stop_event.clear()
        self._consec_failures = 0
        self._last_warn_at = 0.0
        try:
            Path(self._out_path).parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("SandboxPreviewStream: cannot create output dir: %s", exc)
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="sandbox-preview-capture",
        )
        self._thread.start()
        logger.debug(
            "SandboxPreviewStream started — interval=%.1fs out=%s",
            self._interval,
            self._out_path,
        )

    def stop(self) -> None:
        """Signal the capture thread to stop (non-blocking).

        The thread will exit on its own within one capture cycle.
        """
        self._stop_event.set()
        logger.debug("SandboxPreviewStream stop requested")

    @property
    def running(self) -> bool:
        """True if the background thread is alive."""
        return bool(self._thread and self._thread.is_alive())

    # ── Internal ───────────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            self._capture_once()
            # Sleep in 50 ms chunks so stop() is responsive within one interval.
            deadline = time.monotonic() + self._interval
            while not self._stop_event.is_set() and time.monotonic() < deadline:
                time.sleep(0.05)

    def _capture_once(self) -> None:
        try:
            cmd = [self._vmrun, "-T", "ws"]
            if self._guest_user and self._guest_pass:
                cmd += ["-gu", self._guest_user, "-gp", self._guest_pass]
            cmd += ["captureScreen", self._vmx, self._out_path]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=4,
                creationflags=0x08000000,   # CREATE_NO_WINDOW on Windows
            )
            if result.returncode == 0:
                self._consec_failures = 0
                ts_ms = int(time.time() * 1000)
                if self._on_update:
                    try:
                        self._on_update(self._out_path, ts_ms)
                    except Exception as cb_exc:
                        logger.debug("Preview on_update callback error: %s", cb_exc)
            else:
                reason = (result.stderr or result.stdout or "").strip()
                self._record_failure(reason or f"exit {result.returncode}")
        except subprocess.TimeoutExpired:
            self._record_failure("captureScreen timed out after 4 s")
        except FileNotFoundError:
            self._record_failure(f"vmrun not found: {self._vmrun}")
            self._stop_event.set()  # No point retrying without vmrun.exe
        except OSError as exc:
            # Possible on first few captures if VM hasn't started yet
            self._record_failure(str(exc))
        except Exception as exc:  # noqa: BLE001
            self._record_failure(str(exc))

    def _record_failure(self, reason: str) -> None:
        self._consec_failures += 1
        if self._consec_failures <= _SUPPRESS_AFTER:
            logger.debug("Preview capture: %s (attempt %d)", reason, self._consec_failures)
        else:
            now = time.monotonic()
            if now - self._last_warn_at > _SUPPRESSED_WARN_INTERVAL:
                logger.warning(
                    "Sandbox preview unavailable (suppressed): %s", reason
                )
                self._last_warn_at = now
