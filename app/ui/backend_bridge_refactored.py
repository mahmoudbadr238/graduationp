"""
Backend Bridge - QObject facade connecting QML frontend to Python services.

Architecture:
  - Exposes system monitoring, event reading, scanning services via Qt signals/slots
  - Async operations run in QThreadPool with watchdog monitoring
  - All signals are thread-safe (emitted from worker threads, queued to main)
  - Implements result caching for expensive operations
  - User-friendly toast notifications for all outcomes

Signals emitted to QML:
  - snapshotUpdated(data: dict)            # System metrics update
  - eventsLoaded(events: list)             # Windows events
  - scansLoaded(scans: list)               # Scan history
  - scanFinished(type: str, result: dict)  # Scan completion
  - toast(level: str, message: str)        # Notification

Data Models:
  - SystemSnapshotModel: Real-time CPU, RAM, GPU, disk, network metrics
  - ScanResultModel: File/URL/network scan results with cache
  - EventModel: Windows event log with filtering

Async Workers:
  - LoadEventsWorker: Reads Windows event log
  - NetworkScanWorker: Runs nmap scan
  - FileS canWorker: Analyzes files with VirusTotal
  - UrlScanWorker: Checks URL reputation
"""

import logging
from datetime import datetime
from typing import Any, Optional

from PySide6.QtCore import QObject, QThreadPool, QTimer, Signal, Slot

from ..core.container import DI
from ..core.errors import ExternalToolMissing, IntegrationDisabled
from ..core.interfaces import (
    IEventReader,
    IEventRepository,
    IFileScanner,
    INetworkScanner,
    IScanRepository,
    ISystemMonitor,
    IUrlScanner,
)
from ..core.result_cache import get_scan_cache
from ..core.types import ScanRecord, ScanType
from ..core.workers import CancellableWorker, get_watchdog

logger = logging.getLogger(__name__)


