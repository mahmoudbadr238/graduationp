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
        cpu_percent = psutil.cpu_percent(interval=0.1)
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
    
    def _get_gpu_info(self) -> Dict[str, Any]:
        """Get GPU metrics (Nvidia, AMD, or None)."""
        gpu_info = {
            "available": False,
            "vendor": "N/A",
            "usage": None,
            "memory_used": None,
            "memory_total": None,
            "temperature": None,
        }
        # Nvidia
        if HAS_NVIDIA:
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                gpu_info.update({
                    "available": True,
                    "vendor": "Nvidia",
                    "usage": util.gpu,
                    "memory_used": mem.used,
                    "memory_total": mem.total,
                    "temperature": temp,
                })
            except:
                pass
                
        # AMD (basic, via WMI)
        elif HAS_WMI:
            try:
                w = wmi.WMI()
                for gpu in w.Win32_VideoController():
                    if "AMD" in gpu.Name:
                        gpu_info.update({
                            "available": True,
                            "vendor": "AMD",
                            "usage": None,
                            "memory_used": int(gpu.AdapterRAM) if gpu.AdapterRAM else None,
                            "memory_total": int(gpu.AdapterRAM) if gpu.AdapterRAM else None,
                            "temperature": None,
                        })
                        break
            except:
                pass
        
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
                result = subprocess.run(
                    ["powershell", "-Command", "Get-MpComputerStatus | Select-Object -ExpandProperty RealTimeProtectionEnabled"],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    defender_enabled = result.stdout.strip().lower() == "true"
                    security_info["windows_defender"] = {
                        "status": "Active" if defender_enabled else "Inactive",
                        "enabled": defender_enabled
                    }
            except:
                pass
            
            # Check Firewall status
            try:
                result = subprocess.run(
                    ["netsh", "advfirewall", "show", "allprofiles", "state"],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    firewall_enabled = "ON" in result.stdout
                    security_info["firewall"] = {
                        "status": "Enabled" if firewall_enabled else "Disabled",
                        "enabled": firewall_enabled
                    }
            except:
                pass
            
            # Check UAC status
            try:
                import winreg
                reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
                key = winreg.OpenKey(reg, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System")
                uac_value = winreg.QueryValueEx(key, "EnableLUA")[0]
                uac_enabled = uac_value == 1
                security_info["uac"] = {
                    "status": "Enabled" if uac_enabled else "Disabled",
                    "enabled": uac_enabled
                }
                winreg.CloseKey(key)
            except:
                pass
            
            # Check BitLocker status (basic check)
            try:
                result = subprocess.run(
                    ["manage-bde", "-status", "C:"],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    bitlocker_enabled = "Protection On" in result.stdout
                    security_info["bitlocker"] = {
                        "status": "Encrypted" if bitlocker_enabled else "Not Encrypted",
                        "enabled": bitlocker_enabled
                    }
            except:
                pass
            
            # Set antivirus status (same as Windows Defender for now)
            security_info["antivirus"] = security_info["windows_defender"]

            # Check TPM status (requires admin)
            try:
                result = subprocess.run(
                    ["powershell", "-Command", "Get-Tpm | Select-Object -ExpandProperty TpmPresent"],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if "Administrator privilege is required" in result.stderr:
                    security_info["tpm"] = {
                        "status": "Requires Admin",
                        "enabled": False
                    }
                elif result.returncode == 0:
                    tpm_present = result.stdout.strip().lower() == "true"
                    if tpm_present:
                        # Check if TPM is enabled and ready
                        result2 = subprocess.run(
                            ["powershell", "-Command", "Get-Tpm | Select-Object -ExpandProperty TpmReady"],
                            capture_output=True,
                            text=True,
                            timeout=3
                        )
                        tpm_ready = result2.returncode == 0 and result2.stdout.strip().lower() == "true"
                        security_info["tpm"] = {
                            "status": "Available" if tpm_ready else "Present but not ready",
                            "enabled": tpm_ready
                        }
                    else:
                        security_info["tpm"] = {
                            "status": "Not Available",
                            "enabled": False
                        }
            except:
                pass

            # Check Secure Boot status (requires admin)
            try:
                result = subprocess.run(
                    ["powershell", "-Command", "Confirm-SecureBootUEFI"],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if "Administrator privilege is required" in result.stderr or "Access is denied" in result.stderr:
                    security_info["secure_boot"] = {
                        "status": "Requires Admin",
                        "enabled": False
                    }
                elif result.returncode == 0:
                    secure_boot_enabled = result.stdout.strip().lower() == "true"
                    security_info["secure_boot"] = {
                        "status": "Enabled" if secure_boot_enabled else "Disabled",
                        "enabled": secure_boot_enabled
                    }
                else:
                    # Command failed, might be legacy BIOS
                    security_info["secure_boot"] = {
                        "status": "Not Supported",
                        "enabled": False
                    }
            except:
                pass

        except Exception as e:
            print(f"Error getting security info: {e}")

        return security_info