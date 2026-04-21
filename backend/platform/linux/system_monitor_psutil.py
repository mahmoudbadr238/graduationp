"""Linux system monitoring implementation using psutil.

Replaces backend/infra/system_monitor_psutil.py on Linux.
Uses psutil for CPU, memory, disk, network — no WMI or Windows-specific calls.
"""

import contextlib
import logging
import os
from typing import Any

import psutil

from backend.core.interfaces import ISystemMonitor

logger = logging.getLogger(__name__)

try:
    import pynvml
    HAS_NVIDIA = True
except ImportError:
    HAS_NVIDIA = False


class PsutilSystemMonitor(ISystemMonitor):
    """System monitor using psutil for CPU, memory, network, and disk metrics."""

    def __init__(self):
        self._net_io_prev = None
        self._gpu_cache = None
        self._gpu_cache_time = 0
        self._nvml_initialized = False
        self._security_cache = None
        self._security_cache_time = 0
        self._security_loading = False

        if HAS_NVIDIA:
            try:
                pynvml.nvmlInit()
                self._nvml_initialized = True
            except (ImportError, RuntimeError, OSError):
                self._nvml_initialized = False

    def snapshot(self) -> dict[str, Any]:
        """Return current system metrics snapshot."""
        return {
            "cpu": self._get_cpu_info(),
            "mem": self._get_memory_info(),
            "gpu": {
                "available": False,
                "note": "Use GPUService for live GPU data",
            },
            "disk": self._get_disk_info(),
            "net": self._get_network_info(),
        }

    def _get_cpu_info(self) -> dict[str, Any]:
        try:
            cpu_name = "Unknown"
            try:
                with open("/proc/cpuinfo") as f:
                    for line in f:
                        if line.startswith("model name"):
                            cpu_name = line.split(":", 1)[1].strip()
                            break
            except OSError:
                pass

            return {
                "name": cpu_name,
                "usage_percent": psutil.cpu_percent(interval=None),
                "cores": psutil.cpu_count(logical=False) or 0,
                "threads": psutil.cpu_count(logical=True) or 0,
                "freq_current_mhz": getattr(psutil.cpu_freq(), "current", 0) if psutil.cpu_freq() else 0,
            }
        except Exception as e:
            logger.warning("CPU info error: %s", e)
            return {"name": "Error", "usage_percent": 0}

    def _get_memory_info(self) -> dict[str, Any]:
        try:
            mem = psutil.virtual_memory()
            return {
                "total_gb": round(mem.total / (1024**3), 1),
                "used_gb": round(mem.used / (1024**3), 1),
                "available_gb": round(mem.available / (1024**3), 1),
                "percent": mem.percent,
            }
        except Exception as e:
            logger.warning("Memory info error: %s", e)
            return {"total_gb": 0, "percent": 0}

    def _get_disk_info(self) -> dict[str, Any]:
        try:
            disk = psutil.disk_usage("/")
            return {
                "total_gb": round(disk.total / (1024**3), 1),
                "used_gb": round(disk.used / (1024**3), 1),
                "free_gb": round(disk.free / (1024**3), 1),
                "percent": disk.percent,
            }
        except Exception as e:
            logger.warning("Disk info error: %s", e)
            return {"total_gb": 0, "percent": 0}

    def _get_network_info(self) -> dict[str, Any]:
        try:
            net = psutil.net_io_counters()
            return {
                "bytes_sent": net.bytes_sent,
                "bytes_recv": net.bytes_recv,
            }
        except Exception as e:
            logger.warning("Network info error: %s", e)
            return {"bytes_sent": 0, "bytes_recv": 0}
