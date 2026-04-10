"""
Resource Monitor Worker — Sentinel EDR.

Continuously monitors CPU, RAM, and Network I/O using ``psutil`` and
emits live statistics to the QML dashboard via PySide6 signals.

Includes configurable alert thresholds with cooldown to prevent
notification spam, and integrates with ``QSystemTrayIcon`` for native
Windows Action Center toasts.
"""

from __future__ import annotations

import logging
import time
import threading
from typing import Any

import psutil
from PySide6.QtCore import QObject, QThread, Signal, Slot

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────────────────
# Configuration
# ───────────────────────────────────────────────────────────────────

POLL_INTERVAL_SECS = 2.0       # How often to sample metrics
ALERT_COOLDOWN_SECS = 60.0     # Minimum seconds between repeated alerts
CPU_ALERT_THRESHOLD = 90.0     # CPU % to trigger alert
RAM_ALERT_THRESHOLD = 90.0     # RAM % to trigger alert
NET_SPIKE_MBPS = 100.0         # Network spike threshold (MB/s)


# ───────────────────────────────────────────────────────────────────
# Resource Monitor Worker (QThread)
# ───────────────────────────────────────────────────────────────────


class ResourceMonitorWorker(QThread):
    """Background thread that samples system resource usage.

    Signals
    -------
    stats_updated(dict)
        Emitted every ``POLL_INTERVAL_SECS`` with live metrics:
        ``cpu_percent``, ``ram_percent``, ``ram_used_gb``,
        ``ram_total_gb``, ``net_sent_bps``, ``net_recv_bps``,
        ``net_sent_mbps``, ``net_recv_mbps``, ``disk_percent``.
    alert_triggered(str, str)
        ``(title, message)`` — emitted when a threshold is breached
        (with cooldown to avoid spamming).
    """

    stats_updated = Signal(dict)
    alert_triggered = Signal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._running = False

        # Last alert timestamps (for cooldown)
        self._last_cpu_alert = 0.0
        self._last_ram_alert = 0.0
        self._last_net_alert = 0.0

        # Previous network counters (for delta calculation)
        self._prev_net: psutil._common.snetio | None = None
        self._prev_net_time: float = 0.0

    def stop(self) -> None:
        """Request the worker to stop gracefully."""
        self._running = False

    def run(self) -> None:  # noqa: D401
        """Main monitoring loop (runs in background thread)."""
        self._running = True
        logger.info("ResourceMonitor: started (interval=%.1fs)", POLL_INTERVAL_SECS)

        # Initialise network baseline
        try:
            self._prev_net = psutil.net_io_counters()
            self._prev_net_time = time.monotonic()
        except Exception:
            self._prev_net = None

        while self._running:
            try:
                stats = self._collect_stats()
                self.stats_updated.emit(stats)
                self._check_alerts(stats)
            except Exception as exc:
                logger.debug("ResourceMonitor: collection error: %s", exc)

            # Sleep in small increments so stop() is responsive
            end_time = time.monotonic() + POLL_INTERVAL_SECS
            while self._running and time.monotonic() < end_time:
                time.sleep(0.25)

        logger.info("ResourceMonitor: stopped")

    # ─────────────────────────────────────────────────────────────
    # Data collection
    # ─────────────────────────────────────────────────────────────

    def _collect_stats(self) -> dict[str, Any]:
        """Sample all resource metrics."""
        # CPU (non-blocking, averaged over interval)
        cpu = psutil.cpu_percent(interval=0)

        # RAM
        mem = psutil.virtual_memory()
        ram_percent = mem.percent
        ram_used_gb = round(mem.used / (1024 ** 3), 2)
        ram_total_gb = round(mem.total / (1024 ** 3), 2)

        # Network I/O delta
        net_sent_bps = 0.0
        net_recv_bps = 0.0
        try:
            current_net = psutil.net_io_counters()
            now = time.monotonic()
            if self._prev_net and self._prev_net_time:
                dt = now - self._prev_net_time
                if dt > 0:
                    net_sent_bps = (current_net.bytes_sent - self._prev_net.bytes_sent) / dt
                    net_recv_bps = (current_net.bytes_recv - self._prev_net.bytes_recv) / dt
            self._prev_net = current_net
            self._prev_net_time = now
        except Exception:
            pass

        net_sent_mbps = round(net_sent_bps / (1024 * 1024), 2)
        net_recv_mbps = round(net_recv_bps / (1024 * 1024), 2)

        # Disk
        try:
            disk = psutil.disk_usage("/")
            disk_percent = disk.percent
        except Exception:
            disk_percent = 0.0

        return {
            "cpu_percent": round(cpu, 1),
            "ram_percent": round(ram_percent, 1),
            "ram_used_gb": ram_used_gb,
            "ram_total_gb": ram_total_gb,
            "net_sent_bps": round(net_sent_bps),
            "net_recv_bps": round(net_recv_bps),
            "net_sent_mbps": net_sent_mbps,
            "net_recv_mbps": net_recv_mbps,
            "disk_percent": round(disk_percent, 1),
        }

    # ─────────────────────────────────────────────────────────────
    # Alert logic (with cooldown)
    # ─────────────────────────────────────────────────────────────

    def _check_alerts(self, stats: dict[str, Any]) -> None:
        """Check thresholds and emit alerts with cooldown."""
        now = time.monotonic()

        # CPU alert
        if stats["cpu_percent"] >= CPU_ALERT_THRESHOLD:
            if now - self._last_cpu_alert > ALERT_COOLDOWN_SECS:
                self._last_cpu_alert = now
                self.alert_triggered.emit(
                    "⚠️ High CPU Usage",
                    f"CPU usage is at {stats['cpu_percent']}%. "
                    "A process may be consuming excessive resources.",
                )

        # RAM alert
        if stats["ram_percent"] >= RAM_ALERT_THRESHOLD:
            if now - self._last_ram_alert > ALERT_COOLDOWN_SECS:
                self._last_ram_alert = now
                self.alert_triggered.emit(
                    "⚠️ High Memory Usage",
                    f"RAM usage is at {stats['ram_percent']}% "
                    f"({stats['ram_used_gb']:.1f} / {stats['ram_total_gb']:.1f} GB). "
                    "Consider closing unused applications.",
                )

        # Network spike alert
        total_mbps = stats["net_sent_mbps"] + stats["net_recv_mbps"]
        if total_mbps >= NET_SPIKE_MBPS:
            if now - self._last_net_alert > ALERT_COOLDOWN_SECS:
                self._last_net_alert = now
                self.alert_triggered.emit(
                    "⚠️ Network Spike Detected",
                    f"Network throughput: {total_mbps:.1f} MB/s "
                    f"(↑{stats['net_sent_mbps']:.1f} ↓{stats['net_recv_mbps']:.1f} MB/s). "
                    "Possible data exfiltration or large transfer in progress.",
                )


