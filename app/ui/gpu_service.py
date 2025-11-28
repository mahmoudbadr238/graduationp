"""
GPU Service Bridge - QProcess-based GPU telemetry manager
Spawns subprocess worker, handles heartbeat watchdog, circuit breaker
"""

import json
import logging
import sys
import time
from typing import Any

from PySide6.QtCore import Property, QObject, QProcess, QTimer, Signal, Slot

logger = logging.getLogger(__name__)


class GPUServiceBridge(QObject):
    """
    QProcess-based GPU telemetry service

    Features:
    - Subprocess isolation (never blocks UI)
    - Heartbeat watchdog (6s timeout)
    - Circuit breaker (3 fails in 60s = disabled)
    - On-demand start/stop
    """

    # Signals
    metricsUpdated = Signal()
    statusChanged = Signal(str)  # stopped, starting, running, degraded, breaker-open
    updateIntervalChanged = Signal(int)
    gpuCountChanged = Signal(int)
    metricsChanged = Signal()  # Emitted when GPU metrics are updated
    error = Signal(str, str)  # title, message

    def __init__(self, parent=None):
        super().__init__(parent)

        # Process management
        self._proc = QProcess(self)
        self._proc.setProgram(sys.executable)
        self._proc.setArguments(["-u", "-m", "app.gpu.telemetry_worker"])
        self._proc.readyReadStandardOutput.connect(self._on_stdout)
        self._proc.readyReadStandardError.connect(self._on_stderr)
        self._proc.started.connect(self._on_started)
        self._proc.finished.connect(self._on_finished)
        self._proc.errorOccurred.connect(self._on_error)

        # Heartbeat watchdog (20s timeout - GPU metrics can be slow)
        self._hb_timer = QTimer(self)
        self._hb_timer.setInterval(20000)
        self._hb_timer.timeout.connect(self._on_missed_heartbeat)

        # Circuit breaker (track failures)
        self._failures: list[float] = []
        self._breaker_open = False

        # State
        self._status = "stopped"
        self._interval = 2000  # Default 2s
        self._gpu_count = 0
        self._metrics_cache: list[dict[str, Any]] = []

        logger.info("GPU Service Bridge initialized")

    # Properties
    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(int, notify=gpuCountChanged)
    def gpuCount(self) -> int:
        return self._gpu_count

    @Property('QVariantList', notify=metricsChanged)
    def metrics(self) -> list:
        """Get all GPU metrics as a list of dicts"""
        return self._metrics_cache

    def getUpdateInterval(self) -> int:
        return self._interval

    def setUpdateInterval(self, ms: int):
        if ms != self._interval:
            self._interval = ms
            self.updateIntervalChanged.emit(ms)
            # Restart if running
            if self._status == "running":
                self.stop()
                self.start(ms)

    updateInterval = Property(
        int,
        fget=getUpdateInterval,
        fset=setUpdateInterval,
        notify=updateIntervalChanged,
    )

    # Control methods
    @Slot(int)
    def start(self, interval_ms: int = 1000):
        """Start GPU telemetry worker"""
        if self._breaker_open:
            logger.warning("Circuit breaker open - GPU telemetry disabled")
            self.error.emit(
                "GPU Monitoring Disabled", "Too many failures. Restart app to retry."
            )
            return

        if self._proc.state() != QProcess.ProcessState.NotRunning:
            logger.debug("Worker already running")
            return

        self._interval = interval_ms
        self.updateIntervalChanged.emit(interval_ms)

        # Update worker arguments with interval
        self._proc.setArguments(
            ["-u", "-m", "app.gpu.telemetry_worker", str(interval_ms)]
        )

        logger.info(f"Starting GPU worker (interval={interval_ms}ms)")
        self._set_status("starting")
        self._proc.start()
        self._hb_timer.start()

    @Slot()
    def stop(self):
        """Stop GPU telemetry worker"""
        self._hb_timer.stop()

        if self._proc.state() != QProcess.ProcessState.NotRunning:
            logger.info("Stopping GPU worker")
            self._proc.kill()
            self._proc.waitForFinished(500)

        self._set_status("stopped")
        self._gpu_count = 0
        self._metrics_cache.clear()
        self.gpuCountChanged.emit(0)
        self.metricsUpdated.emit()

    @Slot(result=bool)
    def isRunning(self) -> bool:
        """Check if worker is running"""
        return self._proc.state() == QProcess.ProcessState.Running

    @Slot(int, result="QVariantMap")
    def getGPUMetrics(self, gpu_id: int) -> dict[str, Any]:
        """Get metrics for specific GPU"""
        if 0 <= gpu_id < len(self._metrics_cache):
            return self._metrics_cache[gpu_id]
        return {
            "id": gpu_id,
            "name": "Unknown",
            "vendor": "Unknown",
            "usage": 0.0,
            "memUsedMB": 0,
            "memTotalMB": 0,
            "memPercent": 0.0,
            "tempC": 0,
            "powerW": 0.0,
            "powerLimitW": 0.0,
            "clockMHz": 0,
            "fanPercent": 0,
        }

    @Slot(result=list)
    def getAllMetrics(self) -> list[dict[str, Any]]:
        """Get all GPU metrics"""
        return self._metrics_cache.copy()

    # Internal handlers
    def _set_status(self, status: str):
        """Update status and emit signal"""
        if status != self._status:
            self._status = status
            logger.debug(f"Status: {status}")
            self.statusChanged.emit(status)

    def _on_stdout(self):
        """Parse worker stdout (JSON lines)"""
        try:
            data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", "ignore")

            for line in data.strip().splitlines():
                if not line:
                    continue

                try:
                    msg = json.loads(line)
                    msg_type = msg.get("type")

                    if msg_type == "heartbeat":
                        # Reset watchdog
                        self._hb_timer.start()
                        if self._status != "running":
                            self._set_status("running")

                    elif msg_type == "metrics":
                        # Update metrics cache
                        gpus = msg.get("gpus", [])
                        self._metrics_cache = gpus

                        new_count = len(gpus)
                        if new_count != self._gpu_count:
                            self._gpu_count = new_count
                            self.gpuCountChanged.emit(new_count)

                        self.metricsUpdated.emit()
                        self.metricsChanged.emit()

                    elif msg_type == "error":
                        logger.error(f"Worker error: {msg.get('msg')}")

                    elif msg_type == "init":
                        vendors = msg.get("vendors", {})
                        logger.info(f"Worker initialized: {vendors}")

                    elif msg_type == "startup":
                        logger.info(f"Worker started (interval={msg.get('interval')}s)")

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from worker: {line[:100]}")

        except Exception as e:
            logger.exception(f"Error parsing worker output: {e}")

    def _on_stderr(self):
        """Log worker stderr"""
        data = bytes(self._proc.readAllStandardError()).decode("utf-8", "ignore")
        if data.strip():
            logger.warning(f"Worker stderr: {data.strip()}")

    def _on_started(self):
        """Worker process started"""
        logger.info("Worker process started")

    def _on_finished(self, exit_code: int, exit_status):
        """Worker process finished"""
        logger.info(f"Worker finished (code={exit_code}, status={exit_status})")
        self._set_status("stopped")

    def _on_error(self, error):
        """Worker process error"""
        logger.error(f"Worker error: {error}")
        self._set_status("degraded")

    def _on_missed_heartbeat(self):
        """Heartbeat timeout - worker is stalled"""
        logger.warning("Heartbeat missed - worker stalled")

        # Record failure
        self._failures = [t for t in self._failures if time.time() - t < 60]
        self._failures.append(time.time())

        # Kill stalled worker
        self.stop()

        # Circuit breaker check
        if len(self._failures) >= 3:
            logger.error("Circuit breaker OPEN - too many failures")
            self._breaker_open = True
            self._set_status("breaker-open")
            self.error.emit(
                "GPU Telemetry Disabled",
                "GPU monitoring failed multiple times and has been disabled. Restart the application to re-enable.",
            )
        else:
            # Auto-restart
            logger.info(f"Restarting worker (failure {len(self._failures)}/3)")
            self._set_status("restarting")
            QTimer.singleShot(1000, lambda: self.start(self._interval))

    def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up GPU service")
        self.stop()


# Singleton
_gpu_service_instance = None


def get_gpu_service() -> GPUServiceBridge:
    """Get or create GPU service singleton"""
    global _gpu_service_instance
    if _gpu_service_instance is None:
        _gpu_service_instance = GPUServiceBridge()
    return _gpu_service_instance
