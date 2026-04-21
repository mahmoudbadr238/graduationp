"""Linux System Snapshot Service using native platform posture checks."""

from __future__ import annotations

import logging
import platform
import socket
import threading
import time

import psutil
from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from backend.platform.linux.admin import check_admin
from backend.platform.linux.security_posture import collect_security_info
from backend.platform.linux.storage import load_lsblk_index, normalize_linux_mounts

logger = logging.getLogger(__name__)


class SystemSnapshotService(QObject):
    """Linux system monitoring service using psutil and platform-native checks."""

    cpuUsageChanged = Signal()
    memoryUsageChanged = Signal()
    memoryUsedChanged = Signal()
    memoryTotalChanged = Signal()
    memoryAvailableChanged = Signal()
    diskUsageChanged = Signal()
    diskPartitionsChanged = Signal()
    hiddenDiskPartitionsChanged = Signal()
    showHiddenMountsChanged = Signal()
    netUpBpsChanged = Signal()
    netDownBpsChanged = Signal()
    netUpKbpsChanged = Signal()
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
    networkChanged = Signal()
    gpuChanged = Signal()
    uptimeChanged = Signal()
    processListChanged = Signal()
    servicesChanged = Signal()
    startupItemsChanged = Signal()
    installedAppsChanged = Signal()

    _securityInfoReadyInternal = Signal(dict)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._securityInfoReadyInternal.connect(self._onSecurityInfoReady)

        self._platform = platform.system()

        self._cpu_usage = 0.0
        self._memory_usage = 0.0
        self._memory_used = 0
        self._memory_total = 0
        self._memory_available = 0
        self._disk_usage = 0.0
        self._disk_partitions: list[dict] = []
        self._hidden_disk_partitions: list[dict] = []
        self._show_hidden_mounts = False
        self._security_info: dict = {}
        self._top_processes: list[dict] = []
        self._network_interfaces: list[dict] = []
        self._net_up_bps = 0.0
        self._net_down_bps = 0.0

        self._cpu_name = self._get_cpu_name()
        self._cpu_count = psutil.cpu_count(logical=False) or 1
        self._cpu_count_logical = psutil.cpu_count(logical=True) or 1
        self._cpu_frequency = psutil.cpu_freq()
        self._system_uptime = 0.0
        self._cpu_per_core: list[float] = []

        mem = psutil.virtual_memory()
        self._total_ram_gb = round(mem.total / (1024**3), 1)
        self._used_ram_gb = 0.0
        self._available_ram_gb = 0.0

        self._cpu_chart_data: list[float] = []
        self._memory_chart_data: list[float] = []
        self._network_history_up: list[float] = []
        self._network_history_down: list[float] = []
        self._max_history_points = 60

        self._last_net_io = None
        self._last_net_time = None
        self._last_per_nic_io: dict[str, dict] = {}
        self._active_interface_name = ""
        self._active_interface_ipv4 = ""

        self._notification_service = None
        self._services_list: list[dict] = []
        self._startup_items: list[dict] = []
        self._installed_apps: list[dict] = []

        self._lsblk_index: dict[str, dict] = {}
        self._lsblk_loaded_at = 0.0

        self._update_interval_ms = 2000
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_metrics)

        self._update_metrics()
        self._update_disk_partitions()
        self._update_network_interfaces()
        logger.info("Linux snapshot service initialized")

        QTimer.singleShot(3000, self._update_security_info)

    def set_notification_service(self, service) -> None:
        """Set the notification service for security alerts."""
        self._notification_service = service

    def start(self, interval_ms: int = 5000) -> None:
        """Start periodic monitoring."""
        self._update_interval_ms = interval_ms
        self.updateIntervalMsChanged.emit()
        self._update_metrics()
        self._timer.start(interval_ms)
        logger.info("Linux snapshot service started at %sms", interval_ms)

    def stop(self) -> None:
        """Stop monitoring."""
        self._timer.stop()

    def _refresh_lsblk_index(self, force: bool = False) -> dict[str, dict]:
        now = time.monotonic()
        if force or not self._lsblk_index or (now - self._lsblk_loaded_at) > 20:
            self._lsblk_index = load_lsblk_index()
            self._lsblk_loaded_at = now
        return self._lsblk_index

    def _get_cpu_name(self) -> str:
        """Get CPU model name from /proc/cpuinfo."""
        try:
            with open("/proc/cpuinfo", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
        except OSError:
            pass
        return platform.processor() or "Unknown Processor"

    def _update_system_uptime(self) -> None:
        """Update system uptime in seconds."""
        try:
            boot_time = psutil.boot_time()
            self._system_uptime = time.time() - boot_time
            self.systemUptimeChanged.emit()
            self.uptimeChanged.emit()
        except Exception as exc:
            logger.debug("Failed to refresh uptime: %s", exc)

    @Slot()
    def _update_metrics(self) -> None:
        """Update all system metrics."""
        try:
            self._update_system_uptime()

            cpu = psutil.cpu_percent(interval=0)
            self._cpu_usage = cpu
            self.cpuUsageChanged.emit()

            try:
                per_core = psutil.cpu_percent(interval=0, percpu=True)
                if per_core and per_core != self._cpu_per_core:
                    self._cpu_per_core = per_core
                    self.cpuPerCoreChanged.emit()
            except Exception:
                logger.debug("Per-core CPU metrics unavailable", exc_info=True)

            self._cpu_chart_data.append(cpu)
            if len(self._cpu_chart_data) > self._max_history_points:
                self._cpu_chart_data.pop(0)
            self.cpuChartDataChanged.emit()

            mem = psutil.virtual_memory()
            self._memory_usage = mem.percent
            self.memoryUsageChanged.emit()

            self._memory_chart_data.append(mem.percent)
            if len(self._memory_chart_data) > self._max_history_points:
                self._memory_chart_data.pop(0)
            self.memoryChartDataChanged.emit()

            self._memory_used = mem.used
            self._memory_total = mem.total
            self._memory_available = mem.available
            self.memoryUsedChanged.emit()
            self.memoryTotalChanged.emit()
            self.memoryAvailableChanged.emit()

            self._used_ram_gb = round(mem.used / (1024**3), 1)
            self._available_ram_gb = round(mem.available / (1024**3), 1)

            self._update_disk_partitions()
            self._update_network_throughput()
            self._update_top_processes()
            self._update_network_interfaces()
        except Exception as exc:
            logger.warning("Linux snapshot metric refresh failed: %s", exc)

    def _update_network_throughput(self) -> None:
        try:
            net_io = psutil.net_io_counters()
            current_time = time.time()
            if self._last_net_io and self._last_net_time:
                delta = current_time - self._last_net_time
                if delta > 0:
                    bytes_sent = net_io.bytes_sent - self._last_net_io.bytes_sent
                    bytes_recv = net_io.bytes_recv - self._last_net_io.bytes_recv

                    self._net_up_bps = (bytes_sent / delta) * 8.0
                    self._net_down_bps = (bytes_recv / delta) * 8.0
                    self.netUpBpsChanged.emit()
                    self.netDownBpsChanged.emit()
                    self.netUpKbpsChanged.emit()
                    self.netDownKbpsChanged.emit()

                    self._network_history_up.append(self._net_up_bps)
                    self._network_history_down.append(self._net_down_bps)
                    if len(self._network_history_up) > self._max_history_points:
                        self._network_history_up.pop(0)
                    if len(self._network_history_down) > self._max_history_points:
                        self._network_history_down.pop(0)
                    self.networkHistoryUpChanged.emit()
                    self.networkHistoryDownChanged.emit()

            self._last_net_io = net_io
            self._last_net_time = current_time
        except (PermissionError, OSError) as exc:
            logger.debug("Network throughput unavailable: %s", exc)

    def _update_top_processes(self) -> None:
        try:
            processes = []
            for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    info = proc.info
                    cpu = info.get("cpu_percent")
                    if cpu is None or cpu <= 0:
                        continue
                    processes.append(
                        {
                            "pid": info["pid"],
                            "name": info.get("name") or "Unknown",
                            "cpu": round(cpu, 1),
                            "memory": round(info.get("memory_percent") or 0, 1),
                        }
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            processes.sort(key=lambda item: item["cpu"], reverse=True)
            new_top = processes[:10]
            if new_top != self._top_processes:
                self._top_processes = new_top
                self.topProcessesChanged.emit()
        except (PermissionError, OSError) as exc:
            logger.debug("Top process enumeration unavailable: %s", exc)

    def _update_disk_partitions(self) -> None:
        """Update normalized Linux storage data."""
        try:
            visible, hidden = normalize_linux_mounts(
                list(psutil.disk_partitions(all=True)),
                psutil.disk_usage,
                block_index=self._refresh_lsblk_index(),
            )

            primary_usage = next(
                (
                    part["percent"]
                    for part in visible
                    if part.get("isPrimary") and part.get("usageAvailable") and part.get("percent") is not None
                ),
                None,
            )
            if primary_usage is None:
                primary_usage = next(
                    (
                        part["percent"]
                        for part in visible
                        if part.get("usageAvailable") and part.get("percent") is not None
                    ),
                    0.0,
                )
            self._disk_usage = float(primary_usage or 0.0)
            self.diskUsageChanged.emit()

            if visible != self._disk_partitions:
                self._disk_partitions = visible
                self.diskPartitionsChanged.emit()

            if hidden != self._hidden_disk_partitions:
                self._hidden_disk_partitions = hidden
                self.hiddenDiskPartitionsChanged.emit()
                if self._show_hidden_mounts:
                    self.diskPartitionsChanged.emit()
        except Exception as exc:
            logger.warning("Failed to refresh normalized Linux storage data: %s", exc)

    def _update_network_interfaces(self) -> None:
        """Update network interface information."""
        try:
            interfaces = []
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()

            try:
                io_counters = psutil.net_io_counters(pernic=True)
            except (PermissionError, OSError):
                io_counters = {}

            current_time = time.time()
            max_throughput = 0.0
            active_iface = ""
            active_ipv4 = ""

            for iface_name, addr_list in addrs.items():
                iface_data = {
                    "name": iface_name,
                    "isUp": False,
                    "is_up": False,
                    "speed_mbps": 0,
                    "ipv4": "",
                    "ipv6": "",
                    "mac": "",
                }

                if iface_name in stats:
                    stat = stats[iface_name]
                    iface_data["isUp"] = stat.isup
                    iface_data["is_up"] = stat.isup
                    iface_data["speed_mbps"] = stat.speed if stat.speed > 0 else 0

                for addr in addr_list:
                    if addr.family == socket.AF_INET:
                        iface_data["ipv4"] = addr.address
                    elif addr.family == socket.AF_INET6 and not iface_data["ipv6"]:
                        iface_data["ipv6"] = addr.address.split("%")[0]
                    elif hasattr(psutil, "AF_LINK") and addr.family == psutil.AF_LINK:
                        iface_data["mac"] = addr.address

                interfaces.append(iface_data)

                if iface_name in io_counters and self._last_per_nic_io.get(iface_name):
                    last_io = self._last_per_nic_io[iface_name]
                    curr_io = io_counters[iface_name]
                    delta = current_time - last_io["time"]
                    if delta > 0:
                        total_throughput = (
                            (curr_io.bytes_sent - last_io["bytes_sent"])
                            + (curr_io.bytes_recv - last_io["bytes_recv"])
                        ) / delta
                        if total_throughput > max_throughput:
                            max_throughput = total_throughput
                            active_iface = iface_name
                            active_ipv4 = iface_data["ipv4"]

            for iface_name, io_counter in io_counters.items():
                self._last_per_nic_io[iface_name] = {
                    "bytes_sent": io_counter.bytes_sent,
                    "bytes_recv": io_counter.bytes_recv,
                    "time": current_time,
                }

            if interfaces != self._network_interfaces:
                self._network_interfaces = interfaces
                self.networkInterfacesChanged.emit()
                self.networkChanged.emit()

            if active_iface != self._active_interface_name:
                self._active_interface_name = active_iface
                self._active_interface_ipv4 = active_ipv4
        except Exception as exc:
            logger.warning("Failed to refresh network interfaces: %s", exc)

    def _update_security_info(self) -> None:
        """Gather security information in a background thread."""

        def gather() -> None:
            self._do_update_security_info()

        threading.Thread(target=gather, daemon=True).start()

    def _do_update_security_info(self) -> None:
        """Gather Linux security information (background thread)."""
        try:
            info = collect_security_info(
                is_admin=check_admin(),
                os_name=platform.system() + " " + platform.release(),
                kernel=platform.version(),
                uptime=self._get_system_uptime_str(),
            )
        except Exception as exc:
            logger.warning("Failed to gather Linux security posture: %s", exc)
            info = {
                "firewallStatus": "Unknown",
                "antivirus": "Unknown",
                "antivirusEnabled": False,
                "secureBoot": "Unknown",
                "tpmPresent": "N/A",
                "tpmEnabled": False,
                "tpmVersion": "N/A",
                "appArmorEnabled": "Unknown",
                "selinuxEnabled": "Unknown",
                "osName": platform.system() + " " + platform.release(),
                "kernel": platform.version(),
                "uptime": self._get_system_uptime_str(),
                "diskEncryption": "Unknown",
                "diskEncryptionDetail": "Security posture collection failed.",
                "windowsUpdateStatus": "Unknown",
                "windowsUpdateLastInstall": "",
                "windowsUpdateDetail": "Security posture collection failed.",
                "remoteDesktopEnabled": False,
                "remoteDesktopNla": False,
                "remoteDesktopDetail": "Security posture collection failed.",
                "adminAccountCount": 0,
                "adminAccountDetail": "Security posture collection failed.",
                "uacLevel": "N/A",
                "uacDetail": "Not applicable on Linux.",
                "smartScreenEnabled": False,
                "smartScreenDetail": "Not applicable on Linux.",
                "memoryIntegrityEnabled": False,
                "memoryIntegrityDetail": "Not applicable on Linux.",
                "providers": [{"name": "security-posture", "status": "error", "detail": str(exc)}],
                "simplified": {
                    "overall": {
                        "isGood": False,
                        "isWarning": True,
                        "status": "Unavailable",
                        "detail": "Sentinel could not complete Linux security posture collection.",
                    },
                    "internetProtection": {
                        "isGood": False,
                        "isWarning": True,
                        "status": "Unknown",
                        "detail": "Firewall state unavailable.",
                    },
                    "updates": {
                        "isGood": False,
                        "isWarning": True,
                        "status": "Unknown",
                        "detail": "Package update state unavailable.",
                    },
                    "deviceProtection": {
                        "isGood": False,
                        "isWarning": True,
                        "status": "Unknown",
                        "detail": "Endpoint protection state unavailable.",
                    },
                    "remoteAndApps": {
                        "isGood": False,
                        "isWarning": True,
                        "status": "Unknown",
                        "detail": "Remote exposure state unavailable.",
                    },
                    "raw": {
                        "firewallEnabled": False,
                        "firewallName": "",
                        "antivirusEnabled": False,
                        "antivirusName": "Unknown",
                        "antivirusRealtime": False,
                        "secureBoot": "Unknown",
                        "diskEncryption": "Unknown",
                        "diskEncryptionDetail": "Security posture collection failed.",
                        "windowsUpdateStatus": "Unknown",
                        "windowsUpdateLastInstall": "",
                        "remoteDesktopEnabled": False,
                        "remoteDesktopNla": False,
                        "adminAccountCount": 0,
                        "uacLevel": "N/A",
                        "smartScreenEnabled": False,
                        "memoryIntegrityEnabled": False,
                    },
                },
            }

        self._securityInfoReadyInternal.emit(info)

    def _onSecurityInfoReady(self, info: dict) -> None:
        self._security_info = info
        self.securityInfoChanged.emit()

    def _get_system_uptime_str(self) -> str:
        try:
            uptime_seconds = time.time() - psutil.boot_time()
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            if hours > 0:
                return f"{hours}h {minutes}m"
            return f"{minutes}m"
        except Exception:
            return "Unknown"

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

    @Property("QVariantList", notify=diskPartitionsChanged)
    def diskPartitions(self) -> list[dict]:
        if self._show_hidden_mounts:
            return [*self._disk_partitions, *self._hidden_disk_partitions]
        return self._disk_partitions

    @Property("QVariantList", notify=hiddenDiskPartitionsChanged)
    def hiddenDiskPartitions(self) -> list[dict]:
        return self._hidden_disk_partitions

    @Property(bool, notify=showHiddenMountsChanged)
    def showHiddenMounts(self) -> bool:
        return self._show_hidden_mounts

    @showHiddenMounts.setter
    def showHiddenMounts(self, value: bool) -> None:
        enabled = bool(value)
        if enabled == self._show_hidden_mounts:
            return
        self._show_hidden_mounts = enabled
        self.showHiddenMountsChanged.emit()
        self.diskPartitionsChanged.emit()

    @Property(float, notify=netUpBpsChanged)
    def netUpBps(self) -> float:
        return self._net_up_bps

    @Property(float, notify=netDownBpsChanged)
    def netDownBps(self) -> float:
        return self._net_down_bps

    @Property(float, notify=netUpKbpsChanged)
    def netUpKbps(self) -> float:
        return self._net_up_bps / 1000.0

    @Property(float, notify=netDownKbpsChanged)
    def netDownKbps(self) -> float:
        return self._net_down_bps / 1000.0

    @Property(int, notify=updateIntervalMsChanged)
    def updateIntervalMs(self) -> int:
        return self._update_interval_ms

    @updateIntervalMs.setter
    def updateIntervalMs(self, value: int) -> None:
        if value != self._update_interval_ms and value >= 500:
            self._update_interval_ms = value
            self.updateIntervalMsChanged.emit()
            if self._timer.isActive():
                self._timer.start(value)

    @Property("QVariantList", notify=topProcessesChanged)
    def topProcesses(self) -> list[dict]:
        return self._top_processes

    @Property(str, constant=True)
    def platformName(self) -> str:
        return self._platform

    @Property(bool, constant=True)
    def isWindows(self) -> bool:
        return False

    @Property(bool, constant=True)
    def isAdmin(self) -> bool:
        return check_admin()

    @Property("QVariantList", notify=networkInterfacesChanged)
    def networkInterfaces(self) -> list[dict]:
        return self._network_interfaces

    @Property(str, constant=False)
    def activeInterfaceName(self) -> str:
        return self._active_interface_name

    @Property(str, constant=False)
    def activeInterfaceIpv4(self) -> str:
        return self._active_interface_ipv4

    @Property("QVariantList", notify=cpuChartDataChanged)
    def cpuChartData(self) -> list[float]:
        return self._cpu_chart_data

    @Property("QVariantList", notify=memoryChartDataChanged)
    def memoryChartData(self) -> list[float]:
        return self._memory_chart_data

    @Property("QVariantList", notify=networkHistoryUpChanged)
    def networkHistoryUp(self) -> list[float]:
        return self._network_history_up

    @Property("QVariantList", notify=networkHistoryDownChanged)
    def networkHistoryDown(self) -> list[float]:
        return self._network_history_down

    @Property("QVariantMap", notify=securityInfoChanged)
    def securityInfo(self) -> dict:
        return self._security_info

    @Property(str, notify=cpuNameChanged)
    def cpuName(self) -> str:
        return self._cpu_name

    @Property(int, constant=True)
    def cpuCount(self) -> int:
        return self._cpu_count

    @Property(int, constant=True)
    def cpuCountLogical(self) -> int:
        return self._cpu_count_logical

    @Property(float, constant=True)
    def cpuFrequency(self) -> float:
        if self._cpu_frequency:
            return float(self._cpu_frequency.current)
        return 0.0

    @Property(int, constant=True)
    def cpuCores(self) -> int:
        return self._cpu_count

    @Property(int, constant=True)
    def cpuThreads(self) -> int:
        return self._cpu_count_logical

    @Property(float, constant=True)
    def totalRamGB(self) -> float:
        return self._total_ram_gb

    @Property(float, notify=memoryUsageChanged)
    def usedRamGB(self) -> float:
        return self._used_ram_gb

    @Property(float, notify=memoryUsageChanged)
    def availableRamGB(self) -> float:
        return self._available_ram_gb

    @Property(float, notify=systemUptimeChanged)
    def systemUptime(self) -> float:
        return self._system_uptime

    @Property(float, notify=memoryAvailableChanged)
    def memoryAvailable(self) -> float:
        return float(self._memory_available)

    @Property("QVariantList", notify=cpuPerCoreChanged)
    def cpuPerCore(self) -> list[float]:
        return self._cpu_per_core

    @Slot()
    def refreshSecurityInfo(self) -> None:
        self._update_security_info()
