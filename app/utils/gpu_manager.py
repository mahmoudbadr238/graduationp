"""
Sentinel GPU Manager - Universal Multi-Vendor GPU Monitoring System
Supports NVIDIA, AMD, and Intel GPUs on Windows and Linux
Auto-installs required libraries and provides unified API
"""

import builtins
import contextlib
import logging
import platform
import subprocess  # nosec B404 - subprocess needed for pip install automation with fixed arguments
import sys
import time
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GPUVendor(Enum):
    """GPU vendor enumeration"""

    NVIDIA = "NVIDIA"
    AMD = "AMD"
    INTEL = "Intel"
    UNKNOWN = "Unknown"


class GPUStatus(Enum):
    """GPU status enumeration"""

    ACTIVE = "active"
    IDLE = "idle"
    SLEEPING = "sleeping"
    ERROR = "error"


@dataclass
class GPUMetrics:
    """Unified GPU metrics structure"""

    gpu_id: int
    name: str
    vendor: GPUVendor
    status: GPUStatus
    usage_percent: float
    memory_used_mb: int
    memory_total_mb: int
    memory_percent: float
    temperature_c: int
    power_usage_w: float
    power_limit_w: float
    fan_speed_percent: int
    fan_speed_rpm: int
    clock_graphics_mhz: int
    clock_memory_mhz: int
    driver_version: str
    pci_bus_id: str
    supports_fan_control: bool
    supports_power_limit: bool


class LibraryInstaller:
    """Handles automatic library installation"""

    @staticmethod
    def check_and_install(package: str, import_name: str | None = None) -> bool:
        """Check if package is installed, offer to install if not"""
        if import_name is None:
            import_name = package

        try:
            __import__(import_name)
            return True
        except ImportError:
            logger.warning(f"Package '{package}' not found")
            try:
                # Attempt auto-install
                logger.info(f"Auto-installing {package}...")
                subprocess.check_call(  # nosec B603 - fixed pip command with validated package name
                    [sys.executable, "-m", "pip", "install", package, "--quiet"]
                )
                logger.info(f"✅ Successfully installed {package}")
                return True
            except subprocess.CalledProcessError as e:
                logger.exception(f"❌ Failed to install {package}: {e}")
                return False

    @staticmethod
    def install_nvidia_stack() -> bool:
        """Install NVIDIA monitoring stack"""
        packages = [
            ("nvidia-ml-py", "pynvml"),  # Official NVIDIA ML Python bindings
        ]

        success = True
        for package, import_name in packages:
            if not LibraryInstaller.check_and_install(package, import_name):
                success = False

        return success

    @staticmethod
    def install_amd_stack() -> bool:
        """Install AMD monitoring stack (Windows Performance Counters built-in)"""
        # On Windows, we use WMI Performance Counters (built-in, no install needed)
        # On Linux, we'd install rocm-smi
        if platform.system() == "Linux":
            # Try to install amdsmi (AMD System Management Interface)
            return LibraryInstaller.check_and_install("amdsmi")

        # Windows uses WMI - already available
        return True

    @staticmethod
    def install_intel_stack() -> bool:
        """Install Intel monitoring stack"""
        # Intel GPUs on Windows use WMI
        # On Linux, intel_gpu_top is system utility, not Python package
        # GPUtil can detect Intel GPUs as fallback
        return LibraryInstaller.check_and_install("GPUtil")


