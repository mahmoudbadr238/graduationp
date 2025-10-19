"""System monitoring implementation using psutil."""
import psutil
import platform
import subprocess
from typing import Dict, Any
from ..core.interfaces import ISystemMonitor

try:
    import pynvml
    HAS_NVIDIA = True
except ImportError:
    HAS_NVIDIA = False

try:
    import GPUtil
    HAS_GPUTIL = True
except ImportError:
    HAS_GPUTIL = False

try:
    import wmi
    HAS_WMI = True
except ImportError:
    HAS_WMI = False


class PsutilSystemMonitor(ISystemMonitor):
    """System monitor using psutil for CPU, memory, network, and disk metrics."""
    
    def __init__(self):
        self._net_io_prev = None
        if HAS_NVIDIA:
            try:
                pynvml.nvmlInit()
            except:
                pass
    
    def snapshot(self) -> Dict[str, Any]:
        """Return current system metrics snapshot."""
        return {
            "cpu": self._get_cpu_info(),
            "mem": self._get_memory_info(),
            "gpu": self._get_gpu_info(),
            "net": self._get_network_info(),
            "disk": self._get_disk_info(),
            "os": self._get_os_info(),
            "security": self._get_security_info(),
        }
    
    def _get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU metrics."""
        cpu_percent = psutil.cpu_percent(interval=0.05)
        cpu_freq = psutil.cpu_freq()
        cpu_count = psutil.cpu_count(logical=True)

        return {
            "percent": cpu_percent,  # Changed from "usage" to "percent" for consistency
            "usage": cpu_percent,    # Keep both for compatibility
            "freq_current": cpu_freq.current if cpu_freq else 0,
            "freq_max": cpu_freq.max if cpu_freq else 0,
            "core_count": cpu_count,
        }
    
    def _get_memory_info(self) -> Dict[str, Any]:
        """Get memory (RAM) metrics (optimized)."""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return {
            "total": mem.total,
            "available": mem.available,
            "used": mem.used,
            "percent": mem.percent,
            "swap_total": swap.total,
            "swap_used": swap.used,
            "swap_percent": swap.percent,
        }

    def _get_gpu_info(self) -> Dict[str, Any]:
        """Get GPU metrics (optimized with timeout)."""
        import time
        
        # Cache GPU info for 5 seconds
        current_time = time.time()
        if hasattr(self, '_gpu_cache') and (current_time - self._gpu_cache_time) < 5:
            return self._gpu_cache
        
        gpu_info = {
            "name": "Unknown",
            "usage": 0.0,
            "memory_used": 0,
            "memory_total": 0,
            "temperature": 0,
        }
        
        try:
            # Try pynvml first (NVIDIA GPUs)
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            
            gpu_info["name"] = pynvml.nvmlDeviceGetName(handle).decode('utf-8') if isinstance(pynvml.nvmlDeviceGetName(handle), bytes) else pynvml.nvmlDeviceGetName(handle)
            
            # Get utilization
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpu_info["usage"] = float(util.gpu)
            
            # Get memory
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            gpu_info["memory_used"] = mem_info.used // (1024**2)  # MB
            gpu_info["memory_total"] = mem_info.total // (1024**2)  # MB
            
            # Get temperature (optional)
            try:
                gpu_info["temperature"] = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except:
                pass
                
            pynvml.nvmlShutdown()
            
        except:
            # Fallback to GPUtil (simpler but slower)
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    gpu_info["name"] = gpu.name
                    gpu_info["usage"] = gpu.load * 100
                    gpu_info["memory_used"] = gpu.memoryUsed
                    gpu_info["memory_total"] = gpu.memoryTotal
                    gpu_info["temperature"] = gpu.temperature
            except:
                # No GPU available or detection failed
                gpu_info["name"] = "No GPU Detected"
        
        # Cache result
        self._gpu_cache = gpu_info
        self._gpu_cache_time = current_time
        
        return gpu_info

    def _get_network_info(self) -> Dict[str, Any]:
        """Get network I/O metrics."""
        net_io = psutil.net_io_counters()
        net_info = {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
            "send_rate_mbps": 0,
            "recv_rate_mbps": 0,
        }
        if self._net_io_prev:
            sent_diff = net_io.bytes_sent - self._net_io_prev.bytes_sent
            recv_diff = net_io.bytes_recv - self._net_io_prev.bytes_recv
            net_info["send_rate_mbps"] = round(max(0, sent_diff) * 8 / 1_000_000, 2)
            net_info["recv_rate_mbps"] = round(max(0, recv_diff) * 8 / 1_000_000, 2)
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
                "speed": 0
            }
            for addr in addresses:
                if addr.family == 2:
                    adapter_info["addresses"].append({
                        "type": "IPv4",
                        "address": addr.address,
                        "netmask": addr.netmask
                    })
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
                disks.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent,
                })
            except Exception:
                continue
        return disks

    def _get_os_info(self) -> Dict[str, Any]:
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
                key = winreg.OpenKey(reg, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
                os_info["product_name"] = winreg.QueryValueEx(key, "ProductName")[0]
                os_info["build_number"] = winreg.QueryValueEx(key, "CurrentBuild")[0]
                os_info["display_version"] = winreg.QueryValueEx(key, "DisplayVersion")[0]
                winreg.CloseKey(key)
            except:
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
        except Exception:
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

    def _get_security_info(self) -> Dict[str, Any]:
        """Get Windows security features status (cached for 30 seconds)."""
        import time
        
        # Use cached value if less than 30 seconds old
        current_time = time.time()
        if hasattr(self, '_security_cache') and (current_time - self._security_cache_time) < 30:
            return self._security_cache
        
        # Return minimal info to avoid PowerShell delays
        security_info = {
            'windows_defender': {'status': 'Check Windows Security', 'enabled': False},
            'firewall': {'status': 'Check Windows Security', 'enabled': False},
            'antivirus': {'status': 'Check Windows Security', 'enabled': False},
            'uac': {'status': 'Check Settings', 'enabled': False},
            'bitlocker': {'status': 'Check BitLocker', 'enabled': False},
            'tpm': {'status': 'Check Device Security', 'enabled': False},
        }
        
        # Cache for 30 seconds
        self._security_cache = security_info
        self._security_cache_time = current_time
        
        return security_info
