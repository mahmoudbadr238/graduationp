"""QObject bridge connecting QML frontend to Python backend."""
from PySide6.QtCore import QObject, Signal, Slot, QTimer
from typing import Dict, Any
from datetime import datetime
from ..core.container import DI
from ..core.interfaces import (
    ISystemMonitor, IEventReader, INetworkScanner,
    IFileScanner, IUrlScanner, IScanRepository, IEventRepository
)
from ..core.types import ScanType, ScanRecord, EventItem
from ..core.errors import IntegrationDisabled, ExternalToolMissing


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
            print(f"Network scanner disabled: {e}")
        
        try:
            self.file_scanner = DI.resolve(IFileScanner)
        except IntegrationDisabled as e:
            self.file_scanner = None
            print(f"File scanner disabled: {e}")
        
        try:
            self.url_scanner = DI.resolve(IUrlScanner)
        except IntegrationDisabled as e:
            self.url_scanner = None
            print(f"URL scanner disabled: {e}")
        
        # Timer for live updates
        self.live_timer = QTimer()
        self.live_timer.timeout.connect(self._tick)
    
    @Slot()
    def startLive(self):
        """Start live system monitoring (1 second interval)."""
        if not self.live_timer.isActive():
            self.live_timer.start(1000)
            self._tick()  # Emit first snapshot immediately
            self.toast.emit("info", "Live monitoring started")
    
    @Slot()
    def stopLive(self):
        """Stop live system monitoring."""
        if self.live_timer.isActive():
            self.live_timer.stop()
            self.toast.emit("info", "Live monitoring stopped")
    
    def _tick(self):
        """Timer callback - fetch and emit system snapshot."""
        try:
            snapshot = self.sys_monitor.snapshot()
            self.snapshotUpdated.emit(snapshot)
        except Exception as e:
            self.toast.emit("error", f"Monitoring error: {str(e)}")
    
    @Slot()
    def loadRecentEvents(self):
        """Load recent Windows event log entries."""
        try:
            events = self.event_reader.tail(limit=300)
            
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
            
            # Store events in database
            self.event_repo.add_many(events)
        
        except Exception as e:
            self.toast.emit("error", f"Failed to load events: {str(e)}")
            self.eventsLoaded.emit([])
    
    @Slot(str, bool)
    def runNetworkScan(self, target: str, fast: bool = True):
        """
        Run network scan on target.
        
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
        
        self.toast.emit("info", f"Starting network scan: {target}")
        
        try:
            # Run scan (blocking - in production use threading)
            result = self.net_scanner.scan(target, fast)
            
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
            
            self.scanFinished.emit("network", result)
            self.toast.emit("success", f"Network scan completed: {len(result.get('hosts', []))} hosts found")
        
        except Exception as e:
            self.toast.emit("error", f"Network scan failed: {str(e)}")
            self.scanFinished.emit("network", {"error": str(e)})
    
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
