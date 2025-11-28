"""
GPU Backend Bridge - Qt/QML Integration for GPU Manager
Provides live GPU metrics to QML UI with automatic updates
Includes watchdog for hang detection and error recovery
"""

import logging
import time
from typing import Optional

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtQml import QmlElement

from app.utils.gpu_manager import GPUManager, GPUMetrics

# QML Type Registration
QML_IMPORT_NAME = "Sentinel.GPU"
QML_IMPORT_MAJOR_VERSION = 1

logger = logging.getLogger(__name__)

# Watchdog configuration
METRICS_UPDATE_TIMEOUT = 5000  # 5 seconds max per update
WATCHDOG_CHECK_INTERVAL = 2000  # Check every 2 seconds
MAX_CONSECUTIVE_FAILURES = 3  # Disable if 3 failures in a row


@QmlElement
class GPUBackend(QObject):
    """
    GPU Backend for QML Integration
    Exposes GPU metrics and controls to QML UI with error recovery
    Features watchdog for hang detection and auto-recovery
    """

    # Signals for QML
    gpuCountChanged = Signal()
    metricsUpdated = Signal()
    safetyWarning = Signal(str, str)  # gpu_name, warning_message
    statusChanged = Signal(str)  # "ok", "updating", "error", "disabled"

    def __init__(self, parent=None):
        super().__init__(parent)

        # Initialize GPU Manager in a lazy way
        self._manager: Optional[GPUManager] = None
        self._gpu_count = 0
        self._update_interval = 3000  # 3 seconds

        # Metrics cache
        self._metrics_cache: list[dict] = []

        # Watchdog state
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_metrics_safe)
        self._update_timer.setSingleShot(False)

        self._watchdog_timer = QTimer(self)
        self._watchdog_timer.timeout.connect(self._check_watchdog)
        self._watchdog_timer.setSingleShot(False)

        self._last_update_time = 0  # When last update started
        self._last_success_time = 0  # When last update succeeded
        self._consecutive_failures = 0
        self._is_updating = False
        self._status = "initializing"

        # Initialize GPU manager asynchronously
        QTimer.singleShot(500, self._lazy_init)

        logger.info("GPU Backend created (lazy init scheduled)")

    def _lazy_init(self):
        """Initialize GPU manager after UI has loaded"""
        try:
            logger.info("Starting GPU manager initialization...")
            self._manager = GPUManager(auto_install=True)
            self._gpu_count = len(self._manager.list_gpus())

            # Start timers
            self._update_timer.start(self._update_interval)
            self._watchdog_timer.start(WATCHDOG_CHECK_INTERVAL)

            # Initial update
            self._update_metrics_safe()

            # Emit signal that GPUs are ready
            self.gpuCountChanged.emit()
            self._set_status("ok")

            logger.info(f"GPU Backend initialized: {self._gpu_count} GPU(s)")
        except Exception as e:
            logger.exception(f"Failed to initialize GPU manager: {e}")
            self._manager = None
            self._gpu_count = 0
            self._set_status("error")

    def _set_status(self, status: str):
        """Update status and emit signal"""
        if status != self._status:
            self._status = status
            self.statusChanged.emit(status)
            logger.debug(f"GPU Backend status: {status}")

    @Property(int, notify=gpuCountChanged)
    def gpuCount(self) -> int:
        """Number of detected GPUs"""
        return self._gpu_count

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        """Backend status: ok, updating, error, disabled"""
        return self._status

    @Slot(result=int)
    def updateInterval(self) -> int:
        """Get update interval in milliseconds (read-only from QML)"""
        return self._update_interval

    @Slot(int)
    def setUpdateInterval(self, value: int):
        """Set update interval (call from QML)"""
        if value != self._update_interval and value >= 500:
            self._update_interval = value
            if self._update_timer.isActive():
                self._update_timer.setInterval(value)
            logger.info(f"GPU update interval set to {value}ms")

    @Slot(result=list)
    def getGPUList(self) -> list[dict]:
        """
        Get list of all GPUs with basic info

        Returns:
            List of GPU dictionaries for QML
        """
        if not self._manager:
            return []
        try:
            return self._manager.list_gpus()
        except Exception as e:
            logger.error(f"Error getting GPU list: {e}")
            return []

    @Slot(int, result="QVariantMap")
    def getGPUMetrics(self, gpu_id: int) -> dict:
        """
        Get comprehensive metrics for a specific GPU

        Args:
            gpu_id: GPU index

        Returns:
            Dictionary with GPU metrics for QML
        """
        if not self._manager:
            return {}

        if gpu_id < len(self._metrics_cache):
            return self._metrics_cache[gpu_id]

        try:
            metrics = self._manager.get_gpu_metrics(gpu_id)
            if not metrics:
                return {}
            return self._metrics_to_dict(metrics)
        except Exception as e:
            logger.warning(f"Error getting GPU metrics for {gpu_id}: {e}")
            return {}

    @Slot(result=list)
    def getAllMetrics(self) -> list[dict]:
        """
        Get metrics for all GPUs

        Returns:
            List of GPU metrics dictionaries
        """
        return self._metrics_cache.copy()

    @Slot(int, result=float)
    def getUsage(self, gpu_id: int) -> float:
        """Get GPU usage percentage"""
        if not self._manager:
            return 0.0
        try:
            return self._manager.get_gpu_usage(gpu_id)
        except Exception as e:
            logger.warning(f"Error getting GPU usage: {e}")
            return 0.0

    @Slot(int, result=int)
    def getTemperature(self, gpu_id: int) -> int:
        """Get GPU temperature in Celsius"""
        if not self._manager:
            return 0
        try:
            return self._manager.get_temperature(gpu_id)
        except Exception as e:
            logger.warning(f"Error getting GPU temperature: {e}")
            return 0

    @Slot(int, result="QVariantMap")
    def getVRAMUsage(self, gpu_id: int) -> dict:
        """
        Get VRAM usage with error handling

        Returns:
            {used: int, total: int, percent: float}
        """
        try:
            used, total, percent = self._manager.get_vram_usage(gpu_id)
            return {"used": used, "total": total, "percent": round(percent, 1)}
        except Exception as e:
            logger.warning(f"Error getting VRAM usage: {e}")
            return {"used": 0, "total": 0, "percent": 0.0}

    @Slot(int, result="QVariantMap")
    def getPowerUsage(self, gpu_id: int) -> dict:
        """
        Get power usage with error handling

        Returns:
            {current: float, limit: float}
        """
        try:
            current, limit = self._manager.get_power_usage(gpu_id)
            return {"current": round(current, 1), "limit": round(limit, 1)}
        except Exception as e:
            logger.warning(f"Error getting power usage: {e}")
            return {"current": 0.0, "limit": 0.0}

    @Slot(int, result="QVariantMap")
    def getFanSpeed(self, gpu_id: int) -> dict:
        """
        Get fan speed with error handling

        Returns:
            {percent: int, rpm: int}
        """
        try:
            percent, rpm = self._manager.get_fan_speed(gpu_id)
            return {"percent": percent, "rpm": rpm}
        except Exception as e:
            logger.warning(f"Error getting fan speed: {e}")
            return {"percent": 0, "rpm": 0}

    @Slot(int, result="QVariantMap")
    def getGPUMetrics(self, gpu_id: int) -> dict:
        """
        Get comprehensive metrics for a specific GPU

        Args:
            gpu_id: GPU index

        Returns:
            Dictionary with GPU metrics for QML
        """
        if not self._manager:
            return {}

        if gpu_id < len(self._metrics_cache):
            return self._metrics_cache[gpu_id]

        metrics = self._manager.get_gpu_metrics(gpu_id)
        if not metrics:
            return {}

        return self._metrics_to_dict(metrics)

    @Slot(result=list)
    def getAllMetrics(self) -> list[dict]:
        """
        Get metrics for all GPUs

        Returns:
            List of GPU metrics dictionaries
        """
        return self._metrics_cache.copy()

    @Slot(int, result=float)
    def getUsage(self, gpu_id: int) -> float:
        """Get GPU usage percentage"""
        if not self._manager:
            return 0.0
        return self._manager.get_gpu_usage(gpu_id)

    @Slot(int, result=int)
    def getTemperature(self, gpu_id: int) -> int:
        """Get GPU temperature in Celsius"""
        if not self._manager:
            return 0
        return self._manager.get_temperature(gpu_id)

    @Slot(int, result="QVariantMap")
    def getVRAMUsage(self, gpu_id: int) -> dict:
        """
        Get VRAM usage

        Returns:
            {used: int, total: int, percent: float}
        """
        used, total, percent = self._manager.get_vram_usage(gpu_id)
        return {"used": used, "total": total, "percent": round(percent, 1)}

    @Slot(int, result="QVariantMap")
    def getPowerUsage(self, gpu_id: int) -> dict:
        """
        Get power usage

        Returns:
            {current: float, limit: float}
        """
        current, limit = self._manager.get_power_usage(gpu_id)
        return {"current": round(current, 1), "limit": round(limit, 1)}

    @Slot(int, result="QVariantMap")
    def getFanSpeed(self, gpu_id: int) -> dict:
        """
        Get fan speed

        Returns:
            {percent: int, rpm: int}
        """
        percent, rpm = self._manager.get_fan_speed(gpu_id)
        return {"percent": percent, "rpm": rpm}

    @Slot(int, int, result=bool)
    def setFanSpeed(self, gpu_id: int, percent: int) -> bool:
        """
        Set GPU fan speed (requires admin) with error handling

        Args:
            gpu_id: GPU index
            percent: Fan speed percentage (0-100)

        Returns:
            True if successful
        """
        if not 0 <= percent <= 100:
            logger.error(f"Invalid fan speed: {percent}%")
            return False

        if not self._manager:
            return False

        try:
            success = self._manager.set_fan_speed(gpu_id, percent)
            if success:
                logger.info(f"GPU {gpu_id} fan speed set to {percent}%")
            else:
                logger.warning(f"Failed to set GPU {gpu_id} fan speed (requires admin)")
            return success
        except Exception as e:
            logger.error(f"Error setting fan speed: {e}")
            return False

    @Slot(int, int, result=bool)
    def setPowerLimit(self, gpu_id: int, watts: int) -> bool:
        """
        Set GPU power limit (requires admin) with error handling

        Args:
            gpu_id: GPU index
            watts: Power limit in watts

        Returns:
            True if successful
        """
        if watts <= 0:
            logger.error(f"Invalid power limit: {watts}W")
            return False

        if not self._manager:
            return False

        try:
            success = self._manager.set_power_limit(gpu_id, watts)
            if success:
                logger.info(f"GPU {gpu_id} power limit set to {watts}W")
            else:
                logger.warning(f"Failed to set GPU {gpu_id} power limit (requires admin)")
            return success
        except Exception as e:
            logger.error(f"Error setting power limit: {e}")
            return False

    @Slot(result=list)
    def getSafetyWarnings(self) -> list[str]:
        """Get all active safety warnings"""
        if not self._manager:
            return []
        try:
            return self._manager.get_safety_warnings()
        except Exception as e:
            logger.warning(f"Error getting safety warnings: {e}")
            return []

    @Slot()
    def clearSafetyWarnings(self):
        """Clear safety warning history"""
        if self._manager:
            try:
                self._manager.clear_safety_warnings()
            except Exception as e:
                logger.warning(f"Error clearing safety warnings: {e}")

    @Slot()
    def refreshGPUs(self):
        """Force refresh GPU list (re-detect GPUs)"""
        if not self._manager:
            return

        try:
            old_count = self._gpu_count
            self._manager._discover_gpus()
            self._gpu_count = len(self._manager.list_gpus())

            if old_count != self._gpu_count:
                self.gpuCountChanged.emit()
                logger.info(f"GPU count changed: {old_count} → {self._gpu_count}")

            self._update_metrics_safe()
        except Exception as e:
            logger.error(f"Error refreshing GPUs: {e}")

    @Slot()
    def startMonitoring(self):
        """Start automatic monitoring"""
        if not self._update_timer.isActive():
            self._update_timer.start()
            self._watchdog_timer.start()
            logger.info("GPU monitoring started")
            self._set_status("ok")

    @Slot()
    def stopMonitoring(self):
        """Stop automatic monitoring"""
        if self._update_timer.isActive():
            self._update_timer.stop()
        if self._watchdog_timer.isActive():
            self._watchdog_timer.stop()
        logger.info("GPU monitoring stopped")

    def _update_metrics_safe(self):
        """Update metrics with timeout protection (watchdog-safe)"""
        # Check if already updating
        if self._is_updating:
            logger.debug("Update already in progress, skipping")
            return

        try:
            self._is_updating = True
            self._last_update_time = time.time() * 1000  # ms
            self._set_status("updating")
            
            self._update_metrics()
            
            self._last_success_time = time.time() * 1000  # ms
            self._consecutive_failures = 0
            self._set_status("ok")
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
            self._consecutive_failures += 1
            
            if self._consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.error(f"GPU backend disabled after {MAX_CONSECUTIVE_FAILURES} failures")
                self._set_status("disabled")
                self.stopMonitoring()
            else:
                self._set_status("error")
        finally:
            self._is_updating = False

    def _check_watchdog(self):
        """Check if metrics update is hung (watchdog)"""
        if not self._is_updating:
            return

        elapsed = (time.time() * 1000) - self._last_update_time
        if elapsed > METRICS_UPDATE_TIMEOUT:
            logger.error(f"GPU metrics update timeout ({elapsed:.0f}ms > {METRICS_UPDATE_TIMEOUT}ms)")
            self._is_updating = False
            self._consecutive_failures += 1
            self._set_status("error")
            
            # Force recovery: stop and restart monitoring
            if self._consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.error("GPU backend disabled after watchdog timeout")
                self._set_status("disabled")
                self.stopMonitoring()

    def _update_metrics(self):
        """Update metrics cache and emit signal"""
        if not self._manager:
            return

        self._metrics_cache.clear()

        try:
            all_metrics = self._manager.get_all_metrics()
            for metrics in all_metrics:
                self._metrics_cache.append(self._metrics_to_dict(metrics))

            # Check for new safety warnings
            try:
                warnings = self._manager.get_safety_warnings()
                if warnings:
                    # Emit most recent warning
                    last_warning = warnings[-1]
                    # Extract GPU name and warning
                    if "GPU" in last_warning:
                        parts = last_warning.split(")")
                        if len(parts) >= 2:
                            gpu_info = parts[0] + ")"
                            warning_msg = parts[1].strip()
                            self.safetyWarning.emit(gpu_info, warning_msg)
            except Exception as e:
                logger.warning(f"Error processing safety warnings: {e}")

            self.metricsUpdated.emit()
        except Exception as e:
            logger.error(f"Error updating all metrics: {e}")
            raise

    def _metrics_to_dict(self, metrics: GPUMetrics) -> dict:
        """Convert GPUMetrics to QML-friendly dictionary"""
        return {
            "id": metrics.gpu_id,
            "name": metrics.name,
            "vendor": metrics.vendor.value,
            "status": metrics.status.value,
            "usage": round(metrics.usage_percent, 1),
            "memoryUsed": metrics.memory_used_mb,
            "memoryTotal": metrics.memory_total_mb,
            "memoryPercent": round(metrics.memory_percent, 1),
            "temperature": metrics.temperature_c,
            "powerUsage": round(metrics.power_usage_w, 1),
            "powerLimit": round(metrics.power_limit_w, 1),
            "fanSpeedPercent": metrics.fan_speed_percent,
            "fanSpeedRPM": metrics.fan_speed_rpm,
            "clockGraphics": metrics.clock_graphics_mhz,
            "clockMemory": metrics.clock_memory_mhz,
            "driver": metrics.driver_version,
            "pciBus": metrics.pci_bus_id,
            "supportsFanControl": metrics.supports_fan_control,
            "supportsPowerLimit": metrics.supports_power_limit,
            # Temperature status for UI color coding
            "tempStatus": self._get_temp_status(metrics.temperature_c),
            # VRAM status for UI color coding
            "vramStatus": self._get_vram_status(metrics.memory_percent),
        }

    def _get_temp_status(self, temp: int) -> str:
        """Get temperature status for UI"""
        if temp == 0:
            return "unknown"
        if temp < 60:
            return "normal"
        if temp < 75:
            return "warm"
        if temp < 85:
            return "hot"
        return "critical"

    def _get_vram_status(self, percent: float) -> str:
        """Get VRAM usage status for UI"""
        if percent < 50:
            return "normal"
        if percent < 75:
            return "moderate"
        if percent < 90:
            return "high"
        return "critical"

    def cleanup(self):
        """Cleanup resources and stop monitoring"""
        # Stop all timers
        if self._update_timer.isActive():
            self._update_timer.stop()
        if self._watchdog_timer.isActive():
            self._watchdog_timer.stop()
        
        # Cleanup GPU manager
        if self._manager:
            try:
                self._manager.shutdown()
            except Exception as e:
                logger.warning(f"Error shutting down GPU manager: {e}")
            finally:
                self._manager = None

        # Clear cache
        self._metrics_cache.clear()
        
        logger.info("GPU Backend cleanup complete")


# Singleton instance for QML
_gpu_backend_instance = None


def get_gpu_backend() -> GPUBackend:
    """Get or create GPU backend singleton"""
    global _gpu_backend_instance
    if _gpu_backend_instance is None:
        _gpu_backend_instance = GPUBackend()
    return _gpu_backend_instance
