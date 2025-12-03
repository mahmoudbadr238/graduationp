"""QObject bridge connecting QML frontend to Python backend."""

import logging
from datetime import datetime

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


class BackendBridge(QObject):
    """
    Backend facade exposing signals/slots to QML.

    Signals emitted to QML:
    - snapshotUpdated: System metrics snapshot
    - eventsLoaded: Windows events list
    - toast: Notification message (level, message)
    - scanFinished: Scan completion (type, result)
    """

    # Signals
    snapshotUpdated = Signal(dict)
    eventsLoaded = Signal(list)
    scansLoaded = Signal(list)  # scan history
    toast = Signal(str, str)  # level, message
    scanFinished = Signal(str, dict)  # type, result

    # Nmap scan signals (streaming output)
    nmapScanStarted = Signal(str, str, str)  # scanId, scanType, targetHost
    nmapScanOutput = Signal(str, str)  # scanId, outputText
    nmapScanFinished = Signal(
        str, bool, int, str
    )  # scanId, success, exitCode, reportPath

    # AI signals (100% local, no network)
    eventExplanationReady = Signal(str, str)  # eventId, explanationJson
    chatMessageAdded = Signal(str, str)  # role ("user"|"assistant"), content

    def __init__(self):
        super().__init__()

        # Check nmap availability on init
        from ..infra.nmap_cli import check_nmap_installed

        self._nmap_available, self._nmap_path = check_nmap_installed()
        logger.info(f"Nmap available: {self._nmap_available}, path: {self._nmap_path}")

        # Resolve dependencies from DI container
        self.sys_monitor = DI.resolve(ISystemMonitor)
        self.event_reader = DI.resolve(IEventReader)
        self.scan_repo = DI.resolve(IScanRepository)
        self.event_repo = DI.resolve(IEventRepository)

        # Optional integrations (may fail if disabled/missing)
        try:
            self.net_scanner = DI.resolve(INetworkScanner)
        except (IntegrationDisabled, ExternalToolMissing):
            self.net_scanner = None
            # Silenced - status printed at startup via integrations.py

        try:
            self.file_scanner = DI.resolve(IFileScanner)
        except IntegrationDisabled:
            self.file_scanner = None
            # Silenced - status printed at startup via integrations.py

        try:
            self.url_scanner = DI.resolve(IUrlScanner)
        except IntegrationDisabled:
            self.url_scanner = None
            # Silenced - status printed at startup via integrations.py

        # Timer for live updates (throttled to 1s)
        self.live_timer = QTimer()
        self.live_timer.timeout.connect(self._tick)

        # Thread pool for async operations
        self._thread_pool = QThreadPool.globalInstance()

        # Worker watchdog
        self._watchdog = get_watchdog()
        self._watchdog.workerStalled.connect(self._on_worker_stalled)

        # Result cache
        self._cache = get_scan_cache()

        # Active workers (for cancellation)
        self._active_workers: dict[str, CancellableWorker] = {}

        # AI services (100% local, no network calls)
        self._event_explainer = None
        self._security_chatbot = None
        self._chat_conversation: list[dict[str, str]] = []
        self._init_ai_services()

    def _init_ai_services(self):
        """Initialize local AI services (no network calls)."""
        try:
            from ..ai.local_llm_engine import get_llm_engine
            from ..ai.event_explainer import get_event_explainer
            from ..ai.security_chatbot import get_security_chatbot

            llm_engine = get_llm_engine()
            self._event_explainer = get_event_explainer(llm_engine)

            # Chatbot needs event_repo for context
            self._security_chatbot = get_security_chatbot(
                llm_engine,
                snapshot_service=None,  # Set later via set_snapshot_service
                event_repo=self.event_repo,
            )

            mode = "transformers" if llm_engine.is_available else "fallback"
            logger.info(f"AI services initialized (mode: {mode})")
        except Exception as e:
            logger.warning(f"AI services not available: {e}")
            self._event_explainer = None
            self._security_chatbot = None

    def set_snapshot_service(self, snapshot_service):
        """Set snapshot service for chatbot context (called from application.py)."""
        if self._security_chatbot:
            self._security_chatbot._snapshot_service = snapshot_service
            logger.info("Snapshot service connected to AI chatbot")

    @Slot()
    def startLive(self):
        """Start live system monitoring (3 second interval for smooth updates)."""
        if not self.live_timer.isActive():
            self.live_timer.start(3000)  # 3 seconds - balanced for performance
            self._tick()  # Emit first snapshot immediately
            logger.info("Live monitoring started")

    @Slot()
    def stopLive(self):
        """Stop live system monitoring."""
        if self.live_timer.isActive():
            self.live_timer.stop()
            logger.info("Live monitoring stopped")

    def _tick(self):
        """Timer callback - fetch and emit system snapshot."""
        try:
            snapshot = self.sys_monitor.snapshot()
            self.snapshotUpdated.emit(snapshot)
        except Exception as e:
            logger.exception(f"Monitoring error: {e}")
            self.toast.emit("error", f"Monitoring error: {e!s}")

    @Slot()
    def loadRecentEvents(self):
        """Load recent Windows event log entries (async)."""
        worker_id = "load-events"

        def load_task(worker):
            """Background task to load events"""
            worker.signals.heartbeat.emit(worker_id)
            events = self.event_reader.tail(limit=300)
            worker.signals.heartbeat.emit(worker_id)

            # Store in database
            self.event_repo.add_many(events)

            return events

        def on_success(wid, events):
            """Event loading completed"""
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
            self.toast.emit("success", f"Loaded {len(events)} events")
            self._watchdog.unregister_worker(worker_id)

        def on_error(wid, error_msg):
            """Event loading failed"""
            logger.error(f"Failed to load events: {error_msg}")
            self.toast.emit("error", f"Failed to load events: {error_msg}")
            self.eventsLoaded.emit([])
            self._watchdog.unregister_worker(worker_id)

        # Create and start worker
        worker = CancellableWorker(worker_id, load_task, timeout_ms=10000)
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)

        self._watchdog.register_worker(worker_id)
        self._thread_pool.start(worker)

        logger.info("Loading events asynchronously...")

    @Slot(str, bool)
    def runNetworkScan(self, target: str, fast: bool = True):
        """
        Run network scan on target (async with caching).

        Args:
            target: IP address, hostname, or CIDR range
            fast: Quick scan (True) or comprehensive (False)
        """
        if not self.net_scanner:
            self.toast.emit(
                "error", "Network scanning not available (Nmap not installed)"
            )
            return

        if not target:
            self.toast.emit("error", "Target cannot be empty")
            return

        # Check cache first
        from ..core.result_cache import ResultCache

        cache_key = ResultCache.make_key("nmap", target, fast=fast)
        cached_result = self._cache.get(cache_key)

        if cached_result:
            logger.info(f"Network scan cache hit for {target}")
            self.scanFinished.emit("network", cached_result)
            self.toast.emit("info", f"Loaded cached scan for {target}")
            return

        worker_id = f"nmap-{target}"

        def scan_task(worker):
            """Background scan task"""
            worker.signals.heartbeat.emit(worker_id)
            self.toast.emit("info", f"Starting network scan: {target}")

            result = self.net_scanner.scan(target, fast)
            worker.signals.heartbeat.emit(worker_id)

            return result

        def on_success(wid, result):
            """Scan completed"""
            # Guard against callbacks after worker removal (race condition fix)
            if worker_id not in self._active_workers:
                logger.debug(
                    f"Worker {worker_id} already removed, ignoring success callback"
                )
                return
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

                # Save to database
                scan_id = self.scan_repo.add(scan_rec)
                result["scan_id"] = scan_id

                # Cache result (30 min TTL)
                self._cache.set(cache_key, result, ttl_seconds=1800)

                self.scanFinished.emit("network", result)
                self.toast.emit(
                    "success",
                    f"Network scan completed: {len(result.get('hosts', []))} hosts found",
                )

            finally:
                if worker_id in self._active_workers:
                    del self._active_workers[worker_id]
                self._watchdog.unregister_worker(worker_id)

        def on_error(wid, error_msg):
            """Scan failed"""
            # Guard against callbacks after worker removal (race condition fix)
            if worker_id not in self._active_workers:
                logger.debug(
                    f"Worker {worker_id} already removed, ignoring error callback"
                )
                return
            logger.error(f"Network scan failed: {error_msg}")
            self.toast.emit("error", f"Network scan failed: {error_msg}")
            self.scanFinished.emit("network", {"error": error_msg})
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]
            self._watchdog.unregister_worker(worker_id)

        # Create and start worker
        worker = CancellableWorker(
            worker_id, scan_task, timeout_ms=60000
        )  # 60s timeout
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)

        self._active_workers[worker_id] = worker
        self._watchdog.register_worker(worker_id)
        self._thread_pool.start(worker)

        logger.info(f"Network scan started for {target}")

    def _on_worker_stalled(self, worker_id: str):
        """Handle stalled worker (watchdog notification)"""
        logger.warning(f"Worker stalled: {worker_id}")
        self.toast.emit("warning", f"Task '{worker_id}' appears to be stalled")

        # Attempt to cancel - mark as removed first to prevent callback race
        if worker_id in self._active_workers:
            worker = self._active_workers.pop(worker_id)  # Remove first
            try:
                worker.cancel()
            except Exception as e:
                logger.debug(f"Worker cancel failed (may already be done): {e}")
            # Unregister from watchdog after removal
            try:
                self._watchdog.unregister_worker(worker_id)
            except Exception as e:
                logger.debug(f"Watchdog unregister failed: {e}")

    @Slot(result=bool)
    def nmapAvailable(self):
        """Check if Nmap is available for scanning."""
        return self.net_scanner is not None

    @Slot(result=bool)
    def virusTotalEnabled(self):
        """Check if VirusTotal integration is enabled."""
        return self.file_scanner is not None and self.url_scanner is not None

    @Slot()
    def loadScanHistory(self):
        """Load all scan records from database."""
        try:
            scans = self.scan_repo.get_all()

            # Convert ScanRecord objects to dicts for QML
            scan_dicts = []
            for scan in scans:
                scan_dicts.append(
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
                )

            self.scansLoaded.emit(scan_dicts)
            if len(scan_dicts) > 0:
                self.toast.emit("info", f"Loaded {len(scan_dicts)} scan records")
        except (OSError, ValueError, KeyError) as e:
            self.toast.emit("error", f"Failed to load scan history: {e!s}")
            self.scansLoaded.emit([])

    @Slot(str)
    def exportScanHistoryCSV(self, path: str):
        """Export scan history to CSV file."""
        try:
            import csv
            from pathlib import Path

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

            self.toast.emit("success", f"✓ Exported {len(scans)} records to {path}")

        except (OSError, PermissionError) as e:
            self.toast.emit("error", f"CSV export failed: {e!s}")

    @Slot(str)
    def scanFile(self, path: str):
        """
        Scan a file for threats (async - does not block UI).

        Args:
            path: Absolute path to file
        """
        if not self.file_scanner:
            self.toast.emit(
                "error", "File scanning not available (VirusTotal API key required)"
            )
            return

        if not path:
            self.toast.emit("error", "File path cannot be empty")
            return

        # Validate path length to prevent issues
        if len(path) > 2048:
            self.toast.emit("error", "File path too long")
            return

        worker_id = f"file-scan-{hash(path) % 10000}"

        # Prevent duplicate scans
        if worker_id in self._active_workers:
            self.toast.emit("warning", "File scan already in progress")
            return

        self.toast.emit("info", f"Scanning file: {path}")
        scan_start_time = datetime.now()

        def scan_task(worker):
            """Background file scan task"""
            worker.signals.heartbeat.emit(worker_id)
            return self.file_scanner.scan_file(path)

        def on_success(wid, result):
            """File scan completed"""
            if worker_id not in self._active_workers:
                return
            try:
                if "error" in result:
                    self.toast.emit("error", result["error"])
                    self.scanFinished.emit("file", result)
                    return

                # Create scan record
                scan_rec = ScanRecord(
                    id=None,
                    started_at=scan_start_time,
                    finished_at=datetime.now(),
                    type=ScanType.FILE,
                    target=path,
                    status="completed",
                    findings=result,
                    meta={},
                )

                # Save to database
                scan_id = self.scan_repo.add(scan_rec)
                result["scan_id"] = scan_id

                self.scanFinished.emit("file", result)

                # Check VT results if available
                if result.get("vt_check") and result.get("vt_result", {}).get("found"):
                    vt = result["vt_result"]
                    malicious = vt.get("malicious", 0)
                    if malicious > 0:
                        self.toast.emit(
                            "warning", f"File flagged by {malicious} engines"
                        )
                    else:
                        self.toast.emit("success", "File appears clean")
                else:
                    self.toast.emit(
                        "success", f"File scanned: {result.get('sha256', '')[:16]}..."
                    )
            finally:
                if worker_id in self._active_workers:
                    del self._active_workers[worker_id]
                self._watchdog.unregister_worker(worker_id)

        def on_error(wid, error_msg):
            """File scan failed"""
            if worker_id not in self._active_workers:
                return
            logger.error(f"File scan failed: {error_msg}")
            self.toast.emit("error", f"File scan failed: {error_msg}")
            self.scanFinished.emit("file", {"error": error_msg})
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]
            self._watchdog.unregister_worker(worker_id)

        # Create and start worker with 120s timeout for large files
        worker = CancellableWorker(worker_id, scan_task, timeout_ms=120000)
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)

        self._active_workers[worker_id] = worker
        self._watchdog.register_worker(worker_id)
        self._thread_pool.start(worker)

        logger.info(f"File scan started for {path}")

    @Slot(str)
    def scanUrl(self, url: str):
        """
        Scan a URL for threats (async - does not block UI).

        Args:
            url: URL to scan
        """
        if not self.url_scanner:
            self.toast.emit(
                "error",
                "URL scanning not available (VirusTotal API key not configured)",
            )
            return

        if not url:
            self.toast.emit("error", "URL cannot be empty")
            return

        # Basic URL validation
        if len(url) > 2048:
            self.toast.emit("error", "URL too long")
            return

        worker_id = f"url-scan-{hash(url) % 10000}"

        # Prevent duplicate scans
        if worker_id in self._active_workers:
            self.toast.emit("warning", "URL scan already in progress")
            return

        self.toast.emit("info", f"Scanning URL: {url}")
        scan_start_time = datetime.now()

        def scan_task(worker):
            """Background URL scan task"""
            worker.signals.heartbeat.emit(worker_id)
            return self.url_scanner.scan_url(url)

        def on_success(wid, result):
            """URL scan completed"""
            if worker_id not in self._active_workers:
                return
            try:
                if "error" in result:
                    self.toast.emit("error", result["error"])
                    self.scanFinished.emit("url", result)
                    return

                # Create scan record
                scan_rec = ScanRecord(
                    id=None,
                    started_at=scan_start_time,
                    finished_at=datetime.now(),
                    type=ScanType.URL,
                    target=url,
                    status=result.get("status", "completed"),
                    findings=result,
                    meta={},
                )

                # Save to database
                scan_id = self.scan_repo.add(scan_rec)
                result["scan_id"] = scan_id

                self.scanFinished.emit("url", result)

                # Check results
                if result.get("status") == "submitted":
                    self.toast.emit("info", "URL submitted for analysis")
                elif result.get("found"):
                    malicious = result.get("malicious", 0)
                    if malicious > 0:
                        self.toast.emit(
                            "warning", f"URL flagged by {malicious} engines"
                        )
                    else:
                        self.toast.emit("success", "URL appears clean")
            finally:
                if worker_id in self._active_workers:
                    del self._active_workers[worker_id]
                self._watchdog.unregister_worker(worker_id)

        def on_error(wid, error_msg):
            """URL scan failed"""
            if worker_id not in self._active_workers:
                return
            logger.error(f"URL scan failed: {error_msg}")
            self.toast.emit("error", f"URL scan failed: {error_msg}")
            self.scanFinished.emit("url", {"error": error_msg})
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]
            self._watchdog.unregister_worker(worker_id)

        # Create and start worker with 60s timeout for network operations
        worker = CancellableWorker(worker_id, scan_task, timeout_ms=60000)
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)

        self._active_workers[worker_id] = worker
        self._watchdog.register_worker(worker_id)
        self._thread_pool.start(worker)

        logger.info(f"URL scan started for {url}")

    @Slot(result=list)
    def getScanHistory(self) -> list:
        """Get recent scan history."""
        try:
            records = self.scan_repo.all(limit=50)

            # Convert to dicts for QML
            return [
                {
                    "id": rec.id,
                    "started_at": rec.started_at.isoformat(),
                    "finished_at": (
                        rec.finished_at.isoformat() if rec.finished_at else ""
                    ),
                    "type": rec.type.value,
                    "target": rec.target,
                    "status": rec.status,
                }
                for rec in records
            ]
        except (OSError, ValueError, AttributeError) as e:
            # Database errors or data conversion failures
            self.toast.emit("error", f"Failed to load history: {e!s}")
            return []

    # ============ Nmap Typed Scan (Streaming) ============

    @Slot(result=bool)
    def nmapAvailable(self) -> bool:
        """Check if Nmap is installed and available."""
        return self._nmap_available

    @Slot(result=str)
    def nmapPath(self) -> str:
        """Get the path to nmap executable."""
        return self._nmap_path or ""

    @Slot(str, str)
    def runNmapScan(self, scan_type: str, target_host: str) -> None:
        """
        Run Nmap scan with streaming output.

        Args:
            scan_type: One of the scan profile types (host_discovery, port_scan, etc.)
            target_host: Target IP/hostname (empty string for network-wide scans)
        """
        from ..infra.nmap_cli import (
            SCAN_PROFILES,
            NmapCli,
            get_local_subnet,
            get_reports_dir,
        )
        from ..core.workers import WorkerWatchdog
        import subprocess
        import sys

        # Check nmap availability first
        if not self._nmap_available:
            self.toast.emit(
                "error", "Nmap is not installed. Please install from https://nmap.org"
            )
            self.nmapScanFinished.emit("", False, 1, "")
            return

        # Generate scan ID
        scan_id = f"{scan_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        target = target_host.strip() if target_host else ""

        # Emit started signal
        self.nmapScanStarted.emit(scan_id, scan_type, target)

        worker_id = f"nmap-{scan_id}"

        # Accumulated output for this scan
        accumulated_output = []

        # Get scan profile
        profile = SCAN_PROFILES.get(scan_type)
        if not profile:
            self.toast.emit("error", f"Unknown scan type: {scan_type}")
            self.nmapScanFinished.emit(scan_id, False, 1, "")
            return

        def scan_task(worker: CancellableWorker):
            """Background task: run nmap scan with streaming."""
            worker.signals.heartbeat.emit(worker.worker_id)

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

            worker.signals.heartbeat.emit(worker.worker_id)

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
                start_time = datetime.now()

                for line in iter(process.stdout.readline, ""):
                    if not line:
                        break

                    accumulated_output.append(line)
                    self.nmapScanOutput.emit(scan_id, line)
                    worker.signals.heartbeat.emit(worker.worker_id)

                    # Check timeout
                    elapsed = (datetime.now() - start_time).total_seconds()
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
                    f.write(f"Date: {datetime.now().isoformat()}\n")
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
        self._watchdog.register_worker(
            worker_id, stale_threshold_sec=WorkerWatchdog.EXTENDED_STALE_THRESHOLD_SEC
        )
        self._thread_pool.start(worker)

        logger.info(f"Nmap scan started: {scan_type} -> {target or 'local network'}")

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

    # ==================== AI FEATURES (100% LOCAL) ====================

    @Slot(result=bool)
    def aiAvailable(self) -> bool:
        """Check if AI services are available."""
        return self._event_explainer is not None

    @Slot(result=str)
    def aiMode(self) -> str:
        """Get the current AI mode (transformers or fallback)."""
        if self._event_explainer is None:
            return "unavailable"
        try:
            from ..ai.local_llm_engine import get_llm_engine

            engine = get_llm_engine()
            return "transformers" if engine.is_available else "fallback"
        except Exception:
            return "fallback"

    @Slot(int)
    def requestEventExplanation(self, event_index: int) -> None:
        """
        Request AI explanation for an event by its index in the loaded events.

        Args:
            event_index: Index of the event in the current events list
        """
        if self._event_explainer is None:
            self.toast.emit("error", "AI services not available")
            return

        worker_id = f"ai-explain-{event_index}"

        # Prevent duplicate requests
        if worker_id in self._active_workers:
            return

        def explain_task(worker):
            """Background AI explanation task."""
            worker.signals.heartbeat.emit(worker_id)

            # Get events from repo
            events = self.event_reader.tail(limit=300)
            if event_index < 0 or event_index >= len(events):
                raise ValueError(f"Event index {event_index} out of range")

            event = events[event_index]

            # Build event dict for explainer
            event_dict = {
                "log_name": getattr(event, "log_name", "Windows"),
                "provider": getattr(event, "source", "Unknown"),
                "source": getattr(event, "source", "Unknown"),
                "event_id": getattr(event, "event_id", 0),
                "level": getattr(event, "level", "Information"),
                "message": getattr(event, "message", ""),
                "time_created": (
                    getattr(event, "timestamp", "").isoformat()
                    if hasattr(getattr(event, "timestamp", None), "isoformat")
                    else str(getattr(event, "timestamp", ""))
                ),
            }

            worker.signals.heartbeat.emit(worker_id)

            # Get explanation
            explanation = self._event_explainer.explain_event(event_dict)

            return (str(event_index), explanation)

        def on_success(wid: str, result: tuple) -> None:
            """Explanation completed."""
            event_id, explanation = result
            import json

            try:
                explanation_json = json.dumps(explanation)
                self.eventExplanationReady.emit(event_id, explanation_json)
            except Exception as e:
                logger.error(f"Failed to serialize explanation: {e}")
                self.toast.emit("error", "Failed to process AI explanation")
            finally:
                self._watchdog.unregister_worker(worker_id)
                if worker_id in self._active_workers:
                    del self._active_workers[worker_id]

        def on_error(wid: str, error_msg: str) -> None:
            """Explanation failed."""
            logger.error(f"AI explanation failed: {error_msg}")
            self.toast.emit("error", f"AI explanation failed: {error_msg}")
            self._watchdog.unregister_worker(worker_id)
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]

        # Create and start worker
        worker = CancellableWorker(worker_id, explain_task, timeout_ms=30000)
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)

        self._active_workers[worker_id] = worker
        self._watchdog.register_worker(worker_id)
        self._thread_pool.start(worker)

        logger.info(f"AI explanation requested for event {event_index}")

    @Slot(str)
    def sendChatMessage(self, user_text: str) -> None:
        """
        Send a message to the security chatbot.

        Args:
            user_text: User's message text
        """
        if not user_text or not user_text.strip():
            return

        user_text = user_text.strip()

        if self._security_chatbot is None:
            self.toast.emit("error", "AI chatbot not available")
            # Still emit user message so UI shows it
            self.chatMessageAdded.emit("user", user_text)
            self.chatMessageAdded.emit(
                "assistant", "I'm sorry, the AI assistant is not available right now."
            )
            return

        # Add user message to conversation
        self._chat_conversation.append({"role": "user", "content": user_text})
        self.chatMessageAdded.emit("user", user_text)

        worker_id = f"ai-chat-{len(self._chat_conversation)}"

        def chat_task(worker):
            """Background chat task."""
            worker.signals.heartbeat.emit(worker_id)

            # Get response from chatbot
            response = self._security_chatbot.answer(
                self._chat_conversation[
                    :-1
                ],  # Exclude current message (already in prompt)
                user_text,
            )

            return response

        def on_success(wid: str, response: str) -> None:
            """Chat response ready."""
            # Add assistant response to conversation
            self._chat_conversation.append({"role": "assistant", "content": response})
            self.chatMessageAdded.emit("assistant", response)

            self._watchdog.unregister_worker(worker_id)
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]

        def on_error(wid: str, error_msg: str) -> None:
            """Chat failed."""
            logger.error(f"AI chat failed: {error_msg}")
            error_response = (
                "I encountered an error processing your request. Please try again."
            )
            self._chat_conversation.append(
                {"role": "assistant", "content": error_response}
            )
            self.chatMessageAdded.emit("assistant", error_response)

            self._watchdog.unregister_worker(worker_id)
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]

        # Create and start worker
        worker = CancellableWorker(worker_id, chat_task, timeout_ms=60000)
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)

        self._active_workers[worker_id] = worker
        self._watchdog.register_worker(worker_id)
        self._thread_pool.start(worker)

        logger.debug(f"AI chat message sent: {user_text[:50]}...")

    @Slot()
    def clearChatHistory(self) -> None:
        """Clear the chat conversation history."""
        self._chat_conversation.clear()
        logger.info("Chat history cleared")
