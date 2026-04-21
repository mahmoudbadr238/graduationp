"""
GPU Service Bridge - QProcess-based GPU telemetry manager
Spawns subprocess worker, handles heartbeat watchdog, circuit breaker
Enhanced with history tracking for charts (MSI Afterburner style)
"""

import json
import logging
import sys
import time
from collections import deque
from typing import Any

from PySide6.QtCore import Property, QObject, QProcess, QTimer, Signal, Slot

from backend.runtime import is_frozen, resolve_app_path

logger = logging.getLogger(__name__)

# History configuration
HISTORY_MAX_POINTS = 60  # 60 data points for charts (1 minute at 1s interval)

HISTORY_FIELDS = {
    "usage": "usage",
    "memUsage": "memPercent",
    "temperature": "tempC",
    "power": "powerW",
    "powerPercent": "powerPercent",
    "clockCore": "clockMHz",
    "clockMem": "clockMemMHz",
    "fanSpeed": "fanPercent",
    "memController": "memControllerUtil",
}

METRIC_STATUS_OK = "ok"


class GPUServiceBridge(QObject):
    """
    QProcess-based GPU telemetry service

    Features:
    - Subprocess isolation (never blocks UI)
    - Heartbeat watchdog (6s timeout)
    - Circuit breaker (3 fails in 60s = disabled)
    - On-demand start/stop
    - History tracking for real-time charts
    """

    # Signals
    metricsUpdated = Signal()
    statusChanged = Signal(str)  # stopped, starting, running, degraded, breaker-open
    updateIntervalChanged = Signal(int)
    gpuCountChanged = Signal(int)
    metricsChanged = Signal()  # Emitted when GPU metrics are updated
    historyUpdated = Signal()  # Emitted when history data is updated
    error = Signal(str, str)  # title, message

    def __init__(self, parent=None):
        super().__init__(parent)

        # Process management
        self._proc = QProcess(self)
        self._configure_worker_process()
        self._proc.readyReadStandardOutput.connect(self._on_stdout)
        self._proc.readyReadStandardError.connect(self._on_stderr)
        self._proc.started.connect(self._on_started)
        self._proc.finished.connect(self._on_finished)
        self._proc.errorOccurred.connect(self._on_error)

        # Heartbeat watchdog (60s timeout - WMI queries can be very slow on some systems)
        self._hb_timer = QTimer(self)
        self._hb_timer.setInterval(60000)  # Increased from 30s to 60s for WMI stability
        self._hb_timer.timeout.connect(self._on_missed_heartbeat)

        # Circuit breaker (track failures)
        self._failures: list[float] = []
        self._breaker_open = False
        self._last_restart_time = 0.0  # Track last restart to prevent tight loops
        self._min_restart_cooldown = 5.0  # Minimum seconds between restarts

        # State
        self._status = "stopped"
        self._interval = 2000  # Default 2s
        self._gpu_count = 0
        self._metrics_cache: list[dict[str, Any]] = []

        # History tracking for charts (per GPU)
        # Each GPU has history for: usage, temp, memory, power, clockCore, clockMem
        self._history: dict[int, dict[str, deque]] = {}

        logger.info("GPU Service Bridge initialized")

    def _configure_worker_process(self, interval_ms: int | None = None) -> bool:
        """Configure the subprocess used for GPU telemetry."""
        if is_frozen():
            worker_path = resolve_app_path("sentinel_gpu_worker.exe")
            if not worker_path.exists():
                logger.warning("GPU worker executable not found: %s", worker_path)
                return False

            args: list[str] = []
            if interval_ms is not None:
                args.append(str(interval_ms))

            self._proc.setProgram(str(worker_path))
            self._proc.setArguments(args)
            return True

        # Platform-aware worker module
        from backend.platform import IS_LINUX
        if IS_LINUX:
            worker_module = "backend.platform.linux.telemetry_worker"
        else:
            worker_module = "backend.engines.gpu.telemetry_worker"

        args = ["-u", "-m", worker_module]
        if interval_ms is not None:
            args.append(str(interval_ms))

        self._proc.setProgram(sys.executable)
        self._proc.setArguments(args)
        return True

    def _init_gpu_history(self, gpu_id: int):
        """Initialize history tracking for a GPU"""
        if gpu_id not in self._history:
            self._history[gpu_id] = {
                "usage": deque(maxlen=HISTORY_MAX_POINTS),
                "memUsage": deque(maxlen=HISTORY_MAX_POINTS),
                "temperature": deque(maxlen=HISTORY_MAX_POINTS),
                "power": deque(maxlen=HISTORY_MAX_POINTS),
                "powerPercent": deque(maxlen=HISTORY_MAX_POINTS),
                "clockCore": deque(maxlen=HISTORY_MAX_POINTS),
                "clockMem": deque(maxlen=HISTORY_MAX_POINTS),
                "fanSpeed": deque(maxlen=HISTORY_MAX_POINTS),
                "memController": deque(maxlen=HISTORY_MAX_POINTS),
            }

    def _update_history(self, metrics: list[dict[str, Any]]):
        """Update history from current metrics"""
        for gpu in metrics:
            gpu_id = gpu.get("id", 0)
            self._init_gpu_history(gpu_id)

            hist = self._history[gpu_id]
            for history_key, metric_key in HISTORY_FIELDS.items():
                sample = self._history_sample(gpu, metric_key)
                if sample is not None:
                    hist[history_key].append(sample)
                elif hist[history_key]:
                    # Keep the last known good value instead of injecting a fake zero
                    # when a backend temporarily loses access to a sensor.
                    hist[history_key].append(hist[history_key][-1])

        self.historyUpdated.emit()

    def _history_sample(self, gpu: dict[str, Any], metric_key: str) -> float | None:
        """Return a numeric history sample only when a metric is actually available."""
        metric_status = gpu.get("metricStatus") or {}
        status = metric_status.get(metric_key)
        if status not in (None, METRIC_STATUS_OK):
            return None

        value = gpu.get(metric_key)
        if value is None:
            return None

        try:
            number = float(value)
        except (TypeError, ValueError):
            return None

        if number != number:  # NaN guard
            return None
        return number

    # Properties
    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(int, notify=gpuCountChanged)
    def gpuCount(self) -> int:
        return self._gpu_count

    @Property("QVariantList", notify=metricsChanged)
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

        if not self._configure_worker_process(interval_ms):
            self._set_status("stopped")
            self.error.emit(
                "GPU Monitoring Unavailable",
                "sentinel_gpu_worker.exe is missing from the application folder.",
            )
            return

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
            "usage": None,
            "memUsedMB": None,
            "memTotalMB": None,
            "memPercent": None,
            "tempC": None,
            "powerW": None,
            "powerLimitW": None,
            "clockMHz": None,
            "fanPercent": None,
            "provider": "none",
            "providerStatus": "unavailable",
            "providerDetail": "No GPU telemetry is available.",
            "metricStatus": {
                "usage": "unavailable",
                "memUsedMB": "unavailable",
                "memTotalMB": "unavailable",
                "memPercent": "unavailable",
                "tempC": "unavailable",
                "powerW": "unavailable",
                "powerLimitW": "unavailable",
                "clockMHz": "unavailable",
                "fanPercent": "unavailable",
            },
            "metricMessages": {},
        }

    @Slot(result=list)
    def getAllMetrics(self) -> list[dict[str, Any]]:
        """Get all GPU metrics"""
        return self._metrics_cache.copy()

    @Slot(int, str, result=list)
    def getHistory(self, gpu_id: int, metric_type: str) -> list[float]:
        """
        Get history data for a specific GPU and metric type.

        Args:
            gpu_id: GPU index
            metric_type: One of 'usage', 'memUsage', 'temperature', 'power',
                        'powerPercent', 'clockCore', 'clockMem', 'fanSpeed', 'memController'

        Returns:
            List of historical values
        """
        if gpu_id in self._history and metric_type in self._history[gpu_id]:
            return list(self._history[gpu_id][metric_type])
        return []

    @Slot(int, result="QVariantMap")
    def getAllHistory(self, gpu_id: int) -> dict[str, list]:
        """
        Get all history data for a specific GPU.

        Args:
            gpu_id: GPU index

        Returns:
            Dictionary with all metric histories
        """
        if gpu_id in self._history:
            return {key: list(val) for key, val in self._history[gpu_id].items()}
        return {}

    @Slot()
    def clearHistory(self):
        """Clear all history data"""
        self._history.clear()
        self.historyUpdated.emit()

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

                        # Debug: Log received metrics for AMD GPUs
                        for g in gpus:
                            if g.get("vendor") == "AMD":
                                logger.debug(
                                    f"AMD GPU received: {g.get('name')}, usage={g.get('usage')}, mem={g.get('memUsedMB')}/{g.get('memTotalMB')}MB, driver={g.get('driverVersion')}"
                                )

                        new_count = len(gpus)
                        if new_count != self._gpu_count:
                            self._gpu_count = new_count
                            self.gpuCountChanged.emit(new_count)

                        # Update history for charts
                        self._update_history(gpus)

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
            # Check cooldown to prevent tight restart loops
            time_since_last_restart = time.time() - self._last_restart_time
            if time_since_last_restart < self._min_restart_cooldown:
                # Immediate failure - likely a fundamental issue, open circuit breaker
                logger.error("GPU worker failed immediately after restart - disabling")
                self._breaker_open = True
                self._set_status("breaker-open")
                self.error.emit(
                    "GPU Telemetry Disabled",
                    "GPU monitoring is unavailable on this system.",
                )
                return

            # Auto-restart with cooldown
            restart_delay = max(1000, int(self._min_restart_cooldown * 1000))
            logger.info(
                f"Restarting worker in {restart_delay}ms (failure {len(self._failures)}/3)"
            )
            self._set_status("restarting")
            self._last_restart_time = time.time()
            QTimer.singleShot(restart_delay, lambda: self.start(self._interval))

    def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up GPU service")
        self._history.clear()
        self.stop()


# Singleton
_gpu_service_instance = None


def get_gpu_service() -> GPUServiceBridge:
    """Get or create GPU service singleton"""
    global _gpu_service_instance
    if _gpu_service_instance is None:
        _gpu_service_instance = GPUServiceBridge()
    return _gpu_service_instance