class SystemSnapshotModel:
    """
    Data model for system metrics snapshot.

    Thread-safe representation of CPU, memory, GPU, disk, and network metrics.
    Updated every 2-3 seconds during live monitoring.
    """

    def __init__(self):
        """Initialize empty snapshot."""
        self.timestamp = datetime.now().isoformat()
        self.cpu = {
            "percent": 0.0,  # Global CPU %
            "cores": [],  # Per-core metrics
            "count": 0,  # Core count
        }
        self.memory = {
            "totalMB": 0,
            "usedMB": 0,
            "availableMB": 0,
            "percent": 0.0,
        }
        self.disk = {
            "totalMB": 0,
            "usedMB": 0,
            "freeMB": 0,
            "percent": 0.0,
        }
        self.gpu = {
            "count": 0,
            "devices": [],  # List of GPU metrics
        }
        self.network = {
            "interfaces": [],
            "connections": 0,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for QML."""
        return {
            "timestamp": self.timestamp,
            "cpu": self.cpu,
            "memory": self.memory,
            "disk": self.disk,
            "gpu": self.gpu,
            "network": self.network,
        }

    @staticmethod
    def from_monitor_snapshot(data: dict) -> "SystemSnapshotModel":
        """Create from system monitor snapshot dict."""
        model = SystemSnapshotModel()
        model.timestamp = data.get("timestamp", model.timestamp)
        model.cpu = data.get("cpu", model.cpu)
        model.memory = data.get("memory", model.memory)
        model.disk = data.get("disk", model.disk)
        model.gpu = data.get("gpu", model.gpu)
        model.network = data.get("network", model.network)
        return model


class BackendBridge(QObject):
    """
    Main QObject bridge exposing backend services to QML.

    Connects Python service layer (system monitor, event reader, scanners)
    to Qt/QML frontend with proper async/threading support.

    Features:
      - Live system monitoring (2-3s refresh rate)
      - Async event log loading with watchdog
      - Network scanning with result caching
      - File/URL scanning with progress updates
      - Toast notifications for all operations
      - Automatic error recovery and user-friendly messages

    Usage from QML:
        backend.startLive()           # Start live system monitoring
        backend.loadRecentEvents()    # Load Windows event log async
        backend.runNetworkScan("192.168.1.0/24", fast=true)  # Async scan
        backend.scanFile("/path/to/file")  # Async file scan
    """

    # System monitoring
    snapshotUpdated = Signal(dict)  # Real-time system metrics

    # Event log
    eventsLoaded = Signal(list)  # Windows event log

    # Scan results
    scansLoaded = Signal(list)  # Scan history
    scanFinished = Signal(str, dict)  # type (network/file/url), result

    # User notifications
    toast = Signal(str, str)  # level (success/error/warning/info), message

    # Progress updates
    scanProgress = Signal(str, int)  # task_id, percent (0-100)

    # Nmap scan signals (streaming output)
    nmapScanStarted = Signal(str, str, str)  # scanId, scanType, targetHost
    nmapScanOutput = Signal(str, str)  # scanId, outputText
    nmapScanFinished = Signal(
        str, bool, int, str
    )  # scanId, success, exitCode, reportPath

    def __init__(self):
        """Initialize backend bridge and resolve dependencies."""
        super().__init__()

        # Check nmap availability on init
        from ..infra.nmap_cli import check_nmap_installed

        self._nmap_available, self._nmap_path = check_nmap_installed()
        logger.info(f"Nmap available: {self._nmap_available}, path: {self._nmap_path}")

        # Resolve required services from DI container
        self.sys_monitor = DI.resolve(ISystemMonitor)
        self.event_reader = DI.resolve(IEventReader)
        self.scan_repo = DI.resolve(IScanRepository)
        self.event_repo = DI.resolve(IEventRepository)

        # Resolve optional services (may fail if disabled/not configured)
        self.net_scanner: Optional[INetworkScanner] = None
        self.file_scanner: Optional[IFileScanner] = None
        self.url_scanner: Optional[IUrlScanner] = None

        try:
            self.net_scanner = DI.resolve(INetworkScanner)
        except (IntegrationDisabled, ExternalToolMissing) as e:
            logger.warning(f"Network scanner unavailable: {e}")

        try:
            self.file_scanner = DI.resolve(IFileScanner)
        except IntegrationDisabled as e:
            logger.warning(f"File scanner unavailable: {e}")

        try:
            self.url_scanner = DI.resolve(IUrlScanner)
        except IntegrationDisabled as e:
            logger.warning(f"URL scanner unavailable: {e}")

        # Thread pool and watchdog
        self._thread_pool = QThreadPool.globalInstance()
        # Increase thread pool size for better concurrency with multiple scanners
        self._thread_pool.setMaxThreadCount(max(8, self._thread_pool.maxThreadCount()))
        self._watchdog = get_watchdog()
        self._watchdog.workerStalled.connect(self._on_worker_stalled)

        # Live monitoring timer (updates every 3 seconds)
        self.live_timer = QTimer()
        self.live_timer.timeout.connect(self._on_live_tick)
        self._last_snapshot: Optional[SystemSnapshotModel] = None

        # Result caching (30 min TTL for expensive scans)
        self._cache = get_scan_cache()

        # Active workers (for cancellation)
        self._active_workers: dict[str, CancellableWorker] = {}

        logger.info(
            "Backend bridge initialized with services: "
            f"monitor={'yes' if self.sys_monitor else 'no'}, "
            f"events={'yes' if self.event_reader else 'no'}, "
            f"nmap={'yes' if self.net_scanner else 'no'}, "
            f"vt={'yes' if self.file_scanner else 'no'}"
        )

    # ============ Live System Monitoring ============

    @Slot()
    def startLive(self) -> None:
        """Start live system monitoring (3 second interval)."""
        if not self.live_timer.isActive():
            self.live_timer.start(3000)
            self._on_live_tick()  # Emit first snapshot immediately
            logger.info("Live monitoring started")
            self.toast.emit("info", "System monitoring started")

    @Slot()
    def stopLive(self) -> None:
        """Stop live system monitoring."""
        if self.live_timer.isActive():
            self.live_timer.stop()
            logger.info("Live monitoring stopped")

    def _on_live_tick(self) -> None:
        """Timer callback: fetch and emit current system snapshot."""
        try:
            snapshot_dict = self.sys_monitor.snapshot()
            self._last_snapshot = SystemSnapshotModel.from_monitor_snapshot(
                snapshot_dict
            )
            self.snapshotUpdated.emit(self._last_snapshot.to_dict())

        except Exception as e:
            logger.exception(f"Snapshot error: {e}")
            self.toast.emit("error", f"Failed to get system metrics: {e!s}")

    # ============ Event Log Loading ============

    @Slot()
    def loadRecentEvents(self) -> None:
        """Load recent Windows event log entries (async with watchdog)."""
        worker_id = "load-events"

        def load_task(worker: CancellableWorker):
            """Background task: read event log."""
            worker.emit_heartbeat()

            # Read events from Windows event log
            events = self.event_reader.tail(limit=300)

            # Store in local database
            self.event_repo.add_many(events)

            worker.emit_heartbeat()
            return events

        def on_success(wid: str, events: list) -> None:
            """Event loading succeeded."""
            try:
                # Convert EventItem objects to dicts for QML
                event_dicts = [
                    {
                        "timestamp": evt.timestamp.isoformat(),
                        "level": evt.level,
                        "source": evt.source,
                        "message": evt.message,
                    }
                    for evt in events
                ]

                self.eventsLoaded.emit(event_dicts)
                msg = f"Loaded {len(events)} event records"
                logger.info(msg)
                self.toast.emit("success", msg)

            finally:
                self._watchdog.unregister_worker(worker_id)
                if worker_id in self._active_workers:
                    del self._active_workers[worker_id]

        def on_error(wid: str, error_msg: str) -> None:
            """Event loading failed."""
            logger.error(f"Failed to load events: {error_msg}")
            self.toast.emit("error", f"Event log error: {error_msg}")
            self.eventsLoaded.emit([])
            self._watchdog.unregister_worker(worker_id)
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]

        # Create and start worker
        worker = CancellableWorker(
            worker_id,
            load_task,
            timeout_ms=10000,
        )
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)

        self._active_workers[worker_id] = worker
        self._watchdog.register_worker(worker_id)
        self._thread_pool.start(worker)

        logger.info("Event loading started")
        self.toast.emit("info", "Loading event log...")

    @Slot()
    def loadScanHistory(self) -> None:
        """Load all scan records from database (async)."""
        worker_id = "load-scans"

        def load_task(worker: CancellableWorker):
            """Background task: read scan history."""
            worker.emit_heartbeat()
            scans = self.scan_repo.get_all()
            worker.emit_heartbeat()
            return scans

        def on_success(wid: str, scans: list) -> None:
            """Scan history loaded."""
            try:
                scan_dicts = [
                    {
                        "id": scan.id or 0,
                        "type": (
                            scan.type.value
                            if hasattr(scan.type, "value")
                            else str(scan.type)
                        ),
                        "target": scan.target or "",
                        "status": scan.status or "unknown",
                        "started_at": (
                            scan.started_at.isoformat() if scan.started_at else ""
                        ),
                        "finished_at": (
                            scan.finished_at.isoformat() if scan.finished_at else ""
                        ),
                        "findings": scan.findings or {},
                    }
                    for scan in scans
                ]

                self.scansLoaded.emit(scan_dicts)
                logger.info(f"Loaded {len(scan_dicts)} scan records")
                if len(scan_dicts) > 0:
                    self.toast.emit("info", f"Loaded {len(scan_dicts)} scans")

            finally:
                self._watchdog.unregister_worker(worker_id)
                if worker_id in self._active_workers:
                    del self._active_workers[worker_id]

        def on_error(wid: str, error_msg: str) -> None:
            """Scan history load failed."""
            logger.error(f"Failed to load scans: {error_msg}")
            self.toast.emit("error", f"Scan history error: {error_msg}")
            self.scansLoaded.emit([])
            self._watchdog.unregister_worker(worker_id)
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]

        worker = CancellableWorker(worker_id, load_task, timeout_ms=15000)
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)

        self._active_workers[worker_id] = worker
        self._watchdog.register_worker(worker_id)
        self._thread_pool.start(worker)

        logger.info("Scan history loading started")

    # ============ Network Scanning ============

    @Slot(str, bool)
    def runNetworkScan(self, target: str, fast: bool = True) -> None:
        """
        Run network scan (async with caching).

        Args:
            target: IP, hostname, or CIDR range
            fast: Quick scan (True) or comprehensive (False)
        """
        if not self.net_scanner:
            self.toast.emit("error", "Nmap not available - network scanning disabled")
            logger.warning("Network scan attempted but nmap unavailable")
            return

        if not target or not target.strip():
            self.toast.emit("error", "Target IP/CIDR cannot be empty")
            return

        # Check cache first
        cache_key = f"nmap:{target}:fast={fast}"
        cached = self._cache.get(cache_key)

        if cached:
            logger.info(f"Network scan cache hit for {target}")
            self.scanFinished.emit("network", cached)
            self.toast.emit("info", f"Loaded cached results for {target}")
            return

        worker_id = f"nmap-{target}"

        def scan_task(worker: CancellableWorker):
            """Background task: run nmap scan."""
            worker.emit_heartbeat()
            self.toast.emit("info", f"Scanning network: {target}")

            result = self.net_scanner.scan(target, fast=fast)

            worker.emit_heartbeat()
            return result

        def on_success(wid: str, result: dict) -> None:
            """Network scan succeeded."""
            try:
                # Create scan record
                scan_rec = ScanRecord(
                    id=None,
                    started_at=datetime.now(),
                    finished_at=datetime.now(),
                    type=ScanType.NETWORK,
                    target=target,
                    status=result.get("status", "completed"),
                    findings=result,
                    meta={"fast": fast},
                )

                scan_id = self.scan_repo.add(scan_rec)
                result["scan_id"] = scan_id

                # Cache for 30 minutes
                self._cache.set(cache_key, result, ttl_seconds=1800)

                hosts = len(result.get("hosts", []))
                self.scanFinished.emit("network", result)
                msg = f"Network scan complete: {hosts} hosts found"
                logger.info(msg)
                self.toast.emit("success", msg)

            finally:
                self._watchdog.unregister_worker(worker_id)
                if worker_id in self._active_workers:
                    del self._active_workers[worker_id]

        def on_error(wid: str, error_msg: str) -> None:
            """Network scan failed."""
            logger.error(f"Network scan failed: {error_msg}")
            self.toast.emit("error", f"Scan failed: {error_msg}")
            self.scanFinished.emit("network", {"error": error_msg})
            self._watchdog.unregister_worker(worker_id)
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]

        worker = CancellableWorker(
            worker_id,
            scan_task,
            timeout_ms=120000,  # 2 minute timeout for scans
        )
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)

        self._active_workers[worker_id] = worker
        # Use extended threshold for network scans (nmap can take time)
        from app.core.workers import WorkerWatchdog

        self._watchdog.register_worker(
            worker_id, stale_threshold_sec=WorkerWatchdog.EXTENDED_STALE_THRESHOLD_SEC
        )
        self._thread_pool.start(worker)

        logger.info(f"Network scan started for {target}")

    # ============ File Scanning ============

    @Slot(str)
    def scanFile(self, path: str) -> None:
        """
        Scan file for threats (async).

        Args:
            path: Absolute file path
        """
        if not self.file_scanner:
            self.toast.emit(
                "error", "File scanning unavailable - VirusTotal API key required"
            )
            return

        if not path or not path.strip():
            self.toast.emit("error", "File path cannot be empty")
            return

        worker_id = f"scan-file-{hash(path)}"

        def scan_task(worker: CancellableWorker):
            """Background task: scan file."""
            worker.emit_heartbeat()
            self.toast.emit("info", f"Scanning file: {path}")

            result = self.file_scanner.scan_file(path)

            worker.emit_heartbeat()
            return result

        def on_success(wid: str, result: dict) -> None:
            """File scan succeeded."""
            try:
                if "error" in result:
                    self.toast.emit("error", result["error"])
                    self.scanFinished.emit("file", result)
                    return

                # Create scan record
                scan_rec = ScanRecord(
                    id=None,
                    started_at=datetime.now(),
                    finished_at=datetime.now(),
                    type=ScanType.FILE,
                    target=path,
                    status="completed",
                    findings=result,
                    meta={},
                )

                scan_id = self.scan_repo.add(scan_rec)
                result["scan_id"] = scan_id

                self.scanFinished.emit("file", result)

                # Check VirusTotal results
                if result.get("vt_check") and result.get("vt_result", {}).get("found"):
                    vt = result["vt_result"]
                    malicious = vt.get("malicious", 0)
                    if malicious > 0:
                        self.toast.emit(
                            "warning",
                            f"[WARNING] File flagged by {malicious} antivirus engines",
                        )
                    else:
                        self.toast.emit("success", "[OK] File appears clean")
                else:
                    self.toast.emit("success", "[OK] File scanned successfully")

            finally:
                self._watchdog.unregister_worker(worker_id)
                if worker_id in self._active_workers:
                    del self._active_workers[worker_id]

        def on_error(wid: str, error_msg: str) -> None:
            """File scan failed."""
            logger.error(f"File scan failed: {error_msg}")
            self.toast.emit("error", f"File scan error: {error_msg}")
            self.scanFinished.emit("file", {"error": error_msg})
            self._watchdog.unregister_worker(worker_id)
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]

        worker = CancellableWorker(
            worker_id,
            scan_task,
            timeout_ms=60000,
        )
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)

        self._active_workers[worker_id] = worker
        self._watchdog.register_worker(worker_id)
        self._thread_pool.start(worker)

        logger.info(f"File scan started for {path}")

    # ============ URL Scanning ============

    @Slot(str)
    def scanUrl(self, url: str) -> None:
        """
        Scan URL for threats (async).

        Args:
            url: URL to scan
        """
        if not self.url_scanner:
            self.toast.emit(
                "error", "URL scanning unavailable - VirusTotal API key required"
            )
            return

        if not url or not url.strip():
            self.toast.emit("error", "URL cannot be empty")
            return

        worker_id = f"scan-url-{hash(url)}"

        def scan_task(worker: CancellableWorker):
            """Background task: scan URL."""
            worker.emit_heartbeat()
            self.toast.emit("info", f"Scanning URL: {url}")

            result = self.url_scanner.scan_url(url)

            worker.emit_heartbeat()
            return result

        def on_success(wid: str, result: dict) -> None:
            """URL scan succeeded."""
            try:
                if "error" in result:
                    self.toast.emit("error", result["error"])
                    self.scanFinished.emit("url", result)
                    return

                # Create scan record
                scan_rec = ScanRecord(
                    id=None,
                    started_at=datetime.now(),
                    finished_at=datetime.now(),
                    type=ScanType.URL,
                    target=url,
                    status=result.get("status", "completed"),
                    findings=result,
                    meta={},
                )

                scan_id = self.scan_repo.add(scan_rec)
                result["scan_id"] = scan_id

                self.scanFinished.emit("url", result)

                if result.get("status") == "submitted":
                    self.toast.emit("info", "URL submitted for analysis")
                elif result.get("found"):
                    malicious = result.get("malicious", 0)
                    if malicious > 0:
                        self.toast.emit(
                            "warning", f"[WARNING] URL flagged by {malicious} engines"
                        )
                    else:
                        self.toast.emit("success", "[OK] URL appears clean")

            finally:
                self._watchdog.unregister_worker(worker_id)
                if worker_id in self._active_workers:
                    del self._active_workers[worker_id]

        def on_error(wid: str, error_msg: str) -> None:
            """URL scan failed."""
            logger.error(f"URL scan failed: {error_msg}")
            self.toast.emit("error", f"URL scan error: {error_msg}")
            self.scanFinished.emit("url", {"error": error_msg})
            self._watchdog.unregister_worker(worker_id)
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]

        worker = CancellableWorker(
            worker_id,
            scan_task,
            timeout_ms=60000,
        )
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)

        self._active_workers[worker_id] = worker
        self._watchdog.register_worker(worker_id)
        self._thread_pool.start(worker)

        logger.info(f"URL scan started for {url}")

    # ============ Nmap Scan (Streaming) ============

    @Slot(str, str)
    def runNmapScan(self, scan_type: str, target_host: str) -> None:
        """
        Run Nmap scan with streaming output.

        Args:
            scan_type: One of the scan profile types (host_discovery, port_scan, etc.)
            target_host: Target IP/hostname (empty string for network-wide scans)
        """
        # Check nmap availability first (double-check, UI should also check)
        if not self._nmap_available:
            self.toast.emit(
                "error", "Nmap is not installed. Please install from https://nmap.org"
            )
            self.nmapScanFinished.emit("", False, 1, "")
            return

        # Generate scan ID
        from datetime import datetime

        scan_id = f"{scan_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        target = target_host.strip() if target_host else ""

        # Emit started signal
        self.nmapScanStarted.emit(scan_id, scan_type, target)

        worker_id = f"nmap-{scan_id}"

        # Accumulated output for this scan
        accumulated_output = []

        def scan_task(worker: CancellableWorker):
            """Background task: run nmap scan with streaming."""
            worker.emit_heartbeat()

            from ..infra.nmap_cli import (
                NmapCli,
                SCAN_PROFILES,
                get_local_subnet,
                get_reports_dir,
            )
            import subprocess
            import sys

            # Get scan profile
            profile = SCAN_PROFILES.get(scan_type)
            if not profile:
                return {
                    "success": False,
                    "exit_code": 1,
                    "report_path": "",
                    "error": f"Unknown scan type: {scan_type}",
                }

            # Determine target
            if profile["requires_host"]:
                if not target:
                    return {
                        "success": False,
                        "exit_code": 1,
                        "report_path": "",
                        "error": "Target host required",
                    }

                # Validate target
                is_valid, error_msg = NmapCli.validate_target(target)
                if not is_valid:
                    return {
                        "success": False,
                        "exit_code": 1,
                        "report_path": "",
                        "error": error_msg,
                    }

                scan_target = target
            else:
                # Network-wide scan
                scan_target = get_local_subnet()
                self.nmapScanOutput.emit(
                    scan_id, f"[INFO] Auto-detected local subnet: {scan_target}\n"
                )

            worker.emit_heartbeat()

            # Build command
            cmd = [self._nmap_path] + profile["args"] + [scan_target]
            timeout = profile.get("timeout", 1800)

            # Emit command info
            self.nmapScanOutput.emit(
                scan_id, f"[INFO] Starting: {profile['description']}\n"
            )
            self.nmapScanOutput.emit(scan_id, f"[INFO] Target: {scan_target}\n")
            self.nmapScanOutput.emit(scan_id, f"[INFO] Command: {' '.join(cmd)}\n")
            self.nmapScanOutput.emit(scan_id, "-" * 60 + "\n\n")

            # Platform-specific flags
            _IS_WINDOWS = sys.platform == "win32"
            flags = subprocess.CREATE_NO_WINDOW if _IS_WINDOWS else 0

            try:
                # Start process
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=flags,
                )

                # Stream output
                from datetime import datetime as dt

                start_time = dt.now()

                for line in iter(process.stdout.readline, ""):
                    if not line:
                        break

                    accumulated_output.append(line)
                    self.nmapScanOutput.emit(scan_id, line)
                    worker.emit_heartbeat()

                    # Check timeout
                    elapsed = (dt.now() - start_time).total_seconds()
                    if elapsed > timeout:
                        process.kill()
                        self.nmapScanOutput.emit(
                            scan_id, f"\n[ERROR] Scan timed out after {timeout}s\n"
                        )
                        return {"success": False, "exit_code": -1, "report_path": ""}

                    # Check cancellation
                    if worker.is_cancelled():
                        process.kill()
                        self.nmapScanOutput.emit(
                            scan_id, "\n[CANCELLED] Scan was cancelled\n"
                        )
                        return {"success": False, "exit_code": -2, "report_path": ""}

                process.stdout.close()
                exit_code = process.wait()

                # Save report
                report_path = get_reports_dir() / f"nmap_{scan_id}.txt"
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(f"Nmap Scan Report\n")
                    f.write(f"================\n")
                    f.write(f"Scan Type: {profile['description']}\n")
                    f.write(f"Target: {scan_target}\n")
                    f.write(f"Date: {dt.now().isoformat()}\n")
                    f.write(f"Command: {' '.join(cmd)}\n")
                    f.write("-" * 60 + "\n\n")
                    f.writelines(accumulated_output)

                success = exit_code == 0
                return {
                    "success": success,
                    "exit_code": exit_code,
                    "report_path": str(report_path),
                }

            except FileNotFoundError:
                return {
                    "success": False,
                    "exit_code": 1,
                    "report_path": "",
                    "error": "Nmap not found",
                }
            except Exception as e:
                return {
                    "success": False,
                    "exit_code": 1,
                    "report_path": "",
                    "error": str(e),
                }

        def on_success(wid: str, result: dict) -> None:
            """Scan completed."""
            success = result.get("success", False)
            exit_code = result.get("exit_code", 1)
            report_path = result.get("report_path", "")

            if success:
                self.nmapScanOutput.emit(scan_id, f"\n[SUCCESS] Scan completed\n")
                self.nmapScanOutput.emit(
                    scan_id, f"[INFO] Report saved: {report_path}\n"
                )
                self.toast.emit("success", "Nmap scan completed")
            else:
                error = result.get("error", "Unknown error")
                self.nmapScanOutput.emit(scan_id, f"\n[ERROR] {error}\n")
                self.toast.emit("error", f"Scan failed: {error}")

            self.nmapScanFinished.emit(scan_id, success, exit_code, report_path)

            self._watchdog.unregister_worker(worker_id)
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]

        def on_error(wid: str, error_msg: str) -> None:
            """Scan failed."""
            self.nmapScanOutput.emit(scan_id, f"\n[ERROR] {error_msg}\n")
            self.toast.emit("error", f"Scan error: {error_msg}")
            self.nmapScanFinished.emit(scan_id, False, 1, "")

            self._watchdog.unregister_worker(worker_id)
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]

        # Create and start worker
        worker = CancellableWorker(
            worker_id,
            scan_task,
            timeout_ms=3600000,  # 1 hour max for vuln scans
        )
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)

        self._active_workers[worker_id] = worker
        from app.core.workers import WorkerWatchdog

        self._watchdog.register_worker(
            worker_id, stale_threshold_sec=WorkerWatchdog.EXTENDED_STALE_THRESHOLD_SEC
        )
        self._thread_pool.start(worker)

        logger.info(f"Nmap scan started: {scan_type} -> {target or 'local network'}")

    @Slot(str)
    def exportNmapScanReport(self, scan_id: str) -> None:
        """Request export of scan report (re-save if needed)."""
        # For now, reports are auto-saved. This could open file dialog in future.
        self.toast.emit("info", "Report was auto-saved during scan")

    @Slot(str)
    def openNmapReport(self, report_path: str) -> None:
        """Open a saved report file."""
        import os
        import sys

        if not os.path.exists(report_path):
            self.toast.emit("error", "Report file not found")
            return

        try:
            if sys.platform == "win32":
                os.startfile(report_path)
            elif sys.platform == "darwin":
                import subprocess

                subprocess.run(["open", report_path], check=False)
            else:
                import subprocess

                subprocess.run(["xdg-open", report_path], check=False)

            self.toast.emit("success", "Opening report...")
        except Exception as e:
            self.toast.emit("error", f"Could not open report: {e}")

    # ============ Status Query Methods ============

    @Slot(result=bool)
    def nmapAvailable(self) -> bool:
        """Check if Nmap is installed and available."""
        return self._nmap_available

    @Slot(result=str)
    def nmapPath(self) -> str:
        """Get the path to nmap executable."""
        return self._nmap_path or ""

    @Slot(result=bool)
    def virusTotalEnabled(self) -> bool:
        """Check if VirusTotal integration is available."""
        return self.file_scanner is not None and self.url_scanner is not None

    # ============ Error Handling ============

    def _on_worker_stalled(self, worker_id: str, elapsed_sec: float) -> None:
        """Handle stalled worker detection from watchdog."""
        logger.warning(f"Worker stalled: {worker_id} ({elapsed_sec:.1f}s no heartbeat)")
        self.toast.emit(
            "warning", f"Task '{worker_id}' appears stalled, attempting cancellation"
        )

        # Attempt cancellation
        if worker_id in self._active_workers:
            self._active_workers[worker_id].cancel()
            del self._active_workers[worker_id]

    # ============ Export Functions ============

    @Slot(str)
    def exportScanHistoryCSV(self, path: str) -> None:
        """Export all scan history to CSV file (async)."""
        worker_id = "export-csv"

        def export_task(worker: CancellableWorker):
            """Background task: export CSV."""
            import csv
            from pathlib import Path

            worker.emit_heartbeat()

            # Ensure directory exists
            Path(path).parent.mkdir(parents=True, exist_ok=True)

            scans = self.scan_repo.get_all()

            with open(path, "w", newline="", encoding="utf-8") as f:
                fieldnames = [
                    "ID",
                    "Type",
                    "Target",
                    "Status",
                    "Started At",
                    "Finished At",
                    "Findings",
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for scan in scans:
                    writer.writerow(
                        {
                            "ID": scan.id or "",
                            "Type": (
                                scan.type.value
                                if hasattr(scan.type, "value")
                                else str(scan.type)
                            ),
                            "Target": scan.target or "",
                            "Status": scan.status or "",
                            "Started At": (
                                scan.started_at.isoformat() if scan.started_at else ""
                            ),
                            "Finished At": (
                                scan.finished_at.isoformat() if scan.finished_at else ""
                            ),
                            "Findings": str(scan.findings) if scan.findings else "",
                        }
                    )

            worker.emit_heartbeat()
            return len(scans)

        def on_success(wid: str, count: int) -> None:
            """CSV export succeeded."""
            msg = f"[OK] Exported {count} records to {path}"
            logger.info(msg)
            self.toast.emit("success", msg)
            self._watchdog.unregister_worker(worker_id)

        def on_error(wid: str, error_msg: str) -> None:
            """CSV export failed."""
            logger.error(f"CSV export failed: {error_msg}")
            self.toast.emit("error", f"Export error: {error_msg}")
            self._watchdog.unregister_worker(worker_id)

        worker = CancellableWorker(worker_id, export_task, timeout_ms=30000)
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)

        self._watchdog.register_worker(worker_id)
        self._thread_pool.start(worker)

        logger.info(f"CSV export started to {path}")

    # ============ Cleanup ============

    def cleanup(self) -> None:
        """Clean up resources on app shutdown."""
        logger.info("BackendBridge cleanup")
        self.stopLive()

        # Cancel all active workers
        for worker_id, worker in list(self._active_workers.items()):
            logger.info(f"Cancelling worker: {worker_id}")
            worker.cancel()
            self._watchdog.unregister_worker(worker_id)

        self._active_workers.clear()
