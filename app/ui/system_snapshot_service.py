"""Cross-platform System Snapshot Service using psutil."""

import platform
import socket
import subprocess
import sys
import time
from typing import Dict, List, Optional

import psutil
from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer

from app.utils.security_info import SecurityInfo

# Subprocess flags - CREATE_NO_WINDOW only works on Windows
_IS_WINDOWS = platform.system() == "Windows"
_SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if _IS_WINDOWS else 0


class SystemSnapshotService(QObject):
    """Cross-platform system monitoring service using psutil.
    
    Works on Windows, Linux, and macOS. Platform-specific features
    are guarded and degrade gracefully.
    """
    
    # Signals for property changes
    cpuUsageChanged = Signal()
    memoryUsageChanged = Signal()
    memoryUsedChanged = Signal()
    memoryTotalChanged = Signal()
    memoryAvailableChanged = Signal()
    diskUsageChanged = Signal()
    diskPartitionsChanged = Signal()
    netUpBpsChanged = Signal()  # Primary network throughput in bits per second
    netDownBpsChanged = Signal()
    netUpKbpsChanged = Signal()  # Legacy compatibility (derived from Bps)
    netDownKbpsChanged = Signal()
    updateIntervalMsChanged = Signal()
    topProcessesChanged = Signal()
    networkInterfacesChanged = Signal()
    securityInfoChanged = Signal()
    cpuChartDataChanged = Signal()
    memoryChartDataChanged = Signal()
    networkHistoryUpChanged = Signal()
    networkHistoryDownChanged = Signal()
    cpuNameChanged = Signal()
    cpuCountChanged = Signal()
    cpuCountLogicalChanged = Signal()
    cpuFrequencyChanged = Signal()
    systemUptimeChanged = Signal()
    cpuPerCoreChanged = Signal()
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        # Detect platform once
        self._platform = platform.system()
        self._is_windows = self._platform == "Windows"
        self._is_linux = self._platform == "Linux"
        self._is_macos = self._platform == "Darwin"
        
        # Metrics
        self._cpu_usage = 0.0
        self._memory_usage = 0.0
        self._memory_used = 0
        self._memory_total = 0
        self._memory_available = 0
        self._disk_usage = 0.0
        self._disk_partitions: List[Dict] = []
        self._net_up_bps = 0.0  # Primary: bits per second
        self._net_down_bps = 0.0
        self._top_processes: List[Dict] = []
        self._network_interfaces: List[Dict] = []
        self._security_info: Dict = {}
        
        # CPU details
        self._cpu_name = self._get_cpu_name()
        self._cpu_count = psutil.cpu_count(logical=False) or 1  # Physical cores
        self._cpu_count_logical = psutil.cpu_count(logical=True) or 1  # Logical cores
        self._cpu_frequency = psutil.cpu_freq()
        self._system_uptime = 0.0
        self._cpu_per_core: List[float] = []  # Per-core CPU usage
        
        # Chart data (historical)
        self._cpu_chart_data: List[float] = []
        self._memory_chart_data: List[float] = []
        self._network_history_up: List[float] = []
        self._network_history_down: List[float] = []
        self._max_history_points = 60  # Keep last 60 data points
        
        # Network tracking
        self._last_net_io = None
        self._last_net_time = None
        self._last_per_nic_io = {}  # Track per-interface stats
        self._active_interface_name = ""
        self._active_interface_ipv4 = ""
        
        # Update timer
        self._update_interval_ms = 2000  # Default 2 seconds
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_metrics)
        
        # Initial update
        self._update_metrics()
        self._update_security_info()  # Security info updated once at startup
        print("[SnapshotService] Initial metrics updated")
        
    def start(self, interval_ms: int = 2000):
        """Start monitoring with specified interval."""
        self._update_interval_ms = interval_ms
        self.updateIntervalMsChanged.emit()
        # Force initial update before starting timer
        self._update_metrics()
        self._timer.start(interval_ms)
        print(f"[SnapshotService] Started with {interval_ms}ms interval")
        
    def stop(self):
        """Stop monitoring."""
        self._timer.stop()
    
    def _get_cpu_name(self) -> str:
        """Get CPU model name from system."""
        try:
            if self._is_windows:
                try:
                    import winreg
                    reg_path = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
                        cpu_name = winreg.QueryValueEx(key, "ProcessorNameString")[0]
                        return cpu_name.strip()
                except Exception:
                    return "Intel/AMD Processor"
            elif self._is_linux:
                try:
                    with open('/proc/cpuinfo', 'r') as f:
                        for line in f:
                            if 'model name' in line:
                                return line.split(':', 1)[1].strip()
                except Exception:
                    return "Linux Processor"
            elif self._is_macos:
                try:
                    result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        return result.stdout.strip()
                except Exception:
                    return "Apple Silicon"
        except Exception:
            pass
        return "Unknown Processor"
        
    def _update_system_uptime(self):
        """Update system uptime in seconds."""
        try:
            import datetime
            boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
            now = datetime.datetime.now()
            uptime_seconds = (now - boot_time).total_seconds()
            self._system_uptime = uptime_seconds
            self.systemUptimeChanged.emit()
        except Exception as e:
            print(f"[SystemSnapshot] Error getting uptime: {e}")
        
    @Slot()
    def _update_metrics(self):
        """Update all system metrics."""
        try:
            # System uptime
            self._update_system_uptime()
            
            # CPU usage (non-blocking)
            cpu = psutil.cpu_percent(interval=0)
            self._cpu_usage = cpu
            self.cpuUsageChanged.emit()
            
            # Per-core CPU usage
            try:
                per_core = psutil.cpu_percent(interval=0, percpu=True)
                if per_core and per_core != self._cpu_per_core:
                    self._cpu_per_core = per_core
                    self.cpuPerCoreChanged.emit()
            except Exception:
                pass  # Per-core not available
                
            # Add to chart history
            self._cpu_chart_data.append(cpu)
            if len(self._cpu_chart_data) > self._max_history_points:
                self._cpu_chart_data.pop(0)
            self.cpuChartDataChanged.emit()
            
            # Memory usage
            mem = psutil.virtual_memory()
            self._memory_usage = mem.percent
            self.memoryUsageChanged.emit()
                
            # Add to chart history
            self._memory_chart_data.append(mem.percent)
            if len(self._memory_chart_data) > self._max_history_points:
                self._memory_chart_data.pop(0)
            self.memoryChartDataChanged.emit()
                
            self._memory_used = mem.used
            self.memoryUsedChanged.emit()
            self._memory_total = mem.total
            self.memoryTotalChanged.emit()
            self._memory_available = mem.available
            self.memoryAvailableChanged.emit()
            
            # Disk usage (system partition)
            try:
                if self._is_windows:
                    disk = psutil.disk_usage("C:\\")
                else:
                    disk = psutil.disk_usage("/")
                self._disk_usage = disk.percent
                self.diskUsageChanged.emit()
            except (PermissionError, OSError):
                pass  # Disk not accessible
            
            # Update disk partitions
            self._update_disk_partitions()
            
            # Network throughput (calculate delta in bits per second)
            try:
                net_io = psutil.net_io_counters()
                current_time = time.time()
                
                if self._last_net_io and self._last_net_time:
                    time_delta = current_time - self._last_net_time
                    if time_delta > 0:
                        bytes_sent = net_io.bytes_sent - self._last_net_io.bytes_sent
                        bytes_recv = net_io.bytes_recv - self._last_net_io.bytes_recv
                        
                        # Calculate bits per second (bytes * 8 / time)
                        up_bps = (bytes_sent / time_delta) * 8.0
                        down_bps = (bytes_recv / time_delta) * 8.0
                        
                        # Update values (always emit)
                        self._net_up_bps = up_bps
                        self.netUpBpsChanged.emit()
                        self.netUpKbpsChanged.emit()  # Also emit legacy signal
                        
                        # Add to network history
                        self._network_history_up.append(up_bps)
                        if len(self._network_history_up) > self._max_history_points:
                            self._network_history_up.pop(0)
                        self.networkHistoryUpChanged.emit()
                        
                        self._net_down_bps = down_bps
                        self.netDownBpsChanged.emit()
                        self.netDownKbpsChanged.emit()  # Also emit legacy signal
                        
                        # Add to network history
                        self._network_history_down.append(down_bps)
                        if len(self._network_history_down) > self._max_history_points:
                            self._network_history_down.pop(0)
                        self.networkHistoryDownChanged.emit()
                
                self._last_net_io = net_io
                self._last_net_time = current_time
            except (PermissionError, OSError):
                pass  # Network stats not accessible
            
            # Top processes by CPU
            try:
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                    try:
                        info = proc.info
                        if info['cpu_percent'] is not None and info['cpu_percent'] > 0:
                            processes.append({
                                'pid': info['pid'],
                                'name': info['name'] or 'Unknown',
                                'cpu': round(info['cpu_percent'], 1),
                                'memory': round(info['memory_percent'] or 0, 1)
                            })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                # Sort by CPU and take top 10
                processes.sort(key=lambda p: p['cpu'], reverse=True)
                new_top = processes[:10]
                
                if new_top != self._top_processes:
                    self._top_processes = new_top
                    self.topProcessesChanged.emit()
                    
            except (PermissionError, OSError):
                pass  # Process enumeration not accessible
            
            # Network interfaces
            self._update_network_interfaces()
                
        except Exception as e:
            print(f"[SystemSnapshot] Error updating metrics: {e}")
    
    def _update_disk_partitions(self):
        """Update disk partitions with usage information."""
        try:
            partitions = []
            disk_partitions = psutil.disk_partitions(all=False)  # Physical partitions only
            
            for partition in disk_partitions:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    part_data = {
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "fstype": partition.fstype,
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent
                    }
                    partitions.append(part_data)
                except (PermissionError, OSError):
                    # Skip inaccessible partitions
                    continue
            
            if partitions != self._disk_partitions:
                self._disk_partitions = partitions
                self.diskPartitionsChanged.emit()
        except Exception as e:
            print(f"[SystemSnapshot] Error updating disk partitions: {e}")
    
    def _update_network_interfaces(self):
        """Update network interfaces list with IPs and stats."""
        try:
            interfaces = []
            
            # Get interface addresses
            addrs = psutil.net_if_addrs()
            # Get interface stats
            stats = psutil.net_if_stats()
            # Get per-interface IO counters (may not be available on all platforms)
            try:
                io_counters = psutil.net_io_counters(pernic=True)
            except (PermissionError, OSError):
                io_counters = {}
            
            current_time = time.time()
            max_throughput = 0
            active_iface = ""
            active_ipv4 = ""
            
            for iface_name, addr_list in addrs.items():
                iface_data = {
                    "name": iface_name,
                    "is_up": False,
                    "speed_mbps": 0,
                    "ipv4": "",
                    "ipv6": "",
                    "mac": ""
                }
                
                # Get stats
                if iface_name in stats:
                    stat = stats[iface_name]
                    iface_data["is_up"] = stat.isup
                    iface_data["speed_mbps"] = stat.speed if stat.speed > 0 else 0
                
                # Parse addresses
                for addr in addr_list:
                    if addr.family == socket.AF_INET:
                        iface_data["ipv4"] = addr.address
                    elif addr.family == socket.AF_INET6:
                        # Take the first IPv6, strip zone ID
                        if not iface_data["ipv6"]:
                            ipv6_addr = addr.address.split('%')[0]  # Remove zone ID
                            iface_data["ipv6"] = ipv6_addr
                    elif hasattr(psutil, 'AF_LINK') and addr.family == psutil.AF_LINK:
                        # macOS/BSD
                        iface_data["mac"] = addr.address
                    elif hasattr(socket, 'AF_PACKET') and addr.family == socket.AF_PACKET:
                        # Linux
                        iface_data["mac"] = addr.address
                
                interfaces.append(iface_data)
                
                # Determine most active interface
                if iface_name in io_counters and self._last_per_nic_io.get(iface_name):
                    last_io = self._last_per_nic_io[iface_name]
                    curr_io = io_counters[iface_name]
                    time_delta = current_time - last_io['time']
                    
                    if time_delta > 0:
                        bytes_sent = curr_io.bytes_sent - last_io['bytes_sent']
                        bytes_recv = curr_io.bytes_recv - last_io['bytes_recv']
                        total_throughput = (bytes_sent + bytes_recv) / time_delta
                        
                        if total_throughput > max_throughput:
                            max_throughput = total_throughput
                            active_iface = iface_name
                            active_ipv4 = iface_data["ipv4"]
            
            # Update per-interface tracking
            for iface_name, io_counter in io_counters.items():
                self._last_per_nic_io[iface_name] = {
                    'bytes_sent': io_counter.bytes_sent,
                    'bytes_recv': io_counter.bytes_recv,
                    'time': current_time
                }
            
            # Update stored values
            if interfaces != self._network_interfaces:
                self._network_interfaces = interfaces
                self.networkInterfacesChanged.emit()
            
            if active_iface != self._active_interface_name:
                self._active_interface_name = active_iface
                self._active_interface_ipv4 = active_ipv4
                
        except Exception as e:
            print(f"[SystemSnapshot] Error updating network interfaces: {e}")
    
    # Properties
    @Property(float, notify=cpuUsageChanged)
    def cpuUsage(self) -> float:
        return self._cpu_usage
    
    @Property(float, notify=memoryUsageChanged)
    def memoryUsage(self) -> float:
        return self._memory_usage
    
    @Property(float, notify=memoryUsedChanged)
    def memoryUsed(self) -> float:
        return float(self._memory_used)
    
    @Property(float, notify=memoryTotalChanged)
    def memoryTotal(self) -> float:
        return float(self._memory_total)
    
    @Property(float, notify=diskUsageChanged)
    def diskUsage(self) -> float:
        return self._disk_usage
    
    @Property('QVariantList', notify=diskPartitionsChanged)
    def diskPartitions(self) -> List[Dict]:
        """List of disk partitions with usage information."""
        return self._disk_partitions
    
    @Property(float, notify=netUpBpsChanged)
    def netUpBps(self) -> float:
        """Network upload speed in bits per second (primary property for QML)."""
        return self._net_up_bps
    
    @Property(float, notify=netDownBpsChanged)
    def netDownBps(self) -> float:
        """Network download speed in bits per second (primary property for QML)."""
        return self._net_down_bps
    
    @Property(float, notify=netUpKbpsChanged)
    def netUpKbps(self) -> float:
        """Legacy: Upload speed in kilobits per second (derived from netUpBps)."""
        return self._net_up_bps / 1000.0
    
    @Property(float, notify=netDownKbpsChanged)
    def netDownKbps(self) -> float:
        """Legacy: Download speed in kilobits per second (derived from netDownBps)."""
        return self._net_down_bps / 1000.0
    
    @Property(int, notify=updateIntervalMsChanged)
    def updateIntervalMs(self) -> int:
        return self._update_interval_ms
    
    @updateIntervalMs.setter
    def updateIntervalMs(self, value: int):
        if value != self._update_interval_ms and value >= 500:
            self._update_interval_ms = value
            self.updateIntervalMsChanged.emit()
            if self._timer.isActive():
                self._timer.start(value)
    
    @Property('QVariantList', notify=topProcessesChanged)
    def topProcesses(self) -> List[Dict]:
        return self._top_processes
    
    @Property(str, constant=True)
    def platformName(self) -> str:
        """Platform name for display."""
        return self._platform
    
    @Property(bool, constant=True)
    def isWindows(self) -> bool:
        return self._is_windows
    
    @Property(bool, constant=True)
    def isLinux(self) -> bool:
        return self._is_linux
    
    @Property(bool, constant=True)
    def isMacOS(self) -> bool:
        return self._is_macos
    
    @Property('QVariantList', notify=networkInterfacesChanged)
    def networkInterfaces(self) -> List[Dict]:
        """List of network interfaces with their addresses and stats."""
        return self._network_interfaces
    
    @Property(str, constant=False)
    def activeInterfaceName(self) -> str:
        """Name of the interface with highest current throughput."""
        return self._active_interface_name
    
    @Property(str, constant=False)
    def activeInterfaceIpv4(self) -> str:
        """IPv4 address of the most active interface."""
        return self._active_interface_ipv4
    
    @Property('QVariantList', notify=cpuChartDataChanged)
    def cpuChartData(self) -> List[float]:
        """Historical CPU usage data for charting."""
        return self._cpu_chart_data
    
    @Property('QVariantList', notify=memoryChartDataChanged)
    def memoryChartData(self) -> List[float]:
        """Historical memory usage data for charting."""
        return self._memory_chart_data
    
    @Property('QVariantList', notify=networkHistoryUpChanged)
    def networkHistoryUp(self) -> List[float]:
        """Historical upload speed data (bps) for charting."""
        return self._network_history_up
    
    @Property('QVariantList', notify=networkHistoryDownChanged)
    def networkHistoryDown(self) -> List[float]:
        """Historical download speed data (bps) for charting."""
        return self._network_history_down
    
    @Property('QVariantMap', notify=securityInfoChanged)
    def securityInfo(self) -> Dict:
        """Security status information (firewall, AV, etc.)."""
        return self._security_info
    
    @Property(str, notify=cpuNameChanged)
    def cpuName(self) -> str:
        """CPU model name."""
        return self._cpu_name
    
    @Property(int, constant=True)
    def cpuCount(self) -> int:
        """Number of physical CPU cores."""
        return self._cpu_count
    
    @Property(int, constant=True)
    def cpuCountLogical(self) -> int:
        """Number of logical CPU cores (including hyperthreading)."""
        return self._cpu_count_logical
    
    @Property(float, constant=True)
    def cpuFrequency(self) -> float:
        """CPU frequency information (MHz)."""
        if self._cpu_frequency:
            return float(self._cpu_frequency.current)
        return 0.0
    
    @Property(float, notify=systemUptimeChanged)
    def systemUptime(self) -> float:
        """System uptime in seconds."""
        return self._system_uptime
    
    @Property(float, notify=memoryAvailableChanged)
    def memoryAvailable(self) -> float:
        """Available memory in bytes."""
        return float(self._memory_available)
    
    @Property('QVariantList', notify=cpuPerCoreChanged)
    def cpuPerCore(self) -> List[float]:
        """Per-core CPU usage percentages."""
        return self._cpu_per_core
    
    def _update_security_info(self):
        """Gather security information about the system."""
        info = {
            "firewallStatus": "Unknown",
            "antivirus": "Unknown",
            "antivirusEnabled": False,
            "secureBoot": "N/A",
            "tpmPresent": "N/A",
            "tpmEnabled": False,
            "tpmVersion": "Unknown",
            "appArmorEnabled": "N/A",
            "selinuxEnabled": "N/A",
            "osName": platform.system() + " " + platform.release(),
            "kernel": platform.version(),
            "uptime": self._get_system_uptime(),
            # Extended security metrics (Windows only)
            "diskEncryption": "Unknown",
            "diskEncryptionDetail": "",
            "windowsUpdateStatus": "Unknown",
            "windowsUpdateLastInstall": "",
            "windowsUpdateDetail": "",
            "remoteDesktopEnabled": False,
            "remoteDesktopNla": True,
            "remoteDesktopDetail": "",
            "adminAccountCount": 0,
            "adminAccountDetail": "",
            "uacLevel": "Unknown",
            "uacDetail": "",
            "smartScreenEnabled": True,
            "smartScreenDetail": "",
            "memoryIntegrityEnabled": False,
            "memoryIntegrityDetail": "",
            # Simplified security status for user-friendly UI
            "simplified": None,
        }
        
        try:
            if self._is_windows:
                # Use centralized SecurityInfo service for Windows
                security_status = SecurityInfo.get_all_security_status()
                
                # Map SecurityInfo output to our format
                fw_status = security_status.get("firewall", {})
                info["firewallStatus"] = "Enabled" if fw_status.get("enabled") else "Disabled"
                
                av_status = security_status.get("antivirus", {}) if "antivirus" in security_status else security_status.get("defender", {})
                info["antivirusEnabled"] = av_status.get("enabled", False)
                if av_status.get("enabled"):
                    realtime = av_status.get("realtime_protection", False)
                    info["antivirus"] = f"Windows Defender (Real-time: {'On' if realtime else 'Off'})"
                else:
                    info["antivirus"] = "Windows Defender (Disabled)"
                
                info["secureBoot"] = self._check_secure_boot()
                
                # Get proper TPM status
                tpm_status = SecurityInfo.get_tpm_status()
                info["tpmPresent"] = "Present" if tpm_status.get("present") else "Not Present"
                info["tpmEnabled"] = tpm_status.get("enabled", False)
                info["tpmVersion"] = tpm_status.get("version", "Unknown")
                
                # Get extended security metrics
                try:
                    extended = SecurityInfo.get_extended_security_status()
                    
                    # Disk Encryption
                    disk_enc = extended.get("diskEncryption", {})
                    info["diskEncryption"] = disk_enc.get("status", "Unknown")
                    info["diskEncryptionDetail"] = disk_enc.get("detail", "")
                    
                    # Windows Update
                    win_update = extended.get("windowsUpdate", {})
                    info["windowsUpdateStatus"] = win_update.get("status", "Unknown")
                    info["windowsUpdateLastInstall"] = win_update.get("lastInstallDate", "")
                    info["windowsUpdateDetail"] = win_update.get("detail", "")
                    
                    # Remote Desktop
                    rdp = extended.get("remoteDesktop", {})
                    info["remoteDesktopEnabled"] = rdp.get("enabled", False)
                    info["remoteDesktopNla"] = rdp.get("nlaEnabled", True)
                    info["remoteDesktopDetail"] = rdp.get("detail", "")
                    
                    # Admin Accounts
                    admin = extended.get("adminAccounts", {})
                    info["adminAccountCount"] = admin.get("count", 0)
                    info["adminAccountDetail"] = admin.get("detail", "")
                    
                    # UAC Level
                    uac = extended.get("uacLevel", {})
                    info["uacLevel"] = uac.get("level", "Unknown")
                    info["uacDetail"] = uac.get("detail", "")
                    
                    # SmartScreen
                    smartscreen = extended.get("smartScreen", {})
                    info["smartScreenEnabled"] = smartscreen.get("enabled", True)
                    info["smartScreenDetail"] = smartscreen.get("detail", "")
                    
                    # Memory Integrity
                    mem_int = extended.get("memoryIntegrity", {})
                    info["memoryIntegrityEnabled"] = mem_int.get("enabled", False)
                    info["memoryIntegrityDetail"] = mem_int.get("detail", "")
                    
                except Exception as e:
                    print(f"[SystemSnapshot] Error gathering extended security info: {e}")
                
                # Get simplified security status for user-friendly UI
                try:
                    info["simplified"] = SecurityInfo.get_simplified_security_status()
                except Exception as e:
                    print(f"[SystemSnapshot] Error gathering simplified security info: {e}")
                    
            elif self._is_linux:
                # Check Linux Firewall (ufw/firewalld)
                info["firewallStatus"] = self._check_linux_firewall()
                info["antivirus"] = self._check_linux_antivirus()
                info["appArmorEnabled"] = self._check_apparmor()
                info["selinuxEnabled"] = self._check_selinux()
        except Exception as e:
            print(f"[SystemSnapshot] Error gathering security info: {e}")
        
        self._security_info = info
        self.securityInfoChanged.emit()
    
    def _get_system_uptime(self) -> str:
        """Get system uptime as a formatted string."""
        try:
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            
            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
        except Exception:
            return "Unknown"
    
    def _check_windows_firewall(self) -> str:
        """Check Windows Firewall status."""
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "show", "allprofiles", "state"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if self._is_windows else 0
            )
            
            if result.returncode == 0:
                # Parse output to check if any profile is ON
                output = result.stdout.lower()
                if "state" in output and "on" in output:
                    return "Enabled"
                elif "state" in output and "off" in output:
                    return "Disabled"
            return "Unknown"
        except Exception:
            return "Unknown"
    
    def _check_windows_antivirus(self) -> str:
        """Check for installed antivirus on Windows."""
        try:
            # Check Windows Security Center via WMI
            result = subprocess.run(
                ["powershell", "-Command", 
                 "Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct | Select-Object -ExpandProperty displayName"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=_SUBPROCESS_FLAGS
            )
            
            if result.returncode == 0 and result.stdout.strip():
                av_products = [line.strip() for line in result.stdout.split('\n') if line.strip()]
                if av_products:
                    return ", ".join(av_products)
            
            # Fallback: assume Windows Defender
            return "Windows Security"
        except Exception:
            return "Windows Security"
    
    def _check_secure_boot(self) -> str:
        """Check if Secure Boot is enabled (Windows)."""
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Confirm-SecureBootUEFI"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=_SUBPROCESS_FLAGS
            )
            
            if result.returncode == 0:
                output = result.stdout.strip().lower()
                if "true" in output:
                    return "Enabled"
                elif "false" in output:
                    return "Disabled"
            return "N/A"
        except Exception:
            return "N/A"
    
    def _check_tpm(self) -> str:
        """Check if TPM is present (Windows)."""
        try:
            result = subprocess.run(
                ["powershell", "-Command", 
                 "Get-Tpm | Select-Object -ExpandProperty TpmPresent"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=_SUBPROCESS_FLAGS
            )
            
            if result.returncode == 0:
                output = result.stdout.strip().lower()
                if "true" in output:
                    return "Present"
                elif "false" in output:
                    return "Not Present"
            return "Unknown"
        except Exception:
            return "Unknown"
    
    def _check_linux_firewall(self) -> str:
        """Check Linux firewall status (ufw or firewalld)."""
        try:
            # Try ufw first
            result = subprocess.run(
                ["ufw", "status"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                output = result.stdout.lower()
                if "status: active" in output:
                    return "Enabled (ufw)"
                elif "status: inactive" in output:
                    return "Disabled (ufw)"
        except Exception:
            pass
        
        try:
            # Try firewalld
            result = subprocess.run(
                ["firewall-cmd", "--state"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and "running" in result.stdout.lower():
                return "Enabled (firewalld)"
        except Exception:
            pass
        
        return "Unknown"
    
    def _check_linux_antivirus(self) -> str:
        """Check for ClamAV or other AV on Linux."""
        try:
            result = subprocess.run(
                ["which", "clamscan"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                return "ClamAV Installed"
            return "None Detected"
        except Exception:
            return "None Detected"
    
    def _check_apparmor(self) -> str:
        """Check if AppArmor is enabled (Linux)."""
        try:
            result = subprocess.run(
                ["aa-enabled"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return "Enabled"
            return "Disabled"
        except Exception:
            # Check via /sys
            try:
                with open('/sys/module/apparmor/parameters/enabled', 'r') as f:
                    if f.read().strip() == 'Y':
                        return "Enabled"
            except Exception:
                pass
            return "N/A"
    
    def _check_selinux(self) -> str:
        """Check if SELinux is enabled (Linux)."""
        try:
            result = subprocess.run(
                ["getenforce"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                status = result.stdout.strip()
                return status if status else "Disabled"
            return "N/A"
        except Exception:
            return "N/A"
    
    @Slot()
    def refreshSecurityInfo(self):
        """Manually refresh security information."""
        self._update_security_info()