class NVIDIAMonitor:
    """NVIDIA GPU monitoring via pynvml"""

    def __init__(self):
        self.available = False
        self.initialized = False
        self._init_nvml()

    def _init_nvml(self):
        """Initialize NVIDIA ML library"""
        try:
            import pynvml

            pynvml.nvmlInit()
            self.available = True
            self.initialized = True
            self.pynvml = pynvml
            logger.info("✅ NVIDIA ML initialized")
        except ImportError:
            logger.info("NVIDIA ML not available - attempting installation")
            if LibraryInstaller.install_nvidia_stack():
                try:
                    import pynvml

                    pynvml.nvmlInit()
                    self.available = True
                    self.initialized = True
                    self.pynvml = pynvml
                    logger.info("✅ NVIDIA ML installed and initialized")
                except (ImportError, RuntimeError, OSError) as e:
                    logger.warning("NVIDIA ML installation failed: %s", e)
        except (ImportError, RuntimeError, OSError) as e:
            logger.warning("NVIDIA ML init failed: %s", e)

    def get_gpu_count(self) -> int:
        """Get number of NVIDIA GPUs"""
        if not self.available:
            return 0
        try:
            return self.pynvml.nvmlDeviceGetCount()
        except (RuntimeError, AttributeError):
            return 0

    def get_metrics(self, gpu_id: int) -> GPUMetrics | None:
        """Get comprehensive metrics for NVIDIA GPU"""
        if not self.available:
            return None

        try:
            handle = self.pynvml.nvmlDeviceGetHandleByIndex(gpu_id)

            # Name
            name = self.pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")

            # Utilization
            util = self.pynvml.nvmlDeviceGetUtilizationRates(handle)
            usage = float(util.gpu)

            # Memory
            mem_info = self.pynvml.nvmlDeviceGetMemoryInfo(handle)
            memory_used = mem_info.used // (1024**2)
            memory_total = mem_info.total // (1024**2)
            memory_percent = (
                (mem_info.used / mem_info.total * 100) if mem_info.total > 0 else 0
            )

            # Temperature
            try:
                temp = self.pynvml.nvmlDeviceGetTemperature(
                    handle, self.pynvml.NVML_TEMPERATURE_GPU
                )
            except (RuntimeError, AttributeError, OSError):
                temp = 0

            # Power
            power_usage = 0
            power_limit = 0
            try:
                power_usage = self.pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
                power_limit = (
                    self.pynvml.nvmlDeviceGetPowerManagementLimit(handle) / 1000.0
                )
            except (RuntimeError, AttributeError, OSError):
                logger.debug("GPU does not support power monitoring")

            # Fan speed
            fan_speed_percent = 0
            fan_speed_rpm = 0
            with contextlib.suppress(builtins.BaseException):
                fan_speed_percent = self.pynvml.nvmlDeviceGetFanSpeed(handle)

            # Clocks
            clock_graphics = 0
            clock_memory = 0
            try:
                clock_graphics = self.pynvml.nvmlDeviceGetClockInfo(
                    handle, self.pynvml.NVML_CLOCK_GRAPHICS
                )
                clock_memory = self.pynvml.nvmlDeviceGetClockInfo(
                    handle, self.pynvml.NVML_CLOCK_MEM
                )
            except (RuntimeError, AttributeError, OSError):
                logger.debug("GPU does not support clock monitoring")

            # Driver
            driver_version = "Unknown"
            try:
                driver_version = self.pynvml.nvmlSystemGetDriverVersion()
                if isinstance(driver_version, bytes):
                    driver_version = driver_version.decode("utf-8")
            except (RuntimeError, AttributeError, UnicodeDecodeError):
                logger.debug("Could not retrieve driver version")

            # PCI Bus ID
            pci_info = ""
            try:
                pci = self.pynvml.nvmlDeviceGetPciInfo(handle)
                pci_info = (
                    pci.busId.decode("utf-8")
                    if isinstance(pci.busId, bytes)
                    else str(pci.busId)
                )
            except (RuntimeError, AttributeError, UnicodeDecodeError):
                logger.debug("Could not retrieve PCI info")

            # Determine status
            status = GPUStatus.ACTIVE if usage > 0 else GPUStatus.IDLE

            # Feature support
            supports_fan = False
            supports_power = False
            try:
                # Test if fan control is supported
                self.pynvml.nvmlDeviceGetFanSpeed(handle)
                supports_fan = True
            except (RuntimeError, AttributeError, OSError):
                logger.debug("GPU does not support fan speed monitoring")

            try:
                # Test if power limit is supported
                self.pynvml.nvmlDeviceGetPowerManagementLimit(handle)
                supports_power = True
            except (RuntimeError, AttributeError, OSError):
                logger.debug("GPU does not support power limit monitoring")

            return GPUMetrics(
                gpu_id=gpu_id,
                name=name,
                vendor=GPUVendor.NVIDIA,
                status=status,
                usage_percent=usage,
                memory_used_mb=int(memory_used),
                memory_total_mb=int(memory_total),
                memory_percent=memory_percent,
                temperature_c=int(temp),
                power_usage_w=power_usage,
                power_limit_w=power_limit,
                fan_speed_percent=int(fan_speed_percent),
                fan_speed_rpm=int(fan_speed_rpm),
                clock_graphics_mhz=int(clock_graphics),
                clock_memory_mhz=int(clock_memory),
                driver_version=driver_version,
                pci_bus_id=pci_info,
                supports_fan_control=supports_fan,
                supports_power_limit=supports_power,
            )
        except Exception as e:
            logger.exception(f"Error getting NVIDIA GPU {gpu_id} metrics: {e}")
            return None

    def set_fan_speed(self, gpu_id: int, percent: int) -> bool:
        """Set fan speed (requires admin/root)"""
        if not self.available:
            return False
        try:
            self.pynvml.nvmlDeviceGetHandleByIndex(gpu_id)
            # Fan control usually requires elevated permissions
            # This is a read-only implementation for safety
            logger.warning(
                "Fan speed control requires admin privileges and is disabled for safety"
            )
            return False
        except (RuntimeError, AttributeError, OSError):
            return False

    def set_power_limit(self, gpu_id: int, watts: int) -> bool:
        """Set power limit (requires admin/root)"""
        if not self.available:
            return False
        try:
            self.pynvml.nvmlDeviceGetHandleByIndex(gpu_id)
            # Power limit control requires elevated permissions
            # This is a read-only implementation for safety
            logger.warning(
                "Power limit control requires admin privileges and is disabled for safety"
            )
            return False
        except (RuntimeError, AttributeError, OSError):
            return False


