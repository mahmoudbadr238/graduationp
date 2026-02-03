"""System monitoring implementation using psutil."""

import builtins
import contextlib
import logging
import platform
import subprocess  # nosec B404 - subprocess required for Windows security checks (PowerShell, netsh, manage-bde)
from typing import Any

import psutil

from ..core.interfaces import ISystemMonitor
from ..utils.admin import check_admin

logger = logging.getLogger(__name__)

try:
    import pynvml

    HAS_NVIDIA = True
except ImportError:
    HAS_NVIDIA = False

try:
    import GPUtil  # noqa: F401

    HAS_GPUTIL = True
except ImportError:
    HAS_GPUTIL = False

try:
    import wmi  # noqa: F401

    HAS_WMI = True
except ImportError:
    HAS_WMI = False


class PsutilSystemMonitor(ISystemMonitor):
    """System monitor using psutil for CPU, memory, network, and disk metrics."""

    def __init__(self):
        self._net_io_prev = None
        self._gpu_cache = None
        self._gpu_cache_time = 0
        self._nvml_initialized = False
        self._wmi_cache = None  # Cache WMI connection for better performance
        self._pnp_to_phys_cache = None  # Cache PNP to physical GPU index mapping
        self._security_cache = None  # Cache security info (updates every 30s)
        self._security_cache_time = 0
        self._security_loading = False  # Flag to prevent multiple concurrent loads

        # Try to initialize NVIDIA ML once at startup (persistent)
        if HAS_NVIDIA:
            try:
                pynvml.nvmlInit()
                self._nvml_initialized = True
            except (ImportError, RuntimeError, OSError):
                self._nvml_initialized = False

        # Pre-initialize WMI connection and PNP mapping on Windows (major performance boost)
        if platform.system() == "Windows" and HAS_WMI:
            try:
                import wmi

                self._wmi_cache = wmi.WMI(namespace=r"root\cimv2")

                # Build PNP to physical GPU index mapping once at startup
                # Performance counter physical indices match WMI enumeration order
                self._pnp_to_phys_cache = {}
                for phys_idx, wmi_gpu in enumerate(
                    self._wmi_cache.Win32_VideoController()
                ):
                    pnp_id = wmi_gpu.PNPDeviceID or ""
                    if pnp_id:
                        self._pnp_to_phys_cache[pnp_id] = phys_idx
            except (ImportError, RuntimeError, OSError):
                self._wmi_cache = None
                self._pnp_to_phys_cache = None

    def snapshot(self) -> dict[str, Any]:
        """Return current system metrics snapshot (GPU excluded - use GPUService instead)."""
        return {
            "cpu": self._get_cpu_info(),
            "mem": self._get_memory_info(),
            "gpu": {
                "available": False,
                "gpus": [],
                "count": 0,
            },  # Stub - use GPUService for real GPU data
            "net": self._get_network_info(),
            "disks": self._get_disk_info(),
            "os": self._get_os_info(),
            "security": self._get_security_info_cached(),
            "is_admin": check_admin(),
        }

    def _get_cpu_info(self) -> dict[str, Any]:
        """Get CPU metrics."""
        # Use interval=0 for non-blocking call (measures since last call)
        cpu_percent = psutil.cpu_percent(interval=0)
        cpu_freq = psutil.cpu_freq()
        cpu_count = psutil.cpu_count(logical=True)

        return {
            "percent": cpu_percent,  # Changed from "usage" to "percent" for consistency
            "usage": cpu_percent,  # Keep both for compatibility
            "freq_current": cpu_freq.current if cpu_freq else 0,
            "freq_max": cpu_freq.max if cpu_freq else 0,
            "core_count": cpu_count,
        }

    def _get_memory_info(self) -> dict[str, Any]:
        """Get memory metrics."""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        return {
            "total": mem.total,
            "used": mem.used,
            "available": mem.available,
            "percent": mem.percent,
            "swap_total": swap.total,
            "swap_used": swap.used,
            "swap_percent": swap.percent,
        }

    def _get_gpu_info_cached(self) -> dict[str, Any]:
        """
        Get GPU info with aggressive caching to prevent UI lag.
        Cache for 10 seconds since GPU info changes slowly and WMI queries take 14+ seconds.
        """
        import time

        current_time = time.time()

        # Return cached result if less than 10 seconds old
        if hasattr(self, "_gpu_cache") and (current_time - self._gpu_cache_time) < 10:
            return self._gpu_cache

        # Otherwise, call the full GPU detection (this will also cache for 5s internally)
        return self._get_gpu_info()

    def _get_gpu_info(self) -> dict[str, Any]:
        """Get comprehensive GPU metrics for ALL GPUs (NVIDIA, AMD, Intel) with Windows Performance Counters for AMD."""
        import time

        # Cache GPU info for 5 seconds to reduce WMI overhead
        current_time = time.time()
        if hasattr(self, "_gpu_cache") and (current_time - self._gpu_cache_time) < 5:
            return self._gpu_cache

        gpu_result = {
            "gpus": [],  # List of all detected GPUs
            "count": 0,
            "primary": None,  # Primary GPU for backward compatibility
        }

        detected_gpus = []

        # Method 1: NVIDIA GPUs via pynvml (if initialized at startup)
        if self._nvml_initialized:
            try:
                import pynvml

                device_count = pynvml.nvmlDeviceGetCount()

                for i in range(device_count):
                    try:
                        handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                        name = pynvml.nvmlDeviceGetName(handle)
                        if isinstance(name, bytes):
                            name = name.decode("utf-8")

                        # Get utilization
                        util = pynvml.nvmlDeviceGetUtilizationRates(handle)

                        # Get memory
                        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

                        # Get temperature
                        temp = 0
                        with contextlib.suppress(builtins.BaseException):
                            temp = pynvml.nvmlDeviceGetTemperature(
                                handle, pynvml.NVML_TEMPERATURE_GPU
                            )

                        # Get driver version
                        driver_version = "Unknown"
                        try:
                            driver_version = pynvml.nvmlSystemGetDriverVersion()
                            if isinstance(driver_version, bytes):
                                driver_version = driver_version.decode("utf-8")
                        except (RuntimeError, AttributeError, UnicodeDecodeError):
                            pass  # Driver version not available

                        # Get clock speeds
                        clock_graphics = 0
                        with contextlib.suppress(builtins.BaseException):
                            clock_graphics = pynvml.nvmlDeviceGetClockInfo(
                                handle, pynvml.NVML_CLOCK_GRAPHICS
                            )

                        # Get power usage
                        power_usage = 0
                        try:
                            power_usage = (
                                pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
                            )  # mW to W
                        except (RuntimeError, AttributeError, OSError):
                            pass  # Power monitoring not supported

                        gpu_data = {
                            "id": i,
                            "name": name,
                            "vendor": "NVIDIA",
                            "usage": float(util.gpu),
                            "memory_used": mem_info.used // (1024**2),  # MB
                            "memory_total": mem_info.total // (1024**2),  # MB
                            "memory_percent": (
                                (mem_info.used / mem_info.total * 100)
                                if mem_info.total > 0
                                else 0
                            ),
                            "temperature": temp,
                            "driver_version": driver_version,
                            "clock_graphics_mhz": clock_graphics,
                            "power_usage_watts": power_usage,
                        }
                        detected_gpus.append(gpu_data)
                    except (RuntimeError, AttributeError, ValueError, OSError) as e:
                        # Fix: BLE001 - Use specific exception types (psutil errors + NVML RuntimeError)
                        # NVML GPU query failed - may not support all features
                        # Catches pynvml.NVMLError_Unknown and other NVML errors
                        logger.debug("GPU query failed for device %d: %s", i, e)
                        continue
            except (RuntimeError, AttributeError) as e:
                # Fix: S110 - Log exception instead of pass
                # NVML device enumeration failed
                logger.debug(
                    "NVML device enumeration failed: %s", e
                )  # Method 2: WMI for AMD/Intel/Other GPUs + Performance Counters for AMD usage
        if platform.system() == "Windows":
            try:
                # Use cached WMI connection for performance
                if self._wmi_cache:
                    c = self._wmi_cache
                else:
                    import wmi

                    c = wmi.WMI()

                # Get AMD GPU usage from Windows Performance Counters
                gpu_perf_usage = {}
                try:
                    perf_wmi = (
                        self._wmi_cache
                        if self._wmi_cache
                        else wmi.WMI(namespace=r"root\cimv2")
                    )
                    for (
                        counter
                    ) in (
                        perf_wmi.Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine()
                    ):
                        name = counter.Name
                        if "phys_" in name and "_eng_" in name:
                            try:
                                # Extract physical GPU index (matches WMI enumeration order)
                                phys_idx = int(name.split("_phys_")[1].split("_")[0])
                                util = float(counter.UtilizationPercentage or 0)
                                if phys_idx not in gpu_perf_usage:
                                    gpu_perf_usage[phys_idx] = 0
                                gpu_perf_usage[phys_idx] = max(
                                    gpu_perf_usage[phys_idx], util
                                )
                            except (ValueError, IndexError, AttributeError):
                                # Performance counter parsing failed
                                pass
                except (ImportError, OSError, AttributeError):
                    # WMI or performance counters not available
                    pass  # Use cached PNP to physical index mapping
                if self._pnp_to_phys_cache:
                    pnp_to_phys_idx = self._pnp_to_phys_cache
                else:
                    # Build mapping if not cached
                    pnp_to_phys_idx = {}
                    for phys_idx, wmi_gpu in enumerate(c.Win32_VideoController()):
                        pnp_id = wmi_gpu.PNPDeviceID or ""
                        if pnp_id:
                            pnp_to_phys_idx[pnp_id] = phys_idx

                # Get video controllers
                for gpu in c.Win32_VideoController():
                    vendor = "Unknown"
                    if "NVIDIA" in gpu.Name.upper():
                        vendor = "NVIDIA"
                    elif "AMD" in gpu.Name.upper() or "ATI" in gpu.Name.upper():
                        vendor = "AMD"
                    elif "INTEL" in gpu.Name.upper():
                        vendor = "Intel"

                    # Check if already detected via pynvml (NVIDIA)
                    existing_gpu = None
                    for g in detected_gpus:
                        if g["name"] == gpu.Name or (
                            vendor == "NVIDIA" and g["vendor"] == "NVIDIA"
                        ):
                            existing_gpu = g
                            break

                    if existing_gpu:
                        # Enrich NVIDIA GPU with WMI data
                        existing_gpu["pnp_device_id"] = gpu.PNPDeviceID or "Unknown"
                        existing_gpu["driver_date"] = (
                            str(gpu.DriverDate)[:8] if gpu.DriverDate else "Unknown"
                        )
                        existing_gpu["status"] = gpu.Status or "Unknown"
                        continue

                    # Get adapter RAM
                    adapter_ram = 0
                    if gpu.AdapterRAM:
                        adapter_ram = int(gpu.AdapterRAM) // (1024**2)

                    # Get AMD GPU usage from Performance Counters
                    gpu_usage = 0
                    current_pnp_id = gpu.PNPDeviceID or ""
                    if current_pnp_id and current_pnp_id in pnp_to_phys_idx:
                        gpu_phys_idx = pnp_to_phys_idx[current_pnp_id]
                        if gpu_phys_idx in gpu_perf_usage:
                            gpu_usage = round(gpu_perf_usage[gpu_phys_idx], 1)

                    gpu_data = {
                        "id": len(detected_gpus),
                        "name": gpu.Name or "Unknown GPU",
                        "vendor": vendor,
                        "usage": gpu_usage,  # From Performance Counters
                        "memory_used": 0,  # Not available via standard WMI
                        "memory_total": adapter_ram,
                        "memory_percent": 0,
                        "temperature": 0,  # Not available via standard WMI (requires AMD ADL SDK)
                        "driver_version": gpu.DriverVersion or "Unknown",
                        "driver_date": (
                            str(gpu.DriverDate)[:8] if gpu.DriverDate else "Unknown"
                        ),
                        "status": gpu.Status or "Unknown",
                        "pnp_device_id": gpu.PNPDeviceID or "Unknown",
                    }
                detected_gpus.append(gpu_data)
            except (ImportError, OSError, AttributeError):
                # WMI GPU enumeration failed
                pass  # Sort GPUs by PCI bus order to match Windows Task Manager

        def get_pci_order(gpu_info):
            pnp_id = gpu_info.get("pnp_device_id", "")
            if not pnp_id or pnp_id == "Unknown":
                return (999, 999, gpu_info["id"])
            parts = pnp_id.split("\\")
            if len(parts) >= 3:
                bus_device = parts[-1]
                segments = bus_device.split("&")
                try:
                    if len(segments) >= 4:
                        bus_num = int(segments[0])
                        device_num = int(segments[-1], 16)
                        return (bus_num, device_num, 0)
                except (ValueError, IndexError):
                    # PCI ID parsing failed
                    pass
            return (500, 500, gpu_info["id"])

        detected_gpus.sort(key=get_pci_order)  # Re-assign IDs after sorting
        for idx, gpu in enumerate(detected_gpus):
            gpu["id"] = idx

        # Populate result
        gpu_result["gpus"] = detected_gpus
        gpu_result["count"] = len(detected_gpus)

        # Set primary GPU
        if detected_gpus:
            nvidia_gpus = [g for g in detected_gpus if g["vendor"] == "NVIDIA"]
            primary = nvidia_gpus[0] if nvidia_gpus else detected_gpus[0]
            gpu_result["primary"] = primary
            # Legacy format
            gpu_result["name"] = primary["name"]
            gpu_result["usage"] = primary["usage"]
            gpu_result["memory_used"] = primary["memory_used"]
            gpu_result["memory_total"] = primary["memory_total"]
            gpu_result["temperature"] = primary.get("temperature", 0)
        else:
            gpu_result["primary"] = None
            gpu_result["name"] = "No GPU Detected"
            gpu_result["usage"] = 0
            gpu_result["memory_used"] = 0
            gpu_result["memory_total"] = 0
            gpu_result["temperature"] = 0

        # Cache result
        self._gpu_cache = gpu_result
        self._gpu_cache_time = current_time

        return gpu_result

    def _get_network_info(self) -> dict[str, Any]:
        """Get network I/O metrics with auto-scaling units (Bps, KBps, Mbps)."""
        net_io = psutil.net_io_counters()

        # Calculate rates
        send_rate_bps = 0
        recv_rate_bps = 0
        if self._net_io_prev:
            sent_diff = net_io.bytes_sent - self._net_io_prev.bytes_sent
            recv_diff = net_io.bytes_recv - self._net_io_prev.bytes_recv
            send_rate_bps = max(0, sent_diff)  # Bytes per second
            recv_rate_bps = max(0, recv_diff)  # Bytes per second

        # Auto-scale send rate
        def format_rate(bps):
            """Format rate with auto-scaling units."""
            if bps < 1024:  # < 1 KB/s
                return {
                    "value": round(bps, 2),
                    "unit": "Bps",
                    "formatted": f"{bps:.2f} Bps",
                }
            if bps < 1024 * 1024:  # < 1 MB/s
                kbps = bps / 1024
                return {
                    "value": round(kbps, 2),
                    "unit": "KBps",
                    "formatted": f"{kbps:.2f} KBps",
                }
            # >= 1 MB/s
            mbps = bps / (1024 * 1024)
            return {
                "value": round(mbps, 2),
                "unit": "MBps",
                "formatted": f"{mbps:.2f} MBps",
            }

        net_info = {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
            "send_rate": format_rate(send_rate_bps),
            "recv_rate": format_rate(recv_rate_bps),
            # Legacy fields for backwards compatibility
            "send_rate_mbps": round(send_rate_bps / (1024 * 1024), 2),
            "recv_rate_mbps": round(recv_rate_bps / (1024 * 1024), 2),
        }
        self._net_io_prev = net_io
        # Adapter details
        adapters = []
        net_if_addrs = psutil.net_if_addrs()
        net_if_stats = psutil.net_if_stats()
        for interface_name, addresses in net_if_addrs.items():
            if "Loopback" in interface_name or "Virtual" in interface_name:
                continue
            adapter_info = {
                "name": interface_name,
                "addresses": [],
                "is_up": False,
                "speed": 0,
            }
            for addr in addresses:
                if addr.family == 2:
                    adapter_info["addresses"].append(
                        {
                            "type": "IPv4",
                            "address": addr.address,
                            "netmask": addr.netmask,
                        }
                    )
            if interface_name in net_if_stats:
                stats = net_if_stats[interface_name]
                adapter_info["is_up"] = stats.isup
                adapter_info["speed"] = stats.speed
            if adapter_info["addresses"]:
                adapters.append(adapter_info)
        net_info["adapters"] = adapters
        return net_info

    def _get_disk_info(self) -> list:
        """Get disk usage metrics for all available drives."""
        disks = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disks.append(
                    {
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "fstype": partition.fstype,
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent,
                    }
                )
            except (OSError, PermissionError):
                # Disk access error (permission denied, disk not ready)
                continue
        return disks

    def _get_os_info(self) -> dict[str, Any]:
        """Get operating system information."""
        try:
            uname = platform.uname()
            os_info = {
                "name": uname.system,
                "version": uname.version,
                "release": uname.release,
                "architecture": uname.machine,
                "processor": uname.processor,
                "hostname": uname.node,
            }
            # Registry for product name/build
            try:
                import winreg

                reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
                key = winreg.OpenKey(
                    reg, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
                )
                os_info["product_name"] = winreg.QueryValueEx(key, "ProductName")[0]
                os_info["build_number"] = winreg.QueryValueEx(key, "CurrentBuild")[0]
                os_info["display_version"] = winreg.QueryValueEx(key, "DisplayVersion")[
                    0
                ]
                winreg.CloseKey(key)
            except (OSError, AttributeError):
                # Windows registry not available or keys missing
                os_info["product_name"] = f"{uname.system} {uname.release}"
                os_info["build_number"] = uname.version
                os_info["display_version"] = uname.release
            # Boot time/uptime
            boot_time = psutil.boot_time()
            from datetime import datetime

            boot_datetime = datetime.fromtimestamp(boot_time)
            os_info["boot_time"] = boot_datetime.isoformat()
            import time

            os_info["uptime"] = int(time.time() - boot_time)
            return os_info
        except (OSError, ValueError):
            # System info gathering failed
            return {
                "name": "Unknown",
                "version": "Unknown",
                "release": "Unknown",
                "architecture": "Unknown",
                "processor": "Unknown",
                "hostname": "Unknown",
                "product_name": "Unknown",
                "build_number": "Unknown",
                "display_version": "Unknown",
                "boot_time": "",
                "uptime": 0,
            }

    def _get_security_info(self) -> dict[str, Any]:
        """Get Windows security features status."""
        security_info = {
            "windows_defender": {"status": "Unknown", "enabled": False},
            "firewall": {"status": "Unknown", "enabled": False},
            "antivirus": {"status": "Unknown", "enabled": False},
            "uac": {"status": "Unknown", "enabled": False},
            "bitlocker": {"status": "Unknown", "enabled": False},
            "tpm": {"status": "Unknown", "enabled": False},
            "secure_boot": {"status": "Unknown", "enabled": False},
        }

        try:
            # Check Windows Defender status
            try:
                result = subprocess.run(  # nosec B603 B607 - fixed PowerShell command, no user input
                    [
                        "powershell",
                        "-Command",
                        "Get-MpComputerStatus | Select-Object -ExpandProperty RealTimeProtectionEnabled",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if result.returncode == 0:
                    defender_enabled = result.stdout.strip().lower() == "true"
                    security_info["windows_defender"] = {
                        "status": "Active" if defender_enabled else "Inactive",
                        "enabled": defender_enabled,
                    }
            except (OSError, subprocess.SubprocessError):
                # PowerShell or Defender query failed
                pass

            # Check Firewall status
            try:
                result = subprocess.run(  # nosec B603 B607 - fixed netsh command, no user input
                    ["netsh", "advfirewall", "show", "allprofiles", "state"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if result.returncode == 0:
                    firewall_enabled = "ON" in result.stdout
                    security_info["firewall"] = {
                        "status": "Enabled" if firewall_enabled else "Disabled",
                        "enabled": firewall_enabled,
                    }
            except (OSError, subprocess.SubprocessError):
                # Firewall query failed
                pass

            # Check UAC status
            try:
                import winreg

                reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
                key = winreg.OpenKey(
                    reg, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
                )
                uac_value = winreg.QueryValueEx(key, "EnableLUA")[0]
                uac_enabled = uac_value == 1
                security_info["uac"] = {
                    "status": "Enabled" if uac_enabled else "Disabled",
                    "enabled": uac_enabled,
                }
                winreg.CloseKey(key)
            except (OSError, AttributeError):
                # Windows registry access failed
                pass

            # Check BitLocker status (basic check)
            try:
                result = subprocess.run(  # nosec B603 B607 - fixed manage-bde command, no user input
                    ["manage-bde", "-status", "C:"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if result.returncode == 0:
                    bitlocker_enabled = "Protection On" in result.stdout
                    security_info["bitlocker"] = {
                        "status": "Encrypted" if bitlocker_enabled else "Not Encrypted",
                        "enabled": bitlocker_enabled,
                    }
            except (OSError, subprocess.SubprocessError):
                # BitLocker query failed
                pass  # Set antivirus status (same as Windows Defender for now)
            security_info["antivirus"] = security_info["windows_defender"]

            # Check TPM status (requires admin)
            try:
                result = subprocess.run(  # nosec B603 B607 - fixed PowerShell command, no user input
                    [
                        "powershell",
                        "-Command",
                        "Get-Tpm | Select-Object -ExpandProperty TpmPresent",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if "Administrator privilege is required" in result.stderr:
                    security_info["tpm"] = {
                        "status": "Requires Admin",
                        "enabled": False,
                    }
                elif result.returncode == 0:
                    tpm_present = result.stdout.strip().lower() == "true"
                    if tpm_present:
                        # Check if TPM is enabled and ready
                        result2 = subprocess.run(  # nosec B603 B607 - fixed PowerShell command, no user input
                            [
                                "powershell",
                                "-Command",
                                "Get-Tpm | Select-Object -ExpandProperty TpmReady",
                            ],
                            check=False,
                            capture_output=True,
                            text=True,
                            timeout=3,
                        )
                        tpm_ready = (
                            result2.returncode == 0
                            and result2.stdout.strip().lower() == "true"
                        )
                        security_info["tpm"] = {
                            "status": (
                                "Available" if tpm_ready else "Present but not ready"
                            ),
                            "enabled": tpm_ready,
                        }
                    else:
                        security_info["tpm"] = {
                            "status": "Not Available",
                            "enabled": False,
                        }
            except (OSError, subprocess.SubprocessError):
                # TPM query failed
                pass

            # Check Secure Boot status (requires admin)
            try:
                result = subprocess.run(  # nosec B603 B607 - fixed PowerShell command, no user input
                    ["powershell", "-Command", "Confirm-SecureBootUEFI"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if (
                    "Administrator privilege is required" in result.stderr
                    or "Access is denied" in result.stderr
                ):
                    security_info["secure_boot"] = {
                        "status": "Requires Admin",
                        "enabled": False,
                    }
                elif result.returncode == 0:
                    secure_boot_enabled = result.stdout.strip().lower() == "true"
                    security_info["secure_boot"] = {
                        "status": "Enabled" if secure_boot_enabled else "Disabled",
                        "enabled": secure_boot_enabled,
                    }
                else:
                    # Command failed, might be legacy BIOS
                    security_info["secure_boot"] = {
                        "status": "Not Supported",
                        "enabled": False,
                    }
            except (OSError, subprocess.SubprocessError):
                # Secure Boot query failed
                pass

        except (OSError, subprocess.SubprocessError, ImportError) as e:
            # Security info gathering failed
            print(f"Error getting security info: {e}")

        return security_info

    def _get_security_info_cached(self) -> dict[str, Any]:
        """Get security info with 30-second caching to avoid expensive subprocess calls.
        
        Returns placeholder on first call and loads in background thread.
        """
        import threading
        import time

        now = time.time()

        # Return cached value if less than 30 seconds old
        if self._security_cache and (now - self._security_cache_time) < 30:
            return self._security_cache

        # Return placeholder immediately on first call, load in background
        if not self._security_cache and not self._security_loading:
            self._security_loading = True
            
            def load_security_info():
                try:
                    self._security_cache = self._get_security_info()
                    self._security_cache_time = time.time()
                finally:
                    self._security_loading = False
            
            thread = threading.Thread(target=load_security_info, daemon=True)
            thread.start()
            
            # Return placeholder while loading
            return {
                "windows_defender": {"status": "Loading...", "enabled": False},
                "firewall": {"status": "Loading...", "enabled": False},
                "antivirus": {"status": "Loading...", "enabled": False},
                "uac": {"status": "Loading...", "enabled": False},
                "bitlocker": {"status": "Loading...", "enabled": False},
                "tpm": {"status": "Loading...", "enabled": False},
                "secure_boot": {"status": "Loading...", "enabled": False},
            }

        # Refresh cache in background if expired
        if not self._security_loading:
            self._security_loading = True
            
            def refresh_security_info():
                try:
                    self._security_cache = self._get_security_info()
                    self._security_cache_time = time.time()
                finally:
                    self._security_loading = False
            
            thread = threading.Thread(target=refresh_security_info, daemon=True)
            thread.start()

        # Return stale cache while refreshing (better than blocking)
        return self._security_cache or {
            "windows_defender": {"status": "Loading...", "enabled": False},
            "firewall": {"status": "Loading...", "enabled": False},
            "antivirus": {"status": "Loading...", "enabled": False},
            "uac": {"status": "Loading...", "enabled": False},
            "bitlocker": {"status": "Loading...", "enabled": False},
            "tpm": {"status": "Loading...", "enabled": False},
            "secure_boot": {"status": "Loading...", "enabled": False},
        }
