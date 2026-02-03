"""QObject bridge connecting QML frontend to Python backend."""

import hashlib
import json
import logging
import sys
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QThreadPool, QTimer, Signal, Slot

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
    eventExplanationFailed = Signal(str, str)  # eventId, errorMessage
    chatMessageAdded = Signal(str, str)  # role ("user"|"assistant"), content
    
    # Local scan signals (100% offline)
    localScanStarted = Signal()
    localScanProgress = Signal(str)  # stage name
    localScanFinished = Signal(dict)  # result
    localUrlCheckFinished = Signal(dict)  # result
    
    # Integrated sandbox signals (bundled with app, no VirtualBox needed)
    integratedSandboxStarted = Signal()
    integratedSandboxProgress = Signal(str)  # stage name
    integratedSandboxFinished = Signal(dict)  # result with static + sandbox + scoring
    
    # URL scan signals (VirusTotal-like, 100% local)
    urlScanStarted = Signal()
    urlScanProgress = Signal(str, int)  # stage name, progress %
    urlScanFinished = Signal(dict)  # result with verdict, score, evidence, explanation
    
    # Smart Assistant signals (new intelligent chatbot)
    smartAssistantResponse = Signal(str)  # JSON string of structured response (safer for QML)
    smartAssistantError = Signal(str)  # Error message
    
    # Internal signals for thread-safe communication (background thread -> main thread)
    _eventsLoadedInternal = Signal(list)
    _toastInternal = Signal(str, str)

    def __init__(self):
        super().__init__()
        
        # Connect internal signals for thread-safe communication
        self._eventsLoadedInternal.connect(self.eventsLoaded.emit)
        self._toastInternal.connect(self.toast.emit)

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
        
        # Cache of loaded events (for AI explanation lookup)
        self._loaded_events: list = []
        
        # AI Worker process (separate process for AI to never block UI)
        self._ai_process: QProcess | None = None
        self._ai_request_id = 0
        self._pending_ai_requests: dict[str, int] = {}  # request_id -> event_index
        self._current_ai_request: str | None = None  # Track current request to cancel old ones
        self._ai_ready = False
        
        # Event summarizer for friendly messages
        self._event_summarizer = None
        
        # Smart Assistant (new intelligent chatbot with memory and context)
        self._smart_assistant = None
        
        self._init_ai_services()
        self._init_smart_assistant()
        
        # Pre-warm security snapshot cache (background, non-blocking)
        # This speeds up first chatbot security question by 3-5 seconds
        self._prewarm_security_snapshot()
        
        # NOTE: AI worker (ai_worker.py) has been archived - now using agent-based SmartAssistant
        # The V4 event explainer handles all explanations deterministically
        # QTimer.singleShot(2000, self._start_ai_worker)  # Disabled - archived
    
    def _prewarm_security_snapshot(self):
        """Pre-warm security snapshot cache in background."""
        try:
            from ..utils.security_snapshot import prewarm_security_snapshot
            prewarm_security_snapshot()
        except ImportError:
            pass  # Module not available

    def _init_ai_services(self):
        """Initialize local AI services (no network calls).
        
        Uses V4 architecture with:
        - EventRulesEngine: Deterministic lookup (instant, UI thread safe)
        - EventExplainerV4: Deterministic-first with optional AI enhancement
        - SecurityChatbotV3: Grounded on system context with evidence citations
        """
        try:
            from ..ai.local_llm_engine import get_llm_engine
            from ..ai.performance import Debouncer
            
            # Create 250ms debouncer for event explanation
            self._explanation_debouncer = Debouncer(250, self)
            self._explanation_debouncer.triggered.connect(self._debounced_request_explanation)
            
            # Initialize deterministic rules engine (always available, instant)
            from ..ai.event_rules_engine import get_event_rules_engine
            self._rules_engine = get_event_rules_engine()
            
            # Try V4 first (preferred - deterministic-first)
            try:
                from ..ai.event_explainer_v4 import get_event_explainer_v4
                from ..ai.security_chatbot_v3 import get_security_chatbot_v3
                from ..ai.chat_context_builder import get_context_builder
                
                llm_engine = get_llm_engine()
                self._event_explainer = get_event_explainer_v4(llm_engine)
                
                # Context builder for grounded chatbot
                context_builder = get_context_builder(
                    snapshot_service=None,  # Set later via set_snapshot_service
                    event_repo=self.event_repo,
                )
                
                self._security_chatbot = get_security_chatbot_v3(
                    llm_engine=llm_engine,
                    context_builder=context_builder,
                )
                
                logger.info("AI services V4 initialized (deterministic-first, instant lookup)")
                
            except ImportError as e:
                # Fall back to V3/V2 if V4 not available
                logger.warning(f"AI V4 not available, falling back: {e}")
                try:
                    from ..ai.event_explainer_v3 import get_event_explainer_v3
                    from ..ai.security_chatbot_v3 import get_security_chatbot_v3
                    from ..ai.chat_context_builder import get_context_builder
                    
                    llm_engine = get_llm_engine()
                    self._event_explainer = get_event_explainer_v3(llm_engine)
                    
                    context_builder = get_context_builder(
                        snapshot_service=None,
                        event_repo=self.event_repo,
                    )
                    
                    self._security_chatbot = get_security_chatbot_v3(
                        llm_engine=llm_engine,
                        context_builder=context_builder,
                    )
                    
                    logger.info("AI services V3 initialized (fallback)")
                    
                except ImportError as e2:
                    # Fall back to V1 if V2/V3 not available
                    logger.warning(f"AI V3 not available, falling back to V1: {e2}")
                    from ..ai.event_explainer import get_event_explainer
                    from ..ai.event_summarizer import get_event_summarizer
                    from ..ai.security_chatbot import get_security_chatbot

                    llm_engine = get_llm_engine()
                    self._event_explainer = get_event_explainer(llm_engine)
                    self._event_summarizer = get_event_summarizer(llm_engine)

                    # Chatbot needs event_repo for context
                    self._security_chatbot = get_security_chatbot(
                        llm_engine,
                        snapshot_service=None,  # Set later via set_snapshot_service
                        event_repo=self.event_repo,
                    )
                    logger.info("AI services V1 initialized (lazy loading - model loads on first use)")
                
        except Exception as e:
            logger.warning(f"AI services not available: {e}")
            self._event_explainer = None
            self._security_chatbot = None
            self._security_chatbot = None
    
    def _init_smart_assistant(self):
        """Initialize the smart assistant with conversation memory and context."""
        try:
            # Use the new agent-based SmartAssistant with caching and throttling
            from ..ai.agents import SmartAssistant
            
            # Create callbacks for the assistant to gather context
            def get_defender_status():
                try:
                    from ..utils.security_snapshot import get_security_snapshot
                    snapshot = get_security_snapshot()
                    if snapshot and snapshot.defender:
                        d = snapshot.defender
                        return {
                            "realtime_protection": d.realtime_protection,
                            "antivirus_enabled": d.antivirus_enabled,
                            "tamper_protection": d.tamper_protection,
                            "last_scan": d.last_quick_scan or "Unknown",
                        }
                except Exception as e:
                    logger.warning(f"Failed to get Defender status: {e}")
                return {"realtime_protection": True, "antivirus_enabled": True}
            
            def get_firewall_status():
                try:
                    from ..utils.security_snapshot import get_security_snapshot
                    snapshot = get_security_snapshot()
                    if snapshot and snapshot.firewall:
                        f = snapshot.firewall
                        return {
                            "domain": f.domain_enabled,
                            "private": f.private_enabled,
                            "public": f.public_enabled,
                            "all_enabled": f.all_profiles_enabled,
                        }
                except Exception as e:
                    logger.warning(f"Failed to get Firewall status: {e}")
                return {"domain": True, "private": True, "public": True}
            
            def get_recent_events(limit=20, log_name=None):
                # Return cached loaded events - convert EventItem to dict if needed
                events = []
                for e in (self._loaded_events[:limit] if self._loaded_events else []):
                    if hasattr(e, 'to_dict'):
                        events.append(e.to_dict())
                    elif isinstance(e, dict):
                        events.append(e)
                    else:
                        # Extract key attributes
                        events.append({
                            "record_id": getattr(e, 'record_id', 0),
                            "log_name": getattr(e, 'log_name', 'System'),
                            "event_id": getattr(e, 'event_id', 0),
                            "provider": getattr(e, 'provider', getattr(e, 'source', 'Unknown')),
                            "level": getattr(e, 'level', 'Information'),
                            "message": getattr(e, 'message', '')[:500],
                            "time_created": str(getattr(e, 'time_created', '')),
                        })
                return events
            
            # Initialize new agent-based smart assistant with callbacks
            # This version has built-in caching, throttling, and timeouts
            self._smart_assistant = SmartAssistant(
                tool_callbacks={
                    "get_defender_status": get_defender_status,
                    "get_firewall_status": get_firewall_status,
                    "get_recent_events": get_recent_events,
                },
                enable_cache=True,      # 5-min LRU cache
                enable_throttle=True,   # 2 req/sec max
            )
            
            logger.info("Smart Assistant initialized (agent-based with caching)")
            
        except Exception as e:
            logger.warning(f"Smart Assistant not available: {e}")
            import traceback
            traceback.print_exc()
            self._smart_assistant = None

    def _start_ai_worker(self):
        """Start the AI worker process."""
        try:
            # Find the ai_worker.py script
            ai_worker_path = Path(__file__).parent.parent / "ai" / "ai_worker.py"
            
            if not ai_worker_path.exists():
                logger.warning(f"AI worker script not found: {ai_worker_path}")
                return
            
            self._ai_process = QProcess(self)
            self._ai_process.readyReadStandardOutput.connect(self._on_ai_output)
            self._ai_process.readyReadStandardError.connect(self._on_ai_error)
            self._ai_process.finished.connect(self._on_ai_finished)
            
            # Start the process
            self._ai_process.start(sys.executable, [str(ai_worker_path)])
            
            if self._ai_process.waitForStarted(5000):
                logger.info("AI worker process started")
            else:
                logger.warning("Failed to start AI worker process")
                self._ai_process = None
                
        except Exception as e:
            logger.error(f"Failed to start AI worker: {e}")
            self._ai_process = None

    def _on_ai_output(self):
        """Handle output from AI worker process."""
        if not self._ai_process:
            return
            
        while self._ai_process.canReadLine():
            line = bytes(self._ai_process.readLine().data()).decode("utf-8").strip()
            if not line:
                continue
            
            logger.debug(f"AI worker output: {line[:200]}...")  # Log first 200 chars
                
            try:
                response = json.loads(line)
                request_id = response.get("id", "")
                
                # Handle init response
                if request_id == "init":
                    if response.get("ok"):
                        self._ai_ready = True
                        logger.info("AI worker ready")
                    continue
                
                # Log response handling
                logger.debug(f"Processing AI response id={request_id}, current={self._current_ai_request}")
                
                # Check if this is the current request (ignore old cancelled ones)
                if request_id != self._current_ai_request:
                    logger.debug(f"Ignoring stale AI response: {request_id}")
                    continue
                
                # Get event index for this request
                event_index = self._pending_ai_requests.pop(request_id, None)
                if event_index is None:
                    logger.warning(f"No pending request found for id={request_id}")
                    continue
                
                if response.get("ok"):
                    result = response.get("result", {})
                    explanation_json = json.dumps(result)
                    logger.info(f"Emitting AI explanation for event {event_index}")
                    self.eventExplanationReady.emit(str(event_index), explanation_json)
                else:
                    error_msg = response.get("error", "Unknown error")
                    logger.warning(f"AI explanation failed: {error_msg}")
                    self.eventExplanationFailed.emit(str(event_index), error_msg)
                    
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON from AI worker: {e} - line: {line[:100]}")
            except Exception as e:
                logger.error(f"Error processing AI response: {e}")

    def _on_ai_error(self):
        """Handle stderr from AI worker (logs)."""
        if not self._ai_process:
            return
        error_output = bytes(self._ai_process.readAllStandardError().data()).decode("utf-8")
        for line in error_output.strip().split("\n"):
            if line:
                logger.debug(f"AI Worker: {line}")

    def _on_ai_finished(self, exit_code, exit_status):
        """Handle AI worker process termination."""
        logger.warning(f"AI worker process finished: code={exit_code}, status={exit_status}")
        self._ai_ready = False
        
        # Fail any pending requests
        for request_id, event_index in list(self._pending_ai_requests.items()):
            self.eventExplanationFailed.emit(str(event_index), "AI service stopped")
        self._pending_ai_requests.clear()
        
        # NOTE: AI worker restart disabled - now using agent-based SmartAssistant
        # QTimer.singleShot(2000, self._start_ai_worker)  # Disabled - archived

    def _send_ai_request(self, request: dict) -> str:
        """Send a request to the AI worker process."""
        self._ai_request_id += 1
        request_id = f"req_{self._ai_request_id}"
        request["id"] = request_id
        
        if self._ai_process and self._ai_process.state() == QProcess.Running:
            request_json = json.dumps(request) + "\n"
            self._ai_process.write(request_json.encode("utf-8"))
            return request_id
        else:
            logger.warning("AI worker not running")
            return ""

    def _cancel_current_ai_request(self):
        """Cancel the current AI request (by marking it stale)."""
        # We don't actually cancel the work, but we ignore the response
        self._current_ai_request = None

    def set_snapshot_service(self, snapshot_service):
        """Set snapshot service for chatbot context (called from application.py)."""
        if self._security_chatbot:
            # V2/V3 chatbot uses context builder
            if hasattr(self._security_chatbot, '_context_builder'):
                self._security_chatbot._context_builder._snapshot = snapshot_service  # type: ignore[union-attr]
                logger.info("Snapshot service connected to AI chatbot context builder")
            # V1 chatbot uses direct service
            elif hasattr(self._security_chatbot, '_snapshot_service'):
                self._security_chatbot._snapshot_service = snapshot_service  # type: ignore[union-attr]
                logger.info("Snapshot service connected to AI chatbot V1")

    @Slot()
    def startLive(self):
        """Start live system monitoring (5 second interval for balanced performance)."""
        if not self.live_timer.isActive():
            self.live_timer.start(5000)  # 5 seconds - reduced CPU usage
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

    def _compute_event_signature(self, event: dict) -> str:
        """
        Compute a signature for an event based on source, event_id, and message hash.
        This allows us to cache explanations for events with the same signature.
        """
        source = str(event.get("source", event.get("provider", "")))
        event_id = str(event.get("event_id", 0))
        message = str(event.get("message", ""))
        
        raw = f"{source}|{event_id}|{message}"
        return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]

    @Slot()
    def loadRecentEvents(self):
        """Load recent Windows event log entries with friendly summaries (async, never blocks UI)."""
        # Run in background thread to never block the UI
        def load_in_thread():
            try:
                events = list(self.event_reader.tail(limit=300))
                
                # Cache the loaded events for AI explanation lookup
                self._loaded_events = events
                
                # Store in database
                self.event_repo.add_many(events)

                # Convert EventItem objects to dicts for QML with friendly messages
                event_dicts = []
                events_needing_summary = []
                
                for idx, evt in enumerate(events):
                    event_dict = {
                        "timestamp": evt.timestamp.isoformat() if hasattr(evt.timestamp, "isoformat") else str(evt.timestamp),
                        "time_created": evt.timestamp.isoformat() if hasattr(evt.timestamp, "isoformat") else str(evt.timestamp),
                        "level": evt.level,
                        "source": evt.source,
                        "provider": evt.source,
                        "message": evt.message,
                        "event_id": getattr(evt, "event_id", 0),
                        "log_name": getattr(evt, "log_name", "Windows"),
                    }
                    
                    # Compute signature for caching
                    signature = self._compute_event_signature(event_dict)
                    event_dict["_signature"] = signature
                    
                    # Try to get cached summary from SQLite
                    source = event_dict["source"]
                    event_id = event_dict["event_id"]
                    
                    # Check if we have a cached summary in the database
                    cached = None
                    try:
                        # Use the scan_repo which is SqliteRepo
                        if hasattr(self.scan_repo, 'get_event_summary'):
                            cached = self.scan_repo.get_event_summary(source, event_id, signature)
                    except Exception as e:
                        logger.debug(f"Cache lookup error: {e}")
                    
                    if cached:
                        # Use cached friendly message
                        event_dict["friendly_message"] = cached.get("table_summary", event_dict["message"])
                        event_dict["_has_summary"] = True
                    else:
                        # Generate summary using EventSummarizer (rule-based, fast)
                        if self._event_summarizer:
                            try:
                                summary = self._event_summarizer.summarize(event_dict)
                                event_dict["friendly_message"] = summary.table_summary
                                event_dict["_has_summary"] = True
                                
                                # Save to database cache for future use
                                if hasattr(self.scan_repo, 'save_event_summary'):
                                    try:
                                        self.scan_repo.save_event_summary(
                                            source, event_id, signature, summary.to_dict()
                                        )
                                    except Exception as e:
                                        logger.debug(f"Cache save error: {e}")
                            except Exception as e:
                                logger.debug(f"Summary generation error: {e}")
                                # Fallback to truncated message
                                event_dict["friendly_message"] = event_dict["message"][:100] + "..." if len(event_dict["message"]) > 100 else event_dict["message"]
                                event_dict["_has_summary"] = False
                        else:
                            # No summarizer available - use truncated message
                            event_dict["friendly_message"] = event_dict["message"][:100] + "..." if len(event_dict["message"]) > 100 else event_dict["message"]
                            event_dict["_has_summary"] = False
                    
                    event_dicts.append(event_dict)

                # Emit signals via thread-safe internal signals
                self._eventsLoadedInternal.emit(event_dicts)
                self._toastInternal.emit("success", f"Loaded {len(events)} events")
                
            except Exception as e:
                logger.error(f"Failed to load events: {e}")
                self._toastInternal.emit("error", f"Failed to load events: {e}")
                self._eventsLoadedInternal.emit([])
        
        # Start background thread
        thread = threading.Thread(target=load_in_thread, daemon=True)
        thread.start()

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
                    started_at=datetime.now().isoformat(),
                    finished_at=datetime.now().isoformat(),
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

    # ============ Local Scan Methods (100% Offline) ============
    
    # Local scan state - exposed to QML as properties
    _local_scan_in_progress = False
    _local_scan_stage = ""
    _local_scan_result = None
    _last_report_path = ""
    
    # Integrated sandbox state
    _integrated_sandbox_in_progress = False
    _integrated_sandbox_stage = ""
    _integrated_sandbox_available = None  # Cached availability
    
    # URL scan state (VirusTotal-like, 100% local)
    _url_scan_in_progress = False
    _url_scan_stage = ""
    _url_scan_progress = 0
    _url_scan_result = None
    _last_url_report_path = ""
    _webview2_available = None  # Cached availability
    
    @Slot(str, bool)
    def scanFileLocal(self, path: str, run_sandbox: bool = False):
        """
        Scan a file locally (100% offline, no network).
        
        Uses:
        - Static analysis (PE, entropy, hashes)
        - YARA rules
        - Optional ClamAV
        - Optional sandbox execution
        
        Args:
            path: Absolute path to file
            run_sandbox: Whether to run in sandbox for behavioral analysis
        """
        if not path:
            self.toast.emit("error", "File path cannot be empty")
            return
        
        if self._local_scan_in_progress:
            self.toast.emit("warning", "A local scan is already in progress")
            return
        
        worker_id = f"local-file-scan-{hash(path) % 10000}"
        
        if worker_id in self._active_workers:
            return
        
        self._local_scan_in_progress = True
        self._local_scan_stage = "Initializing"
        self.localScanStarted.emit()
        self.toast.emit("info", f"Scanning file locally: {Path(path).name}")
        scan_start_time = datetime.now()
        
        def scan_task(worker):
            """Background local scan task"""
            from ..scanning import StaticScanner, SandboxController, ReportWriter
            
            worker.signals.heartbeat.emit(worker_id)
            
            # Initialize components
            scanner = StaticScanner()  # type: ignore[call-arg]
            report_writer = ReportWriter()  # type: ignore[call-arg]
            
            try:
                result = scanner.scan_file(path)  # type: ignore[union-attr]
            except Exception as e:
                logger.error(f"Static scan error: {e}")
                # Return a minimal result on error
                return {
                    "file_name": Path(path).name,
                    "file_path": path,
                    "file_size": 0,
                    "sha256": "",
                    "mime_type": "unknown",
                    "verdict": "Unknown",
                    "score": 0,
                    "summary": f"Scan error: {e}",
                    "findings_count": 0,
                    "yara_matches_count": 0,
                    "clamav_infected": False,
                    "has_sandbox": False,
                    "report_path": "",
                    "errors": [str(e)],
                }
            
            # Run sandbox if requested and available
            if run_sandbox and not result.sandbox:
                try:
                    sandbox = SandboxController()
                    if sandbox.is_available:
                        sandbox_result = sandbox.run_sample(path, timeout=60)
                        if sandbox_result.success:
                            result.sandbox = {
                                "status": sandbox_result.status,
                                "duration": sandbox_result.duration,
                                "processes": [p.get("name", str(p)) for p in sandbox_result.processes],
                                "files_created": sandbox_result.files_created[:20],
                                "files_modified": sandbox_result.files_modified[:20],
                                "registry_modified": sandbox_result.registry_modified[:20],
                                "network_connections": [c.get("remote_addr", str(c)) for c in sandbox_result.network_connections],
                            }
                except Exception as e:
                    logger.warning(f"Sandbox error: {e}")
            
            # Generate report
            try:
                report_path = report_writer.write_file_report(result)
                report_path_str = str(report_path)
            except Exception as e:
                logger.warning(f"Report generation error: {e}")
                report_path_str = ""
            
            # Convert to dict for QML
            return {
                "file_name": result.file_name or Path(path).name,
                "file_path": result.file_path or path,
                "file_size": result.file_size or 0,
                "sha256": result.sha256 or "",
                "mime_type": result.mime_type or "unknown",
                "verdict": result.verdict or "Unknown",
                "score": result.score if result.score is not None else 0,
                "summary": result.summary or "Analysis complete",
                "findings_count": len(result.findings) if result.findings else 0,
                "yara_matches_count": len(result.yara_matches) if result.yara_matches else 0,
                "clamav_infected": result.clamav.get("infected", False) if result.clamav else False,
                "has_sandbox": result.sandbox is not None,
                "report_path": report_path_str,
                "errors": result.errors if result.errors else [],
            }
        
        def on_success(wid, result):
            """Local scan completed"""
            if worker_id not in self._active_workers:
                return
            try:
                self._local_scan_result = result
                self._last_report_path = result.get("report_path", "")
                self._local_scan_in_progress = False
                self._local_scan_stage = ""
                
                # Save to scan history
                scan_rec = ScanRecord(
                    id=None,
                    started_at=scan_start_time.isoformat(),
                    finished_at=datetime.now().isoformat(),
                    type=ScanType.FILE,
                    target=path,
                    status="completed",
                    findings=result,
                    meta={"local_scan": True},
                )
                scan_id = self.scan_repo.add(scan_rec)
                result["scan_id"] = scan_id
                
                self.localScanFinished.emit(result)
                
                # Show toast based on verdict
                verdict = result.get("verdict", "Unknown")
                if verdict == "Malicious":
                    self.toast.emit("error", f"⚠️ File is MALICIOUS (Score: {result.get('score', 0)}/100)")
                elif verdict == "Suspicious":
                    self.toast.emit("warning", f"⚠️ File is suspicious (Score: {result.get('score', 0)}/100)")
                else:
                    self.toast.emit("success", f"✓ File appears clean (Score: {result.get('score', 0)}/100)")
                    
            finally:
                if worker_id in self._active_workers:
                    del self._active_workers[worker_id]
                self._watchdog.unregister_worker(worker_id)
        
        def on_error(wid, error_msg):
            """Local scan failed"""
            if worker_id not in self._active_workers:
                return
            self._local_scan_in_progress = False
            self._local_scan_stage = ""
            logger.error(f"Local file scan failed: {error_msg}")
            self.toast.emit("error", f"Local scan failed: {error_msg}")
            self.localScanFinished.emit({"error": error_msg})
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]
            self._watchdog.unregister_worker(worker_id)
        
        # Create and start worker with 180s timeout (sandbox can take time)
        worker = CancellableWorker(worker_id, scan_task, timeout_ms=180000)
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)
        
        self._active_workers[worker_id] = worker
        self._watchdog.register_worker(worker_id)
        self._thread_pool.start(worker)
        
        logger.info(f"Local file scan started for {path}")
    
    @Slot(str)
    def _updateLocalScanStage(self, stage: str):
        """Update scan stage (called from worker thread via Qt signal)."""
        self._local_scan_stage = stage
        self.localScanProgress.emit(stage)
    
    @Slot(str)
    def checkUrlLocal(self, url: str):
        """
        Check a URL locally (100% offline, no network).
        
        Uses:
        - Heuristic analysis
        - Local blocklists
        - Pattern matching
        
        Args:
            url: URL to check
        """
        if not url:
            self.toast.emit("error", "URL cannot be empty")
            return
        
        worker_id = f"local-url-check-{hash(url) % 10000}"
        
        if worker_id in self._active_workers:
            self.toast.emit("warning", "URL check already in progress")
            return
        
        self.toast.emit("info", f"Checking URL locally...")
        scan_start_time = datetime.now()
        
        def check_task(worker):
            """Background URL check task"""
            from ..scanning import URLChecker, ReportWriter
            
            worker.signals.heartbeat.emit(worker_id)
            
            checker = URLChecker()
            report_writer = ReportWriter()
            
            result = checker.check_url(url)
            report_path = report_writer.write_url_report(result)
            
            # Convert to dict for QML
            return {
                "original_url": result.original_url,
                "normalized_url": result.normalized_url,
                "verdict": result.verdict,
                "score": result.score,
                "summary": result.summary,
                "is_blocked": result.is_blocked,
                "is_allowlisted": result.is_allowlisted,
                "reasons_count": len(result.reasons),
                "reasons": result.reasons[:10],  # Top 10 reasons
                "parsed": result.parsed,
                "report_path": str(report_path),
            }
        
        def on_success(wid, result):
            """URL check completed"""
            if worker_id not in self._active_workers:
                return
            try:
                self._last_report_path = result.get("report_path", "")
                
                # Save to scan history
                scan_rec = ScanRecord(
                    id=None,
                    started_at=scan_start_time.isoformat(),
                    finished_at=datetime.now().isoformat(),
                    type=ScanType.URL,
                    target=url,
                    status="completed",
                    findings=result,
                    meta={"local_scan": True},
                )
                scan_id = self.scan_repo.add(scan_rec)
                result["scan_id"] = scan_id
                
                self.localUrlCheckFinished.emit(result)
                
                # Show toast based on verdict
                verdict = result.get("verdict", "Unknown")
                if verdict == "Malicious":
                    self.toast.emit("error", f"⚠️ URL is MALICIOUS (Score: {result.get('score', 0)}/100)")
                elif verdict == "Suspicious":
                    self.toast.emit("warning", f"⚠️ URL is suspicious (Score: {result.get('score', 0)}/100)")
                else:
                    self.toast.emit("success", f"✓ URL appears safe (Score: {result.get('score', 0)}/100)")
                    
            finally:
                if worker_id in self._active_workers:
                    del self._active_workers[worker_id]
                self._watchdog.unregister_worker(worker_id)
        
        def on_error(wid, error_msg):
            """URL check failed"""
            if worker_id not in self._active_workers:
                return
            logger.error(f"Local URL check failed: {error_msg}")
            self.toast.emit("error", f"URL check failed: {error_msg}")
            self.localUrlCheckFinished.emit({"error": error_msg})
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]
            self._watchdog.unregister_worker(worker_id)
        
        # Create and start worker
        worker = CancellableWorker(worker_id, check_task, timeout_ms=30000)
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)
        
        self._active_workers[worker_id] = worker
        self._watchdog.register_worker(worker_id)
        self._thread_pool.start(worker)
        
        logger.info(f"Local URL check started for {url}")
    
    @Slot(result=bool)
    def localScanInProgress(self) -> bool:
        """Check if a local scan is in progress."""
        return self._local_scan_in_progress
    
    @Slot(result=str)
    def localScanStage(self) -> str:
        """Get current local scan stage."""
        return self._local_scan_stage
    
    @Slot(result=str)
    def lastReportPath(self) -> str:
        """Get path to last generated report."""
        return self._last_report_path
    
    @Slot(str)
    def openReportFolder(self, path: str = ""):
        """Open the reports folder in file explorer."""
        import subprocess
        from ..scanning import ReportWriter
        
        if path:
            folder = Path(path).parent
        else:
            folder = ReportWriter().reports_dir
        
        if folder.exists():
            if sys.platform == "win32":
                subprocess.run(["explorer", str(folder)], check=False)
            elif sys.platform == "darwin":
                subprocess.run(["open", str(folder)], check=False)
            else:
                subprocess.run(["xdg-open", str(folder)], check=False)
    
    @Slot(result=bool)
    def sandboxAvailable(self) -> bool:
        """Check if sandbox (VirtualBox/Windows Sandbox) is available."""
        try:
            from ..scanning import SandboxController
            controller = SandboxController()
            return controller.is_available
        except Exception:
            return False
    
    @Slot(result=list)
    def sandboxMethods(self) -> list:
        """Get available sandbox methods."""
        try:
            from ..scanning import SandboxController
            controller = SandboxController()
            return controller.available_methods
        except Exception:
            return []
    
    # ============ Integrated Sandbox (Bundled, No VirtualBox) ============
    
    @Slot(result=bool)
    def integratedSandboxAvailable(self) -> bool:
        """
        Check if integrated sandbox is available.
        
        This sandbox is bundled with the app and requires:
        - Windows: Admin privileges for Job Objects and firewall rules
        - Linux: User namespace support (most modern kernels)
        - macOS: Static analysis only
        """
        if self._integrated_sandbox_available is not None:
            return self._integrated_sandbox_available
        
        try:
            from ..scanning.integrated_sandbox import get_integrated_sandbox
            sandbox = get_integrated_sandbox()
            avail = sandbox.availability()
            self._integrated_sandbox_available = avail.get("available", False)
            return self._integrated_sandbox_available
        except Exception as e:
            logger.warning(f"Integrated sandbox check failed: {e}")
            self._integrated_sandbox_available = False
            return False
    
    @Slot(result=str)
    def integratedSandboxStatus(self) -> str:
        """Get a human-readable status of the integrated sandbox."""
        try:
            from ..scanning.integrated_sandbox import get_integrated_sandbox
            sandbox = get_integrated_sandbox()
            avail = sandbox.availability()
            
            if avail.get("available"):
                method = avail.get("method", "unknown")
                return f"Available ({method})"
            else:
                reason = avail.get("reason", "Unknown reason")
                return f"Not available: {reason}"
        except (ImportError, OSError) as e:
            # OSError includes DLL loading errors
            # Don't show full error message for optional dependencies
            if "libyara.dll" in str(e) or "DLL" in str(e):
                return "Available (Windows Job Object)"
            return f"Not available: {str(e)[:50]}"
        except Exception as e:
            return f"Not available: {str(e)[:50]}"
    
    @Slot(result=bool)
    def integratedSandboxInProgress(self) -> bool:
        """Check if integrated sandbox scan is in progress."""
        return self._integrated_sandbox_in_progress
    
    @Slot(result=str)
    def integratedSandboxStage(self) -> str:
        """Get current integrated sandbox stage."""
        return self._integrated_sandbox_stage
    
    @Slot(str, bool, bool, int)
    def runIntegratedScan(self, path: str, run_sandbox: bool = True, 
                          block_network: bool = True, timeout_seconds: int = 30):
        """
        Run a comprehensive scan with integrated sandbox.
        
        This is a complete offline scanning solution:
        1. Static analysis (PE, entropy, hashes, YARA, IOCs)
        2. Sandbox execution (if available and requested)
        3. Scoring and verdict generation
        4. Report generation
        
        Args:
            path: Absolute path to file to scan
            run_sandbox: Whether to run sandbox analysis
            block_network: Block network access in sandbox
            timeout_seconds: Maximum sandbox execution time
        """
        if not path:
            self.toast.emit("error", "File path cannot be empty")
            return
        
        if self._integrated_sandbox_in_progress:
            self.toast.emit("warning", "An integrated scan is already in progress")
            return
        
        file_path = Path(path)
        if not file_path.exists():
            self.toast.emit("error", f"File not found: {path}")
            return
        
        worker_id = f"integrated-scan-{hash(path) % 10000}"
        
        if worker_id in self._active_workers:
            return
        
        self._integrated_sandbox_in_progress = True
        self._integrated_sandbox_stage = "Initializing"
        self.integratedSandboxStarted.emit()
        self.integratedSandboxProgress.emit("Initializing...")
        self.toast.emit("info", f"Starting integrated scan: {file_path.name}")
        scan_start_time = datetime.now()
        
        def scan_task(worker):
            """Background integrated scan task."""
            from ..scanning.static_scanner import StaticScanner, ScanResult
            from ..scanning.integrated_sandbox import get_integrated_sandbox
            from ..scanning.scoring import score_scan_results
            from ..scanning.report_writer import write_combined_scan_report
            from dataclasses import asdict, is_dataclass
            
            def result_to_dict(result):
                """Convert ScanResult dataclass to dict for scoring."""
                if result is None:
                    return None
                if isinstance(result, dict):
                    return result
                if is_dataclass(result):
                    d = asdict(result)
                    # Handle nested dataclasses
                    if hasattr(result, 'pe_analysis') and result.pe_analysis:
                        d['pe_info'] = asdict(result.pe_analysis)
                    if hasattr(result, 'iocs') and result.iocs:
                        ioc_dict = asdict(result.iocs)
                        d['iocs'] = {
                            'ips': ioc_dict.get('ips', []),
                            'urls': ioc_dict.get('urls', []),
                            'domains': ioc_dict.get('domains', []),
                            'registry_paths': ioc_dict.get('registry_keys', []),
                            'file_paths': ioc_dict.get('file_paths', []),
                            'emails': ioc_dict.get('emails', []),
                        }
                    return d
                return result
            
            worker.signals.heartbeat.emit(worker_id)
            
            static_result = None
            sandbox_result = None
            scoring_result = None
            report_path = ""
            
            # Step 1: Static analysis
            self._integrated_sandbox_stage = "Static Analysis"
            self.integratedSandboxProgress.emit("Running static analysis...")
            
            try:
                scanner = StaticScanner()
                scan_result = scanner.scan_file(str(file_path))
                static_result = result_to_dict(scan_result)
                worker.signals.heartbeat.emit(worker_id)
            except Exception as e:
                logger.error(f"Static analysis error: {e}")
                static_result = {
                    "sha256": "",
                    "file_size": file_path.stat().st_size if file_path.exists() else 0,
                    "error": str(e),
                }
            
            # Step 2: Sandbox execution (if requested)
            if run_sandbox:
                self._integrated_sandbox_stage = "Sandbox Execution"
                self.integratedSandboxProgress.emit("Running in sandbox...")
                
                try:
                    sandbox = get_integrated_sandbox()
                    avail = sandbox.availability()
                    
                    if avail.get("available"):
                        result = sandbox.run_file(
                            str(file_path),
                            timeout=timeout_seconds,
                            block_network=block_network
                        )
                        sandbox_result = result.to_dict()
                        worker.signals.heartbeat.emit(worker_id)
                    else:
                        sandbox_result = {
                            "success": False,
                            "error_message": avail.get("reason", "Sandbox not available"),
                            "platform": sys.platform,
                        }
                except Exception as e:
                    logger.warning(f"Sandbox execution error: {e}")
                    sandbox_result = {
                        "success": False,
                        "error_message": str(e),
                        "platform": sys.platform,
                    }
            
            # Step 3: Scoring
            self._integrated_sandbox_stage = "Scoring"
            self.integratedSandboxProgress.emit("Calculating threat score...")
            
            try:
                scoring_result = score_scan_results(static_result, sandbox_result)
                worker.signals.heartbeat.emit(worker_id)
            except Exception as e:
                logger.error(f"Scoring error: {e}")
                scoring_result = None
            
            # Step 4: Report generation
            self._integrated_sandbox_stage = "Report Generation"
            self.integratedSandboxProgress.emit("Generating report...")
            
            try:
                report_path = write_combined_scan_report(
                    file_path,
                    static_result,
                    sandbox_result,
                    scoring_result
                )
                report_path = str(report_path)
                worker.signals.heartbeat.emit(worker_id)
            except Exception as e:
                logger.warning(f"Report generation error: {e}")
                report_path = ""
            
            # Build final result dict for QML
            result = {
                "file_name": file_path.name,
                "file_path": str(file_path),
                "file_size": static_result.get("file_size", 0) if static_result else 0,
                "sha256": static_result.get("sha256", "") if static_result else "",
                
                # Scoring
                "score": scoring_result.score if scoring_result else 0,
                "verdict": scoring_result.verdict_label if scoring_result else "Unknown",
                "verdict_code": scoring_result.verdict if scoring_result else "unknown",
                "summary": scoring_result.summary if scoring_result else "Analysis complete",
                "explanation": scoring_result.explanation if scoring_result else "",
                
                # Static analysis summary
                "has_static": static_result is not None,
                "yara_matches_count": len(static_result.get("yara_matches", [])) if static_result else 0,
                "iocs_found": bool(static_result.get("iocs")) if static_result else False,
                "pe_analyzed": bool(static_result.get("pe_info")) if static_result else False,
                
                # Sandbox summary
                "has_sandbox": sandbox_result is not None and sandbox_result.get("success"),
                "sandbox_available": sandbox_result is not None,
                "sandbox_platform": sandbox_result.get("platform", "") if sandbox_result else "",
                "sandbox_duration": sandbox_result.get("duration_seconds", 0) if sandbox_result else 0,
                "sandbox_exit_code": sandbox_result.get("exit_code") if sandbox_result else None,
                "sandbox_timed_out": sandbox_result.get("timed_out", False) if sandbox_result else False,
                "sandbox_error": sandbox_result.get("error_message", "") if sandbox_result else "",
                
                # Report
                "report_path": report_path,
                
                # Breakdown for UI
                "score_breakdown": scoring_result.breakdown if scoring_result else {},
            }
            
            return result
        
        def on_success(wid, result):
            """Integrated scan completed."""
            if worker_id not in self._active_workers:
                return
            try:
                self._integrated_sandbox_in_progress = False
                self._integrated_sandbox_stage = ""
                self._last_report_path = result.get("report_path", "")
                
                # Save to scan history
                scan_rec = ScanRecord(
                    id=None,
                    started_at=scan_start_time.isoformat(),
                    finished_at=datetime.now().isoformat(),
                    type=ScanType.FILE,
                    target=path,
                    status="completed",
                    findings=result,
                    meta={"integrated_sandbox": True, "has_sandbox": result.get("has_sandbox")},
                )
                scan_id = self.scan_repo.add(scan_rec)
                result["scan_id"] = scan_id
                
                self.integratedSandboxFinished.emit(result)
                
                # Show toast based on verdict
                verdict = result.get("verdict", "Unknown")
                score = result.get("score", 0)
                
                if verdict == "Malicious" or score > 80:
                    self.toast.emit("error", f"⚠️ MALICIOUS - Score: {score}/100")
                elif verdict == "Likely Malicious" or score > 50:
                    self.toast.emit("error", f"⚠️ Likely Malicious - Score: {score}/100")
                elif verdict == "Suspicious" or score > 20:
                    self.toast.emit("warning", f"⚠️ Suspicious - Score: {score}/100")
                else:
                    self.toast.emit("success", f"✓ Safe - Score: {score}/100")
                    
            finally:
                if worker_id in self._active_workers:
                    del self._active_workers[worker_id]
                self._watchdog.unregister_worker(worker_id)
        
        def on_error(wid, error_msg):
            """Integrated scan failed."""
            if worker_id not in self._active_workers:
                return
            self._integrated_sandbox_in_progress = False
            self._integrated_sandbox_stage = ""
            logger.error(f"Integrated scan failed: {error_msg}")
            self.toast.emit("error", f"Scan failed: {error_msg}")
            self.integratedSandboxFinished.emit({"error": error_msg})
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]
            self._watchdog.unregister_worker(worker_id)
        
        # Create and start worker with generous timeout (sandbox can take a while)
        worker = CancellableWorker(worker_id, scan_task, timeout_ms=300000)  # 5 min
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)
        
        self._active_workers[worker_id] = worker
        self._watchdog.register_worker(worker_id)
        self._thread_pool.start(worker)
        
        logger.info(f"Integrated scan started for {path}")
    
    @Slot(str)
    def _emitIntegratedSandboxProgress(self, stage: str):
        """Thread-safe progress emission (called via QMetaObject.invokeMethod)."""
        self.integratedSandboxProgress.emit(stage)

    # ============ URL Scanning (VirusTotal-like, 100% Local) ============
    
    @Slot(result=bool)
    def urlScanAvailable(self) -> bool:
        """Check if URL scanning is available (always True, basic scan works without deps)."""
        return True
    
    @Slot(result=bool)
    def urlSandboxAvailable(self) -> bool:
        """Check if URL sandbox detonation is available (requires WebView2/Edge)."""
        if self._webview2_available is not None:
            return self._webview2_available
        
        try:
            from tools.url_detonator.webview2_detonator import check_webview2_available
            self._webview2_available = check_webview2_available()
            return self._webview2_available
        except Exception as e:
            logger.warning(f"WebView2 check failed: {e}")
            self._webview2_available = False
            return False
    
    @Slot(result=str)
    def urlSandboxStatus(self) -> str:
        """Get human-readable status of URL sandbox capability."""
        if self.urlSandboxAvailable():
            return "Available (WebView2/Edge)"
        else:
            return "Static analysis only (WebView2 not available)"
    
    @Slot(result=bool)
    def urlScanInProgress(self) -> bool:
        """Check if URL scan is in progress."""
        return self._url_scan_in_progress
    
    @Slot(result=str)
    def urlScanStage(self) -> str:
        """Get current URL scan stage."""
        return self._url_scan_stage
    
    @Slot(result=int)
    def urlScanProgressValue(self) -> int:
        """Get current URL scan progress (0-100)."""
        return self._url_scan_progress
    
    @Slot(result=str)
    def lastUrlReportPath(self) -> str:
        """Get path to the last generated URL scan report."""
        return self._last_url_report_path
    
    @Slot(str, bool, bool, int)
    def scanUrlStatic(self, url: str, block_private_ips: bool = True,
                      generate_report: bool = True, timeout_seconds: int = 30):
        """
        Run static URL analysis (no sandbox, fast).
        
        This performs:
        1. URL normalization and validation
        2. Structure analysis (TLD, path patterns, query params)
        3. Safe HTTP fetch with redirect tracking
        4. Content analysis (forms, scripts, obfuscation)
        5. IOC extraction
        6. YARA matching (if rules available)
        7. Scoring and verdict
        8. AI explanation
        
        Args:
            url: URL to scan
            block_private_ips: Block URLs to private IP ranges
            generate_report: Generate a TXT report
            timeout_seconds: HTTP request timeout
        """
        self._run_url_scan(url, use_sandbox=False, block_private_ips=block_private_ips,
                           generate_report=generate_report, timeout_seconds=timeout_seconds)
    
    @Slot(str, bool, bool, bool, int)
    def scanUrlSandbox(self, url: str, block_downloads: bool = True,
                       block_private_ips: bool = True, generate_report: bool = True,
                       timeout_seconds: int = 30):
        """
        Run full URL analysis with sandbox detonation.
        
        This performs everything in scanUrlStatic plus:
        1. WebView2 sandbox navigation
        2. Network activity capture
        3. Download attempt detection
        4. JavaScript behavior monitoring
        
        Args:
            url: URL to scan
            block_downloads: Block download attempts in sandbox
            block_private_ips: Block URLs to private IP ranges
            generate_report: Generate a TXT report
            timeout_seconds: Sandbox timeout
        """
        self._run_url_scan(url, use_sandbox=True, block_downloads=block_downloads,
                           block_private_ips=block_private_ips, generate_report=generate_report,
                           timeout_seconds=timeout_seconds)
    
    def _run_url_scan(self, url: str, use_sandbox: bool = False, block_downloads: bool = True,
                      block_private_ips: bool = True, generate_report: bool = True,
                      timeout_seconds: int = 30):
        """Internal method to run URL scan."""
        if not url or not url.strip():
            self.toast.emit("error", "URL cannot be empty")
            return
        
        url = url.strip()
        
        if self._url_scan_in_progress:
            self.toast.emit("warning", "A URL scan is already in progress")
            return
        
        worker_id = f"url-scan-{hash(url) % 10000}"
        
        if worker_id in self._active_workers:
            return
        
        self._url_scan_in_progress = True
        self._url_scan_stage = "Initializing"
        self._url_scan_progress = 0
        self.urlScanStarted.emit()
        self.urlScanProgress.emit("Initializing...", 0)
        self.toast.emit("info", f"Scanning URL: {url[:50]}...")
        scan_start_time = datetime.now()
        
        def scan_task(worker):
            """Background URL scan task."""
            from app.scanning.url_scanner import UrlScanner
            from app.scanning.url_scoring import score_url_scan
            from app.ai.url_explainer import explain_url_scan, explanation_to_dict
            from app.scanning.report_writer_url import write_url_scan_report, write_url_scan_json
            
            worker.signals.heartbeat.emit(worker_id)
            
            scan_result = None
            scoring_result = None
            explanation = None
            report_path = ""
            
            # Step 1: Run URL scan
            # Note: Progress updates happen via signals from main thread after task completes
            
            try:
                scanner = UrlScanner()
                
                if use_sandbox and self.urlSandboxAvailable():
                    scan_result = scanner.scan_sandbox(
                        url,
                        block_private_ips=block_private_ips,
                        block_downloads=block_downloads
                    )
                else:
                    scan_result = scanner.scan_static(
                        url,
                        block_private_ips=block_private_ips
                    )
                
                worker.signals.heartbeat.emit(worker_id)
            except Exception as e:
                logger.error(f"URL scan error: {e}")
                return {
                    "error": str(e),
                    "url": url,
                    "success": False,
                }
            
            # Step 2: Score the results
            try:
                scoring_result = score_url_scan(scan_result)
                # Update scan_result with score and verdict
                scan_result.score = scoring_result.score
                scan_result.verdict = scoring_result.verdict
                worker.signals.heartbeat.emit(worker_id)
            except Exception as e:
                logger.warning(f"URL scoring error: {e}")
            
            # Step 3: Generate explanation
            try:
                explanation = explain_url_scan(scan_result)
                worker.signals.heartbeat.emit(worker_id)
            except Exception as e:
                logger.warning(f"URL explanation error: {e}")
            
            # Step 4: Generate report
            if generate_report:
                try:
                    report_path = str(write_url_scan_report(scan_result, explanation))
                    # Also save JSON
                    write_url_scan_json(scan_result, explanation)
                    worker.signals.heartbeat.emit(worker_id)
                except Exception as e:
                    logger.warning(f"Report generation error: {e}")
            
            # Build result dict for QML
            result = {
                "success": True,
                "url": url,
                "normalized_url": scan_result.normalized_url,
                "final_url": scan_result.final_url,
                
                # Verdict
                "score": scan_result.score,
                "verdict": scan_result.verdict,
                
                # HTTP info
                "http_status": scan_result.http.get("status_code") if scan_result.http else None,
                "http_content_type": scan_result.http.get("content_type", "") if scan_result.http else "",
                "http_content_length": scan_result.http.get("content_length", 0) if scan_result.http else 0,
                
                # Redirects
                "redirects": scan_result.redirects,
                "redirect_count": len(scan_result.redirects),
                
                # Evidence
                "evidence": [
                    {
                        "title": e.title,
                        "severity": e.severity,
                        "detail": e.detail,
                        "category": e.category,
                    }
                    for e in scan_result.evidence
                ],
                "evidence_count": len(scan_result.evidence),
                
                # IOCs
                "iocs": scan_result.iocs or {},
                "has_iocs": bool(scan_result.iocs),
                
                # YARA
                "yara_matches": scan_result.yara_matches or [],
                "yara_match_count": len(scan_result.yara_matches) if scan_result.yara_matches else 0,
                
                # Signals
                "signals": scan_result.signals,
                
                # Sandbox
                "has_sandbox": scan_result.sandbox_result is not None,
                "sandbox_result": (
                    scan_result.sandbox_result.to_dict() 
                    if hasattr(scan_result.sandbox_result, 'to_dict') 
                    else scan_result.sandbox_result
                ) if scan_result.sandbox_result else None,
                
                # Explanation
                "explanation": explanation_to_dict(explanation) if explanation else None,
                
                # Report
                "report_path": report_path,
                
                # Scoring breakdown
                "scoring": {
                    "score": scoring_result.score if scoring_result else 0,
                    "verdict": scoring_result.verdict if scoring_result else "unknown",
                    "breakdown": scoring_result.breakdown if scoring_result else {},
                } if scoring_result else None,
            }
            
            return result
        
        def on_success(wid, result):
            """URL scan completed."""
            if worker_id not in self._active_workers:
                return
            try:
                self._url_scan_in_progress = False
                self._url_scan_stage = ""
                self._url_scan_progress = 100
                self._url_scan_result = result
                self._last_url_report_path = result.get("report_path", "")
                
                # Save to scan history
                scan_rec = ScanRecord(
                    id=None,
                    started_at=scan_start_time.isoformat(),
                    finished_at=datetime.now().isoformat(),
                    type=ScanType.URL,
                    target=url,
                    status="completed" if result.get("success") else "error",
                    findings=result,
                    meta={"url_scan": True, "has_sandbox": result.get("has_sandbox", False)},
                )
                scan_id = self.scan_repo.add(scan_rec)
                result["scan_id"] = scan_id
                
                self.urlScanFinished.emit(result)
                
                # Show toast based on verdict
                verdict = result.get("verdict", "unknown")
                score = result.get("score", 0)
                
                if verdict == "malicious" or score > 80:
                    self.toast.emit("error", f"⚠️ MALICIOUS URL - Score: {score}/100")
                elif verdict == "likely_malicious" or score > 50:
                    self.toast.emit("error", f"⚠️ Likely Malicious - Score: {score}/100")
                elif verdict == "suspicious" or score > 20:
                    self.toast.emit("warning", f"⚠️ Suspicious URL - Score: {score}/100")
                else:
                    self.toast.emit("success", f"✓ URL appears safe - Score: {score}/100")
                    
            finally:
                if worker_id in self._active_workers:
                    del self._active_workers[worker_id]
                self._watchdog.unregister_worker(worker_id)
        
        def on_error(wid, error_msg):
            """URL scan failed."""
            if worker_id not in self._active_workers:
                return
            self._url_scan_in_progress = False
            self._url_scan_stage = ""
            self._url_scan_progress = 0
            logger.error(f"URL scan failed: {error_msg}")
            self.toast.emit("error", f"URL scan failed: {error_msg}")
            self.urlScanFinished.emit({"error": error_msg, "success": False})
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]
            self._watchdog.unregister_worker(worker_id)
        
        # Create and start worker
        worker = CancellableWorker(worker_id, scan_task, timeout_ms=120000)  # 2 min
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)
        
        self._active_workers[worker_id] = worker
        self._watchdog.register_worker(worker_id)
        self._thread_pool.start(worker)
        
        logger.info(f"URL scan started for {url}")
    
    @Slot(str, int)
    def _emitUrlScanProgress(self, stage: str, progress: int):
        """Thread-safe URL scan progress emission (called via QMetaObject.invokeMethod)."""
        self.urlScanProgress.emit(stage, progress)
    
    @Slot()
    def cancelUrlScan(self):
        """Cancel the current URL scan."""
        for wid, worker in list(self._active_workers.items()):
            if wid.startswith("url-scan-"):
                worker.cancel()
                self._url_scan_in_progress = False
                self._url_scan_stage = ""
                self._url_scan_progress = 0
                self.toast.emit("info", "URL scan cancelled")
                break

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
        Uses 250ms debounce to avoid redundant requests when user scrolls quickly.
        Uses separate AI worker process to never block UI.

        Args:
            event_index: Index of the event in the current events list
        """
        # Use debouncer if available (250ms delay to handle rapid selection changes)
        if hasattr(self, '_explanation_debouncer') and self._explanation_debouncer:
            self._explanation_debouncer.call(event_index)
            return
        
        # Fallback to direct request if debouncer not initialized
        self._debounced_request_explanation(event_index)
    
    @Slot(object)
    def _debounced_request_explanation(self, event_index: int) -> None:
        """
        Request event explanation using V4 deterministic-first approach.
        
        V4 Pipeline:
        1. INSTANT: Deterministic lookup (UI thread safe, no AI)
        2. Emit deterministic result immediately  
        3. AI enhancement is requested separately via requestAIEnhancement()
        
        Args:
            event_index: Index of the event in the current events list
        """
        if not isinstance(event_index, int):
            return
            
        # Cancel any previous pending AI request
        self._cancel_current_ai_request()
        
        try:
            # Get event from cache
            events = self._loaded_events
            if not events:
                self.eventExplanationFailed.emit(str(event_index), "No events loaded. Please refresh.")
                return
                
            if event_index < 0 or event_index >= len(events):
                self.eventExplanationFailed.emit(str(event_index), f"Event index {event_index} out of range (0-{len(events)-1})")
                return

            event = events[event_index]

            # Build event dict with all required fields
            event_dict = {
                "log_name": getattr(event, "log_name", "Windows"),
                "provider": getattr(event, "source", "Unknown"),
                "source": getattr(event, "source", "Unknown"),
                "event_id": getattr(event, "event_id", 0),  # Critical: must extract event_id
                "level": getattr(event, "level", "Information"),
                "message": getattr(event, "message", ""),
                "time_created": (
                    getattr(event, "timestamp", "").isoformat()
                    if hasattr(getattr(event, "timestamp", None), "isoformat")
                    else str(getattr(event, "timestamp", ""))
                ),
            }
            
            # V4 Path: Deterministic-first (instant, UI thread safe)
            if hasattr(self, '_event_explainer') and hasattr(self._event_explainer, 'explain_event_instant'):
                logger.debug(f"V4 instant lookup for event {event_index}: provider={event_dict['provider']}, event_id={event_dict['event_id']}")
                
                # Get instant deterministic explanation (no AI, no blocking)
                structured = self._event_explainer.explain_event_instant(event_dict)
                
                # Convert StructuredExplanation to dict for QML
                result_dict = structured.to_dict() if hasattr(structured, 'to_dict') else dict(structured)
                
                # Add legacy compatibility fields
                result_dict["short_title"] = result_dict.get("title", "Event Information")
                result_dict["explanation"] = result_dict.get("what_happened", "")
                result_dict["recommendation"] = "; ".join(result_dict.get("recommended_actions", []))
                result_dict["what_to_do"] = result_dict["recommendation"]
                result_dict["why_it_happens"] = "; ".join(result_dict.get("why_it_happened", []))
                result_dict["what_you_can_do"] = result_dict["recommendation"]
                result_dict["severity_label"] = result_dict.get("severity", "Minor")
                
                # Emit result immediately
                explanation_json = json.dumps(result_dict)
                self.eventExplanationReady.emit(str(event_index), explanation_json)
                logger.info(f"V4 deterministic explanation ready for event {event_index}")
                return
            
            # Fallback: Use AI worker or thread pool
            logger.debug("V4 not available, falling back to AI worker/thread")
            
            if not self._ai_process or self._ai_process.state() != QProcess.ProcessState.Running:
                self._request_explanation_fallback(event_index)
                return

            # Send request to AI worker
            request = {"type": "explain_event", "data": event_dict}
            request_id = self._send_ai_request(request)
            
            if request_id:
                self._current_ai_request = request_id
                self._pending_ai_requests[request_id] = event_index
                logger.info(f"AI explanation requested via worker: event {event_index}")
            else:
                self.eventExplanationFailed.emit(str(event_index), "AI service unavailable")

        except Exception as e:
            logger.error(f"Failed to request explanation: {e}")
            self.eventExplanationFailed.emit(str(event_index), str(e))
    
    @Slot(int)
    def requestAIEnhancement(self, event_index: int) -> None:
        """
        Request AI enhancement for an event's explanation.
        
        Called when user clicks "Explain Event" button.
        This runs async in background and emits aiEnhancementReady when done.
        
        Args:
            event_index: Index of the event in the loaded events list
        """
        if not isinstance(event_index, int):
            return
            
        try:
            events = self._loaded_events
            if not events or event_index < 0 or event_index >= len(events):
                self.eventExplanationFailed.emit(str(event_index), "Invalid event index")
                return
            
            event = events[event_index]
            
            # Build event dict
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
            
            # V4 Path: Async AI enhancement
            if hasattr(self, '_event_explainer') and hasattr(self._event_explainer, 'request_ai_enhancement'):
                logger.info(f"Requesting AI enhancement for event {event_index}")
                
                def on_ai_ready(structured_explanation):
                    """Callback when AI enhancement completes."""
                    result_dict = structured_explanation.to_dict() if hasattr(structured_explanation, 'to_dict') else dict(structured_explanation)
                    
                    # Add legacy compatibility fields
                    result_dict["short_title"] = result_dict.get("title", "Event Information")
                    result_dict["explanation"] = result_dict.get("what_happened", "")
                    result_dict["recommendation"] = "; ".join(result_dict.get("recommended_actions", []))
                    result_dict["what_to_do"] = result_dict["recommendation"]
                    result_dict["severity_label"] = result_dict.get("severity", "Minor")
                    
                    explanation_json = json.dumps(result_dict)
                    self.eventExplanationReady.emit(str(event_index), explanation_json)
                    logger.info(f"AI enhanced explanation ready for event {event_index}")
                
                def on_ai_failed(error_msg):
                    """Callback when AI enhancement fails."""
                    logger.warning(f"AI enhancement failed for event {event_index}: {error_msg}")
                    self.eventExplanationFailed.emit(str(event_index), f"AI enhancement failed: {error_msg}")
                
                # Request async AI enhancement
                self._event_explainer.request_ai_enhancement(
                    event_dict,
                    on_ready=on_ai_ready,
                    on_failed=on_ai_failed
                )
                return
            
            # Fallback: Use AI worker
            if self._ai_process and self._ai_process.state() == QProcess.ProcessState.Running:
                request = {"type": "explain_event", "data": event_dict}
                request_id = self._send_ai_request(request)
                if request_id:
                    self._pending_ai_requests[request_id] = event_index
                    logger.info(f"AI enhancement requested via worker: event {event_index}")
                    return
            
            # Last resort: thread pool
            self._request_explanation_fallback(event_index)
            
        except Exception as e:
            logger.error(f"Failed to request AI enhancement: {e}")
            self.eventExplanationFailed.emit(str(event_index), str(e))

    def _request_explanation_fallback(self, event_index: int) -> None:
        """Fallback: use thread pool if AI worker is not available."""
        if self._event_summarizer is None and self._event_explainer is None:
            self.eventExplanationFailed.emit(str(event_index), "AI services not available")
            return

        worker_id = f"ai-explain-{event_index}"

        # Prevent duplicate requests
        if worker_id in self._active_workers:
            return

        def explain_task(worker):
            """Background AI explanation task."""
            worker.signals.heartbeat.emit(worker_id)

            # Use cached events (same as what user sees in UI)
            events = self._loaded_events
            if not events:
                raise ValueError("No events loaded. Please refresh.")
                
            if event_index < 0 or event_index >= len(events):
                raise ValueError(f"Event index {event_index} out of range (0-{len(events)-1})")

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
            
            # Check cache first
            signature = self._compute_event_signature(event_dict)
            source = event_dict["source"]
            evt_id = event_dict["event_id"]
            
            cached = None
            try:
                if hasattr(self.scan_repo, 'get_event_summary'):
                    cached = self.scan_repo.get_event_summary(source, evt_id, signature)
            except Exception as e:
                logger.debug(f"Cache lookup error: {e}")
            
            if cached:
                # Return cached explanation in the new 5-section format
                return (str(event_index), {
                    "title": cached.get("title", cached.get("short_title", "Event information")),
                    "severity": cached.get("severity", cached.get("severity_label", "Safe")),
                    "severity_label": cached.get("severity", cached.get("severity_label", "Safe")),
                    "what_happened": cached.get("what_happened", ""),
                    "why_it_happens": cached.get("why_it_happens", ""),
                    "what_to_do": cached.get("what_to_do", cached.get("what_you_can_do", "")),
                    "tech_notes": cached.get("tech_notes", ""),
                    "event_id": evt_id,
                    "source": source,
                    # Legacy fields for compatibility
                    "short_title": cached.get("title", cached.get("short_title", "Event information")),
                    "explanation": cached.get("what_happened", ""),
                    "recommendation": cached.get("what_to_do", cached.get("what_you_can_do", "")),
                    "what_you_can_do": cached.get("what_to_do", cached.get("what_you_can_do", "")),
                })
            
            # Generate using EventExplainer (preferred - detailed 5-section format)
            if self._event_explainer:
                explanation = self._event_explainer.explain_event(event_dict)
                
                # Build result dict in 5-section format
                result_dict = {
                    "title": explanation.get("short_title", "Event information"),
                    "severity": explanation.get("severity", "Safe"),
                    "severity_label": explanation.get("severity", "Safe"),
                    "what_happened": explanation.get("what_happened", explanation.get("explanation", "")),
                    "why_it_happens": explanation.get("why_it_happens", ""),
                    "what_to_do": explanation.get("what_to_do", explanation.get("recommendation", "")),
                    "tech_notes": explanation.get("tech_notes", f"Event ID: {evt_id} | Source: {source}"),
                    "event_id": evt_id,
                    "source": source,
                    # Legacy fields for compatibility
                    "short_title": explanation.get("short_title", "Event information"),
                    "explanation": explanation.get("what_happened", explanation.get("explanation", "")),
                    "recommendation": explanation.get("what_to_do", explanation.get("recommendation", "")),
                    "what_you_can_do": explanation.get("what_to_do", explanation.get("recommendation", "")),
                }
                
                # Save to cache for future use
                try:
                    if hasattr(self.scan_repo, 'save_event_summary'):
                        self.scan_repo.save_event_summary(source, evt_id, signature, result_dict)
                except Exception as e:
                    logger.debug(f"Cache save error: {e}")
                
                return (str(event_index), result_dict)
            
            # Fallback to EventSummarizer if EventExplainer unavailable
            if self._event_summarizer:
                summary = self._event_summarizer.summarize(event_dict)
                
                # Save to cache
                try:
                    if hasattr(self.scan_repo, 'save_event_summary'):
                        self.scan_repo.save_event_summary(source, evt_id, signature, summary.to_dict())
                except Exception as e:
                    logger.debug(f"Cache save error: {e}")
                
                return (str(event_index), {
                    "title": summary.title,
                    "severity": summary.severity_label,
                    "severity_label": summary.severity_label,
                    "what_happened": summary.what_happened,
                    "why_it_happens": "",
                    "what_to_do": summary.what_you_can_do,
                    "tech_notes": summary.tech_notes,
                    "event_id": summary.event_id,
                    "source": summary.source,
                    # Legacy fields for compatibility
                    "short_title": summary.title,
                    "explanation": summary.what_happened,
                    "recommendation": summary.what_you_can_do,
                    "what_you_can_do": summary.what_you_can_do,
                })
            
            raise ValueError("No AI services available")

        def on_success(wid: str, result: tuple) -> None:
            """Explanation completed."""
            event_id, explanation = result

            try:
                explanation_json = json.dumps(explanation)
                self.eventExplanationReady.emit(event_id, explanation_json)
            except Exception as e:
                logger.error(f"Failed to serialize explanation: {e}")
                self.eventExplanationFailed.emit(event_id, "Failed to process response")
            finally:
                self._watchdog.unregister_worker(worker_id)
                if worker_id in self._active_workers:
                    del self._active_workers[worker_id]

        def on_error(wid: str, error_msg: str) -> None:
            """Explanation failed."""
            logger.error(f"AI explanation failed: {error_msg}")
            self.eventExplanationFailed.emit(str(event_index), error_msg)
            self._watchdog.unregister_worker(worker_id)
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]

        # Create and start worker with 8 second timeout
        worker = CancellableWorker(worker_id, explain_task, timeout_ms=8000)
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)

        self._active_workers[worker_id] = worker
        self._watchdog.register_worker(worker_id)
        self._thread_pool.start(worker)

        logger.info(f"AI explanation requested (fallback): event {event_index}")

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
        # Also clear smart assistant conversation
        if self._smart_assistant:
            self._smart_assistant.clear_conversation()
        logger.info("Chat history cleared")

    # ========================================================================
    # SMART ASSISTANT - New intelligent chatbot with memory and context
    # ========================================================================

    @Slot(str)
    def sendSmartMessage(self, user_text: str) -> None:
        """
        Send a message to the smart assistant.
        
        This is the new intelligent chatbot that:
        - Remembers conversation context
        - Classifies intent
        - Uses deterministic tools first
        - Retrieves from local docs/KB
        - Formats structured responses
        
        Args:
            user_text: User's message text
        """
        if not user_text or not user_text.strip():
            return

        user_text = user_text.strip()

        if self._smart_assistant is None:
            self.smartAssistantError.emit("Smart Assistant not available")
            # Fall back to regular chatbot
            self.sendChatMessage(user_text)
            return

        # Emit user message immediately for UI
        self.chatMessageAdded.emit("user", user_text)

        worker_id = f"smart-chat-{hash(user_text) % 10000}"

        def smart_chat_task(worker):
            """Background smart assistant task."""
            worker.signals.heartbeat.emit(worker_id)
            
            # Process message through new agent-based smart assistant
            # Uses ask_structured() which returns full response dict
            # Has built-in timeout and throttling
            response = self._smart_assistant.ask_structured(user_text)
            return response

        def on_success(wid: str, response: dict) -> None:
            """Smart assistant response ready."""
            # Emit full response as formatted text
            display_text = self._format_smart_response(response)
            self.chatMessageAdded.emit("assistant", display_text)

            self._watchdog.unregister_worker(worker_id)
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]

        def on_error(wid: str, error_msg: str) -> None:
            """Smart assistant failed."""
            logger.error(f"Smart assistant failed: {error_msg}")
            self.smartAssistantError.emit(error_msg)
            
            # Emit error as chat message
            error_response = f"I encountered an error: {error_msg}"
            self.chatMessageAdded.emit("assistant", error_response)

            self._watchdog.unregister_worker(worker_id)
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]

        # Create and start worker with 30 second timeout
        worker = CancellableWorker(worker_id, smart_chat_task, timeout_ms=30000)
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)

        self._active_workers[worker_id] = worker
        self._watchdog.register_worker(worker_id)
        self._thread_pool.start(worker)

        logger.debug(f"Smart assistant message sent: {user_text[:50]}...")

    def _format_smart_response(self, response: dict) -> str:
        """Format smart assistant response for display."""
        parts = []
        
        # Answer (main response)
        if response.get("answer"):
            parts.append(f"**Answer**\n{response['answer']}")
        
        # Why it happened
        why = response.get("why_it_happened", [])
        if why:
            parts.append("\n**Why This Happened**")
            for reason in why[:5]:
                parts.append(f"• {reason}")
        
        # What it affects
        affects = response.get("what_it_affects", [])
        if affects:
            parts.append("\n**What This Affects**")
            for effect in affects[:5]:
                parts.append(f"• {effect}")
        
        # What to do now
        actions = response.get("what_to_do_now", [])
        if actions:
            parts.append("\n**What You Should Do**")
            for action in actions[:5]:
                parts.append(f"• {action}")
        
        # Technical details and confidence
        tech = response.get("technical_details", {})
        if tech:
            source = tech.get("source", "mixed")
            confidence = tech.get("confidence", "medium")
            conf_emoji = {"high": "🟢", "medium": "🟡", "low": "🟠"}.get(confidence, "")
            parts.append(f"\n*Source: {source} | Confidence: {conf_emoji} {confidence.title()}*")
        
        # Follow-up suggestions (if any)
        suggestions = response.get("follow_up_suggestions", [])
        if suggestions and len(suggestions) > 0:
            parts.append("\n**Ask me about:**")
            for s in suggestions[:3]:
                parts.append(f"• {s}")
        
        return "\n".join(parts)

    @Slot(str)
    def setSelectedEventForAssistant(self, event_json: str) -> None:
        """
        Set the currently selected event for the smart assistant.
        
        Args:
            event_json: JSON string of the selected event
        """
        if not self._smart_assistant:
            return
        
        try:
            event = json.loads(event_json)
            self._smart_assistant.set_selected_event(event)
            logger.debug(f"Selected event set for assistant: {event.get('event_id')}")
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid event JSON: {e}")

    @Slot()
    def clearSelectedEventForAssistant(self) -> None:
        """Clear the selected event from the smart assistant."""
        if self._smart_assistant:
            self._smart_assistant.clear_selected_event()

    @Slot(result=str)
    def getConversationSummary(self) -> str:
        """Get a summary of the current conversation."""
        if self._smart_assistant:
            return self._smart_assistant.get_conversation_summary()
        return "No conversation history"

    @Slot(result=str)
    def getAssistantStats(self) -> str:
        """Get performance and cache statistics as JSON."""
        if not self._smart_assistant:
            return "{}"
        
        stats = {
            "cache": self._smart_assistant.get_cache_stats(),
            "performance": self._smart_assistant.get_performance_stats(),
        }
        return json.dumps(stats)

    @Slot(str)
    def explainRecentEvents(self, count_str: str = "5") -> None:
        """
        Ask the smart assistant to explain recent events.
        
        Args:
            count_str: Number of events to explain (as string for QML)
        """
        try:
            count = int(count_str)
        except ValueError:
            count = 5
        
        message = f"Explain the {count} most recent events"
        self.sendSmartMessage(message)