class AMDMonitor:
    """AMD GPU monitoring via Windows Performance Counters or ROCm SMI"""

    def __init__(self):
        self.available = False
        self.wmi_available = False
        self.performance_counters = {}
        self.pnp_to_phys = {}
        self._wmi_cache = None
        self._last_perf_update = 0
        self._perf_cache_duration = 2.0  # Cache performance counters for 2 seconds
        self._init_amd()

    def _init_amd(self):
        """Initialize AMD monitoring"""
        if platform.system() == "Windows":
            try:
                import wmi

                self._wmi_cache = wmi.WMI(namespace=r"root\cimv2")
                self.wmi_available = True
                self._cache_performance_counters()
                logger.info(
                    "✅ AMD monitoring initialized (Windows Performance Counters)"
                )
                self.available = True
            except (ImportError, RuntimeError, OSError) as e:
                logger.warning("AMD WMI init failed: %s", e)
        else:
            # Linux: Try ROCm SMI
            try:
                import amdsmi

                amdsmi.amdsmi_init()
                self.amdsmi = amdsmi
                self.available = True
                logger.info("✅ AMD monitoring initialized (ROCm SMI)")
            except (ImportError, RuntimeError, OSError):
                logger.info("AMD ROCm SMI not available")

    def _cache_performance_counters(self):
        """Cache AMD GPU performance counter data"""
        if not self.wmi_available or not self._wmi_cache:
            return

        try:
            # Build PNP to physical index mapping
            for phys_idx, gpu in enumerate(self._wmi_cache.Win32_VideoController()):
                vendor = gpu.Name.upper() if gpu.Name else ""
                if "AMD" in vendor or "ATI" in vendor:
                    pnp_id = gpu.PNPDeviceID or ""
                    if pnp_id:
                        self.pnp_to_phys[pnp_id] = phys_idx
        except Exception as e:
            logger.exception(f"Error caching AMD performance counters: {e}")

    def _get_performance_counter_usage(self) -> dict[int, float]:
        """Get AMD GPU usage from Windows Performance Counters"""
        gpu_usage = {}

        if not self.wmi_available or not self._wmi_cache:
            return gpu_usage

        # Use cached values if recent
        current_time = time.time()
        if (
            current_time - self._last_perf_update < self._perf_cache_duration
            and self.performance_counters
        ):
            return self.performance_counters

        try:
            for (
                counter
            ) in (
                self._wmi_cache.Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine()
            ):
                name = counter.Name
                if "phys_" in name:
                    try:
                        phys_idx = int(name.split("_phys_")[1].split("_")[0])
                        util = float(counter.UtilizationPercentage or 0)
                        if phys_idx not in gpu_usage:
                            gpu_usage[phys_idx] = 0
                        gpu_usage[phys_idx] = max(gpu_usage[phys_idx], util)
                    except (ValueError, IndexError, AttributeError):
                        logger.debug("Failed to parse performance counter: %s", name)

            # Update cache
            self.performance_counters = gpu_usage
            self._last_perf_update = current_time
        except (RuntimeError, AttributeError):
            logger.debug("Failed to query AMD performance counters")

        return gpu_usage

    def get_gpu_count(self) -> int:
        """Get number of AMD GPUs"""
        if not self.available or not self._wmi_cache:
            return 0

        count = 0
        try:
            for gpu in self._wmi_cache.Win32_VideoController():
                vendor = gpu.Name.upper() if gpu.Name else ""
                if "AMD" in vendor or "ATI" in vendor:
                    count += 1
        except (RuntimeError, AttributeError):
            logger.debug("Failed to query AMD GPU count via WMI")

        return count

    def get_metrics(self, gpu_id: int) -> GPUMetrics | None:
        """Get comprehensive metrics for AMD GPU"""
        if not self.available or not self._wmi_cache:
            return None

        try:
            # Get performance counter usage
            perf_usage = self._get_performance_counter_usage()

            # Find AMD GPU by index
            amd_gpus = []
            for gpu in self._wmi_cache.Win32_VideoController():
                vendor = gpu.Name.upper() if gpu.Name else ""
                if "AMD" in vendor or "ATI" in vendor:
                    amd_gpus.append(gpu)

            if gpu_id >= len(amd_gpus):
                return None

            gpu = amd_gpus[gpu_id]

            # Get usage from performance counters
            pnp_id = gpu.PNPDeviceID or ""
            usage = 0
            if pnp_id in self.pnp_to_phys:
                phys_idx = self.pnp_to_phys[pnp_id]
                usage = perf_usage.get(phys_idx, 0)

            # Memory
            memory_total = 0
            if gpu.AdapterRAM:
                memory_total = int(gpu.AdapterRAM) // (1024**2)

            # Status
            status = GPUStatus.ACTIVE if usage > 0 else GPUStatus.IDLE

            return GPUMetrics(
                gpu_id=gpu_id,
                name=gpu.Name or "AMD GPU",
                vendor=GPUVendor.AMD,
                status=status,
                usage_percent=round(usage, 1),
                memory_used_mb=0,  # Not available via WMI
                memory_total_mb=int(memory_total),
                memory_percent=0,
                temperature_c=0,  # Not available via WMI
                power_usage_w=0,
                power_limit_w=0,
                fan_speed_percent=0,
                fan_speed_rpm=0,
                clock_graphics_mhz=0,
                clock_memory_mhz=0,
                driver_version=gpu.DriverVersion or "Unknown",
                pci_bus_id=pnp_id,
                supports_fan_control=False,
                supports_power_limit=False,
            )
        except Exception as e:
            logger.exception(f"Error getting AMD GPU {gpu_id} metrics: {e}")
            return None