# ───────────────────────────────────────────────────────────────────
# Resource Monitor Bridge (QObject — exposed to QML)
# ───────────────────────────────────────────────────────────────────


class ResourceMonitorBridge(QObject):
    """PySide6 bridge exposing live resource stats to QML.

    Properties (readable from QML)
    ------------------------------
    cpuPercent, ramPercent, ramUsedGb, ramTotalGb,
    netSentMbps, netRecvMbps, diskPercent, isRunning.

    Signals
    -------
    statsChanged()
        Emitted when any stat property changes.
    alertTriggered(str, str)
        ``(title, message)`` forwarded from the worker.
    """

    statsChanged = Signal()
    alertTriggered = Signal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._worker: ResourceMonitorWorker | None = None
        self._lock = threading.Lock()

        # Current values
        self._cpu = 0.0
        self._ram = 0.0
        self._ram_used = 0.0
        self._ram_total = 0.0
        self._net_sent = 0.0
        self._net_recv = 0.0
        self._disk = 0.0
        self._running = False

        # Alert log
        self._alert_log: list[str] = []

    # ── QML-readable properties (via getter slots) ──

    @Slot(result=float)
    def getCpuPercent(self) -> float:
        return self._cpu

    @Slot(result=float)
    def getRamPercent(self) -> float:
        return self._ram

    @Slot(result=float)
    def getRamUsedGb(self) -> float:
        return self._ram_used

    @Slot(result=float)
    def getRamTotalGb(self) -> float:
        return self._ram_total

    @Slot(result=float)
    def getNetSentMbps(self) -> float:
        return self._net_sent

    @Slot(result=float)
    def getNetRecvMbps(self) -> float:
        return self._net_recv

    @Slot(result=float)
    def getDiskPercent(self) -> float:
        return self._disk

    @Slot(result=bool)
    def getIsRunning(self) -> bool:
        return self._running

    @Slot(result=str)
    def getAlertLog(self) -> str:
        return "\n".join(self._alert_log) if self._alert_log else ""

    # ── Control slots ──

    @Slot()
    def start(self) -> None:
        """Start the resource monitor."""
        with self._lock:
            if self._running:
                return
            self._running = True

        self._worker = ResourceMonitorWorker(parent=self)
        self._worker.stats_updated.connect(self._on_stats)
        self._worker.alert_triggered.connect(self._on_alert)
        self._worker.start()
        self.statsChanged.emit()
        logger.info("ResourceMonitorBridge: started")

    @Slot()
    def stop(self) -> None:
        """Stop the resource monitor."""
        with self._lock:
            if not self._running:
                return
            self._running = False

        if self._worker:
            self._worker.stop()
            self._worker.wait(5000)
            self._worker.deleteLater()
            self._worker = None

        self.statsChanged.emit()
        logger.info("ResourceMonitorBridge: stopped")

    # ── Private callbacks ──

    def _on_stats(self, stats: dict) -> None:
        """Update internal state from worker."""
        self._cpu = stats.get("cpu_percent", 0.0)
        self._ram = stats.get("ram_percent", 0.0)
        self._ram_used = stats.get("ram_used_gb", 0.0)
        self._ram_total = stats.get("ram_total_gb", 0.0)
        self._net_sent = stats.get("net_sent_mbps", 0.0)
        self._net_recv = stats.get("net_recv_mbps", 0.0)
        self._disk = stats.get("disk_percent", 0.0)
        self.statsChanged.emit()

    def _on_alert(self, title: str, message: str) -> None:
        """Forward alert to UI and log it."""
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._alert_log.append(f"[{ts}] {title}: {message}")
        # Keep last 100 alerts
        if len(self._alert_log) > 100:
            self._alert_log = self._alert_log[-100:]
        self.alertTriggered.emit(title, message)


# ───────────────────────────────────────────────────────────────────
# Module-level convenience
# ───────────────────────────────────────────────────────────────────

_bridge: ResourceMonitorBridge | None = None
_bridge_lock = threading.Lock()


def get_resource_monitor_bridge() -> ResourceMonitorBridge:
    """Return the singleton ``ResourceMonitorBridge`` instance."""
    global _bridge
    with _bridge_lock:
        if _bridge is None:
            _bridge = ResourceMonitorBridge()
        return _bridge
