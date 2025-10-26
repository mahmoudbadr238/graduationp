"""
GPU Backend Bridge - Qt/QML Integration for GPU Manager
Provides live GPU metrics to QML UI with automatic updates
"""

from PySide6.QtCore import QObject, Signal, Slot, QTimer, Property
from PySide6.QtQml import QmlElement
from typing import List, Dict, Optional
import logging

from app.utils.gpu_manager import GPUManager, GPUMetrics

# QML Type Registration
QML_IMPORT_NAME = "Sentinel.GPU"
QML_IMPORT_MAJOR_VERSION = 1

logger = logging.getLogger(__name__)


@QmlElement
class GPUBackend(QObject):
    """
    GPU Backend for QML Integration
    Exposes GPU metrics and controls to QML UI
    """
    
    # Signals for QML
    gpuCountChanged = Signal()
    metricsUpdated = Signal()
    safetyWarning = Signal(str, str)  # gpu_name, warning_message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize GPU Manager in a lazy way
        self._manager = None
        self._gpu_count = 0
        self._update_interval = 3000  # 3 seconds (reduced from 2s to minimize lag)
        
        # Metrics cache
        self._metrics_cache: List[Dict] = []
        
        # Update timer - start later to avoid blocking UI load
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_metrics)
        self._timer.setSingleShot(False)
        
        # Initialize GPU manager asynchronously
        QTimer.singleShot(500, self._lazy_init)
        
        logger.info("GPU Backend created (lazy init scheduled)")
    
    def _lazy_init(self):
        """Initialize GPU manager after UI has loaded"""
        try:
            logger.info("Starting GPU manager initialization...")
            self._manager = GPUManager(auto_install=True)
            self._gpu_count = len(self._manager.list_gpus())
            
            # Start timer now
            self._timer.start(self._update_interval)
            
            # Initial update
            self._update_metrics()
            
            # Emit signal that GPUs are ready
            self.gpuCountChanged.emit()
            
            logger.info(f"GPU Backend initialized: {self._gpu_count} GPU(s)")
        except Exception as e:
            logger.error(f"Failed to initialize GPU manager: {e}")
            self._manager = None
            self._gpu_count = 0
    
    @Property(int, notify=gpuCountChanged)
    def gpuCount(self) -> int:
        """Number of detected GPUs"""
        return self._gpu_count

    @Slot(result=int)
    def updateInterval(self) -> int:
        """Get update interval in milliseconds (read-only from QML)"""
        return self._update_interval

    @Slot(int)
    def setUpdateInterval(self, value: int):
        """Set update interval (call from QML)"""
        if value != self._update_interval and value >= 500:
            self._update_interval = value
            if self._timer.isActive():
                self._timer.setInterval(value)
            logger.info(f"GPU update interval set to {value}ms")    @Slot(result=list)
    def getGPUList(self) -> List[Dict]:
        """
        Get list of all GPUs with basic info
        
        Returns:
            List of GPU dictionaries for QML
        """
        if not self._manager:
            return []
        return self._manager.list_gpus()
    
    @Slot(int, result='QVariantMap')
    def getGPUMetrics(self, gpu_id: int) -> Dict:
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
    def getAllMetrics(self) -> List[Dict]:
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
    
    @Slot(int, result='QVariantMap')
    def getVRAMUsage(self, gpu_id: int) -> Dict:
        """
        Get VRAM usage
        
        Returns:
            {used: int, total: int, percent: float}
        """
        used, total, percent = self._manager.get_vram_usage(gpu_id)
        return {
            "used": used,
            "total": total,
            "percent": round(percent, 1)
        }
    
    @Slot(int, result='QVariantMap')
    def getPowerUsage(self, gpu_id: int) -> Dict:
        """
        Get power usage
        
        Returns:
            {current: float, limit: float}
        """
        current, limit = self._manager.get_power_usage(gpu_id)
        return {
            "current": round(current, 1),
            "limit": round(limit, 1)
        }
    
    @Slot(int, result='QVariantMap')
    def getFanSpeed(self, gpu_id: int) -> Dict:
        """
        Get fan speed
        
        Returns:
            {percent: int, rpm: int}
        """
        percent, rpm = self._manager.get_fan_speed(gpu_id)
        return {
            "percent": percent,
            "rpm": rpm
        }
    
    @Slot(int, int, result=bool)
    def setFanSpeed(self, gpu_id: int, percent: int) -> bool:
        """
        Set GPU fan speed (requires admin)
        
        Args:
            gpu_id: GPU index
            percent: Fan speed percentage (0-100)
        
        Returns:
            True if successful
        """
        if not 0 <= percent <= 100:
            logger.error(f"Invalid fan speed: {percent}%")
            return False
        
        success = self._manager.set_fan_speed(gpu_id, percent)
        if success:
            logger.info(f"GPU {gpu_id} fan speed set to {percent}%")
        else:
            logger.warning(f"Failed to set GPU {gpu_id} fan speed (requires admin)")
        
        return success
    
    @Slot(int, int, result=bool)
    def setPowerLimit(self, gpu_id: int, watts: int) -> bool:
        """
        Set GPU power limit (requires admin)
        
        Args:
            gpu_id: GPU index
            watts: Power limit in watts
        
        Returns:
            True if successful
        """
        if watts <= 0:
            logger.error(f"Invalid power limit: {watts}W")
            return False
        
        success = self._manager.set_power_limit(gpu_id, watts)
        if success:
            logger.info(f"GPU {gpu_id} power limit set to {watts}W")
        else:
            logger.warning(f"Failed to set GPU {gpu_id} power limit (requires admin)")
        
        return success
    
    @Slot(result=list)
    def getSafetyWarnings(self) -> List[str]:
        """Get all active safety warnings"""
        if not self._manager:
            return []
        return self._manager.get_safety_warnings()
    
    @Slot()
    def clearSafetyWarnings(self):
        """Clear safety warning history"""
        if self._manager:
            self._manager.clear_safety_warnings()
    
    @Slot()
    def refreshGPUs(self):
        """Force refresh GPU list (re-detect GPUs)"""
        if not self._manager:
            return
            
        old_count = self._gpu_count
        self._manager._discover_gpus()
        self._gpu_count = len(self._manager.list_gpus())
        
        if old_count != self._gpu_count:
            self.gpuCountChanged.emit()
            logger.info(f"GPU count changed: {old_count} → {self._gpu_count}")
        
        self._update_metrics()
    
    @Slot()
    def startMonitoring(self):
        """Start automatic monitoring"""
        if not self._timer.isActive():
            self._timer.start()
            logger.info("GPU monitoring started")
    
    @Slot()
    def stopMonitoring(self):
        """Stop automatic monitoring"""
        if self._timer.isActive():
            self._timer.stop()
            logger.info("GPU monitoring stopped")
    
    def _update_metrics(self):
        """Update metrics cache and emit signal"""
        if not self._manager:
            return
            
        self._metrics_cache.clear()
        
        all_metrics = self._manager.get_all_metrics()
        for metrics in all_metrics:
            self._metrics_cache.append(self._metrics_to_dict(metrics))
        
        # Check for new safety warnings
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
        
        self.metricsUpdated.emit()
    
    def _metrics_to_dict(self, metrics: GPUMetrics) -> Dict:
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
            "vramStatus": self._get_vram_status(metrics.memory_percent)
        }
    
    def _get_temp_status(self, temp: int) -> str:
        """Get temperature status for UI"""
        if temp == 0:
            return "unknown"
        elif temp < 60:
            return "normal"
        elif temp < 75:
            return "warm"
        elif temp < 85:
            return "hot"
        else:
            return "critical"
    
    def _get_vram_status(self, percent: float) -> str:
        """Get VRAM usage status for UI"""
        if percent < 50:
            return "normal"
        elif percent < 75:
            return "moderate"
        elif percent < 90:
            return "high"
        else:
            return "critical"
    
    def cleanup(self):
        """Cleanup resources"""
        self._timer.stop()
        if self._manager:
            self._manager.shutdown()
        logger.info("GPU Backend cleanup complete")


# Singleton instance for QML
_gpu_backend_instance = None

def get_gpu_backend() -> GPUBackend:
    """Get or create GPU backend singleton"""
    global _gpu_backend_instance
    if _gpu_backend_instance is None:
        _gpu_backend_instance = GPUBackend()
    return _gpu_backend_instance