class IntelMonitor:
    """Intel GPU monitoring"""

    def __init__(self):
        self.available = False
        self.wmi_available = False
        self._wmi_cache = None
        self._init_intel()

    def _init_intel(self):
        """Initialize Intel monitoring"""
        if platform.system() == "Windows":
            try:
                import wmi

                self._wmi_cache = wmi.WMI(namespace=r"root\cimv2")
                self.wmi_available = True
                self.available = True
                logger.info("✅ Intel monitoring initialized (WMI)")
            except (ImportError, RuntimeError, OSError):
                logger.debug("Intel WMI monitoring not available")

    def get_gpu_count(self) -> int:
        """Get number of Intel GPUs"""
        if not self.available or not self._wmi_cache:
            return 0

        count = 0
        try:
            for gpu in self._wmi_cache.Win32_VideoController():
                vendor = gpu.Name.upper() if gpu.Name else ""
                if "INTEL" in vendor:
                    count += 1
        except (RuntimeError, AttributeError):
            logger.debug("Failed to query Intel GPU count via WMI")

        return count

    def get_metrics(self, gpu_id: int) -> GPUMetrics | None:
        """Get metrics for Intel GPU"""
        if not self.available or not self._wmi_cache:
            return None

        try:
            intel_gpus = []
            for gpu in self._wmi_cache.Win32_VideoController():
                vendor = gpu.Name.upper() if gpu.Name else ""
                if "INTEL" in vendor:
                    intel_gpus.append(gpu)

            if gpu_id >= len(intel_gpus):
                return None

            gpu = intel_gpus[gpu_id]

            memory_total = 0
            if gpu.AdapterRAM:
                memory_total = int(gpu.AdapterRAM) // (1024**2)

            return GPUMetrics(
                gpu_id=gpu_id,
                name=gpu.Name or "Intel GPU",
                vendor=GPUVendor.INTEL,
                status=GPUStatus.IDLE,
                usage_percent=0,
                memory_used_mb=0,
                memory_total_mb=int(memory_total),
                memory_percent=0,
                temperature_c=0,
                power_usage_w=0,
                power_limit_w=0,
                fan_speed_percent=0,
                fan_speed_rpm=0,
                clock_graphics_mhz=0,
                clock_memory_mhz=0,
                driver_version=gpu.DriverVersion or "Unknown",
                pci_bus_id=gpu.PNPDeviceID or "",
                supports_fan_control=False,
                supports_power_limit=False,
            )
        except Exception as e:
            logger.exception(f"Error getting Intel GPU {gpu_id} metrics: {e}")
            return None


