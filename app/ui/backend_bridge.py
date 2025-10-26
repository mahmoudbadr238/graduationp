"""QObject bridge connecting QML frontend to Python backend."""
from PySide6.QtCore import QObject, Signal, Slot, QTimer, QThreadPool
from typing import Dict, Any
from datetime import datetime
from ..core.container import DI
from ..core.interfaces import (
    ISystemMonitor, IEventReader, INetworkScanner,
    IFileScanner, IUrlScanner, IScanRepository, IEventRepository
)
from ..core.types import ScanType, ScanRecord, EventItem
from ..core.errors import IntegrationDisabled, ExternalToolMissing
from ..core.workers import CancellableWorker, get_watchdog, WorkerSignals
from ..core.result_cache import get_scan_cache
import logging

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

    def __init__(self):
        super().__init__()

        # Resolve dependencies from DI container
        self.sys_monitor = DI.resolve(ISystemMonitor)
        self.event_reader = DI.resolve(IEventReader)
        self.scan_repo = DI.resolve(IScanRepository)
        self.event_repo = DI.resolve(IEventRepository)

        # Optional integrations (may fail if disabled/missing)
        try:
            self.net_scanner = DI.resolve(INetworkScanner)
        except (IntegrationDisabled, ExternalToolMissing) as e:
            self.net_scanner = None
            logger.warning(f"Network scanner disabled: {e}")

        try:
            self.file_scanner = DI.resolve(IFileScanner)
        except IntegrationDisabled as e:
            self.file_scanner = None
            logger.warning(f"File scanner disabled: {e}")

        try:
            self.url_scanner = DI.resolve(IUrlScanner)
        except IntegrationDisabled as e:
            self.url_scanner = None
            logger.warning(f"URL scanner disabled: {e}")

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
        self._active_workers: Dict[str, CancellableWorker] = {}

    @Slot()
    def startLive(self):
        """Start live system monitoring (1 second interval)."""
        if not self.live_timer.isActive():
            self.live_timer.start(1000)
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
            logger.error(f"Monitoring error: {e}")
            self.toast.emit("error", f"Monitoring error: {str(e)}")    @Slot()
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
                    "message": evt.message
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
            self.toast.emit("error", "Network scanning not available (Nmap not installed)")
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
                    meta={"fast": fast}
                )
                
                # Save to database
                scan_id = self.scan_repo.add(scan_rec)
                result["scan_id"] = scan_id
                
                # Cache result (30 min TTL)
                self._cache.set(cache_key, result, ttl_seconds=1800)
                
                self.scanFinished.emit("network", result)
                self.toast.emit("success", f"Network scan completed: {len(result.get('hosts', []))} hosts found")
                
            finally:
                self._watchdog.unregister_worker(worker_id)
        
        def on_error(wid, error_msg):
            """Scan failed"""
            logger.error(f"Network scan failed: {error_msg}")
            self.toast.emit("error", f"Network scan failed: {error_msg}")
            self.scanFinished.emit("network", {"error": error_msg})
            self._watchdog.unregister_worker(worker_id)
        
        # Create and start worker
        worker = CancellableWorker(worker_id, scan_task, timeout_ms=60000)  # 60s timeout
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
        
        # Attempt to cancel
        if worker_id in self._active_workers:
            self._active_workers[worker_id].cancel()
            del self._active_workers[worker_id]
    
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
                scan_dicts.append({
                    "id": scan.id or 0,
                    "type": scan.type.value if hasattr(scan.type, 'value') else str(scan.type),
                    "target": scan.target or "",
                    "status": scan.status or "unknown",
                    "started_at": scan.started_at.isoformat() if scan.started_at else "",
                    "finished_at": scan.finished_at.isoformat() if scan.finished_at else "",
                    "findings": scan.findings or {}
                })
            
            self.scansLoaded.emit(scan_dicts)
            if len(scan_dicts) > 0:
                self.toast.emit("info", f"Loaded {len(scan_dicts)} scan records")
        except Exception as e:
            self.toast.emit("error", f"Failed to load scan history: {str(e)}")
            self.scansLoaded.emit([])
    
    @Slot(str)
    def exportScanHistoryCSV(self, path: str):
        """Export scan history to CSV file."""
        try:
            import csv
            import os
            from pathlib import Path
            
            # Ensure directory exists
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            
            scans = self.scan_repo.get_all()
            
            with open(path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['ID', 'Type', 'Target', 'Status', 'Started At', 'Finished At', 'Findings']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for scan in scans:
                    writer.writerow({
                        'ID': scan.id or '',
                        'Type': scan.type.value if hasattr(scan.type, 'value') else str(scan.type),
                        'Target': scan.target or '',
                        'Status': scan.status or '',
                        'Started At': scan.started_at.isoformat() if scan.started_at else '',
                        'Finished At': scan.finished_at.isoformat() if scan.finished_at else '',
                        'Findings': str(scan.findings) if scan.findings else ''
                    })
            
            self.toast.emit("success", f"✓ Exported {len(scans)} records to {path}")
            
        except Exception as e:
            self.toast.emit("error", f"CSV export failed: {str(e)}")
    
    @Slot(str)
    def scanFile(self, path: str):
        """
        Scan a file for threats.
        
        Args:
            path: Absolute path to file
        """
        if not self.file_scanner:
            self.toast.emit("error", "File scanning not available (VirusTotal API key required)")
            return
        
        if not path:
            self.toast.emit("error", "File path cannot be empty")
            return
        
        self.toast.emit("info", f"Scanning file: {path}")
        
        try:
            # Run scan (blocking - in production use threading)
            result = self.file_scanner.scan_file(path)
            
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
                meta={}
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
                    self.toast.emit("warning", f"File flagged by {malicious} engines")
                else:
                    self.toast.emit("success", "File appears clean")
            else:
                self.toast.emit("success", f"File scanned: {result.get('sha256', '')[:16]}...")
        
        except Exception as e:
            self.toast.emit("error", f"File scan failed: {str(e)}")
            self.scanFinished.emit("file", {"error": str(e)})
    
    @Slot(str)
    def scanUrl(self, url: str):
        """
        Scan a URL for threats.
        
        Args:
            url: URL to scan
        """
        if not self.url_scanner:
            self.toast.emit("error", "URL scanning not available (VirusTotal API key not configured)")
            return
        
        if not url:
            self.toast.emit("error", "URL cannot be empty")
            return
        
        self.toast.emit("info", f"Scanning URL: {url}")
        
        try:
            # Run scan (blocking - in production use threading)
            result = self.url_scanner.scan_url(url)
            
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
                meta={}
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
                    self.toast.emit("warning", f"URL flagged by {malicious} engines")
                else:
                    self.toast.emit("success", "URL appears clean")
        
        except Exception as e:
            self.toast.emit("error", f"URL scan failed: {str(e)}")
            self.scanFinished.emit("url", {"error": str(e)})
    
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
                    "finished_at": rec.finished_at.isoformat() if rec.finished_at else "",
                    "type": rec.type.value,
                    "target": rec.target,
                    "status": rec.status
                }
                for rec in records
            ]
        except Exception as e:
            self.toast.emit("error", f"Failed to load history: {str(e)}")
            return []
