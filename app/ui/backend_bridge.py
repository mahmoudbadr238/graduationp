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
    eventPreviewReady = Signal(str, str)  # eventId, briefJson
    chatMessageAdded = Signal(str, str)  # role ("user"|"assistant"), content

    # Agent step tracking signals
    agentStepAdded = Signal(str)  # JSON step object
    agentStepsCleared = Signal()  # reset timeline

    # Local scan signals (100% offline)
    localScanStarted = Signal()
    localScanProgress = Signal(str)  # stage name
    localScanFinished = Signal(dict)  # result
    localUrlCheckFinished = Signal(dict)  # result

    # Integrated sandbox signals (bundled with app, no VirtualBox needed)
    integratedSandboxStarted = Signal()
    integratedSandboxProgress = Signal(str)  # stage name
    integratedSandboxFinished = Signal(dict)  # result with static + sandbox + scoring

    # VMware pipeline signals (analyzer_dynamic.py — new clean pipeline)
    sandboxProgress = Signal(int)  # 0-100 progress
    sandboxFinished = Signal(dict)  # SandboxJobResult
    sandboxFailed = Signal(str)  # error message
    sandboxStateChanged = Signal(
        str
    )  # JobState constant: IDLE/STARTING/RUNNING/COLLECTING/CLEANUP/FINISHED/FAILED/CANCELLED
    sandboxExplainFinished = Signal(
        dict
    )  # AI explanation response from report_explainer.explain_report()
    scanReportExported = Signal(
        dict
    )  # {ok, exported_report_path, exported_artifacts_path, sha256}
    sentinelReportLoaded = Signal(
        dict
    )  # normalized SentinelReport dict (for history replay in QML)
    scanHistoryLoaded = Signal(
        str, list
    )  # (request_id, list-of-scan_history-row-dicts)
    vmwareDiagnosticsResult = Signal(list)  # list of check dicts
    sandboxScreenshot = Signal(str)  # absolute path to latest PNG screenshot

    # Sandbox live view signals (real-time event streaming)
    sandboxEventBatch = Signal(str)  # JSON array of sandbox events
    sandboxStatsUpdate = Signal(str)  # JSON object with session stats
    sandboxSessionEnded = Signal(str)  # JSON session summary

    # Live preview signals (video-like window capture)
    sandboxPreviewStarted = Signal()  # Preview capture started
    sandboxPreviewStopped = Signal()  # Preview capture stopped
    sandboxPreviewFrameReady = Signal(int)  # New frame available (frame number)
    sandboxWindowFound = Signal(bool)  # Whether sandbox window was found
    sandboxAutopilotAction = Signal(str)  # Autopilot performed an action (JSON)

    # URL scan signals (VirusTotal-like, 100% local)
    urlScanStarted = Signal()
    urlScanProgress = Signal(str, int)  # stage name, progress %
    urlScanFinished = Signal(dict)  # result with verdict, score, evidence, explanation

    # Smart Assistant signals (new intelligent chatbot)
    smartAssistantResponse = Signal(
        str
    )  # JSON string of structured response (safer for QML)
    smartAssistantError = Signal(str)  # Error message

    # Resolution Report signals
    resolutionSessionsLoaded = Signal(str)  # JSON string of sessions array

    # ScanCenter signals — market-ready file scanner (v3 report pipeline)
    scanCenterProgress = Signal(int, str)       # percent 0-100, stage label
    scanCenterFinished = Signal(dict)           # V3Report.to_dict() — full report
    scanCenterFailed   = Signal(str)            # error message
    scanCenterHistoryLoaded = Signal(list)      # list[dict] history rows
    scanCenterExplainFinished = Signal(dict)    # AiExplanation.to_dict()
    scanCenterExported  = Signal(dict)          # {ok, report_path, zip_path, sha256}
    scanCenterPhaseUpdate = Signal(str)         # JSON: {phase, status, summary, score, pct}
    # Emitted from the preview-capture thread; carries a cache-busted file:/// URL
    # or an empty string when the preview stops.
    scanCenterPreviewUpdated = Signal(str)      # "file:///path/to/preview.png?ts=N" | ""

    # Navigation signal (for cross-page navigation)
    navigateTo = Signal(str)  # route name (e.g., "ai-assistant")

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
        self._current_ai_request: str | None = (
            None  # Track current request to cancel old ones
        )
        self._ai_ready = False

        # Event summarizer for friendly messages
        self._event_summarizer = None

        # Smart Assistant (new intelligent chatbot with memory and context)
        self._smart_assistant = None

        # Sandbox session for live event streaming
        self._sandbox_session = None
        self._sandbox_cancelled = False

        # VMware pipeline job tracking
        self._vmware_job_id: str | None = None
        self._vmware_cancel_events: dict[str, threading.Event] = {}

        # Live preview (video-like window capture)
        self._window_capture = None  # WindowCaptureService instance
        self._preview_provider = None  # SandboxPreviewProvider for QML
        self._preview_controller = None  # SandboxPreviewController for signals
        self._installer_autopilot = None  # InstallerAutopilot for safe interaction
        self._autopilot_enabled = False

        # Agent step tracking (for Agent Report / Replay pages)
        self._agent_steps: list[dict] = []

        # Debounce guard: prevents multiple concurrent list-scan-history threads
        self._list_scan_history_pending: bool = False

        # ScanCenter pipeline state
        self._scancenter_controller = None   # ScanController while a scan is running
        self._scancenter_cancel = threading.Event()
        self._scancenter_current_report: dict | None = None  # last finished V3 report

        self._init_ai_services()
        self._init_smart_assistant()
        self._init_scan_history_table()

        # Pre-warm security snapshot cache (background, non-blocking)
        # This speeds up first chatbot security question by 3-5 seconds
        self._prewarm_security_snapshot()

        # NOTE: AI worker (ai_worker.py) has been archived - now using agent-based SmartAssistant
        # The V4 event explainer handles all explanations deterministically
        # QTimer.singleShot(2000, self._start_ai_worker)  # Disabled - archived

    def _event_to_dict(self, e) -> dict:
        """Convert an event object to a dictionary."""
        if hasattr(e, "to_dict"):
            return e.to_dict()
        if isinstance(e, dict):
            return e
        return {
            "record_id": getattr(e, "record_id", 0),
            "log_name": getattr(e, "log_name", "System"),
            "event_id": getattr(e, "event_id", 0),
            "provider": getattr(e, "provider", getattr(e, "source", "Unknown")),
            "level": getattr(e, "level", "Information"),
            "message": getattr(e, "message", "")[:500],
            "time_created": str(getattr(e, "time_created", "")),
        }

    def _normalize_file_scan_result_for_qml(self, result: dict | None) -> dict:
        """Ensure file scan payload always contains QML-consumed keys."""
        payload = result if isinstance(result, dict) else {}
        normalized = dict(payload)

        iocs = normalized.get("iocs")
        if not isinstance(iocs, dict):
            iocs = {}
        normalized["iocs"] = iocs

        yara_matches = normalized.get("yara_matches")
        if not isinstance(yara_matches, list):
            yara_matches = []

        pe_info = normalized.get("pe_info")
        if not isinstance(pe_info, dict):
            pe_info = {}

        pe_analysis = normalized.get("pe_analysis")
        if not isinstance(pe_analysis, dict):
            pe_analysis = {}

        sandbox_data = normalized.get("sandbox_result")
        if not isinstance(sandbox_data, dict):
            sandbox_data = normalized.get("sandbox")
        if not isinstance(sandbox_data, dict):
            sandbox_data = {}

        defaults = {
            "file_name": "",
            "file_path": "",
            "file_size": 0,
            "sha256": "",
            "mime_type": "",
            "verdict": "Unknown",
            "score": 0,
            "summary": "",
            "explanation": "",
            "yara_matches_count": None,
            "iocs_found": None,
            "pe_analyzed": None,
            "has_sandbox": None,
            "sandbox_duration": None,
            "sandbox_error": "",
            "report_content": "",
            "report_path": "",
            "error": "",
        }
        normalized = {**defaults, **normalized}

        if normalized.get("yara_matches_count") is None:
            if isinstance(normalized.get("yara_match_count"), int):
                normalized["yara_matches_count"] = normalized.get("yara_match_count", 0)
            else:
                normalized["yara_matches_count"] = len(yara_matches)

        if normalized.get("iocs_found") is None:
            normalized["iocs_found"] = any(bool(v) for v in iocs.values())

        if normalized.get("pe_analyzed") is None:
            normalized["pe_analyzed"] = bool(pe_info or pe_analysis)

        if normalized.get("has_sandbox") is None:
            normalized["has_sandbox"] = bool(sandbox_data) and bool(
                sandbox_data.get("success", True)
            )

        if normalized.get("sandbox_duration") is None:
            normalized["sandbox_duration"] = sandbox_data.get(
                "duration_seconds",
                sandbox_data.get("duration", 0),
            )

        if not normalized.get("sandbox_error"):
            normalized["sandbox_error"] = sandbox_data.get(
                "error_message",
                sandbox_data.get("error", ""),
            )

        normalized["summary"] = str(normalized.get("summary") or "")
        normalized["explanation"] = str(normalized.get("explanation") or "")
        normalized["error"] = str(normalized.get("error") or "")
        normalized["report_content"] = str(normalized.get("report_content") or "")
        normalized["report_path"] = str(normalized.get("report_path") or "")

        return normalized

    def _normalize_url_scan_result_for_qml(self, result: dict | None) -> dict:
        """Ensure URL scan payload always contains QML-consumed keys."""
        payload = result if isinstance(result, dict) else {}
        normalized = dict(payload)

        redirects = normalized.get("redirects")
        if not isinstance(redirects, list):
            redirects = []
        normalized["redirects"] = redirects

        evidence = normalized.get("evidence")
        if not isinstance(evidence, list):
            evidence = []
        normalized["evidence"] = evidence

        iocs = normalized.get("iocs")
        if not isinstance(iocs, dict):
            iocs = {}
        normalized["iocs"] = iocs

        yara_matches = normalized.get("yara_matches")
        if not isinstance(yara_matches, list):
            yara_matches = []

        explanation = normalized.get("explanation")
        if explanation and not isinstance(explanation, dict):
            explanation = {"technical_summary": str(explanation)}
        if isinstance(explanation, dict):
            explanation_defaults = {
                "what_it_is": "",
                "why_risky": "",
                "what_to_do": "",
                "technical_summary": "",
                "confidence": "",
            }
            explanation = {**explanation_defaults, **explanation}
        normalized["explanation"] = explanation

        defaults = {
            "success": None,
            "url": "",
            "final_url": "",
            "http_status": 0,
            "redirect_count": None,
            "verdict": "unknown",
            "score": 0,
            "summary": "",
            "evidence_count": None,
            "has_iocs": None,
            "yara_match_count": None,
            "report_content": "",
            "error": "",
        }
        normalized = {**defaults, **normalized}

        if not normalized.get("url"):
            normalized["url"] = str(
                normalized.get("input_url")
                or normalized.get("normalized_url")
                or normalized.get("final_url")
                or ""
            )

        if not normalized.get("final_url"):
            normalized["final_url"] = str(
                normalized.get("normalized_url") or normalized.get("url") or ""
            )

        if normalized.get("redirect_count") is None:
            normalized["redirect_count"] = len(redirects)

        if normalized.get("evidence_count") is None:
            normalized["evidence_count"] = len(evidence)

        if normalized.get("has_iocs") is None:
            normalized["has_iocs"] = any(bool(v) for v in iocs.values())

        if normalized.get("yara_match_count") is None:
            normalized["yara_match_count"] = len(yara_matches)

        if normalized.get("success") is None:
            normalized["success"] = not bool(normalized.get("error"))

        normalized["summary"] = str(normalized.get("summary") or "")
        normalized["error"] = str(normalized.get("error") or "")
        normalized["report_content"] = str(normalized.get("report_content") or "")

        return normalized

    # ==================== AGENT STEP TRACKING ====================

    def _add_agent_step(
        self, title: str, purpose: str, action: str, result: str
    ) -> None:
        """Add an agent step and emit to QML for the timeline/replay."""
        import time

        step = {
            "index": len(self._agent_steps),
            "timestamp": time.time(),
            "title": title,
            "purpose": purpose,
            "action": action,
            "result": result,
        }
        self._agent_steps.append(step)
        self.agentStepAdded.emit(json.dumps(step))

    @Slot(result=str)
    def getAgentSteps(self) -> str:
        """Return all agent steps as JSON array for QML."""
        return json.dumps(self._agent_steps)

    # ==================== EVENT PREVIEW (INSTANT, NO AI) ====================

    @Slot(int)
    def previewEvent(self, event_index: int) -> None:
        """
        Instant friendly preview for an event (no AI, no async).
        Called when user selects an event row.
        """
        if not isinstance(event_index, int):
            return

        # Clear agent steps for this new event
        self._agent_steps.clear()
        self.agentStepsCleared.emit()
        self._add_agent_step(
            "Event Selected",
            "User selected an event row",
            "parsed event fields",
            f"Event index {event_index} selected",
        )

        try:
            events = self._loaded_events
            if not events or event_index < 0 or event_index >= len(events):
                return

            event = events[event_index]
            provider = getattr(event, "source", "Unknown")
            event_id = getattr(event, "event_id", 0)
            level = getattr(event, "level", "Information")
            message = getattr(event, "message", "")

            self._add_agent_step(
                "Knowledge Base Lookup",
                "Find a known explanation for this event",
                "matched template by provider + event_id",
                f"Looking up {provider}:{event_id}",
            )

            # Use rules engine for instant lookup (no AI)
            brief = self._generate_friendly_preview(provider, event_id, level, message)

            self._add_agent_step(
                "Preview Generated",
                "Format a short friendly summary",
                "built meaning + risk + actions",
                f"Risk: {brief.get('risk', 'Low')}",
            )

            preview_json = json.dumps(brief)
            self.eventPreviewReady.emit(str(event_index), preview_json)
            logger.info(
                f"Preview ready for event {event_index}: {brief.get('risk', 'Low')}"
            )

        except Exception as e:
            logger.error(f"Failed to preview event: {e}")

    def _generate_friendly_preview(
        self, provider: str, event_id: int, level: str, message: str
    ) -> dict:
        """
        Generate a friendly, non-technical preview from KB rules.
        Returns {meaning, risk, risk_reason, actions[]}.
        """
        # Use the rules engine if available
        if hasattr(self, "_event_explainer") and self._event_explainer:
            try:
                from ..ai.event_rules_engine import get_event_rules_engine

                engine = get_event_rules_engine()
                kb = engine.lookup(
                    provider=provider,
                    event_id=event_id,
                    level=level,
                    raw_message=message,
                )

                # Map severity to risk
                risk_map = {
                    "Safe": "Low",
                    "Minor": "Low",
                    "Warning": "Medium",
                    "Critical": "High",
                }
                risk = risk_map.get(kb.severity, "Low")

                # Build friendly meaning (no jargon)
                meaning = kb.impact if kb.impact else kb.title
                if not meaning or meaning == "System event recorded":
                    meaning = self._make_friendly_meaning(provider, event_id, level)

                # Build simple actions (max 3, <=10 words each)
                actions = []
                for act in (kb.actions or [])[:3]:
                    simplified = act.split(".")[0].strip()
                    words = simplified.split()
                    if len(words) > 10:
                        simplified = " ".join(words[:10])
                    actions.append(simplified)
                if not actions:
                    actions = self._default_actions(level)

                risk_reason = self._risk_reason(kb.severity, level, kb.matched)

                return {
                    "meaning": meaning,
                    "risk": risk,
                    "risk_reason": risk_reason,
                    "actions": actions,
                    "source_matched": kb.matched,
                    "title": kb.title,
                }
            except Exception as e:
                logger.debug(f"KB preview error: {e}")

        # Fallback: generic template based on level
        risk_map = {
            "Error": "Medium",
            "Critical": "High",
            "Warning": "Medium",
            "Information": "Low",
            "Info": "Low",
        }
        risk = risk_map.get(level, "Low")
        return {
            "meaning": self._make_friendly_meaning(provider, event_id, level),
            "risk": risk,
            "risk_reason": f"This is a{'n ' + level.lower() if level else ' normal'} event",
            "actions": self._default_actions(level),
            "source_matched": False,
            "title": f"Event {event_id}",
        }

    @staticmethod
    def _make_friendly_meaning(provider: str, event_id: int, level: str) -> str:
        """Create a simple, jargon-free meaning sentence."""
        level_lower = level.lower() if level else "informational"
        if level_lower in ("error", "critical"):
            return f"Your computer noticed a problem reported by {provider}."
        if level_lower == "warning":
            return f"Your computer flagged something worth checking from {provider}."
        return (
            f"A routine system update was logged by {provider}. Nothing to worry about."
        )

    @staticmethod
    def _default_actions(level: str) -> list:
        """Return default simple actions based on event level."""
        level_lower = (level or "").lower()
        if level_lower in ("error", "critical"):
            return [
                "Check if your apps work normally",
                "Restart your computer if needed",
                "Contact support if it repeats",
            ]
        if level_lower == "warning":
            return ["Keep an eye on this event", "No action needed right now"]
        return ["No action needed"]

    @staticmethod
    def _risk_reason(severity: str, level: str, matched: bool) -> str:
        """Return a simple risk explanation."""
        if severity in ("Safe", "Minor"):
            return "This event is routine and safe"
        if severity == "Warning":
            return "This may need attention if it repeats often"
        if severity == "Critical":
            return "This event may indicate a real problem"
        return f"Based on the event level: {level}"

    def _prewarm_security_snapshot(self):
        """Pre-warm security snapshot cache in background."""
        try:
            from ..utils.security_snapshot import prewarm_security_snapshot

            prewarm_security_snapshot()
        except ImportError:
            pass  # Module not available

    def _init_ai_services(self):
        """Initialize AI services with Groq Cloud as primary provider.

        Uses V5 architecture with:
        - Groq Cloud AI as primary provider (free tier)
        - Offline EventRulesEngine for instant KB lookups
        - SQLite caching for persistence
        - Claude/OpenAI as fallback providers
        """
        try:
            from ..ai.performance import Debouncer

            # Create 250ms debouncer for event explanation
            self._explanation_debouncer = Debouncer(250, self)
            self._explanation_debouncer.triggered.connect(
                self._debounced_request_explanation
            )

            # Try V5 (Groq-powered) first
            try:
                from ..ai.event_explainer_v5 import get_event_explainer_v5
                from ..ai.providers.groq import is_groq_available
                from ..ai.security_chatbot_v4 import get_security_chatbot_v4

                # Initialize V5 explainer (Groq + offline KB)
                self._event_explainer = get_event_explainer_v5(db_repo=self.scan_repo)

                # Connect signals for async explanations
                self._event_explainer.explanationReady.connect(
                    self._on_v5_explanation_ready
                )
                self._event_explainer.explanationFailed.connect(
                    self._on_v5_explanation_failed
                )

                # Initialize V4 chatbot (Groq with memory)
                self._security_chatbot = get_security_chatbot_v4()
                self._security_chatbot.chatResponseReady.connect(self._on_v4_chat_ready)
                self._security_chatbot.chatResponseFailed.connect(
                    self._on_v4_chat_failed
                )

                # Update chatbot with system context
                self._security_chatbot.set_system_context(
                    {
                        "get_defender_status": self._get_defender_status_for_ai,
                        "get_firewall_status": self._get_firewall_status_for_ai,
                        "get_recent_events": lambda: self._loaded_events[:20],
                    }
                )

                if is_groq_available():
                    logger.info("AI services initialized (Groq Cloud + offline KB)")
                else:
                    logger.info(
                        "AI services initialized (offline KB only - set GROQ_API_KEY for cloud AI)"
                    )

            except ImportError as e:
                # V5 not available - disable AI services
                logger.warning(f"V5 AI not available: {e}. AI services disabled.")
                self._event_explainer = None
                self._security_chatbot = None

        except Exception as e:
            logger.warning(f"AI services not available: {e}")
            self._event_explainer = None
            self._security_chatbot = None

    def _on_v5_explanation_ready(self, request_id: str, result_json: str):
        """Handle V5 explainer async completion (Groq AI enhancement)."""
        try:
            # Look up event_index from pending requests
            pending = getattr(self, "_pending_v5_requests", {})
            event_index = pending.pop(request_id, None)

            if event_index is None:
                # Try extracting from request_id
                event_index = request_id.replace("explain_", "")

            # Parse and add source marker
            result_dict = json.loads(result_json)
            result_dict["ai_enhanced"] = True
            result_dict["source"] = result_dict.get("source", "groq")

            # Add legacy compatibility fields
            result_dict["short_title"] = result_dict.get("title", "Event Information")
            result_dict["explanation"] = result_dict.get("what_happened", "")
            result_dict["recommendation"] = "; ".join(
                result_dict.get("what_to_do", [])
                if isinstance(result_dict.get("what_to_do"), list)
                else [result_dict.get("what_to_do", "")]
            )
            result_dict["why_it_happens"] = "; ".join(
                result_dict.get("why_it_happened", [])
                if isinstance(result_dict.get("why_it_happened"), list)
                else []
            )
            result_dict["what_you_can_do"] = result_dict["recommendation"]
            result_dict["severity_label"] = result_dict.get("severity", "Minor")

            explanation_json = json.dumps(result_dict)
            self.eventExplanationReady.emit(str(event_index), explanation_json)
            logger.info(f"Groq AI enhancement ready for event {event_index}")
            self._add_agent_step(
                "AI Enhancement Complete",
                "Groq Cloud AI returned detailed analysis",
                "post-processed output",
                "AI-enhanced explanation displayed",
            )
        except Exception as e:
            logger.error(f"Failed to emit V5 explanation: {e}")

    def _on_v5_explanation_failed(self, request_id: str, error_msg: str):
        """Handle V5 explainer async failure."""
        event_index = request_id.replace("explain_", "")
        self.eventExplanationFailed.emit(event_index, error_msg)

    def _on_v4_chat_ready(self, request_id: str, response_json: str):
        """Handle V4 chatbot async completion."""
        try:
            response = json.loads(response_json)
            answer = response.get("answer", "")
            # Add to conversation history
            self._chat_conversation.append({"role": "assistant", "content": answer})
            # Emit to QML
            self.chatMessageAdded.emit("assistant", answer)
        except Exception as e:
            logger.error(f"Failed to emit V4 chat response: {e}")
            error_msg = "I encountered an error processing your request."
            self._chat_conversation.append({"role": "assistant", "content": error_msg})
            self.chatMessageAdded.emit("assistant", error_msg)

    def _on_v4_chat_failed(self, request_id: str, error_msg: str):
        """Handle V4 chatbot async failure."""
        error_response = f"Sorry, I encountered an error: {error_msg}"
        self._chat_conversation.append({"role": "assistant", "content": error_response})
        self.chatMessageAdded.emit("assistant", error_response)

    def _get_defender_status_for_ai(self) -> dict:
        """Get Defender status for AI context."""
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

    def _get_firewall_status_for_ai(self) -> dict:
        """Get Firewall status for AI context."""
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

    def _init_smart_assistant(self):
        """Initialize the smart assistant using Groq AI (primary) or Claude/OpenAI (fallback)."""
        try:
            # Helper function for recent events
            def get_recent_events(limit=20, log_name=None):
                events = []
                for e in self._loaded_events[:limit] if self._loaded_events else []:
                    events.append(self._event_to_dict(e))
                return events

            def get_event_details(record_id=None, event_id=None, log_name=None):
                for e in self._loaded_events or []:
                    e_record_id = getattr(
                        e, "record_id", e.get("record_id") if isinstance(e, dict) else 0
                    )
                    e_event_id = getattr(
                        e, "event_id", e.get("event_id") if isinstance(e, dict) else 0
                    )
                    if record_id and e_record_id == record_id:
                        return self._event_to_dict(e)
                    if event_id and e_event_id == event_id:
                        return self._event_to_dict(e)
                return None

            def search_events(query, limit=20):
                query_lower = query.lower()
                matches = []
                for e in self._loaded_events or []:
                    msg = getattr(
                        e,
                        "message",
                        e.get("message", "") if isinstance(e, dict) else "",
                    )
                    provider = getattr(
                        e,
                        "provider",
                        e.get("provider", "") if isinstance(e, dict) else "",
                    )
                    event_id = str(
                        getattr(
                            e,
                            "event_id",
                            e.get("event_id", 0) if isinstance(e, dict) else 0,
                        )
                    )

                    if (
                        query_lower in msg.lower()
                        or query_lower in provider.lower()
                        or query_lower in event_id
                    ):
                        matches.append(self._event_to_dict(e))
                        if len(matches) >= limit:
                            break
                return matches

            tool_callbacks = {
                "get_defender_status": self._get_defender_status_for_ai,
                "get_firewall_status": self._get_firewall_status_for_ai,
                "get_recent_events": get_recent_events,
                "get_event_details": get_event_details,
                "search_events": search_events,
            }

            # Try Groq first (free tier)
            try:
                from ..ai.groq_smart_assistant import create_groq_smart_assistant
                from ..ai.providers.groq import is_groq_available

                if is_groq_available():
                    self._smart_assistant = create_groq_smart_assistant(
                        tool_callbacks=tool_callbacks,
                    )
                    logger.info("Smart Assistant initialized (Groq AI)")
                    return
                logger.info(
                    "Groq not configured, will use assistant with helpful error messages"
                )

            except ImportError as e:
                logger.debug(f"Groq smart assistant not available: {e}")

            # Use Groq assistant - will show helpful error if no API key
            from ..ai.groq_smart_assistant import create_groq_smart_assistant

            self._smart_assistant = create_groq_smart_assistant(
                tool_callbacks=tool_callbacks,
            )
            logger.info("Smart Assistant initialized (Groq)")

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
                logger.debug(
                    f"Processing AI response id={request_id}, current={self._current_ai_request}"
                )

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
        error_output = bytes(self._ai_process.readAllStandardError().data()).decode(
            "utf-8"
        )
        for line in error_output.strip().split("\n"):
            if line:
                logger.debug(f"AI Worker: {line}")

    def _on_ai_finished(self, exit_code, exit_status):
        """Handle AI worker process termination."""
        logger.warning(
            f"AI worker process finished: code={exit_code}, status={exit_status}"
        )
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
            if hasattr(self._security_chatbot, "_context_builder"):
                self._security_chatbot._context_builder._snapshot = snapshot_service  # type: ignore[union-attr]
                logger.info("Snapshot service connected to AI chatbot context builder")
            # V1 chatbot uses direct service
            elif hasattr(self._security_chatbot, "_snapshot_service"):
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

                for idx, evt in enumerate(events):
                    event_dict = {
                        "timestamp": evt.timestamp.isoformat()
                        if hasattr(evt.timestamp, "isoformat")
                        else str(evt.timestamp),
                        "time_created": evt.timestamp.isoformat()
                        if hasattr(evt.timestamp, "isoformat")
                        else str(evt.timestamp),
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
                        if hasattr(self.scan_repo, "get_event_summary"):
                            cached = self.scan_repo.get_event_summary(
                                source, event_id, signature
                            )
                    except Exception as e:
                        logger.debug(f"Cache lookup error: {e}")

                    if cached:
                        # Use cached friendly message
                        event_dict["friendly_message"] = cached.get(
                            "table_summary", event_dict["message"]
                        )
                        event_dict["_has_summary"] = True
                    # Generate summary using EventSummarizer (rule-based, fast)
                    elif self._event_summarizer:
                        try:
                            summary = self._event_summarizer.summarize(event_dict)
                            event_dict["friendly_message"] = summary.table_summary
                            event_dict["_has_summary"] = True

                            # Save to database cache for future use
                            if hasattr(self.scan_repo, "save_event_summary"):
                                try:
                                    self.scan_repo.save_event_summary(
                                        source, event_id, signature, summary.to_dict()
                                    )
                                except Exception as e:
                                    logger.debug(f"Cache save error: {e}")
                        except Exception as e:
                            logger.debug(f"Summary generation error: {e}")
                            # Fallback to truncated message
                            event_dict["friendly_message"] = (
                                event_dict["message"][:100] + "..."
                                if len(event_dict["message"]) > 100
                                else event_dict["message"]
                            )
                            event_dict["_has_summary"] = False
                    else:
                        # No summarizer available - use truncated message
                        event_dict["friendly_message"] = (
                            event_dict["message"][:100] + "..."
                            if len(event_dict["message"]) > 100
                            else event_dict["message"]
                        )
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
    def virusTotalEnabled(self):
        """Check if VirusTotal integration is enabled."""
        return self.file_scanner is not None and self.url_scanner is not None

    @Slot()
    def loadScanHistory(self):
        """Load all scan records from database (async, never blocks UI)."""

        def load_in_thread():
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

                # Emit on main thread via QTimer
                from PySide6.QtCore import QTimer

                QTimer.singleShot(0, lambda: self._emit_scans_loaded(scan_dicts))
            except (OSError, ValueError, KeyError) as e:
                from PySide6.QtCore import QTimer

                QTimer.singleShot(0, lambda err=e: self._emit_scans_error(str(err)))

        # Run in background thread
        import threading

        thread = threading.Thread(
            target=load_in_thread, daemon=True, name="LoadScanHistory"
        )
        thread.start()

    def _emit_scans_loaded(self, scan_dicts):
        """Emit scansLoaded signal on main thread."""
        self.scansLoaded.emit(scan_dicts)
        if len(scan_dicts) > 0:
            self.toast.emit("info", f"Loaded {len(scan_dicts)} scan records")

    def _emit_scans_error(self, error_msg):
        """Emit error toast on main thread."""
        self.toast.emit("error", f"Failed to load scan history: {error_msg}")
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

    # VMware pipeline state (analyzer_dynamic.py)
    _vmware_job_id: str | None = None
    _vmware_cancel_events: dict = {}  # job_id → threading.Event

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
            from ..scanning import ReportWriter, SandboxController, StaticScanner

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

            # Run VMware sandbox if requested
            if run_sandbox and not result.sandbox:
                try:
                    sandbox = SandboxController()

                    # Emit 7-step progress to QML via localScanProgress
                    _step_messages: list[str] = []

                    def _sandbox_progress(step: int, msg: str) -> None:
                        stage = f"Sandbox [{step}/7]: {msg}"
                        _step_messages.append(stage)
                        try:
                            self.localScanProgress.emit(stage)
                        except Exception:
                            pass

                    if not sandbox.is_available:
                        # Always emit step 2 so UI knows sandbox is not configured
                        _sandbox_progress(
                            2,
                            "VMware not configured — see Settings for setup instructions",
                        )
                        result.sandbox = {
                            "status": sandbox.run_sample(path, timeout=5).status,
                            "duration": 0,
                            "processes": [],
                            "files_created": [],
                            "files_modified": [],
                            "registry_modified": [],
                            "network_connections": [],
                            "not_configured": True,
                            "steps": _step_messages,
                        }
                    else:
                        sandbox_result = sandbox.run_sample(
                            path,
                            timeout=120,
                            progress_cb=_sandbox_progress,
                        )
                        result.sandbox = {
                            "status": sandbox_result.status,
                            "duration": sandbox_result.duration,
                            "processes": [
                                (
                                    p.get("name", str(p))
                                    if isinstance(p, dict)
                                    else str(p)
                                )
                                for p in sandbox_result.processes
                            ],
                            "files_created": sandbox_result.files_created[:20],
                            "files_modified": sandbox_result.files_modified[:20],
                            "files_deleted": sandbox_result.files_deleted[:20],
                            "registry_modified": sandbox_result.registry_modified[:20],
                            "network_connections": sandbox_result.network_connections[
                                :20
                            ],
                            "success": sandbox_result.success,
                            "error": sandbox_result.error or "",
                            "steps": _step_messages,
                        }
                except Exception as e:
                    logger.warning(f"VMware sandbox error: {e}")
                    result.sandbox = {
                        "status": "error",
                        "error": str(e),
                        "steps": [],
                    }

            # Generate report
            try:
                report_path = report_writer.write_file_report(result)
                report_path_str = str(report_path)
            except Exception as e:
                logger.warning(f"Report generation error: {e}")
                report_path_str = ""

            # Convert to dict for QML
            sandbox_data = result.sandbox or {}
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
                "yara_matches_count": len(result.yara_matches)
                if result.yara_matches
                else 0,
                "clamav_infected": result.clamav.get("infected", False)
                if result.clamav
                else False,
                "has_sandbox": result.sandbox is not None,
                "sandbox_status": sandbox_data.get("status", ""),
                "sandbox_steps": sandbox_data.get("steps", []),
                "sandbox_success": bool(sandbox_data.get("success", False)),
                "sandbox_duration": sandbox_data.get("duration", 0),
                "sandbox_error": sandbox_data.get("error", ""),
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

                # ── Schema guardrail ────────────────────────────────────────────────
                try:
                    from ..scanning.report_schema import normalize_report_v2 as _nrv2

                    _raw_sr = result.get("sentinel_report")
                    result["sentinel_report"] = _nrv2(
                        _raw_sr if isinstance(_raw_sr, dict) else {}
                    )
                    result.setdefault("sentinel_report_path", "")
                except Exception as _ge:
                    logger.debug("sentinel_report normalize (local) skipped: %s", _ge)
                    result.setdefault("sentinel_report", {})
                    result.setdefault("sentinel_report_path", "")

                self.localScanFinished.emit(result)

                # Show toast based on verdict
                verdict = result.get("verdict", "Unknown")
                if verdict == "Malicious":
                    self.toast.emit(
                        "error",
                        f"⚠️ File is MALICIOUS (Score: {result.get('score', 0)}/100)",
                    )
                elif verdict == "Suspicious":
                    self.toast.emit(
                        "warning",
                        f"⚠️ File is suspicious (Score: {result.get('score', 0)}/100)",
                    )
                else:
                    self.toast.emit(
                        "success",
                        f"✓ File appears clean (Score: {result.get('score', 0)}/100)",
                    )

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
        # Register with longer stall threshold if sandbox is enabled
        stall_threshold = (
            90 if run_sandbox else 30
        )  # 90s for sandbox, 30s for static only
        self._watchdog.register_worker(worker_id, stale_threshold_sec=stall_threshold)
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

        self.toast.emit("info", "Checking URL locally...")
        scan_start_time = datetime.now()

        def check_task(worker):
            """Background URL check task"""
            from ..scanning import ReportWriter, URLChecker

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
                    self.toast.emit(
                        "error",
                        f"⚠️ URL is MALICIOUS (Score: {result.get('score', 0)}/100)",
                    )
                elif verdict == "Suspicious":
                    self.toast.emit(
                        "warning",
                        f"⚠️ URL is suspicious (Score: {result.get('score', 0)}/100)",
                    )
                else:
                    self.toast.emit(
                        "success",
                        f"✓ URL appears safe (Score: {result.get('score', 0)}/100)",
                    )

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
        """Open the reports folder in Windows Explorer."""
        import subprocess

        from ..scanning import ReportWriter

        if path:
            folder = Path(path).parent
        else:
            folder = ReportWriter().reports_dir

        if folder.exists():
            subprocess.run(["explorer", str(folder)], check=False)

    @Slot(result=bool)
    def sandboxAvailable(self) -> bool:
        """Check if VMware sandbox is available and configured."""
        try:
            from ..scanning import SandboxController

            controller = SandboxController()
            return controller.is_available
        except Exception:
            return False

    @Slot(result=list)
    def sandboxMethods(self) -> list:
        """Get available sandbox methods (e.g. [\"VMware Workstation\"])."""
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
        Check if integrated sandbox (Job Object) is available on this Windows system.
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
            reason = avail.get("reason", "Unknown reason")
            return f"Not available: {reason}"
        except (ImportError, OSError) as e:
            # OSError includes DLL loading errors
            # Don't show full error message for optional dependencies
            if "libyara.dll" in str(e) or "DLL" in str(e):
                return "Available (Windows Sandbox/Job Object)"
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
    def runIntegratedScan(
        self,
        path: str,
        run_sandbox: bool = True,
        block_network: bool = True,
        timeout_seconds: int = 30,
    ):
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
            from dataclasses import asdict, is_dataclass

            from ..scanning.friendly_report import get_friendly_report_generator
            from ..scanning.integrated_sandbox import get_integrated_sandbox
            from ..scanning.scoring import score_scan_results
            from ..scanning.static_scanner import StaticScanner

            def result_to_dict(result):
                """Convert ScanResult dataclass to dict for scoring."""
                if result is None:
                    return None
                if isinstance(result, dict):
                    return result
                if is_dataclass(result):
                    d = asdict(result)
                    # Handle nested dataclasses
                    if hasattr(result, "pe_analysis") and result.pe_analysis:
                        d["pe_info"] = asdict(result.pe_analysis)
                    if hasattr(result, "iocs") and result.iocs:
                        ioc_dict = asdict(result.iocs)
                        d["iocs"] = {
                            "ips": ioc_dict.get("ips", []),
                            "urls": ioc_dict.get("urls", []),
                            "domains": ioc_dict.get("domains", []),
                            "registry_paths": ioc_dict.get("registry_keys", []),
                            "file_paths": ioc_dict.get("file_paths", []),
                            "emails": ioc_dict.get("emails", []),
                        }
                    return d
                return result

            worker.signals.heartbeat.emit(worker_id)

            static_result = None
            sandbox_result = None
            scoring_result = None

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
            sandbox_session = None
            if run_sandbox:
                self._integrated_sandbox_stage = "Sandbox Execution"
                self.integratedSandboxProgress.emit("Running in sandbox...")

                try:
                    from ..scanning.sandbox_session import SandboxSession

                    # Create sandbox session for live event tracking
                    def event_batch_callback(events):
                        """Emit event batch to QML."""
                        try:
                            event_dicts = [e.to_dict() for e in events]
                            self.sandboxEventBatch.emit(json.dumps(event_dicts))
                        except Exception as ex:
                            logger.warning(f"Event batch callback error: {ex}")

                    def stats_callback(stats):
                        """Emit stats update to QML."""
                        try:
                            self.sandboxStatsUpdate.emit(json.dumps(stats.to_dict()))
                        except Exception as ex:
                            logger.warning(f"Stats callback error: {ex}")

                    sandbox_session = SandboxSession(
                        event_callback=event_batch_callback,
                        stats_callback=stats_callback,
                        batch_interval_ms=300,  # 300ms batched updates
                    )
                    self._sandbox_session = sandbox_session
                    self._sandbox_cancelled = False

                    # Start the session
                    sandbox_session.start(
                        str(file_path), static_result.get("sha256", "")
                    )

                    sandbox = get_integrated_sandbox()
                    avail = sandbox.availability()

                    if avail.get("available"):
                        # Event callback bridge from sandbox to session
                        from ..scanning.sandbox_session import SandboxEvent

                        # Track if preview started
                        preview_started = [False]  # Use list for closure mutation

                        def sandbox_event_callback(event_type: str, data: dict):
                            if sandbox_session:
                                # Create SandboxEvent from raw data
                                event = SandboxEvent(
                                    event_type=event_type,
                                    timestamp=data.get(
                                        "timestamp", datetime.now().isoformat()
                                    ),
                                    pid=data.get("pid"),
                                    process_name=data.get("name")
                                    or data.get("process_name"),
                                    file_path=data.get("path") or data.get("file_path"),
                                    exit_code=data.get("exit_code"),
                                    description=data.get("description"),
                                )
                                sandbox_session.add_event(event)
                                worker.signals.heartbeat.emit(worker_id)

                                # Start live preview on first process_start event
                                if (
                                    event_type == "process_start"
                                    and not preview_started[0]
                                ):
                                    process_pid = data.get("pid")
                                    if process_pid:
                                        try:
                                            # Get exe name from the file being scanned
                                            exe_name = (
                                                Path(str(file_path)).name
                                                if file_path
                                                else None
                                            )
                                            logger.info(
                                                f"Starting live preview for PID {process_pid}, exe={exe_name}"
                                            )
                                            self._start_live_preview(
                                                process_pid,
                                                sandbox_session.workspace,
                                                exe_name=exe_name,
                                            )
                                            preview_started[0] = True
                                        except Exception as prev_err:
                                            logger.warning(
                                                f"Could not start live preview: {prev_err}"
                                            )

                        # Cancel check callback
                        def cancel_check():
                            return self._sandbox_cancelled

                        result = sandbox.run_file(
                            str(file_path),
                            timeout=timeout_seconds,
                            block_network=block_network,
                            event_callback=sandbox_event_callback,
                            cancel_check=cancel_check,
                        )

                        sandbox_result = result.to_dict()

                        # Stop live preview
                        self._stop_live_preview()
                        self._stop_autopilot()

                        # Stop session and get summary
                        session_summary = sandbox_session.stop(
                            cancelled=self._sandbox_cancelled
                        )
                        sandbox_result["session_summary"] = session_summary

                        # Emit session ended signal
                        self.sandboxSessionEnded.emit(json.dumps(session_summary))

                        worker.signals.heartbeat.emit(worker_id)
                    else:
                        sandbox_session.stop()
                        sandbox_result = {
                            "success": False,
                            "error_message": avail.get(
                                "reason", "Sandbox not available"
                            ),
                            "platform": sys.platform,
                        }
                except Exception as e:
                    logger.warning(f"Sandbox execution error: {e}")
                    if sandbox_session:
                        sandbox_session.stop()
                    self._sandbox_session = None
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

            # Step 4: AI Analysis (optional - uses Groq if available)
            ai_analysis = None
            self._integrated_sandbox_stage = "AI Analysis"
            self.integratedSandboxProgress.emit("AI analyzing results...")

            try:
                from ..ai.providers.groq import is_groq_available

                if is_groq_available():
                    # AI analysis is now handled by the report generator
                    # which uses Groq prompts internally
                    logger.info("Groq available for enhanced report generation")
                worker.signals.heartbeat.emit(worker_id)
            except Exception as e:
                logger.warning(f"AI analysis error: {e}")
                ai_analysis = None

            # Step 5: Report generation (friendly, user-readable)
            self._integrated_sandbox_stage = "Report Generation"
            self.integratedSandboxProgress.emit("Generating report...")

            report_content = ""
            try:
                report_gen = get_friendly_report_generator()
                report_content = report_gen.generate_file_report(
                    file_path, static_result, sandbox_result, scoring_result
                )
                worker.signals.heartbeat.emit(worker_id)
            except Exception as e:
                logger.warning(f"Report generation error: {e}")
                report_content = f"Error generating report: {e}"

            # Build final result dict for QML
            result = {
                "file_name": file_path.name,
                "file_path": str(file_path),
                "file_size": static_result.get("file_size", 0) if static_result else 0,
                "sha256": static_result.get("sha256", "") if static_result else "",
                "mime_type": static_result.get("mime_type", "")
                if static_result
                else "",
                # Scoring
                "score": scoring_result.score if scoring_result else 0,
                "verdict": scoring_result.verdict_label
                if scoring_result
                else "Unknown",
                "verdict_code": scoring_result.verdict if scoring_result else "unknown",
                "summary": scoring_result.summary
                if scoring_result
                else "Analysis complete",
                "explanation": scoring_result.explanation if scoring_result else "",
                # Static analysis summary
                "has_static": static_result is not None,
                "yara_matches_count": len(static_result.get("yara_matches", []))
                if static_result
                else 0,
                "iocs_found": bool(static_result.get("iocs"))
                if static_result
                else False,
                "pe_analyzed": bool(static_result.get("pe_info"))
                if static_result
                else False,
                # Sandbox summary
                "has_sandbox": sandbox_result is not None
                and sandbox_result.get("success"),
                "sandbox_available": sandbox_result is not None,
                "sandbox_platform": sandbox_result.get("platform", "")
                if sandbox_result
                else "",
                "sandbox_duration": sandbox_result.get("duration_seconds", 0)
                if sandbox_result
                else 0,
                "sandbox_exit_code": sandbox_result.get("exit_code")
                if sandbox_result
                else None,
                "sandbox_timed_out": sandbox_result.get("timed_out", False)
                if sandbox_result
                else False,
                "sandbox_error": sandbox_result.get("error_message", "")
                if sandbox_result
                else "",
                # AI Analysis (if available)
                "has_ai_analysis": ai_analysis is not None,
                "ai_verdict": ai_analysis.get("verdict", "") if ai_analysis else "",
                "ai_confidence": ai_analysis.get("confidence", "")
                if ai_analysis
                else "",
                "ai_malware_family": ai_analysis.get("malware_family", "")
                if ai_analysis
                else "",
                "ai_summary": ai_analysis.get("summary", "") if ai_analysis else "",
                "ai_behaviors": ai_analysis.get("behaviors", []) if ai_analysis else [],
                "ai_recommendation": ai_analysis.get("recommendation", "")
                if ai_analysis
                else "",
                "ai_technical_details": ai_analysis.get("technical_details", "")
                if ai_analysis
                else "",
                # Report content (for preview dialog)
                "report_content": report_content,
                "report_path": "",  # Empty - user chooses to save
                # Breakdown for UI
                "score_breakdown": scoring_result.breakdown if scoring_result else {},
            }

            return result

        def on_success(wid, result):
            """Integrated scan completed."""
            if worker_id not in self._active_workers:
                return
            try:
                result = self._normalize_file_scan_result_for_qml(result)
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
                    meta={
                        "integrated_sandbox": True,
                        "has_sandbox": result.get("has_sandbox"),
                    },
                )
                scan_id = self.scan_repo.add(scan_rec)
                result["scan_id"] = scan_id

                # ── Build v2 SentinelReport for VT-style UI sections ──────────
                try:
                    import datetime as _dt

                    from ..scanning.report_schema import (
                        build_empty_report,
                        save_report,
                        score_to_label,
                        score_to_risk,
                    )

                    _job_id = f"static_{int(scan_start_time.timestamp())}"
                    _sr = build_empty_report(job_id=_job_id, mode="static")
                    _fi = _sr["file"]
                    _fi["name"] = file_path.name
                    _fi["path"] = str(file_path)
                    _fi["size_bytes"] = (
                        int(file_path.stat().st_size) if file_path.exists() else 0
                    )
                    _fi["extension"] = file_path.suffix.lower().lstrip(".")
                    _fi["sha256"] = result.get("sha256", "")
                    _fi["sha1"] = result.get("sha1", "")
                    _fi["md5"] = result.get("md5", "")
                    _fi["file_type"] = result.get(
                        "mime_type", result.get("file_type", "")
                    )
                    _sr["static"]["engines"] = result.get("engines", [])
                    _sr["static"]["yara_matches"] = result.get("yara_matches", [])
                    _sr["static"]["pe_analyzed"] = bool(result.get("pe_analyzed"))
                    _sr["static"]["suspicious_imports"] = list(
                        (result.get("pe_info") or {}).get("suspicious_imports", [])
                    )
                    _ioc = result.get("iocs") or {}
                    _sr["iocs"]["ips"] = list(_ioc.get("ips", []))[:30]
                    _sr["iocs"]["domains"] = list(_ioc.get("domains", []))[:30]
                    _sr["iocs"]["urls"] = list(_ioc.get("urls", []))[:20]
                    _sr["iocs"]["registry_keys"] = list(
                        _ioc.get("registry_paths", _ioc.get("registry_keys", []))
                    )[:30]
                    _sr["iocs"]["file_paths"] = list(_ioc.get("file_paths", []))[:30]
                    _score = int(result.get("score") or 0)
                    _sr["verdict"]["score"] = _score
                    _sr["verdict"]["confidence"] = min(95, _score + 10)
                    _sr["verdict"]["risk"] = score_to_risk(_score)
                    _sr["verdict"]["label"] = score_to_label(_score)
                    _sr["verdict"]["reasons"] = list(
                        result.get("highlights", result.get("risk_reasons", []))
                    )[:5]
                    _sr["job"]["started_at"] = scan_start_time.isoformat()
                    _sr["job"]["finished_at"] = _dt.datetime.now().isoformat()
                    _saved = save_report(_sr, _job_id)
                    result["sentinel_report"] = _sr
                    result["sentinel_report_path"] = str(_saved)
                except Exception as _se:
                    logger.warning(
                        "Could not build v2 sentinel_report for integrated scan: %s",
                        _se,
                    )

                # ── Schema guardrail ────────────────────────────────────────
                # Guarantee sentinel_report is a normalized v2 dict and
                # sentinel_report_path is always a string before QML sees it.
                try:
                    from ..scanning.report_schema import normalize_report_v2 as _nrv2

                    _raw_sr = result.get("sentinel_report")
                    result["sentinel_report"] = _nrv2(
                        _raw_sr if isinstance(_raw_sr, dict) else {}
                    )
                    result.setdefault("sentinel_report_path", "")
                except Exception as _ge:
                    logger.debug(
                        "sentinel_report normalize (integrated) skipped: %s", _ge
                    )
                    result.setdefault("sentinel_report", {})
                    result.setdefault("sentinel_report_path", "")

                self.integratedSandboxFinished.emit(result)

                # Persist to history
                try:
                    _sr2 = result.get("sentinel_report", {})
                    _fi2 = _sr2.get("file") or {}
                    self._insert_scan_history(
                        job_id=str(_job_id) if "_job_id" in dir() else "",
                        file_name=str(
                            _fi2.get("name") or result.get("file_name") or ""
                        ),
                        sha256=str(_fi2.get("sha256") or ""),
                        verdict_risk=str(
                            (_sr2.get("verdict") or {}).get("risk") or "Low"
                        ),
                        confidence=int(
                            (_sr2.get("verdict") or {}).get("confidence") or 0
                        ),
                        report_path=str(result.get("sentinel_report_path") or ""),
                    )
                except Exception as _ihe:
                    logger.debug("_insert_scan_history (integrated) skipped: %s", _ihe)

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
            self.integratedSandboxFinished.emit(
                self._normalize_file_scan_result_for_qml(
                    {"error": error_msg, "summary": f"Scan failed: {error_msg}"}
                )
            )
            # Persist failure to scan_history so it appears in the UI
            try:
                import datetime as _dt2
                import os as _os

                _fail_job = f"fail_{int(_dt2.datetime.now().timestamp())}"
                _fname = _os.path.basename(path) if path else ""
                self._insert_scan_history(
                    job_id=_fail_job,
                    file_name=_fname,
                    sha256="",
                    verdict_risk="Failed",
                    confidence=0,
                    report_path="",
                )
            except Exception as _fe:
                logger.debug("_insert_scan_history (failure) skipped: %s", _fe)
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]
            self._watchdog.unregister_worker(worker_id)

        # Create and start worker with generous timeout (sandbox can take a while)
        worker = CancellableWorker(worker_id, scan_task, timeout_ms=300000)  # 5 min
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)
        worker.signals.heartbeat.connect(self._watchdog.heartbeat)

        self._active_workers[worker_id] = worker
        # Register with a conservative threshold to avoid false-positive stalls.
        stall_threshold = max(timeout_seconds + 120, 180) if run_sandbox else 120
        self._watchdog.register_worker(worker_id, stale_threshold_sec=stall_threshold)
        self._thread_pool.start(worker)

        logger.info(f"Integrated scan started for {path}")

    @Slot()
    def cancelSandbox(self):
        """Cancel the currently running sandbox execution."""
        if self._sandbox_session is not None:
            logger.info("Sandbox cancellation requested by user")
            self._sandbox_cancelled = True
            self._stop_live_preview()
            self.toast.emit("info", "Cancelling sandbox execution...")
        else:
            logger.warning("No active sandbox session to cancel")

    @Slot(bool)
    def setAutopilotEnabled(self, enabled: bool):
        """Enable or disable installer autopilot during sandbox execution."""
        self._autopilot_enabled = enabled
        if enabled:
            self._start_autopilot()
            logger.info("Installer autopilot enabled")
            self.toast.emit(
                "info", "🤖 Autopilot enabled - will safely click installer buttons"
            )
        else:
            self._stop_autopilot()
            logger.info("Installer autopilot disabled")
            self.toast.emit("info", "Autopilot disabled")

    @Slot(result=bool)
    def isAutopilotEnabled(self) -> bool:
        """Check if autopilot is enabled."""
        return self._autopilot_enabled

    def _start_live_preview(
        self, pid: int, session_path: Path, exe_name: str | None = None
    ):
        """Start live preview capture for a sandboxed process."""
        try:
            from ..scanning.window_capture import WindowCaptureService

            if self._window_capture is not None:
                self._window_capture.stop()

            # Frame callback to update QML image provider
            def on_frame_received(frame_data: bytes, width: int, height: int):
                if self._preview_provider:
                    self._preview_provider.update_frame(frame_data, width, height)
                # Emit frame number for QML to refresh image
                frame_num = (
                    self._window_capture._frame_count if self._window_capture else 0
                )
                self.sandboxPreviewFrameReady.emit(frame_num)

            # Window found callback to update QML status
            def on_window_status(found: bool, title: str):
                self.sandboxWindowFound.emit(found)
                if self._preview_controller:
                    if found:
                        self._preview_controller.set_window_found(title)
                    else:
                        self._preview_controller.set_status(
                            "No visible app window (console/background process)"
                        )

            # Status callback for detailed status updates
            def on_status_update(status: str):
                if self._preview_controller:
                    self._preview_controller.set_status(status)

            # Create window capture service with proper callbacks
            self._window_capture = WindowCaptureService(
                target_pid=pid,
                session_folder=session_path,
                fps=8,  # 8 FPS is good balance for smooth preview without high CPU
                max_frames=500,
                frame_callback=on_frame_received,
                window_found_callback=on_window_status,
                status_callback=on_status_update,
                exe_name=exe_name,  # Pass exe name for fallback window search
            )

            # Start capturing
            if self._window_capture.start():
                self.sandboxPreviewStarted.emit()
                logger.info(f"Live preview started for PID {pid}")
            else:
                logger.warning(f"Failed to start live preview for PID {pid}")

        except ImportError as e:
            logger.warning(f"WindowCaptureService not available: {e}")
        except Exception as e:
            logger.warning(f"Failed to start live preview: {e}")

    def _stop_live_preview(self):
        """Stop live preview capture."""
        if self._window_capture is not None:
            self._window_capture.stop()
            self._window_capture = None
            self.sandboxPreviewStopped.emit()
            logger.info("Live preview stopped")

    def _start_autopilot(self):
        """Start installer autopilot if sandbox is running."""
        if self._sandbox_session is None:
            return

        try:
            from ..scanning.installer_autopilot import InstallerAutopilot

            if self._installer_autopilot is not None:
                self._installer_autopilot.stop()

            # Get PID from window capture if available
            pid = self._window_capture.pid if self._window_capture else None
            if pid is None:
                logger.warning("No PID available for autopilot")
                return

            self._installer_autopilot = InstallerAutopilot(pid=pid)

            # Action callback to notify QML
            def on_action(action):
                import json

                self.sandboxAutopilotAction.emit(
                    json.dumps(
                        {
                            "button_text": action.button_text,
                            "window_title": action.window_title,
                            "timestamp": action.timestamp.isoformat(),
                        }
                    )
                )

            self._installer_autopilot.on_action = on_action
            self._installer_autopilot.start()
            logger.info(f"Installer autopilot started for PID {pid}")

        except ImportError:
            logger.warning("InstallerAutopilot not available")
        except Exception as e:
            logger.warning(f"Failed to start autopilot: {e}")

    def _stop_autopilot(self):
        """Stop installer autopilot."""
        if self._installer_autopilot is not None:
            self._installer_autopilot.stop()
            self._installer_autopilot = None
            logger.info("Installer autopilot stopped")

    @Slot(str)
    def _emitIntegratedSandboxProgress(self, stage: str):
        """Thread-safe progress emission (called via QMetaObject.invokeMethod)."""
        self.integratedSandboxProgress.emit(stage)

    @Slot(str, str, result=bool)
    def saveReportToFile(self, content: str, file_path: str) -> bool:
        """
        Save report content to a file chosen by user.

        Args:
            content: Report text content
            file_path: Destination file path

        Returns:
            True if saved successfully
        """
        try:
            path = Path(file_path)
            # Ensure .txt extension
            if not path.suffix:
                path = path.with_suffix(".txt")

            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write content
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"Report saved to: {path}")
            self.toast.emit("success", f"Report saved: {path.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            self.toast.emit("error", f"Failed to save report: {e}")
            return False

    @Slot(str)
    def copyToClipboard(self, text: str):
        """Copy text to system clipboard."""
        try:
            from PySide6.QtGui import QGuiApplication

            clipboard = QGuiApplication.clipboard()
            clipboard.setText(text)
            self.toast.emit("success", "Copied to clipboard")
        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")
            self.toast.emit("error", "Failed to copy to clipboard")

    @Slot(str, str)
    def exportScanReport(self, report_path: str, dest_dir: str) -> None:
        """Export a v2 SentinelReport and its artifacts to *dest_dir*.

        Steps:
        1. Validate report_path exists and is a JSON file.
        2. Copy report.json → dest_dir/<fileName>_<sha256[:8]>_report.json
        3. Zip any sibling artifacts/ folder → dest_dir/<fileName>_<sha256[:8]>_artifacts.zip
        4. Copy SHA-256 to clipboard and return it in result.
        5. Emit toast + scanReportExported signal.
        """
        import shutil
        import zipfile
        from pathlib import Path as _P

        def _run() -> None:
            try:
                src = _P(report_path)
                if not src.is_file():
                    raise FileNotFoundError(f"Report not found: {src}")
                dst = _P(dest_dir)
                dst.mkdir(parents=True, exist_ok=True)

                # 1. Read report to get friendly name + SHA256
                import json as _json

                with open(src, encoding="utf-8") as fh:
                    _rep = _json.load(fh)
                fi = _rep.get("file") or {}
                fname_raw = fi.get("name") or src.stem
                # Sanitise for filesystem
                safe_name = "".join(
                    c if c.isalnum() or c in "-_()" else "_" for c in fname_raw
                )[:48].rstrip("_")
                sha256 = str(fi.get("sha256") or "")[:8] or "unknown"
                prefix = f"{safe_name}_{sha256}"

                # 2. Copy report.json with friendly name
                shutil.copy2(src, dst / f"{prefix}_report.json")

                # 3. Zip artifacts folder if it exists
                artifacts_dir = src.parent / "artifacts"
                if artifacts_dir.is_dir():
                    zip_path = dst / f"{prefix}_artifacts.zip"
                    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        for f in artifacts_dir.rglob("*"):
                            if f.is_file():
                                zf.write(f, f.relative_to(artifacts_dir.parent))

                # 4. Copy full SHA256 to clipboard
                full_sha256 = str(fi.get("sha256") or "")
                if full_sha256:
                    try:
                        from PySide6.QtGui import QGuiApplication

                        QGuiApplication.clipboard().setText(full_sha256)
                    except Exception:
                        pass

                # 5. Notify
                artifacts_zip_path = (
                    str(dst / f"{prefix}_artifacts.zip")
                    if artifacts_dir.is_dir()
                    else ""
                )
                result_dict = {
                    "ok": True,
                    "exported_report_path": str(dst / f"{prefix}_report.json"),
                    "exported_artifacts_path": artifacts_zip_path,
                    "sha256": full_sha256,
                    "dest_dir": str(dst),
                }
                short_dest = _P(dest_dir).name or str(dst)
                sha_hint = " • SHA-256 copied" if full_sha256 else ""
                from PySide6.QtCore import QTimer

                QTimer.singleShot(
                    0,
                    lambda rd=result_dict, sd=short_dest, sh=sha_hint: (
                        self.toast.emit("success", f"Exported to {sd}{sh}"),
                        self.scanReportExported.emit(rd),
                    ),
                )
            except Exception as exc:
                logger.exception("exportScanReport failed: %s", exc)
                from PySide6.QtCore import QTimer

                QTimer.singleShot(
                    0,
                    lambda e=str(exc): self.toast.emit("error", f"Export failed: {e}"),
                )

        import threading as _threading

        _threading.Thread(target=_run, daemon=True, name="export-report").start()

    @Slot(str)
    def loadSentinelReport(self, path: str) -> None:
        """Load, normalize and emit a v2 SentinelReport from *path*.

        Emits ``sentinelReportLoaded(dict)`` on the Qt main thread.
        Emits a toast on error.
        """
        import json as _json
        from pathlib import Path as _P

        def _run() -> None:
            try:
                from ..scanning.report_schema import normalize_report_v2 as _nrv2

                with open(_P(path), encoding="utf-8") as fh:
                    raw = _json.load(fh)
                normalized = _nrv2(raw if isinstance(raw, dict) else {})
                normalized["_loaded_from"] = str(path)
                from PySide6.QtCore import QTimer

                QTimer.singleShot(
                    0, lambda r=normalized: self.sentinelReportLoaded.emit(r)
                )
            except Exception as exc:
                logger.exception("loadSentinelReport failed: %s", exc)
                from PySide6.QtCore import QTimer

                QTimer.singleShot(
                    0,
                    lambda e=str(exc): self.toast.emit(
                        "error", f"Could not load report: {e}"
                    ),
                )

        import threading as _threading

        _threading.Thread(target=_run, daemon=True, name="load-sentinel-report").start()

    @Slot(str)
    def loadScanReport(self, path: str) -> None:
        """Public alias for loadSentinelReport — loads, normalizes and emits."""
        self.loadSentinelReport(path)

    # ── Dedicated Scan History table ──────────────────────────────────────────

    @property
    def _scan_history_db(self) -> "Path":
        from pathlib import Path as _P

        return _P.home() / ".sentinel" / "sentinel.db"

    def _init_scan_history_table(self) -> None:
        """Create the scan_history table if it does not exist (idempotent)."""
        import sqlite3

        try:
            con = sqlite3.connect(str(self._scan_history_db), timeout=5)
            con.execute("""
                CREATE TABLE IF NOT EXISTS scan_history (
                    job_id       TEXT PRIMARY KEY,
                    file_name    TEXT,
                    sha256       TEXT,
                    verdict_risk TEXT,
                    confidence   INTEGER,
                    created_at   TEXT,
                    report_path  TEXT
                )
            """)
            con.commit()
            con.close()
        except Exception as exc:
            logger.warning("scan_history table init failed: %s", exc)

    def _insert_scan_history(
        self,
        job_id: str,
        file_name: str,
        sha256: str,
        verdict_risk: str,
        confidence: int,
        report_path: str,
    ) -> None:
        """INSERT OR REPLACE a row into scan_history (called from worker threads)."""
        import datetime as _dt
        import sqlite3

        try:
            con = sqlite3.connect(str(self._scan_history_db), timeout=5)
            con.execute(
                """INSERT OR REPLACE INTO scan_history
                   (job_id, file_name, sha256, verdict_risk, confidence, created_at, report_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id or "",
                    file_name or "",
                    sha256 or "",
                    verdict_risk or "",
                    int(confidence or 0),
                    _dt.datetime.now().isoformat(timespec="seconds"),
                    report_path or "",
                ),
            )
            con.commit()
            con.close()
        except Exception as exc:
            logger.warning("_insert_scan_history failed: %s", exc)

    @Slot(int, str)
    def listScanHistory(self, limit: int = 100, request_id: str = "") -> None:
        """Load scan_history rows newest-first and emit scanHistoryLoaded(request_id, list).

        Debounced: if a query is already in-flight the new call is silently dropped
        (the existing thread will emit with its own request_id, which QML ignores
        because it won't match the latest _histReqId).
        """
        if self._list_scan_history_pending:
            logger.debug("listScanHistory debounced (request_id=%s)", request_id)
            return
        self._list_scan_history_pending = True

        def _run() -> None:
            import sqlite3

            rows = []
            try:
                con = sqlite3.connect(str(self._scan_history_db), timeout=5)
                con.row_factory = sqlite3.Row
                q = "SELECT * FROM scan_history ORDER BY created_at DESC"
                if limit and limit > 0:
                    q += f" LIMIT {int(limit)}"
                for r in con.execute(q):
                    rows.append(dict(r))
                con.close()
            except Exception as exc:
                logger.warning("listScanHistory query failed: %s", exc)
            finally:
                self._list_scan_history_pending = False
            from PySide6.QtCore import QTimer

            rid = request_id
            QTimer.singleShot(
                0, lambda r=rows, rid=rid: self.scanHistoryLoaded.emit(rid, r)
            )

        import threading as _threading

        _threading.Thread(target=_run, daemon=True, name="list-scan-history").start()

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
    def scanUrlStatic(
        self,
        url: str,
        block_private_ips: bool = True,
        generate_report: bool = True,
        timeout_seconds: int = 30,
    ):
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
        self._run_url_scan(
            url,
            use_sandbox=False,
            block_private_ips=block_private_ips,
            generate_report=generate_report,
            timeout_seconds=timeout_seconds,
        )

    @Slot(str, bool, bool, bool, int)
    def scanUrlSandbox(
        self,
        url: str,
        block_downloads: bool = True,
        block_private_ips: bool = True,
        generate_report: bool = True,
        timeout_seconds: int = 30,
    ):
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
        self._run_url_scan(
            url,
            use_sandbox=True,
            block_downloads=block_downloads,
            block_private_ips=block_private_ips,
            generate_report=generate_report,
            timeout_seconds=timeout_seconds,
        )

    def _run_url_scan(
        self,
        url: str,
        use_sandbox: bool = False,
        block_downloads: bool = True,
        block_private_ips: bool = True,
        generate_report: bool = True,
        timeout_seconds: int = 30,
    ):
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
            from app.ai.url_explainer import explain_url_scan, explanation_to_dict
            from app.scanning.friendly_report import get_friendly_report_generator
            from app.scanning.url_scanner import UrlScanner
            from app.scanning.url_scoring import score_url_scan

            worker.signals.heartbeat.emit(worker_id)

            scan_result = None
            scoring_result = None
            explanation = None
            report_content = ""

            # Step 1: Run URL scan
            # Note: Progress updates happen via signals from main thread after task completes

            try:
                scanner = UrlScanner()

                if use_sandbox and self.urlSandboxAvailable():
                    scan_result = scanner.scan_sandbox(
                        url,
                        block_private_ips=block_private_ips,
                        block_downloads=block_downloads,
                    )
                else:
                    scan_result = scanner.scan_static(
                        url, block_private_ips=block_private_ips
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
                _score_input = scan_result.to_dict() if hasattr(scan_result, "to_dict") else (scan_result if isinstance(scan_result, dict) else vars(scan_result))
                scoring_result = score_url_scan(_score_input)
                # Update scan_result with score and verdict
                if hasattr(scan_result, 'score'):
                    scan_result.score = scoring_result.score
                    scan_result.verdict = scoring_result.verdict
                else:
                    scan_result["score"] = scoring_result.score
                    scan_result["verdict"] = scoring_result.verdict
                worker.signals.heartbeat.emit(worker_id)
            except Exception as e:
                logger.warning(f"URL scoring error: {e}")

            # Step 3: Generate explanation
            try:
                explanation = explain_url_scan(scan_result)
                worker.signals.heartbeat.emit(worker_id)
            except Exception as e:
                logger.warning(f"URL explanation error: {e}")

            # Step 4: AI Analysis (optional - Groq-powered)
            ai_analysis = None
            try:
                from ..ai.providers.groq import is_groq_available

                if is_groq_available():
                    # AI analysis is now handled by the report generator
                    logger.info("Groq available for enhanced URL report generation")
                worker.signals.heartbeat.emit(worker_id)
            except Exception as e:
                logger.warning(f"AI analysis error: {e}")
                ai_analysis = None

            # Step 5: Generate friendly report content
            if generate_report:
                try:
                    report_gen = get_friendly_report_generator()
                    # Build a simple result dict for the friendly report
                    url_result = {
                        "url": url,
                        "score": scan_result.score if scan_result else 0,
                        "verdict": scan_result.verdict if scan_result else "unknown",
                        "reasons": [
                            {
                                "title": e.title,
                                "severity": e.severity,
                                "detail": e.detail,
                            }
                            for e in scan_result.evidence
                        ]
                        if scan_result and scan_result.evidence
                        else [],
                    }
                    report_content = report_gen.generate_url_report(url, url_result)
                    worker.signals.heartbeat.emit(worker_id)
                except Exception as e:
                    logger.warning(f"Report generation error: {e}")
                    report_content = f"Error generating report: {e}"

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
                "http_status": scan_result.http.get("status_code")
                if scan_result.http
                else None,
                "http_content_type": scan_result.http.get("content_type", "")
                if scan_result.http
                else "",
                "http_content_length": scan_result.http.get("content_length", 0)
                if scan_result.http
                else 0,
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
                # YARA — convert YaraMatch dataclass instances to plain dicts
                "yara_matches": [
                    (
                        {
                            "rule_name": getattr(m, "rule_name", str(m)),
                            "description": getattr(m, "description", ""),
                            "severity": getattr(m, "severity", "high"),
                            "category": getattr(m, "category", ""),
                            "matched_strings": list(
                                getattr(m, "matched_strings", []) or []
                            ),
                            "tags": list(getattr(m, "tags", []) or []),
                        }
                        if not isinstance(m, dict)
                        else m
                    )
                    for m in (scan_result.yara_matches or [])
                ],
                "yara_match_count": len(scan_result.yara_matches)
                if scan_result.yara_matches
                else 0,
                # Signals
                "signals": scan_result.signals,
                # Sandbox
                "has_sandbox": scan_result.sandbox_result is not None,
                "sandbox_result": (
                    scan_result.sandbox_result.to_dict()
                    if hasattr(scan_result.sandbox_result, "to_dict")
                    else scan_result.sandbox_result
                )
                if scan_result.sandbox_result
                else None,
                # Explanation
                "explanation": explanation_to_dict(explanation)
                if explanation
                else None,
                # Report content (for preview dialog)
                "report_content": report_content,
                "report_path": "",  # Empty - user chooses to save
                # AI Analysis (if available)
                "has_ai_analysis": ai_analysis is not None,
                "ai_verdict": ai_analysis.get("verdict", "") if ai_analysis else "",
                "ai_confidence": ai_analysis.get("confidence", "")
                if ai_analysis
                else "",
                "ai_threat_type": ai_analysis.get("threat_type", "")
                if ai_analysis
                else "",
                "ai_summary": ai_analysis.get("summary", "") if ai_analysis else "",
                "ai_risks": ai_analysis.get("risks", []) if ai_analysis else [],
                "ai_recommendation": ai_analysis.get("recommendation", "")
                if ai_analysis
                else "",
                # Scoring breakdown
                "scoring": {
                    "score": scoring_result.score if scoring_result else 0,
                    "verdict": scoring_result.verdict if scoring_result else "unknown",
                    "breakdown": scoring_result.breakdown if scoring_result else {},
                }
                if scoring_result
                else None,
            }

            return result

        def on_success(wid, result):
            """URL scan completed."""
            if worker_id not in self._active_workers:
                return
            try:
                result = self._normalize_url_scan_result_for_qml(result)
                self._url_scan_in_progress = False
                self._url_scan_stage = ""
                self._url_scan_progress = 100
                self._url_scan_result = result

                # Save to scan history
                scan_rec = ScanRecord(
                    id=None,
                    started_at=scan_start_time.isoformat(),
                    finished_at=datetime.now().isoformat(),
                    type=ScanType.URL,
                    target=url,
                    status="completed" if result.get("success") else "error",
                    findings=result,
                    meta={
                        "url_scan": True,
                        "has_sandbox": result.get("has_sandbox", False),
                    },
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
                    self.toast.emit(
                        "success", f"✓ URL appears safe - Score: {score}/100"
                    )

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
            self.urlScanFinished.emit(
                self._normalize_url_scan_result_for_qml(
                    {
                        "error": error_msg,
                        "success": False,
                        "summary": f"URL scan failed: {error_msg}",
                        "url": url,
                    }
                )
            )
            if worker_id in self._active_workers:
                del self._active_workers[worker_id]
            self._watchdog.unregister_worker(worker_id)

        # Create and start worker
        worker = CancellableWorker(worker_id, scan_task, timeout_ms=120000)  # 2 min
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)
        worker.signals.heartbeat.connect(self._watchdog.heartbeat)

        self._active_workers[worker_id] = worker
        url_stall_threshold = max(timeout_seconds + (60 if use_sandbox else 30), 90)
        self._watchdog.register_worker(
            worker_id, stale_threshold_sec=url_stall_threshold
        )
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
        import subprocess
        import sys

        from ..core.workers import WorkerWatchdog
        from ..infra.nmap_cli import (
            SCAN_PROFILES,
            NmapCli,
            get_local_subnet,
            get_reports_dir,
        )

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
                    f.write("Nmap Scan Report\n")
                    f.write("================\n")
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
                self.nmapScanOutput.emit(scan_id, "\n[SUCCESS] Scan completed\n")
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
        """Get the current AI mode (online or unavailable)."""
        if self._event_explainer is None:
            return "unavailable"
        try:
            from ..ai.providers.groq import is_groq_available

            return "online" if is_groq_available() else "offline-kb"
        except Exception:
            return "offline-kb"

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
        if hasattr(self, "_explanation_debouncer") and self._explanation_debouncer:
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

        # Track agent steps for the detailed explanation
        self._add_agent_step(
            "Explain Event Requested",
            "User clicked Explain Event button",
            "started detailed AI explanation pipeline",
            f"Event index {event_index}",
        )

        try:
            # Get event from cache
            events = self._loaded_events
            if not events:
                self.eventExplanationFailed.emit(
                    str(event_index), "No events loaded. Please refresh."
                )
                return

            if event_index < 0 or event_index >= len(events):
                self.eventExplanationFailed.emit(
                    str(event_index),
                    f"Event index {event_index} out of range (0-{len(events) - 1})",
                )
                return

            event = events[event_index]

            # Build event dict with all required fields
            event_dict = {
                "log_name": getattr(event, "log_name", "Windows"),
                "provider": getattr(event, "source", "Unknown"),
                "source": getattr(event, "source", "Unknown"),
                "event_id": getattr(
                    event, "event_id", 0
                ),  # Critical: must extract event_id
                "level": getattr(event, "level", "Information"),
                "message": getattr(event, "message", ""),
                "time_created": (
                    getattr(event, "timestamp", "").isoformat()
                    if hasattr(getattr(event, "timestamp", None), "isoformat")
                    else str(getattr(event, "timestamp", ""))
                ),
            }

            # V4 Path: Deterministic-first (instant, UI thread safe)
            if hasattr(self, "_event_explainer") and hasattr(
                self._event_explainer, "explain_event_instant"
            ):
                logger.debug(
                    f"V4 instant lookup for event {event_index}: provider={event_dict['provider']}, event_id={event_dict['event_id']}"
                )

                # Get instant deterministic explanation (no AI, no blocking)
                structured = self._event_explainer.explain_event_instant(event_dict)
                self._add_agent_step(
                    "KB Lookup Complete",
                    "Deterministic explanation from knowledge base",
                    "matched template",
                    f"Title: {getattr(structured, 'title', 'N/A')}",
                )

                # Convert StructuredExplanation to dict for QML
                result_dict = (
                    structured.to_dict()
                    if hasattr(structured, "to_dict")
                    else dict(structured)
                )

                # Add legacy compatibility fields
                result_dict["short_title"] = result_dict.get(
                    "title", "Event Information"
                )
                result_dict["explanation"] = result_dict.get("what_happened", "")
                result_dict["recommendation"] = "; ".join(
                    result_dict.get("recommended_actions", [])
                )
                result_dict["what_to_do"] = result_dict["recommendation"]
                result_dict["why_it_happens"] = "; ".join(
                    result_dict.get("why_it_happened", [])
                )
                result_dict["what_you_can_do"] = result_dict["recommendation"]
                result_dict["severity_label"] = result_dict.get("severity", "Minor")

                # Emit result immediately
                explanation_json = json.dumps(result_dict)
                self.eventExplanationReady.emit(str(event_index), explanation_json)
                logger.info(
                    f"V4 deterministic explanation ready for event {event_index}"
                )

                # If Groq is available, automatically request AI enhancement in background
                if hasattr(self._event_explainer, "explain_event_async"):
                    try:
                        from ..ai.providers.groq import is_groq_available

                        if is_groq_available():
                            # Store event_index for async callback
                            self._pending_v5_requests = getattr(
                                self, "_pending_v5_requests", {}
                            )
                            request_id = self._event_explainer.explain_event_async(
                                event_dict, detail_level="full"
                            )
                            self._pending_v5_requests[request_id] = event_index
                            logger.info(
                                f"Groq AI enhancement requested for event {event_index}"
                            )
                            self._add_agent_step(
                                "AI Enhancement Requested",
                                "Sending to Groq Cloud AI for deeper analysis",
                                "called AI explain endpoint",
                                "Waiting for AI response...",
                            )
                    except ImportError:
                        pass  # Groq not available

                return

            # Fallback: Use AI worker or thread pool
            logger.debug("V4 not available, falling back to AI worker/thread")

            if (
                not self._ai_process
                or self._ai_process.state() != QProcess.ProcessState.Running
            ):
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
                self.eventExplanationFailed.emit(
                    str(event_index), "AI service unavailable"
                )

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
                self.eventExplanationFailed.emit(
                    str(event_index), "Invalid event index"
                )
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
            if hasattr(self, "_event_explainer") and hasattr(
                self._event_explainer, "request_ai_enhancement"
            ):
                logger.info(f"Requesting AI enhancement for event {event_index}")

                def on_ai_ready(structured_explanation):
                    """Callback when AI enhancement completes."""
                    result_dict = (
                        structured_explanation.to_dict()
                        if hasattr(structured_explanation, "to_dict")
                        else dict(structured_explanation)
                    )

                    # Add legacy compatibility fields
                    result_dict["short_title"] = result_dict.get(
                        "title", "Event Information"
                    )
                    result_dict["explanation"] = result_dict.get("what_happened", "")
                    result_dict["recommendation"] = "; ".join(
                        result_dict.get("recommended_actions", [])
                    )
                    result_dict["what_to_do"] = result_dict["recommendation"]
                    result_dict["severity_label"] = result_dict.get("severity", "Minor")

                    explanation_json = json.dumps(result_dict)
                    self.eventExplanationReady.emit(str(event_index), explanation_json)
                    logger.info(
                        f"AI enhanced explanation ready for event {event_index}"
                    )

                def on_ai_failed(error_msg):
                    """Callback when AI enhancement fails."""
                    logger.warning(
                        f"AI enhancement failed for event {event_index}: {error_msg}"
                    )
                    self.eventExplanationFailed.emit(
                        str(event_index), f"AI enhancement failed: {error_msg}"
                    )

                # Request async AI enhancement
                self._event_explainer.request_ai_enhancement(
                    event_dict, on_ready=on_ai_ready, on_failed=on_ai_failed
                )
                return

            # Fallback: Use AI worker
            if (
                self._ai_process
                and self._ai_process.state() == QProcess.ProcessState.Running
            ):
                request = {"type": "explain_event", "data": event_dict}
                request_id = self._send_ai_request(request)
                if request_id:
                    self._pending_ai_requests[request_id] = event_index
                    logger.info(
                        f"AI enhancement requested via worker: event {event_index}"
                    )
                    return

            # Last resort: thread pool
            self._request_explanation_fallback(event_index)

        except Exception as e:
            logger.error(f"Failed to request AI enhancement: {e}")
            self.eventExplanationFailed.emit(str(event_index), str(e))

    def _request_explanation_fallback(self, event_index: int) -> None:
        """Fallback: use thread pool if AI worker is not available."""
        if self._event_summarizer is None and self._event_explainer is None:
            self.eventExplanationFailed.emit(
                str(event_index), "AI services not available"
            )
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
                raise ValueError(
                    f"Event index {event_index} out of range (0-{len(events) - 1})"
                )

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
                if hasattr(self.scan_repo, "get_event_summary"):
                    cached = self.scan_repo.get_event_summary(source, evt_id, signature)
            except Exception as e:
                logger.debug(f"Cache lookup error: {e}")

            if cached:
                # Return cached explanation in the new 5-section format
                return (
                    str(event_index),
                    {
                        "title": cached.get(
                            "title", cached.get("short_title", "Event information")
                        ),
                        "severity": cached.get(
                            "severity", cached.get("severity_label", "Safe")
                        ),
                        "severity_label": cached.get(
                            "severity", cached.get("severity_label", "Safe")
                        ),
                        "what_happened": cached.get("what_happened", ""),
                        "why_it_happens": cached.get("why_it_happens", ""),
                        "what_to_do": cached.get(
                            "what_to_do", cached.get("what_you_can_do", "")
                        ),
                        "tech_notes": cached.get("tech_notes", ""),
                        "event_id": evt_id,
                        "source": source,
                        # Legacy fields for compatibility
                        "short_title": cached.get(
                            "title", cached.get("short_title", "Event information")
                        ),
                        "explanation": cached.get("what_happened", ""),
                        "recommendation": cached.get(
                            "what_to_do", cached.get("what_you_can_do", "")
                        ),
                        "what_you_can_do": cached.get(
                            "what_to_do", cached.get("what_you_can_do", "")
                        ),
                    },
                )

            # Generate using EventExplainer (preferred - detailed 5-section format)
            if self._event_explainer:
                explanation = self._event_explainer.explain_event(event_dict)

                # Build result dict in 5-section format
                result_dict = {
                    "title": explanation.get("short_title", "Event information"),
                    "severity": explanation.get("severity", "Safe"),
                    "severity_label": explanation.get("severity", "Safe"),
                    "what_happened": explanation.get(
                        "what_happened", explanation.get("explanation", "")
                    ),
                    "why_it_happens": explanation.get("why_it_happens", ""),
                    "what_to_do": explanation.get(
                        "what_to_do", explanation.get("recommendation", "")
                    ),
                    "tech_notes": explanation.get(
                        "tech_notes", f"Event ID: {evt_id} | Source: {source}"
                    ),
                    "event_id": evt_id,
                    "source": source,
                    # Legacy fields for compatibility
                    "short_title": explanation.get("short_title", "Event information"),
                    "explanation": explanation.get(
                        "what_happened", explanation.get("explanation", "")
                    ),
                    "recommendation": explanation.get(
                        "what_to_do", explanation.get("recommendation", "")
                    ),
                    "what_you_can_do": explanation.get(
                        "what_to_do", explanation.get("recommendation", "")
                    ),
                }

                # Save to cache for future use
                try:
                    if hasattr(self.scan_repo, "save_event_summary"):
                        self.scan_repo.save_event_summary(
                            source, evt_id, signature, result_dict
                        )
                except Exception as e:
                    logger.debug(f"Cache save error: {e}")

                return (str(event_index), result_dict)

            # Fallback to EventSummarizer if EventExplainer unavailable
            if self._event_summarizer:
                summary = self._event_summarizer.summarize(event_dict)

                # Save to cache
                try:
                    if hasattr(self.scan_repo, "save_event_summary"):
                        self.scan_repo.save_event_summary(
                            source, evt_id, signature, summary.to_dict()
                        )
                except Exception as e:
                    logger.debug(f"Cache save error: {e}")

                return (
                    str(event_index),
                    {
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
                    },
                )

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

    @Slot(int)
    def requestSimplifiedExplanation(self, event_index: int) -> None:
        """
        Request a simplified (non-technical) explanation for an event.

        This is triggered when user clicks "Explain simpler" button.
        Uses simplified prompts with no jargon for non-technical users.

        Args:
            event_index: Index of the event in the loaded events list
        """
        if not isinstance(event_index, int):
            return

        try:
            events = self._loaded_events
            if not events or event_index < 0 or event_index >= len(events):
                self.eventExplanationFailed.emit(
                    str(event_index), "Invalid event index"
                )
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

            # Use event explainer with simplified detail level
            if hasattr(self, "_event_explainer") and hasattr(
                self._event_explainer, "_get_ai_explanation"
            ):
                logger.info(
                    f"Requesting simplified explanation for event {event_index}"
                )

                worker_id = f"ai-simplified-{event_index}"

                # Prevent duplicate requests
                if worker_id in self._active_workers:
                    return

                def simplified_task(worker):
                    """Background simplified explanation task."""
                    worker.signals.heartbeat.emit(worker_id)

                    # Get explanation with simplified detail level
                    result = self._event_explainer._get_ai_explanation(
                        event_dict, detail_level="simplified"
                    )

                    if result:
                        result_dict = (
                            result.to_dict()
                            if hasattr(result, "to_dict")
                            else dict(result)
                        )
                        # Mark as simplified
                        result_dict["detail_level"] = "simplified"
                        result_dict["source"] = "ai"
                        return (str(event_index), result_dict)
                    raise ValueError("Failed to get simplified explanation")

                def on_success(wid: str, result: tuple) -> None:
                    """Simplified explanation completed."""
                    event_id, explanation = result
                    try:
                        explanation_json = json.dumps(explanation)
                        self.eventExplanationReady.emit(event_id, explanation_json)
                    except Exception as e:
                        logger.error(f"Failed to serialize explanation: {e}")
                        self.eventExplanationFailed.emit(
                            event_id, "Failed to process response"
                        )
                    finally:
                        self._watchdog.unregister_worker(worker_id)
                        if worker_id in self._active_workers:
                            del self._active_workers[worker_id]

                def on_error(wid: str, error_msg: str) -> None:
                    """Simplified explanation failed."""
                    logger.error(f"Simplified explanation failed: {error_msg}")
                    self.eventExplanationFailed.emit(str(event_index), error_msg)
                    self._watchdog.unregister_worker(worker_id)
                    if worker_id in self._active_workers:
                        del self._active_workers[worker_id]

                # Create and start worker with 10 second timeout
                worker = CancellableWorker(worker_id, simplified_task, timeout_ms=10000)
                worker.signals.finished.connect(on_success)
                worker.signals.error.connect(on_error)

                self._active_workers[worker_id] = worker
                self._watchdog.register_worker(worker_id)
                self._thread_pool.start(worker)
                return

            self.eventExplanationFailed.emit(
                str(event_index), "Simplified explanation not available"
            )

        except Exception as e:
            logger.error(f"Failed to request simplified explanation: {e}")
            self.eventExplanationFailed.emit(str(event_index), str(e))

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

        # Add user message to conversation and emit immediately for UI
        self._chat_conversation.append({"role": "user", "content": user_text})
        self.chatMessageAdded.emit("user", user_text)

        # Use v4 chatbot's ask() method which handles everything via signals
        # The chatbot creates its own worker and will emit chatResponseReady/Failed
        # Those signals are connected to _on_v4_chat_ready/_on_v4_chat_failed
        try:
            request_id = self._security_chatbot.ask(user_text)
            logger.debug(
                f"AI chat message sent: {user_text[:50]}... (request_id={request_id})"
            )
        except Exception as e:
            logger.error(f"Failed to send chat message: {e}")
            error_response = (
                "I encountered an error processing your request. Please try again."
            )
            self._chat_conversation.append(
                {"role": "assistant", "content": error_response}
            )
            self.chatMessageAdded.emit("assistant", error_response)

    @Slot()
    def clearChatHistory(self) -> None:
        """Clear the chat conversation history."""
        self._chat_conversation.clear()
        # Also clear smart assistant conversation
        if self._smart_assistant:
            self._smart_assistant.clear_conversation()
        logger.info("Chat history cleared")

    # ========================================================================
    # RESOLUTION REPORTS - Track what AI did during help sessions
    # ========================================================================

    @Slot()
    def getResolutionSessions(self) -> None:
        """
        Get all resolution sessions for the Resolution Report page.

        Emits resolutionSessionsLoaded signal with JSON array of sessions.
        """
        try:
            from ..ai.action_record import get_action_log

            action_log = get_action_log()
            sessions = action_log.get_all_sessions()

            # Convert to JSON-serializable list
            sessions_data = [s.to_dict() for s in sessions]

            # Sort by started_at descending (newest first)
            sessions_data.sort(key=lambda x: x.get("started_at", ""), reverse=True)

            sessions_json = json.dumps(sessions_data)
            self.resolutionSessionsLoaded.emit(sessions_json)
            logger.debug(f"Loaded {len(sessions_data)} resolution sessions")

        except Exception as e:
            logger.error(f"Failed to get resolution sessions: {e}")
            self.resolutionSessionsLoaded.emit("[]")

    @Slot(int, str, str)
    def startResolutionSession(
        self, event_id: int, event_source: str, event_summary: str
    ) -> None:
        """
        Start a new resolution session when user asks chatbot to help resolve.

        Args:
            event_id: Event ID being resolved
            event_source: Source of the event
            event_summary: Brief summary of the event
        """
        try:
            if self._security_chatbot and hasattr(
                self._security_chatbot, "start_resolution_session"
            ):
                session_id = self._security_chatbot.start_resolution_session(
                    event_id=event_id,
                    event_source=event_source,
                    event_summary=event_summary,
                )
                logger.info(f"Started resolution session: {session_id}")
            else:
                logger.warning("Security chatbot not available for resolution session")
        except Exception as e:
            logger.error(f"Failed to start resolution session: {e}")

    @Slot(str)
    def endResolutionSession(self, summary: str) -> None:
        """
        End the current resolution session.

        Args:
            summary: Summary of what was done
        """
        try:
            if self._security_chatbot and hasattr(
                self._security_chatbot, "end_resolution_session"
            ):
                session_data = self._security_chatbot.end_resolution_session(summary)
                if session_data:
                    logger.info(
                        f"Ended resolution session with {len(session_data.get('actions', []))} actions"
                    )
        except Exception as e:
            logger.error(f"Failed to end resolution session: {e}")

    @Slot(str)
    def setEventContextForChat(self, event_json: str) -> None:
        """
        Set event context for the chatbot to help resolve.

        Called from EventViewer when user clicks "Ask Chatbot to Help Resolve".

        Args:
            event_json: JSON string with event data and explanation
        """
        import json

        try:
            event_data = json.loads(event_json)

            # Store context for smart assistant
            if self._smart_assistant and hasattr(
                self._smart_assistant, "set_selected_event"
            ):
                self._smart_assistant.set_selected_event(event_data)

            # Build initial message to send to chatbot
            event_id = event_data.get("event_id", "Unknown")
            provider = event_data.get("provider", "Unknown")
            level = event_data.get("level", "Information")

            # Get explanation summary if available
            explanation = event_data.get("explanation", {})
            summary = explanation.get("summary") or explanation.get("what_happened", "")

            # Start a resolution session for audit logging
            try:
                event_id_int = int(event_id) if str(event_id).isdigit() else 0
                self.startResolutionSession(
                    event_id_int, str(provider), str(summary)[:200]
                )
            except Exception as e:
                logger.debug(f"Could not start resolution session: {e}")

            # Create a help request message
            help_message = "I need help resolving this Windows event:\n\n"
            help_message += f"**Event ID:** {event_id}\n"
            help_message += f"**Source:** {provider}\n"
            help_message += f"**Level:** {level}\n"
            if summary:
                help_message += f"**Summary:** {summary}\n"
            help_message += "\nPlease help me understand what caused this and what I should do to fix it."

            # Send the message to chatbot
            self.sendSmartMessage(help_message)

            # Navigate to AI Assistant page
            self.navigateTo.emit("ai-assistant")

            logger.info(
                f"Event context set for chatbot: Event {event_id} from {provider}"
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse event context JSON: {e}")
        except Exception as e:
            logger.exception(f"Error setting event context for chat: {e}")

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
            parts.append(
                f"\n*Source: {source} | Confidence: {conf_emoji} {confidence.title()}*"
            )

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

    # ──────────────────────────────────────────────────────────────────────────
    # VMware sandbox pipeline slots
    # ──────────────────────────────────────────────────────────────────────────

    @Slot(str)
    def startSandboxFileAnalysis(self, file_path: str) -> None:
        """
        Start a full VMware sandbox analysis for the given file.
        Runs the 14-step pipeline in analyzer_dynamic.run_file_analysis().
        Signals: sandboxProgress(int), sandboxFinished(dict), sandboxFailed(str),
                 sandboxScreenshot(str)
        """
        import threading as _threading

        from ..sandbox.analyzer_dynamic import run_file_analysis

        cancel_ev = _threading.Event()
        job_id_box: list[str] = []

        # ── Watchdog: hard ceiling on total job time ──────────────────────────
        _MAX_JOB_SECONDS = 420  # 7-minute absolute maximum
        _emitted = [False]  # mutable flag so closures can set it
        _watchdog_timer: list = [None]  # holds the Timer so we can cancel it

        def _watchdog() -> None:
            """Force-cancel after _MAX_JOB_SECONDS and ensure UI unblocks."""
            logger.error(
                "startSandboxFileAnalysis WATCHDOG fired after %ds — "
                "force-cancelling vmware-sandbox thread for: %s",
                _MAX_JOB_SECONDS,
                file_path,
            )
            cancel_ev.set()  # tells pipeline to abort via _aborted()
            import time as _time

            _time.sleep(5)  # give the thread a moment to emit its own signal
            if not _emitted[0]:
                _emitted[0] = True
                from PySide6.QtCore import QTimer as _QTimer

                _QTimer.singleShot(
                    0,
                    lambda: self.sandboxFailed.emit(
                        f"Sandbox job exceeded maximum time ({_MAX_JOB_SECONDS}s) "
                        f"and was force-cancelled. File: {file_path}"
                    ),
                )
                try:
                    import datetime as _dtw
                    import os as _osw

                    self._insert_scan_history(
                        job_id=f"wdog_{int(_dtw.datetime.now().timestamp())}",
                        file_name=_osw.path.basename(file_path) if file_path else "",
                        sha256="",
                        verdict_risk="Failed",
                        confidence=0,
                        report_path="",
                    )
                except Exception:
                    pass

        def _step_cb(status: str, msg: str) -> None:

            # Reuse agentStepAdded if the signal exists
            if hasattr(self, "agentStepAdded"):
                import json as _json

                self.agentStepAdded.emit(
                    _json.dumps({"status": status, "message": msg})
                )

        def _progress_cb(pct: int) -> None:
            self.sandboxProgress.emit(pct)

        def _screenshot_cb(path: str) -> None:
            self.sandboxScreenshot.emit(path)

        def _run() -> None:
            try:
                result = run_file_analysis(
                    file_path,
                    step_cb=_step_cb,
                    progress_cb=_progress_cb,
                    cancel_event=cancel_ev,
                    screenshot_cb=_screenshot_cb,
                    state_cb=lambda s: self.sandboxStateChanged.emit(s),
                )
                # Store job_id for cancel
                if result.get("job_id"):
                    job_id_box.append(result["job_id"])

                # ── Schema guardrail ────────────────────────────────────────
                # VMware runner returns result["report"] as the v2 dict;
                # ensure sentinel_report is always present and normalized.
                _emit_result = dict(result)
                try:
                    from ..scanning.report_schema import normalize_report_v2 as _nrv2

                    _candidate = _emit_result.get(
                        "sentinel_report"
                    ) or _emit_result.get("report")
                    _emit_result["sentinel_report"] = _nrv2(
                        _candidate if isinstance(_candidate, dict) else {}
                    )
                    _emit_result.setdefault("sentinel_report_path", "")
                except Exception as _ge:
                    logger.debug("sentinel_report normalize (sandbox) skipped: %s", _ge)
                    _emit_result.setdefault("sentinel_report", {})
                    _emit_result.setdefault("sentinel_report_path", "")

                _emitted[0] = True
                self.sandboxFinished.emit(_emit_result)
                try:
                    _sr3 = _emit_result.get("sentinel_report", {})
                    _fi3 = _sr3.get("file") or {}
                    self._insert_scan_history(
                        job_id=str(job_id_box[0])
                        if job_id_box and job_id_box[0]
                        else "",
                        file_name=str(
                            _fi3.get("name") or _emit_result.get("file_name") or ""
                        ),
                        sha256=str(_fi3.get("sha256") or ""),
                        verdict_risk=str(
                            (_sr3.get("verdict") or {}).get("risk") or "Low"
                        ),
                        confidence=int(
                            (_sr3.get("verdict") or {}).get("confidence") or 0
                        ),
                        report_path=str(_emit_result.get("sentinel_report_path") or ""),
                    )
                except Exception as _ihe2:
                    logger.debug("_insert_scan_history (sandbox) skipped: %s", _ihe2)
            except Exception as exc:
                logger.exception("startSandboxFileAnalysis failed")
                _emitted[0] = True
                self.sandboxFailed.emit(str(exc))
                # Persist failure row so history always reflects attempted scans
                try:
                    import datetime as _dt3
                    import os as _os2

                    _fail_job2 = f"vmfail_{int(_dt3.datetime.now().timestamp())}"
                    self._insert_scan_history(
                        job_id=_fail_job2,
                        file_name=_os2.path.basename(file_path) if file_path else "",
                        sha256="",
                        verdict_risk="Failed",
                        confidence=0,
                        report_path="",
                    )
                except Exception as _fe2:
                    logger.debug("_insert_scan_history (vm-failure) skipped: %s", _fe2)
            finally:
                wt = _watchdog_timer[0]
                if wt is not None:
                    wt.cancel()
                jid = job_id_box[0] if job_id_box else None
                if jid and jid in self._vmware_cancel_events:
                    del self._vmware_cancel_events[jid]
                self._vmware_job_id = None

        t = _threading.Thread(target=_run, daemon=True, name="vmware-sandbox")
        _watchdog_timer[0] = _threading.Timer(_MAX_JOB_SECONDS, _watchdog)
        _watchdog_timer[0].daemon = True
        _watchdog_timer[0].start()
        self._vmware_job_id = file_path  # placeholder until we have job_id
        # Pre-register cancel event (keyed by file path until real job_id available)
        self._vmware_cancel_events[file_path] = cancel_ev
        t.start()

    @Slot(str)
    def cancelSandboxJob(self, job_id: str) -> None:
        """Cancel an in-progress sandbox analysis job."""
        ev = self._vmware_cancel_events.get(job_id)
        if ev:
            ev.set()
            logger.info("Sandbox job cancel requested: %s", job_id)
        else:
            # Try to cancel by any active key
            for k, ev2 in list(self._vmware_cancel_events.items()):
                ev2.set()

    @Slot(str)
    def explainReport(self, report_path: str) -> None:
        """
        Load a report.json from *report_path* and generate an AI plain-language
        explanation in a background thread.
        Emits sandboxExplainFinished(dict) when done.
        """
        import json as _json
        import threading as _threading

        def _run() -> None:
            try:
                with open(report_path, encoding="utf-8") as fh:
                    report = _json.load(fh)
                # Use v2 AI explainer (app/ai/report_explainer.py)
                try:
                    from ..ai.report_explainer import explain_report as _explain_v2

                    explanation = _explain_v2(report)
                except ImportError:
                    from ..sandbox.report_explainer import (
                        explain_report as _explain_v1,  # type: ignore[import]
                    )

                    explanation = _explain_v1(report)
            except Exception as exc:
                logger.exception("explainReport failed: %s", exc)
                explanation = {
                    "one_line_summary": "Explanation unavailable.",
                    "risk_level": "Unknown",
                    "top_reasons": [],
                    "what_to_do": [],
                    "false_positive_note": "",
                    "raw": "",
                    "error": str(exc),
                }
            self.sandboxExplainFinished.emit(explanation)

        _threading.Thread(target=_run, daemon=True, name="explain-report").start()

    @Slot()
    def runVmwareDiagnostics(self) -> None:
        """
        Run VMware prerequisite diagnostics in a background thread.
        Emits vmwareDiagnosticsResult(list) when complete.
        """
        import threading as _threading

        from ..sandbox.vmware_runner import VMwareRunner, load_runner_config

        def _run() -> None:
            try:
                cfg, extras = load_runner_config()
                runner = VMwareRunner(config=cfg, extras=extras)
                results = runner.run_diagnostics()
            except Exception as exc:
                results = [
                    {
                        "check": "Diagnostics runner",
                        "passed": False,
                        "message": str(exc),
                        "fix": "Check configuration and try again.",
                    }
                ]
            self.vmwareDiagnosticsResult.emit(results)
            passed = sum(1 for r in results if r.get("passed"))
            total = len(results)
            level = "info" if passed == total else "warning"
            self.toast.emit(
                level, f"VMware Diagnostics: {passed}/{total} checks passed"
            )

        t = _threading.Thread(target=_run, daemon=True, name="vmware-diag")
        t.start()

    # ------------------------------------------------------------------ #
    #  ScanCenter — market-ready file scanner (v3 pipeline)               #
    # ------------------------------------------------------------------ #

    @Slot(str, str)
    def startScanCenter(self, file_path: str, options_json: str = "{}") -> None:
        """Start a v3 scan pipeline for *file_path*.

        *options_json* is a JSON object:
            {use_sandbox, allow_execution, disable_network, run_clamav,
             monitor_seconds, strings_limit}
        """
        import threading as _t

        from ..scancenter.controller import ScanController, ScanOptions

        if self._scancenter_controller is not None:
            self.toast.emit("warning", "A scan is already running. Cancel it first.")
            return

        try:
            raw = json.loads(options_json) if options_json.strip() else {}
        except Exception:
            raw = {}

        opts = ScanOptions(
            use_sandbox=bool(raw.get("use_sandbox", False)),
            allow_execution=bool(raw.get("allow_execution", False)),
            disable_network=bool(raw.get("disable_network", True)),
            run_clamav=bool(raw.get("run_clamav", True)),
            monitor_seconds=int(raw.get("monitor_seconds", 60)),
            strings_limit=int(raw.get("strings_limit", 200)),
            visible_gui=bool(raw.get("use_visible_gui", False)),
        )

        self._scancenter_controller = ScanController()

        def _on_progress(pct: int, label: str) -> None:
            self.scanCenterProgress.emit(pct, label)

        def _run() -> None:
            _stream = None
            # ── Reset Agent Timeline for this new scan ─────────────────────
            self.agentStepsCleared.emit()
            # Emit initial phase states (all pending)
            for _ph in ["static", "iocs", "sandbox", "verdict"]:
                self.scanCenterPhaseUpdate.emit(json.dumps({
                    "phase": _ph, "status": "pending", "summary": "", "score": -1, "pct": 0
                }))

            def _on_agent_step(step: dict) -> None:
                """Forward a pipeline step dict to the QML Agent Timeline
                and emit structured phase updates for the phase-card UI."""
                self.agentStepAdded.emit(json.dumps(step))
                # Map agent-step stages to phase-card updates
                _stage = (step.get("stage") or "").lower()
                _status_raw = (step.get("status") or "ok").lower()
                _title = step.get("title", "")
                _result = step.get("result", "")
                _phase_map = {
                    "static": "static", "hashing": "static", "validate": "static",
                    "iocs": "iocs",
                    "sandbox": "sandbox",
                    "verdict": "verdict",
                }
                _phase = _phase_map.get(_stage)
                if _phase:
                    _ph_status = "running" if _status_raw == "running" else (
                        "done" if _status_raw == "ok" else (
                        "warn" if _status_raw == "warn" else "error"))
                    self.scanCenterPhaseUpdate.emit(json.dumps({
                        "phase": _phase,
                        "status": _ph_status,
                        "summary": _title + (" — " + _result if _result else ""),
                        "score": -1,
                        "pct": 0,
                    }))

            try:
                # ── Start live preview stream when sandbox is requested ───────
                if opts.use_sandbox:
                    try:
                        from ..sandbox_vmware.preview_stream import SandboxPreviewStream
                        from ..sandbox.vmware_runner import load_runner_config
                        import os as _os
                        _cfg, _ = load_runner_config()
                        _preview_out = str(
                            Path(_os.path.abspath("data/artifacts/sandbox_preview.png"))
                        )
                        def _on_preview_update(path: str, ts_ms: int) -> None:
                            # PySide6 queues cross-thread signals automatically
                            url = "file:///" + path.replace("\\", "/") + "?ts=" + str(ts_ms)
                            self.scanCenterPreviewUpdated.emit(url)
                        _stream = SandboxPreviewStream(
                            vmrun_path=_cfg.vmrun_path,
                            vmx_path=_cfg.vmx_path,
                            out_path=_preview_out,
                            interval_sec=0.7,
                            on_update=_on_preview_update,
                            guest_user=_cfg.guest_user or "",
                            guest_pass=_cfg.guest_pass or "",
                        )
                        _stream.start()
                    except Exception as _prev_exc:
                        logger.debug("Could not start preview stream: %s", _prev_exc)

                report = self._scancenter_controller.run(
                    file_path=file_path,
                    options=opts,
                    progress_cb=_on_progress,
                    agent_step_cb=_on_agent_step,
                )
                self._scancenter_current_report = report.to_dict()
                self.scanCenterFinished.emit(self._scancenter_current_report)

                # ── Auto-trigger AI explanation after pipeline completes ──────
                try:
                    from ..scancenter.groq_explainer import explain_report as _ai_explain
                    _ai_result = _ai_explain(report)
                    if _ai_result is not None:
                        from dataclasses import asdict as _asdict
                        _ai_dict = _asdict(_ai_result) if hasattr(_ai_result, '__dataclass_fields__') else (
                            _ai_result.to_dict() if hasattr(_ai_result, 'to_dict') else {}
                        )
                        if _ai_dict:
                            self.scanCenterExplainFinished.emit(_ai_dict)
                            logger.info("Auto-AI explanation generated successfully")
                except Exception as _ai_exc:
                    logger.debug("Auto-AI explanation skipped: %s", _ai_exc)

                # ── Emit final verdict phase as done ──────────────────────────
                self.scanCenterPhaseUpdate.emit(json.dumps({
                    "phase": "verdict", "status": "done",
                    "summary": f"Score: {report.verdict.score}/100 — {report.verdict.risk}" if report.verdict else "Complete",
                    "score": report.verdict.score if report.verdict else 0,
                    "pct": 100,
                }))

                # ── Push actionable success notification ──────────────────────
                try:
                    from ..ui.notification_service import get_notification_service as _get_ns
                    _ns = _get_ns()
                    _v   = report.verdict
                    _score = _v.score  if _v else 0
                    _risk  = (_v.risk  or "Unknown") if _v else "Unknown"
                    _label = (_v.label or "Scan complete") if _v else "Scan complete"
                    _jid   = report.job.job_id if report.job else ""
                    _ntype = "success" if _score < 40 else ("warning" if _score < 70 else "error")
                    _ns.pushRich(
                        title="Scan complete",
                        summary=f"{_risk} \u2014 {_label}  \u2022  score {_score}/100",
                        notification_type=_ntype,
                        action_label="Open report",
                        action_payload_json=json.dumps({"route": "scan-tool", "tab": 0}),
                    )
                except Exception as _ne:
                    logger.debug("Notification push failed: %s", _ne)

            except Exception as exc:
                logger.exception("ScanCenter pipeline failed")
                self.scanCenterFailed.emit(str(exc))

                # ── Push actionable failure notification ──────────────────────
                try:
                    from ..ui.notification_service import get_notification_service as _get_ns
                    _ns = _get_ns()
                    _first_line = str(exc).split("\n")[0][:120]
                    _ns.pushRich(
                        title="Sandbox scan failed",
                        summary=_first_line,
                        notification_type="error",
                        action_label="Open details",
                        action_payload_json=json.dumps({"route": "scan-tool", "tab": 5}),
                    )
                except Exception as _ne2:
                    logger.debug("Notification push failed: %s", _ne2)

            finally:
                # ── Stop preview stream and clear the preview panel ───────────
                if _stream is not None:
                    _stream.stop()
                if opts.use_sandbox:
                    self.scanCenterPreviewUpdated.emit("")  # clears QML panel
                self._scancenter_controller = None

        _t.Thread(target=_run, daemon=True, name="scancenter-scan").start()

    @Slot()
    def cancelScanCenter(self) -> None:
        """Cancel the currently running scan gracefully."""
        ctrl = getattr(self, "_scancenter_controller", None)
        if ctrl is not None:
            ctrl.cancel()
        self.toast.emit("info", "Scan cancelled.")

    @Slot()
    def openVmWindowInScanCenter(self) -> None:
        """Bring the sandbox VMware VM window to the foreground.

        Tries to launch ``vmware.exe <vmx>`` so VMware Workstation opens the
        running VM in a GUI window.  Safe to call even if VMware is already
        showing the VM — it will just focus the existing window.
        """
        import subprocess as _sp
        try:
            from ..sandbox.vmware_runner import load_runner_config
            _cfg, _ = load_runner_config()
            _vmrun_dir = Path(_cfg.vmrun_path).parent
            _vmware_exe = _vmrun_dir / "vmware.exe"
            if not _vmware_exe.exists():
                # Fallback candidate locations
                for _cand in [
                    r"C:\Program Files (x86)\VMware\VMware Workstation\vmware.exe",
                    r"C:\Program Files\VMware\VMware Workstation\vmware.exe",
                ]:
                    if Path(_cand).exists():
                        _vmware_exe = Path(_cand)
                        break
            if _vmware_exe.exists():
                _sp.Popen(
                    [str(_vmware_exe), _cfg.vmx_path],
                    creationflags=0x00000008,  # DETACHED_PROCESS
                )
            else:
                self.toast.emit("warning", "vmware.exe not found — cannot open VM window.")
        except Exception as _exc:
            logger.warning("openVmWindowInScanCenter: %s", _exc)
            self.toast.emit("warning", f"Could not open VM window: {_exc}")

    @Slot(int)
    def loadScanCenterHistory(self, limit: int = 100) -> None:
        """Emit *scanCenterHistoryLoaded* with the most recent *limit* rows."""
        import threading as _t

        from ..scancenter.history_repo import HistoryRepo

        def _run() -> None:
            try:
                rows = HistoryRepo().list_recent(limit=limit)
                self.scanCenterHistoryLoaded.emit(rows)
            except Exception as exc:
                logger.exception("loadScanCenterHistory failed")
                self.toast.emit("error", f"Could not load scan history: {exc}")

        _t.Thread(target=_run, daemon=True, name="scancenter-history").start()

    @Slot(str, str)
    def exportScanCenterReport(self, job_id: str, dest_dir: str = "") -> None:
        """Export the report for *job_id* to *dest_dir* (defaults to ~/.sentinel/reports/)."""
        import threading as _t

        from ..scancenter.export import default_export_dir, export_report, load_report_json
        from ..scancenter.history_repo import HistoryRepo

        def _run() -> None:
            try:
                row = HistoryRepo().get(job_id)
                if not row or not row.get("report_path"):
                    self.scanCenterExported.emit({"ok": False, "error": "Report not found"})
                    return
                report = load_report_json(row["report_path"])
                if report is None:
                    self.scanCenterExported.emit({"ok": False, "error": "Cannot read report JSON"})
                    return
                out_dir = Path(dest_dir) if dest_dir else default_export_dir(job_id)
                result = export_report(report, out_dir)
                self.scanCenterExported.emit(result)
                if result.get("ok"):
                    self.toast.emit("success", f"Report exported to {result.get('report_path','')}")
                else:
                    self.toast.emit("error", f"Export failed: {result.get('error','')}")
            except Exception as exc:
                logger.exception("exportScanCenterReport failed")
                self.scanCenterExported.emit({"ok": False, "error": str(exc)})

        _t.Thread(target=_run, daemon=True, name="scancenter-export").start()

    @Slot(str)
    def explainScanCenterReport(self, report_json: str) -> None:
        """Ask Groq to explain a V3Report supplied as JSON string.

        Falls back to a template explanation when Groq is unavailable.
        """
        import threading as _t

        from ..scancenter.groq_explainer import explain_report
        from ..scancenter.report_schema import V3Report

        def _run() -> None:
            try:
                report = V3Report.from_json(report_json)
                explanation = explain_report(report)
                self.scanCenterExplainFinished.emit(explanation.to_dict())
            except Exception as exc:
                logger.exception("explainScanCenterReport failed")
                self.toast.emit("error", f"AI explanation failed: {exc}")

        _t.Thread(target=_run, daemon=True, name="scancenter-explain").start()

    @Slot(str)
    def openScanCenterReport(self, report_path: str) -> None:
        """Load a previously saved V3Report from *report_path* and re-emit scanCenterFinished."""
        from ..scancenter.export import load_report_json

        try:
            report = load_report_json(report_path)
            if report is None:
                self.toast.emit("error", "Could not load report from disk.")
                return
            self._scancenter_current_report = report.to_dict()
            self.scanCenterFinished.emit(self._scancenter_current_report)
        except Exception as exc:
            logger.exception("openScanCenterReport failed")
            self.toast.emit("error", f"Failed to load report: {exc}")

    @Slot()
    def openScanCenterRunDir(self) -> None:
        """Open the run folder of the most recent ScanCenter report in Explorer."""
        import subprocess as _sp

        try:
            report = self._scancenter_current_report
            if not report:
                self.toast.emit("warning", "No completed scan yet.")
                return
            rp = (
                report.get("report_path")
                or (report.get("job") or {}).get("report_path", "")
            )
            if not rp:
                self.toast.emit("warning", "Report path not stored. Run a scan first.")
                return
            folder = str(Path(rp).parent)
            _sp.Popen(
                ["explorer", folder],
                creationflags=0x00000008,  # DETACHED_PROCESS
            )
        except Exception as exc:
            logger.warning("openScanCenterRunDir: %s", exc)
            self.toast.emit("warning", f"Could not open run folder: {exc}")