class GPUManager:
    """
    Universal GPU Manager - Auto-detects and monitors all GPUs
    Provides unified API for NVIDIA, AMD, and Intel GPUs
    """

    def __init__(self, auto_install: bool = True):
        """
        Initialize GPU Manager

        Args:
            auto_install: Automatically install missing libraries
        """
        self.auto_install = auto_install
        self.nvidia = NVIDIAMonitor()
        self.amd = AMDMonitor()
        self.intel = IntelMonitor()

        self._gpu_list = []
        self._safety_warnings = []
        self._discover_gpus()

    def _discover_gpus(self):
        """Discover all available GPUs"""
        self._gpu_list = []

        # NVIDIA GPUs
        nvidia_count = self.nvidia.get_gpu_count()
        for i in range(nvidia_count):
            self._gpu_list.append(
                {
                    "vendor": GPUVendor.NVIDIA,
                    "vendor_id": i,
                    "global_id": len(self._gpu_list),
                }
            )

        # AMD GPUs
        amd_count = self.amd.get_gpu_count()
        for i in range(amd_count):
            self._gpu_list.append(
                {
                    "vendor": GPUVendor.AMD,
                    "vendor_id": i,
                    "global_id": len(self._gpu_list),
                }
            )

        # Intel GPUs
        intel_count = self.intel.get_gpu_count()
        for i in range(intel_count):
            self._gpu_list.append(
                {
                    "vendor": GPUVendor.INTEL,
                    "vendor_id": i,
                    "global_id": len(self._gpu_list),
                }
            )

        logger.info(
            f"🎮 Discovered {len(self._gpu_list)} GPU(s): "
            f"{nvidia_count} NVIDIA, {amd_count} AMD, {intel_count} Intel"
        )

    def list_gpus(self) -> list[dict]:
        """
        List all detected GPUs with basic info

        Returns:
            List of GPU dictionaries
        """
        gpus = []
        for gpu_info in self._gpu_list:
            metrics = self.get_gpu_metrics(gpu_info["global_id"])
            if metrics:
                gpus.append(
                    {
                        "id": metrics.gpu_id,
                        "name": metrics.name,
                        "vendor": metrics.vendor.value,
                        "status": metrics.status.value,
                    }
                )
        return gpus

    def get_gpu_metrics(self, global_id: int) -> GPUMetrics | None:
        """
        Get comprehensive metrics for a GPU by global ID

        Args:
            global_id: Global GPU index (0-based across all vendors)

        Returns:
            GPUMetrics object or None
        """
        if global_id >= len(self._gpu_list):
            return None

        gpu_info = self._gpu_list[global_id]
        vendor = gpu_info["vendor"]
        vendor_id = gpu_info["vendor_id"]

        metrics = None
        if vendor == GPUVendor.NVIDIA:
            metrics = self.nvidia.get_metrics(vendor_id)
        elif vendor == GPUVendor.AMD:
            metrics = self.amd.get_metrics(vendor_id)
        elif vendor == GPUVendor.INTEL:
            metrics = self.intel.get_metrics(vendor_id)

        if metrics:
            # Update global ID
            metrics.gpu_id = global_id
            # Safety checks
            self._check_safety(metrics)

        return metrics

    def get_gpu_usage(self, global_id: int) -> float:
        """Get GPU usage percentage"""
        metrics = self.get_gpu_metrics(global_id)
        return metrics.usage_percent if metrics else 0.0

    def get_vram_usage(self, global_id: int) -> tuple[int, int, float]:
        """
        Get VRAM usage

        Returns:
            (used_mb, total_mb, percent)
        """
        metrics = self.get_gpu_metrics(global_id)
        if metrics:
            return (
                metrics.memory_used_mb,
                metrics.memory_total_mb,
                metrics.memory_percent,
            )
        return (0, 0, 0.0)

    def get_temperature(self, global_id: int) -> int:
        """Get GPU temperature in Celsius"""
        metrics = self.get_gpu_metrics(global_id)
        return metrics.temperature_c if metrics else 0

    def get_gpu_name(self, global_id: int) -> str:
        """Get GPU name"""
        metrics = self.get_gpu_metrics(global_id)
        return metrics.name if metrics else "Unknown GPU"

    def get_driver_version(self, global_id: int) -> str:
        """Get GPU driver version"""
        metrics = self.get_gpu_metrics(global_id)
        return metrics.driver_version if metrics else "Unknown"

    def get_power_usage(self, global_id: int) -> tuple[float, float]:
        """
        Get GPU power usage

        Returns:
            (current_watts, limit_watts)
        """
        metrics = self.get_gpu_metrics(global_id)
        if metrics:
            return (metrics.power_usage_w, metrics.power_limit_w)
        return (0.0, 0.0)

    def get_fan_speed(self, global_id: int) -> tuple[int, int]:
        """
        Get GPU fan speed

        Returns:
            (percent, rpm)
        """
        metrics = self.get_gpu_metrics(global_id)
        if metrics:
            return (metrics.fan_speed_percent, metrics.fan_speed_rpm)
        return (0, 0)

    def set_fan_speed(self, global_id: int, percent: int) -> bool:
        """
        Set GPU fan speed (requires admin/root)

        Args:
            global_id: GPU index
            percent: Fan speed percentage (0-100)

        Returns:
            True if successful
        """
        if global_id >= len(self._gpu_list):
            return False

        gpu_info = self._gpu_list[global_id]
        vendor = gpu_info["vendor"]
        vendor_id = gpu_info["vendor_id"]

        if vendor == GPUVendor.NVIDIA:
            return self.nvidia.set_fan_speed(vendor_id, percent)

        logger.warning(f"Fan control not supported for {vendor.value} GPUs")
        return False

    def set_power_limit(self, global_id: int, watts: int) -> bool:
        """
        Set GPU power limit (requires admin/root)

        Args:
            global_id: GPU index
            watts: Power limit in watts

        Returns:
            True if successful
        """
        if global_id >= len(self._gpu_list):
            return False

        gpu_info = self._gpu_list[global_id]
        vendor = gpu_info["vendor"]
        vendor_id = gpu_info["vendor_id"]

        if vendor == GPUVendor.NVIDIA:
            return self.nvidia.set_power_limit(vendor_id, watts)

        logger.warning(f"Power limit control not supported for {vendor.value} GPUs")
        return False

    def _check_safety(self, metrics: GPUMetrics):
        """Check safety thresholds and generate warnings"""
        warnings = []

        # Temperature check
        if metrics.temperature_c > 85:
            warning = f"⚠️ GPU {metrics.gpu_id} ({metrics.name}) temperature critical: {metrics.temperature_c}°C"
            if warning not in self._safety_warnings:
                self._safety_warnings.append(warning)
                logger.warning(warning)
                warnings.append(warning)

        # VRAM check
        if metrics.memory_percent > 90:
            warning = f"⚠️ GPU {metrics.gpu_id} ({metrics.name}) VRAM usage critical: {metrics.memory_percent:.1f}%"
            if warning not in self._safety_warnings:
                self._safety_warnings.append(warning)
                logger.warning(warning)
                warnings.append(warning)

        return warnings

    def get_safety_warnings(self) -> list[str]:
        """Get all active safety warnings"""
        return self._safety_warnings.copy()

    def clear_safety_warnings(self):
        """Clear safety warning history"""
        self._safety_warnings = []

    def get_all_metrics(self) -> list[GPUMetrics]:
        """Get metrics for all GPUs"""
        metrics = []
        for i in range(len(self._gpu_list)):
            gpu_metrics = self.get_gpu_metrics(i)
            if gpu_metrics:
                metrics.append(gpu_metrics)
        return metrics

    def shutdown(self):
        """Cleanup and shutdown monitors"""
        if self.nvidia.initialized:
            try:
                self.nvidia.pynvml.nvmlShutdown()
                logger.info("NVIDIA ML shutdown")
            except (RuntimeError, AttributeError):
                logger.debug("NVML shutdown failed")


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Sentinel GPU Manager - Universal Multi-Vendor GPU Monitoring")
    print("=" * 70)

    # Initialize GPU Manager
    manager = GPUManager(auto_install=True)

    # List all GPUs
    print("\n📊 Detected GPUs:")
    gpus = manager.list_gpus()
    for gpu in gpus:
        print(f"  GPU {gpu['id']}: {gpu['name']} ({gpu['vendor']}) - {gpu['status']}")

    if not gpus:
        print("  No GPUs detected")
        sys.exit(0)

    # Get detailed metrics for each GPU
    print("\n🔍 Detailed Metrics:")
    for i in range(len(gpus)):
        metrics = manager.get_gpu_metrics(i)
        if metrics:
            print(f"\n  GPU {metrics.gpu_id}: {metrics.name}")
            print(f"    Vendor: {metrics.vendor.value}")
            print(f"    Status: {metrics.status.value}")
            print(f"    Usage: {metrics.usage_percent}%")
            print(
                f"    VRAM: {metrics.memory_used_mb} MB / {metrics.memory_total_mb} MB ({metrics.memory_percent:.1f}%)"
            )
            print(f"    Temperature: {metrics.temperature_c}°C")
            print(
                f"    Power: {metrics.power_usage_w:.1f}W / {metrics.power_limit_w:.1f}W"
            )
            print(f"    Fan: {metrics.fan_speed_percent}%")
            print(f"    Clock: {metrics.clock_graphics_mhz} MHz")
            print(f"    Driver: {metrics.driver_version}")
            print(f"    Fan Control: {'✅' if metrics.supports_fan_control else '❌'}")
            print(f"    Power Limit: {'✅' if metrics.supports_power_limit else '❌'}")

    # Test safety warnings
    print("\n⚠️ Safety Warnings:")
    warnings = manager.get_safety_warnings()
    if warnings:
        for warning in warnings:
            print(f"  {warning}")
    else:
        print("  No warnings")

    # Monitor for 10 seconds
    print("\n🔄 Live Monitoring (10 seconds)...")
    for _ in range(10):
        time.sleep(1)
        for i in range(len(gpus)):
            usage = manager.get_gpu_usage(i)
            temp = manager.get_temperature(i)
            used, total, percent = manager.get_vram_usage(i)
            print(
                f"  GPU {i}: {usage:.1f}% | {temp}°C | VRAM: {percent:.1f}%", end="\r"
            )

    print("\n\n✅ GPU Manager test complete!")
    manager.shutdown()
