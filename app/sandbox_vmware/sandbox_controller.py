"""QObject controller for the VMware Sandbox Lab UI."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QImage

from .config import SandboxConfig, load_sandbox_config
from .preview_stream import SandboxPreviewStream
from .report_parser import build_llm_prompt, load_report, score_report
from .vmrun_client import VmrunClient, VmrunError

logger = logging.getLogger(__name__)

_GUEST_SCRIPTS_DIR = Path(__file__).parent / "guest_scripts"
_GUEST_POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"


class VmwareTaskWorker(QObject):
    """Run vmrun work in a background QThread."""

    progressChanged = Signal(int)
    statusChanged = Signal(str)
    stepEvent = Signal("QVariantMap")
    vmRunningChanged = Signal(bool)
    finished = Signal("QVariantMap")
    failed = Signal(str)
    done = Signal()

    def __init__(self, task: Callable[[VmwareTaskWorker], dict[str, Any]]):
        super().__init__()
        self._task = task

    def emit_step(self, status: str, message: str) -> None:
        self.stepEvent.emit(
            {
                "time": datetime.now().strftime("%H:%M:%S"),
                "status": status,
                "message": message,
            }
        )

    def emit_status(self, message: str) -> None:
        self.statusChanged.emit(message)

    def emit_progress(self, value: int) -> None:
        self.progressChanged.emit(max(0, min(100, int(value))))

    def set_vm_running(self, running: bool) -> None:
        self.vmRunningChanged.emit(bool(running))

    @Slot()
    def run(self) -> None:
        try:
            payload = self._task(self)
            self.finished.emit(payload)
        except Exception as exc:
            logger.exception("VMware task failed: %s", exc)
            self.failed.emit(str(exc))
        finally:
            self.done.emit()


class SandboxLabController(QObject):
    """VMware Workstation sandbox automation exposed to QML."""

    status = Signal(str)
    step = Signal(str)
    progress = Signal(int)
    isBusy = Signal(bool)
    liveFramePath = Signal(str)
    stepsModelChanged = Signal()
    verdictSummaryChanged = Signal()
    lastRunFolderChanged = Signal()
    replayFramesModelChanged = Signal()
    replayIndexChanged = Signal()
    replayFramePathChanged = Signal()
    replayModeChanged = Signal()
    lastErrorChanged = Signal()
    guestErrorContentChanged = Signal()  # first ~20 lines from guest_error.txt
    availabilityChanged = Signal()
    guestReadyChanged = Signal()
    evidenceChanged = Signal()
    proofMediaChanged = Signal()
    resultSummaryChanged = Signal()
    liveViewStateChanged = Signal()
    automationVisibleChanged = Signal()          # emitted when UI runner starts/stops
    uiRunnerStatusChanged = Signal(str)          # informational status from UI runner

    diagnosticsFinished = Signal("QVariantList")  # list of check dicts

    _captureFrameReady = Signal(str)
    _captureFailure = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._config: SandboxConfig = load_sandbox_config()
        self._client = VmrunClient(self._config)

        self._status_text = "VMware Sandbox Lab ready."
        self._step_text = ""
        self._progress_value = 0
        self._busy = False
        self._available = False
        self._availability_message = ""
        self._guest_ready = False
        self._last_error = ""
        self._guest_error_content = (
            ""  # first 20 lines of guest_error.txt (or transcript)
        )
        self._last_run_folder = ""
        self._live_frame_path = ""
        self._live_view_state = "VM not running"
        self._verdict_summary = ""
        self._result_summary: dict[str, Any] = {}
        self._steps_model: list[dict[str, str]] = []
        self._replay_frames: list[str] = []
        self._replay_index = -1
        self._replay_frame_path = ""
        self._replay_mode = False
        self._report_saved = False
        self._frames_saved = False
        self._verdict_computed = False
        self._media_exported = False
        self._proof_gif_path = ""
        self._proof_mp4_path = ""
        self._last_prompt = ""
        self._last_report_path = ""

        self._thread: QThread | None = None
        self._worker: VmwareTaskWorker | None = None
        self._run_dir: Path | None = None
        self._frames_dir: Path | None = None
        self._run_target = ""
        self._run_mode = ""
        self._run_options: dict[str, Any] = {}
        self._vm_running = False
        self._capture_in_flight = False
        self._capture_index = 0
        self._capture_for_run = False
        self._live_view_enabled = False
        self._last_capture_failure_at = 0.0
        self._run_started_at = ""
        # Thread-safe abort flag: set BEFORE VM stop so the capture timer
        # never fires a captureScreen call against a powered-off VM.
        self._abort_capture = threading.Event()
        # User-triggered cancel flag: set by cancelRun() slot.
        self._cancel_event = threading.Event()
        # UI runner state
        self._automation_visible: bool = False
        self._ui_runner_status: str = ""
        # SandboxPreviewStream: continuously polls vmrun captureScreen on its own
        # daemon thread and pushes BGRA data into the image://sandboxpreview/ provider.
        self._preview_stream: SandboxPreviewStream | None = None

        self._captureFrameReady.connect(self._apply_capture_frame)
        self._captureFailure.connect(self._apply_capture_failure)

        self._capture_timer = QTimer(self)
        self._capture_timer.setInterval(self._config.capture_interval_ms)
        self._capture_timer.timeout.connect(self._capture_live_frame)

        self._refresh_capabilities()
        self._reset_evidence()

    @Property(str, notify=status)
    def statusText(self) -> str:
        return self._status_text

    @Property(str, notify=step)
    def currentStep(self) -> str:
        return self._step_text

    @Property(int, notify=progress)
    def progressValue(self) -> int:
        return self._progress_value

    @Property(bool, notify=isBusy)
    def busy(self) -> bool:
        return self._busy

    @Property(bool, notify=availabilityChanged)
    def available(self) -> bool:
        return self._available

    @Property(str, notify=availabilityChanged)
    def availabilityMessage(self) -> str:
        return self._availability_message

    @Property(bool, notify=guestReadyChanged)
    def guestReady(self) -> bool:
        return self._guest_ready

    @Property(str, notify=liveFramePath)
    def liveFrameSource(self) -> str:
        return self._live_frame_path

    @Property(str, notify=liveViewStateChanged)
    def liveViewState(self) -> str:
        return self._live_view_state

    @Property(bool, notify=automationVisibleChanged)
    def automationVisible(self) -> bool:
        """True while the guest UI runner is actively interacting with the desktop."""
        return self._automation_visible

    @Property(str, notify=uiRunnerStatusChanged)
    def uiRunnerStatus(self) -> str:
        """Last informational message from the guest UI runner."""
        return self._ui_runner_status

    @Property("QVariantList", notify=stepsModelChanged)
    def stepsModel(self) -> list[dict[str, str]]:
        return list(self._steps_model)

    @Property("QVariantList", notify=stepsModelChanged)
    def steps(self) -> list[str]:
        return [
            f"{item['time']} [{item['status']}] {item['message']}"
            for item in self._steps_model
        ]

    @Property(str, notify=verdictSummaryChanged)
    def verdictSummary(self) -> str:
        return self._verdict_summary

    @Property(str, notify=lastRunFolderChanged)
    def lastRunFolder(self) -> str:
        return self._last_run_folder

    @Property("QVariantList", notify=replayFramesModelChanged)
    def replayFramesModel(self) -> list[str]:
        return list(self._replay_frames)

    @Property(int, notify=replayIndexChanged)
    def replayIndex(self) -> int:
        return self._replay_index

    @Property(str, notify=replayFramePathChanged)
    def replayFramePath(self) -> str:
        return self._replay_frame_path

    @Property(bool, notify=replayModeChanged)
    def replayMode(self) -> bool:
        return self._replay_mode

    @Property(str, notify=lastErrorChanged)
    def lastError(self) -> str:
        return self._last_error

    @Property(str, notify=guestErrorContentChanged)
    def guestErrorContent(self) -> str:
        """First ~20 lines of guest_error.txt (or transcript tail) from the last failed run."""
        return self._guest_error_content

    @Property(bool, notify=evidenceChanged)
    def reportSaved(self) -> bool:
        return self._report_saved

    @Property(bool, notify=evidenceChanged)
    def framesSaved(self) -> bool:
        return self._frames_saved

    @Property(bool, notify=evidenceChanged)
    def verdictComputed(self) -> bool:
        return self._verdict_computed

    @Property(bool, notify=evidenceChanged)
    def mediaExported(self) -> bool:
        return self._media_exported

    @Property(str, notify=proofMediaChanged)
    def proofGifPath(self) -> str:
        return self._proof_gif_path

    @Property(str, notify=proofMediaChanged)
    def proofMp4Path(self) -> str:
        return self._proof_mp4_path

    @Property("QVariantMap", notify=resultSummaryChanged)
    def resultSummary(self) -> dict[str, Any]:
        return dict(self._result_summary)

    def shutdown(self) -> None:
        self._capture_timer.stop()
        if self._preview_stream is not None:
            self._preview_stream.stop()
            self._preview_stream = None
        self._teardown_worker()

    @Slot()
    def refreshStatus(self) -> None:
        self._refresh_capabilities()

    @Slot(bool)
    def setLiveViewEnabled(self, enabled: bool) -> None:
        self._live_view_enabled = bool(enabled)
        self._sync_capture_state()

    @Slot(bool)
    def setReplayMode(self, enabled: bool) -> None:
        self._replay_mode = bool(enabled)
        self.replayModeChanged.emit()
        if self._replay_mode and self._replay_frames:
            self.setReplayIndex(max(0, self._replay_index))
        elif self._replay_mode:
            self._replay_frame_path = ""
            self.replayFramePathChanged.emit()

    @Slot(int)
    def setReplayIndex(self, index: int) -> None:
        if not self._replay_frames:
            self._replay_index = -1
            self._replay_frame_path = ""
            self.replayIndexChanged.emit()
            self.replayFramePathChanged.emit()
            return
        clamped = max(0, min(int(index), len(self._replay_frames) - 1))
        self._replay_index = clamped
        self._replay_frame_path = self._replay_frames[clamped]
        self.replayIndexChanged.emit()
        self.replayFramePathChanged.emit()

    @Slot()
    def startVm(self) -> None:
        self._start_task("Starting VM", self._task_start_vm)

    @Slot()
    def stopVm(self) -> None:
        self._start_task("Stopping VM", self._task_stop_vm)

    @Slot()
    def resetToClean(self) -> None:
        self._start_task("Resetting snapshot", self._task_reset)

    @Slot()
    def reset(self) -> None:
        self.resetToClean()

    @Slot()
    def runVmwareDiagnostics(self) -> None:
        """
        Run prerequisite checks and emit diagnosticsFinished with a list of
        { check, passed, message, fix } dicts.

        Runs in a background thread so the UI never blocks.
        """

        def _diag_task(worker: VmwareTaskWorker) -> dict:
            from ..sandbox.vmware_runner import VMwareRunner, load_runner_config

            worker.emit_step("Running", "Running VMware Diagnostics…")
            try:
                cfg, extras = load_runner_config()
                runner = VMwareRunner(
                    config=cfg,
                    extras=extras,
                    step_cb=worker.emit_step,
                )
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
            worker.emit_step("OK", "Diagnostics complete")
            return {"operation": "diagnostics", "checks": results}

        def _finish(payload: dict) -> None:
            if payload.get("operation") == "diagnostics":
                checks = list(payload.get("checks", []))
                self.diagnosticsFinished.emit(checks)

        # Temporarily wire a one-shot finish to emit diagnosticsFinished
        self._pending_diag_finish = _finish
        self._start_task("VMware Diagnostics", _diag_task)

    @Slot(str, int, bool, bool, bool, bool)
    def runFileInSandbox(
        self,
        host_file_path: str,
        monitor_seconds: int = 30,
        disable_network: bool = False,
        kill_on_finish: bool = True,
        allow_run: bool = False,
        interactive_gui: bool = True,
    ) -> None:
        host_path = Path(host_file_path)
        if not host_file_path or not host_path.exists() or not host_path.is_file():
            self._set_last_error(f"Selected file was not found: {host_file_path}")
            return
        self._prepare_run_context(
            "file",
            str(host_path),
            monitor_seconds,
            disable_network,
            kill_on_finish,
            allow_run=allow_run,
            interactive_gui=interactive_gui,
        )
        self._start_task("Running file detonation", self._task_run_file)

    @Slot(str, int, bool, bool)
    def runFile(
        self,
        host_file_path: str,
        monitor_seconds: int = 30,
        disable_network: bool = False,
        kill_on_finish: bool = True,
    ) -> None:
        self.runFileInSandbox(
            host_file_path, monitor_seconds, disable_network, kill_on_finish
        )

    @Slot()
    def cancelRun(self) -> None:
        """Abort the current sandbox run (sets _cancel_event; pipeline polls it)."""
        if self._busy:
            self._cancel_event.set()
            self._set_status(
                "Cancellation requested — waiting for pipeline to clean up…"
            )

    @Slot(str)
    def runUrlInSandbox(self, url: str) -> None:
        cleaned = url.strip()
        if not cleaned:
            self._set_last_error("Enter a URL before starting URL detonation.")
            return
        self._prepare_run_context("url", cleaned, 45, True, True)
        self._start_task("Running URL detonation", self._task_run_url)

    @Slot(str, int, bool, bool)
    def runUrl(
        self,
        url: str,
        monitor_seconds: int = 45,
        disable_network: bool = True,
        kill_on_finish: bool = True,
    ) -> None:
        cleaned = url.strip()
        if not cleaned:
            self._set_last_error("Enter a URL before starting URL detonation.")
            return
        self._prepare_run_context(
            "url", cleaned, monitor_seconds, disable_network, kill_on_finish
        )
        self._start_task("Running URL detonation", self._task_run_url)

    @Slot()
    def openLastRunFolder(self) -> None:
        if not self._last_run_folder:
            self._set_last_error(
                "No completed Sandbox Lab run folder is available yet."
            )
            return
        self._open_in_explorer(Path(self._last_run_folder))

    @Slot()
    def openProofMedia(self) -> None:
        for candidate in (self._proof_mp4_path, self._proof_gif_path):
            if candidate and Path(candidate).exists():
                self._open_in_explorer(Path(candidate))
                return
        self._set_last_error("No proof media is available yet.")

    @Slot(str, result=str)
    def copyAiPrompt(self, report_path: str = "") -> str:
        prompt = self._build_prompt(report_path)
        if not prompt:
            self._set_last_error("No AI prompt is available yet.")
            return ""
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(prompt)
            self._set_status("AI prompt copied to clipboard.")
        return prompt

    def _refresh_capabilities(self) -> None:
        messages: list[str] = []
        try:
            self._client.validate_host_requirements()
            self._available = True
            messages.append("VMware automation configured.")
        except VmrunError as exc:
            self._available = False
            messages.append(str(exc))
        self._guest_ready = self._config.guest_ready
        if self._guest_ready:
            messages.append("Guest credentials loaded.")
        else:
            messages.append(
                "Guest credentials missing; set SANDBOX_GUEST_USER and SANDBOX_GUEST_PASS."
            )
        self._availability_message = " ".join(messages)
        self.availabilityChanged.emit()
        self.guestReadyChanged.emit()
        self._set_status(self._availability_message)

    def _prepare_run_context(
        self,
        mode: str,
        target: str,
        monitor_seconds: int,
        disable_network: bool,
        kill_on_finish: bool,
        *,
        allow_run: bool = False,
        interactive_gui: bool = True,
    ) -> None:
        self._clear_run_state()
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self._config.host_results_dir / f"run_{run_id}"
        frames_dir = run_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        self._run_dir = run_dir
        self._frames_dir = frames_dir
        self._last_run_folder = str(run_dir)
        self._run_mode = mode
        self._run_target = target
        self._run_options = {
            "monitorSeconds": int(monitor_seconds),
            "disableNetwork": bool(disable_network),
            "killOnFinish":   bool(kill_on_finish),
            "allowRun":       bool(allow_run),
            "interactiveGui": bool(interactive_gui) and bool(allow_run),  # only relevant when allowRun=True
        }
        self._run_started_at = datetime.now().isoformat()
        self._capture_index = 0
        self._capture_for_run = True
        # Clear flags so new run starts fresh
        self._abort_capture.clear()
        self._cancel_event.clear()
        self._set_status(f"Prepared run folder: {run_dir}")
        self.lastRunFolderChanged.emit()

    def _clear_run_state(self) -> None:
        self._steps_model = []
        self.stepsModelChanged.emit()
        self._result_summary = {}
        self.resultSummaryChanged.emit()
        self._verdict_summary = ""
        self.verdictSummaryChanged.emit()
        self._last_prompt = ""
        self._last_report_path = ""
        self._replay_frames = []
        self._replay_index = -1
        self._replay_frame_path = ""
        self.replayFramesModelChanged.emit()
        self.replayIndexChanged.emit()
        self.replayFramePathChanged.emit()
        self._proof_gif_path = ""
        self._proof_mp4_path = ""
        self.proofMediaChanged.emit()
        self._set_last_error("")
        self._guest_error_content = ""
        self.guestErrorContentChanged.emit()
        self._reset_evidence()

    def _start_task(
        self, label: str, task: Callable[[VmwareTaskWorker], dict[str, Any]]
    ) -> None:
        if self._busy:
            self._set_last_error("Sandbox Lab is already busy.")
            return
        self._busy = True
        self.isBusy.emit(True)
        self._progress_value = 0
        self.progress.emit(0)
        self._step_text = label
        self.step.emit(label)
        self._append_step("Pending", f"{label} queued")
        self._set_status(label)

        self._thread = QThread(self)
        self._worker = VmwareTaskWorker(task)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progressChanged.connect(self._on_worker_progress)
        self._worker.statusChanged.connect(self._set_status)
        self._worker.stepEvent.connect(self._on_worker_step)
        self._worker.vmRunningChanged.connect(self._on_worker_vm_running)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.failed.connect(self._on_worker_failed)
        self._worker.done.connect(self._teardown_worker)
        self._thread.start()

    def _teardown_worker(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(2000)
            self._thread.deleteLater()
            self._thread = None
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._busy:
            self._busy = False
            self.isBusy.emit(False)
        self._sync_capture_state()

    def _task_start_vm(self, worker: VmwareTaskWorker) -> dict[str, Any]:
        self._client.validate_host_requirements()
        worker.emit_step("Running", "Starting VM in nogui mode")
        worker.emit_progress(30)
        self._client.start(nogui=True)
        worker.set_vm_running(True)
        worker.emit_step("OK", "VM started")
        worker.emit_progress(100)
        return {"success": True, "operation": "start"}

    def _task_stop_vm(self, worker: VmwareTaskWorker) -> dict[str, Any]:
        self._client.validate_host_requirements()
        worker.emit_step("Running", "Stopping VM")
        worker.emit_progress(40)
        self._client.stop(hard=True)
        worker.set_vm_running(False)
        worker.emit_step("OK", "VM stopped")
        worker.emit_progress(100)
        return {"success": True, "operation": "stop"}

    def _task_reset(self, worker: VmwareTaskWorker) -> dict[str, Any]:
        self._client.validate_host_requirements()
        worker.emit_step(
            "Running", f"Reverting to snapshot '{self._config.snapshot_name}'"
        )
        worker.emit_progress(30)
        try:
            self._client.stop(hard=True)
        except VmrunError:
            pass
        self._client.revert_to_snapshot()
        worker.set_vm_running(False)
        worker.emit_step("OK", "Snapshot restored")
        worker.emit_progress(100)
        return {"success": True, "operation": "reset"}

    def _task_run_file(self, worker: VmwareTaskWorker) -> dict[str, Any]:
        from dataclasses import asdict, is_dataclass

        sample_path = Path(self._run_target)

        # ── Static analysis on host (PE, YARA, hashes, entropy, IOCs) ──────
        static_info: dict[str, Any] = {}
        worker.emit_step(
            "Running", "Static analysis: hashing, PE, YARA, IOC extraction…"
        )
        try:
            from ..scanning.static_scanner import StaticScanner

            scanner = StaticScanner()
            result = scanner.scan_file(str(sample_path), run_clamav=False)
            raw: dict[str, Any] = (
                result.to_dict()
                if hasattr(result, "to_dict")
                else (asdict(result) if is_dataclass(result) else {})
            )
            static_info = raw
            sha_short = str(raw.get("sha256", ""))[:16]
            yara_count = len(raw.get("yara_matches") or [])
            entropy_val = float((raw.get("static") or {}).get("entropy") or 0)
            iocs_dict = raw.get("iocs") or {}
            ioc_count = sum(
                len(v) if isinstance(v, list) else (1 if v else 0)
                for v in (iocs_dict.values() if isinstance(iocs_dict, dict) else [])
            )
            pe_sus = bool((raw.get("pe_analysis") or {}).get("suspicious_imports"))
            parts = [
                f"SHA256={sha_short}…",
                f"entropy={entropy_val:.2f}",
                f"YARA={yara_count}",
            ]
            if pe_sus:
                parts.append("suspicious PE imports")
            if ioc_count:
                parts.append(f"{ioc_count} IOCs")
            worker.emit_step("OK", "Static: " + "  |  ".join(parts))
        except Exception as exc:
            worker.emit_step("Failed", f"Static analysis error (continuing): {exc}")

        # Build a per-job canonical guest path so mkdir / copy / check / run.ps1
        # all reference the same unambiguous location.
        _guest_base = self._config.guest_in_dir.rsplit("\\", 1)[0].rstrip("\\")
        _job_id = self._run_dir.name if self._run_dir else f"job_{int(time.time())}"
        _safe_name = "".join(
            c if (c.isalnum() or c in "._-") else "_" for c in sample_path.name
        )
        _guest_job_in = f"{_guest_base}\\jobs\\{_job_id}\\in"
        guest_path = f"{_guest_job_in}\\{_safe_name}"
        logger.info("Canonical guest sample path: %s", guest_path)
        args = [
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            self._config.guest_runner_path,
            "-SamplePath",
            guest_path,
            "-MonitorSeconds",
            str(self._run_options["monitorSeconds"]),
        ]
        if self._run_options["disableNetwork"]:
            args.append("-DisableNetwork")
        if self._run_options["killOnFinish"]:
            args.append("-KillOnFinish")
        if self._run_options.get("allowRun"):
            args.append("-AllowRun")

        payload = self._task_run_pipeline(worker, sample_path, guest_path, args)

        # ── Merge static + behavioral for richer verdict ─────────────────
        if static_info:
            payload["static_analysis"] = static_info
            yara_count = len(static_info.get("yara_matches") or [])
            iocs_dict = static_info.get("iocs") or {}
            ioc_count = sum(
                len(v) if isinstance(v, list) else (1 if v else 0)
                for v in (iocs_dict.values() if isinstance(iocs_dict, dict) else [])
            )
            base_score = int(payload.get("score") or 0)
            boost = min(30, yara_count * 10 + ioc_count * 3)
            if boost:
                payload["score"] = min(100, base_score + boost)
                highlights = list(payload.get("highlights") or [])
                if yara_count:
                    highlights.insert(
                        0, f"YARA: {yara_count} rule(s) matched on host static scan."
                    )
                if ioc_count:
                    highlights.insert(
                        0, f"IOCs: {ioc_count} indicator(s) extracted from host file."
                    )
                payload["highlights"] = highlights
            # Escalate verdict if static says Malicious and behavioral was lower
            if static_info.get("verdict") == "Malicious" and payload.get(
                "verdict"
            ) not in ("Malicious",):
                payload["verdict"] = "Malicious"
                payload["summary"] = f"[Static: Malicious] {payload.get('summary', '')}"

        # ── Build and save v2 SentinelReport ─────────────────────────────────
        try:
            import datetime as _dt

            from ..scanning.report_schema import (  # type: ignore[import]
                build_empty_report,
                report_dir,
                save_report,
                score_to_label,
                score_to_risk,
            )

            job_id = self._run_dir.name if self._run_dir else f"run_{int(time.time())}"
            sentinel = build_empty_report(job_id=job_id, mode="sandbox")
            guest_json = payload.get("report_json") or {}

            # file section
            fi = sentinel["file"]
            fi["name"] = sample_path.name
            fi["path"] = str(sample_path)
            fi["size_bytes"] = (
                int(sample_path.stat().st_size) if sample_path.exists() else 0
            )
            fi["extension"] = sample_path.suffix.lower()
            # file_type: prefer scanner detection, fall back to mime
            fi["file_type"] = (
                static_info.get("file_type") or static_info.get("mime_type") or ""
            )
            fi["sha256"] = static_info.get("sha256", "")
            fi["sha1"] = static_info.get("sha1", "")
            fi["md5"] = static_info.get("md5", "")
            _sig = static_info.get("signature") or {}
            fi["signed"] = _sig.get("valid")  # True / False / None
            fi["publisher"] = str(_sig.get("subject", "")) if _sig else None

            # static section
            _st = sentinel["static"]
            _st["entropy"] = float(
                (static_info.get("static") or {}).get("entropy") or 0
            )
            _st["yara_matches"] = list(static_info.get("yara_matches") or [])
            _st["top_strings"] = list(
                (static_info.get("static") or {}).get("strings") or []
            )[:50]
            _st["suspicious_imports"] = list(
                (static_info.get("pe_analysis") or {}).get("suspicious_imports") or []
            )
            _st["pe_analyzed"] = bool(static_info.get("pe_analysis"))
            _st["engines"] = list(static_info.get("engines") or [])

            # iocs — merge host-side static IOCs + guest behavioral IOCs
            _ioc_src = static_info.get("iocs") or {}
            sentinel["iocs"]["ips"] = list(_ioc_src.get("ips", []))
            sentinel["iocs"]["domains"] = list(_ioc_src.get("domains", []))
            sentinel["iocs"]["urls"] = list(_ioc_src.get("urls", []))
            sentinel["iocs"]["registry_keys"] = list(
                _ioc_src.get("registry", _ioc_src.get("registry_keys", []))
            )
            sentinel["iocs"]["file_paths"] = list(
                _ioc_src.get("paths", _ioc_src.get("file_paths", []))
            )
            sentinel["iocs"]["hashes"] = []
            _g_iocs = guest_json.get("iocs") or {}
            for _h_key, _s_key in (
                ("ips", "ips"),
                ("domains", "domains"),
                ("urls", "urls"),
                ("registry", "registry_keys"),
            ):
                _seen = set(sentinel["iocs"].get(_s_key, []))
                for _v in _g_iocs.get(_h_key) or []:
                    if _v not in _seen:
                        sentinel["iocs"][_s_key].append(_v)
                        _seen.add(_v)

            # sandbox section
            _sb = sentinel["sandbox"]
            _sb["mode"] = str(
                guest_json.get("analysis_mode", guest_json.get("mode", "run"))
            )
            _sb["executed"] = bool(guest_json.get("executed", False))
            _sb["processes_started"] = [
                {
                    "name": p.get("name", ""),
                    "pid": p.get("pid", 0),
                    "cmdline": "",
                    "parent": "",
                }
                for p in (guest_json.get("spawned_processes") or [])
            ]
            _sb["files_created"] = list(guest_json.get("files_created") or [])[:30]
            _sb["files_modified"] = []
            _sb["registry_modified"] = list(guest_json.get("registry_modified") or [])[
                :20
            ]
            _sb["network_attempts"] = [
                {"remote_addr": c, "remote_port": 0, "proto": "tcp", "pid": 0}
                for c in (guest_json.get("network_connections") or [])[:30]
            ]
            _sb["dns_queries"] = list(guest_json.get("dns_queries") or [])[:20]
            _sb["alerts"] = list(guest_json.get("alerts") or [])
            _sb["highlights"] = list(guest_json.get("highlights") or [])
            # sandbox.errors: prefer guest-reported errors; patch in host error when empty
            _sb_errors = list(guest_json.get("errors") or [])
            if not _sb_errors and payload.get("error"):
                _host_err = str(payload["error"])[:600]
                _snip = str(payload.get("guest_error_content") or "").strip()
                if _snip:
                    _host_err = f"{_host_err}\n\n[guest diagnostics]\n{_snip[:800]}"
                _sb_errors = [_host_err]
            _sb["errors"] = _sb_errors
            # executed=False when error present (guest ran but failed)
            if payload.get("error") and not _sb["executed"]:
                _sb["executed"] = False

            # verdict section
            _final_score = int(payload.get("score") or 0)
            sentinel["verdict"]["score"] = _final_score
            sentinel["verdict"]["confidence"] = _final_score
            sentinel["verdict"]["risk"] = score_to_risk(_final_score)
            sentinel["verdict"]["label"] = score_to_label(_final_score)
            sentinel["verdict"]["reasons"] = list(payload.get("highlights") or [])[:5]

            # timestamps + duration
            sentinel["job"]["started_at"] = self._run_started_at or ""
            _finished_iso = _dt.datetime.now().isoformat()
            sentinel["job"]["finished_at"] = _finished_iso
            sentinel["job"]["mode"] = "sandbox"
            try:
                _dur = (
                    _dt.datetime.fromisoformat(_finished_iso)
                    - _dt.datetime.fromisoformat(self._run_started_at)
                ).total_seconds()
                sentinel["job"]["duration_sec"] = round(max(0.0, _dur), 1)
            except Exception:
                sentinel["job"]["duration_sec"] = 0.0

            save_report(sentinel, job_id)
            payload["sentinel_report"] = sentinel
            payload["sentinel_report_path"] = str(report_dir(job_id) / "report.json")
            worker.emit_step(
                "OK", f"Sentinel v2 report → data/reports/{job_id}/report.json"
            )
        except Exception as _sent_exc:
            worker.emit_step(
                "Failed", f"v2 report build failed (non-critical): {_sent_exc}"
            )

        return payload

    def _task_run_url(self, worker: VmwareTaskWorker) -> dict[str, Any]:
        args = [
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            self._config.guest_open_url_path,
            "-Url",
            self._run_target,
            "-MonitorSeconds",
            str(self._run_options["monitorSeconds"]),
        ]
        if self._run_options["disableNetwork"]:
            args.append("-DisableNetwork")
        if self._run_options["killOnFinish"]:
            args.append("-KillOnFinish")
        return self._task_run_pipeline(worker, None, None, args)

    def _task_run_pipeline(
        self,
        worker: VmwareTaskWorker,
        sample_path: Path | None,
        guest_sample_path: str | None,
        guest_args: list[str],
    ) -> dict[str, Any]:
        assert self._run_dir is not None
        assert self._frames_dir is not None
        report_path = self._run_dir / "report.json"
        payload: dict[str, Any] = {
            "success": False,
            "run_dir": str(self._run_dir),
            "report_path": str(report_path),
            "mode": self._run_mode,
            "target": self._run_target,
            "vmx": self._config.vmx_path,
            "options": dict(self._run_options),
            "proof_gif": "",
            "proof_mp4": "",
            "error": "",
            "mp4_note": "",
        }
        error_text = ""

        try:
            self._client.validate_host_requirements()
            self._client.ensure_guest_credentials()
            worker.emit_progress(5)
            worker.emit_step("Running", "Reverting VM to clean snapshot")
            try:
                self._client.stop(hard=True)
            except VmrunError:
                pass
            self._client.revert_to_snapshot()
            worker.emit_step("OK", "Snapshot restored")

            worker.emit_progress(15)
            worker.emit_step("Running", "Starting VM (headless – live view in app)")
            self._client.start(nogui=True)
            worker.set_vm_running(True)
            worker.emit_step("OK", "VM started")

            worker.emit_progress(22)
            worker.emit_step("Running", "Waiting for VMware Tools to become ready…")
            self._client.wait_for_tools(
                timeout=180,
                poll_interval=3,
                cancel_event=self._cancel_event,
            )
            worker.emit_step("OK", "VMware Tools is running — guest is ready")

            # ── Create sandbox directories in guest ───────────────────────
            worker.emit_progress(30)
            worker.emit_step("Running", "Preparing C:\\Sandbox directories in guest")
            # Derive guest in-dir from the canonical sample path when available;
            # fall back to the legacy location so URL-mode tasks are unaffected.
            if guest_sample_path is not None:
                _g_in_dir = guest_sample_path.rsplit("\\", 1)[0]
                _g_out_dir = "C:\\Sandbox\\out"
            else:
                _g_in_dir = "C:\\Sandbox\\in"
                _g_out_dir = "C:\\Sandbox\\out"
            _mkdir_cmd = f"New-Item -ItemType Directory -Force -Path '{_g_in_dir}','{_g_out_dir}' | Out-Null"
            self._client.run_program_in_guest(
                _GUEST_POWERSHELL,
                ["-ExecutionPolicy", "Bypass", "-Command", _mkdir_cmd],
                wait=True,
                timeout=60,
            )
            worker.emit_step(
                "OK", f"Guest directories ready: {_g_in_dir}  {_g_out_dir}"
            )

            # ── Deploy runner script from host into guest ─────────────────
            worker.emit_progress(33)
            if self._run_mode == "file":
                _host_script = _GUEST_SCRIPTS_DIR / "run.ps1"
                _guest_script = self._config.guest_runner_path
            else:
                _host_script = _GUEST_SCRIPTS_DIR / "open_url.ps1"
                _guest_script = self._config.guest_open_url_path
            worker.emit_step("Running", f"Deploying {_host_script.name} to guest")
            self._client.copy_file_from_host_to_guest(_host_script, _guest_script)
            worker.emit_step("OK", f"Runner script deployed to {_guest_script}")

            if sample_path is not None and guest_sample_path is not None:
                worker.emit_progress(35)
                # Derived from canonical guest_sample_path — same value used in mkdir above.
                _g_in_dir = guest_sample_path.rsplit("\\", 1)[0]
                _safe_filename = guest_sample_path.rsplit("\\", 1)[-1]
                _probe_host = self._run_dir / f"probe_{_safe_filename}"
                _expected_size = (
                    sample_path.stat().st_size if sample_path.exists() else 0
                )

                # ── Local helper: collect dir /b diagnostics into run_dir ─────────
                def _collect_diagnostics() -> tuple[str, str]:
                    """
                    Redirect 'dir /b <_g_in_dir>' to a temp file in the guest,
                    copy it back to run_dir/dir_listing.txt, then delete the temp.
                    Returns (listing_content, error_detail).  Never raises.
                    """
                    _dg = "C:\\Windows\\Temp\\sentinel_dir_listing.txt"
                    _dh = self._run_dir / "dir_listing.txt"
                    _content = ""
                    _err = ""
                    try:
                        self._client.run_program_in_guest(
                            "cmd.exe",
                            ["/c", f'dir /b "{_g_in_dir}" > "{_dg}" 2>&1'],
                            wait=True,
                            timeout=12,
                        )
                    except VmrunError as _e:
                        _err = str(_e)
                    try:
                        self._client.copy_file_from_guest_to_host(_dg, _dh, timeout=15)
                        _content = _dh.read_text(errors="replace").strip()
                        try:
                            self._client.run_program_in_guest(
                                "cmd.exe",
                                ["/c", f'del /f /q "{_dg}"'],
                                wait=True,
                                timeout=8,
                            )
                        except VmrunError:
                            pass
                    except VmrunError as _e2:
                        _err = f"{_err}; retrieval: {_e2}".lstrip("; ")
                    # Always persist errors to disk so they survive the session
                    if _err:
                        (self._run_dir / "dir_listing_error.txt").write_text(
                            _err, encoding="utf-8"
                        )
                    return _content, _err

                def _listing_block(content: str, error: str) -> str:
                    if content:
                        return f"\n  dir /b output :\n{content}"
                    if error:
                        return f"\n  dir /b        : unavailable — {error}"
                    return "\n  dir /b        : (not attempted)"

                # ── Copy sample into guest ────────────────────────────────────────
                worker.emit_step(
                    "Running", f"Copying sample to guest: {guest_sample_path}"
                )
                self._client.copy_file_from_host_to_guest(
                    sample_path, guest_sample_path
                )
                worker.emit_step("OK", f"Sample copied → {guest_sample_path}")

                # ── Primary verification: round-trip copy-back probe ──────────────
                # copyFileFromGuestToHost succeeds iff the file exists at that exact
                # path — no dependency on runProgramInGuest at all.
                worker.emit_step(
                    "Running",
                    f"[probe] Verifying guest file via round-trip copy: {guest_sample_path}",
                )
                _probe_exc_val: VmrunError | None = None
                try:
                    self._client.copy_file_from_guest_to_host(
                        guest_sample_path, _probe_host, timeout=30
                    )
                except VmrunError as _px:
                    _probe_exc_val = _px

                if _probe_exc_val is not None:
                    _dc, _de = _collect_diagnostics()
                    _fail_msg = (
                        f"Sample copy verification failed — probe round-trip copy returned an error.\n"
                        f"  Expected path : {guest_sample_path}\n"
                        f"  Expected size : {_expected_size} bytes\n"
                        f"  Guest in-dir  : {_g_in_dir}\n"
                        f"  vmrun error   : {_probe_exc_val}"
                        f"{_listing_block(_dc, _de)}"
                    )
                    worker.emit_step("Failed", _fail_msg)
                    raise VmrunError(_fail_msg) from _probe_exc_val

                # Probe copy succeeded — validate size
                _probe_size = _probe_host.stat().st_size if _probe_host.exists() else -1
                _size_ok = _probe_size > 0 and (
                    _expected_size == 0 or _probe_size == _expected_size
                )

                # Persist size-check record unconditionally
                (self._run_dir / "probe_size_check.txt").write_text(
                    f"guest_sample_path : {guest_sample_path}\n"
                    f"expected_size     : {_expected_size}\n"
                    f"probe_size        : {_probe_size}\n"
                    f"size_ok           : {_size_ok}\n",
                    encoding="utf-8",
                )

                # Remove probe file from host
                try:
                    _probe_host.unlink(missing_ok=True)
                except OSError:
                    pass

                if not _size_ok:
                    _dc, _de = _collect_diagnostics()
                    _fail_msg = (
                        f"Sample copy verification failed — probe size mismatch.\n"
                        f"  Expected path : {guest_sample_path}\n"
                        f"  Expected size : {_expected_size} bytes\n"
                        f"  Probe size    : {_probe_size} bytes\n"
                        f"  Guest in-dir  : {_g_in_dir}"
                        f"{_listing_block(_dc, _de)}"
                    )
                    worker.emit_step("Failed", _fail_msg)
                    raise VmrunError(_fail_msg)

                worker.emit_step(
                    "OK",
                    f"[probe] Sample verified in guest: {guest_sample_path} ({_probe_size} bytes)",
                )

            worker.emit_progress(50)
            worker.emit_step("Running", "Launching guest PowerShell automation")
            self._client.run_program_in_guest(
                _GUEST_POWERSHELL,
                guest_args,
                wait=True,
                interactive=True,
                timeout=max(120, int(self._run_options["monitorSeconds"]) + 180),
            )
            worker.emit_step("OK", "Guest automation finished")

            # ── Guest UI Runner: visible interaction in Session 1 ─────────────
            # Only runs when allowRun=True (execute mode) on file targets.
            # Non-fatal: failure only emits a warning step.
            _ui_key_frames: list[str] = []
            if self._run_mode == "file" and guest_sample_path is not None:
                _ui_result = self._run_ui_automation(worker, guest_sample_path)
                _ui_key_frames                = _ui_result.get("frames", [])
                payload["automation_visible"]  = _ui_result.get("automation_visible", False)
                payload["ui_steps"]            = _ui_result.get("ui_steps", [])
                payload["ui_frames_dir"]       = _ui_result.get("frames_dir", "")
                payload["uac_secure_desktop"]  = _ui_result.get("uac_secure_desktop")
            else:
                payload["automation_visible"]  = False
                payload["ui_steps"]            = []
                payload["uac_secure_desktop"]  = None
            payload["ui_key_frames"] = _ui_key_frames

            worker.emit_progress(70)
            worker.emit_step("Running", "Polling for guest report.json")
            self._poll_report_from_guest(report_path)
            worker.emit_step("OK", "report.json copied to host")

            worker.emit_progress(82)
        except Exception as exc:
            error_text = str(exc)
            worker.emit_step("Failed", error_text)
            # ── Pull transcript + error file back from guest before VM reverts ──
            # The VM is still running at this point (finally hasn't run yet).
            if self._run_dir:
                for _guest_artifact, _host_name in [
                    ("C:\\Sandbox\\out\\guest_transcript.txt", "guest_transcript.txt"),
                    ("C:\\Sandbox\\out\\guest_error.txt", "guest_error.txt"),
                ]:
                    try:
                        self._client.copy_file_from_guest_to_host(
                            _guest_artifact, self._run_dir / _host_name, timeout=20
                        )
                    except Exception:
                        pass
                # ── Collect guest diagnostics into a structured payload field ─────────
                # First 20 non-blank lines of guest_error.txt (preferred);
                # fall back to last 40 lines of transcript.
                _guest_snippet = ""
                for _artifact_name in ("guest_error.txt", "guest_transcript.txt"):
                    _artifact_path = self._run_dir / _artifact_name
                    if _artifact_path.exists():
                        try:
                            _all_lines = _artifact_path.read_text(
                                encoding="utf-8", errors="replace"
                            ).splitlines()
                            if _artifact_name == "guest_error.txt":
                                # first 20 non-blank lines
                                _snippet_lines = [l for l in _all_lines if l.strip()][
                                    :20
                                ]
                            else:
                                # last 40 lines for transcript
                                _snippet_lines = _all_lines[-40:]
                            _guest_snippet = "\n".join(_snippet_lines)
                        except Exception:
                            pass
                        if _guest_snippet.strip():
                            break
                if _guest_snippet.strip():
                    error_text = (
                        f"{error_text}\n\n[guest diagnostics]\n{_guest_snippet}"
                    )
        finally:
            # ── ABORT CAPTURE FIRST (thread-safe flag, checked by timer before vmrun)
            # Setting this before stop()/revert ensures no new captureScreen calls
            # are dispatched against a powered-off VM regardless of timer/signal lag.
            self._abort_capture.set()
            # Signal the main-thread Qt property so _sync_capture_state also stops the timer
            worker.set_vm_running(False)
            worker.emit_step("Running", "Resetting VM to clean snapshot")
            try:
                try:
                    self._client.stop(hard=True)
                except VmrunError:
                    pass
                self._client.revert_to_snapshot()
                worker.emit_step("OK", "Cleanup snapshot restore completed")
            except Exception as cleanup_exc:
                cleanup_text = f"Cleanup failed: {cleanup_exc}"
                if error_text:
                    error_text = f"{error_text} | {cleanup_text}"
                else:
                    error_text = cleanup_text
                worker.emit_step("Failed", cleanup_text)

        time.sleep(0.8)
        # Only export frames if capture was active; the VM is already off so
        # _export_media reads existing PNGs from disk — it never calls captureScreen.
        if self._config.capture_enabled and self._frames_dir is not None:
            export_result = self._export_media(self._frames_dir, self._run_dir, worker)
        else:
            export_result = {
                "proof_gif": "",
                "proof_mp4": "",
                "frames_saved": bool(self._replay_frames),
                "media_exported": False,
                "mp4_note": "Capture disabled.",
            }
        payload.update(export_result)

        # ── Guarantee report.json always exists ──────────────────────────────
        if not report_path.exists() and self._run_dir is not None:
            try:
                from ..scanning.report_schema import (  # type: ignore[import]
                    build_empty_report,
                )
                from ..scanning.report_schema import save_report as _save_report

                _job_id = self._run_dir.name
                _minimal = build_empty_report(job_id=_job_id, mode="sandbox")
                _err_lines: list[str] = (
                    [error_text]
                    if error_text
                    else ["report.json not produced by guest script"]
                )
                for _art in ("guest_error.txt", "guest_transcript.txt"):
                    _art_path = self._run_dir / _art
                    if _art_path.exists():
                        try:
                            _lines = _art_path.read_text(
                                encoding="utf-8", errors="replace"
                            ).splitlines()[-80:]
                            _err_lines.extend([f"[{_art}] {l}" for l in _lines])
                        except Exception:
                            pass
                        break
                _minimal["sandbox"]["errors"] = _err_lines
                _minimal["verdict"]["label"] = "Failed"
                _minimal["verdict"]["risk"] = "unknown"
                _save_report(_minimal, _job_id)
                # Also write to the local run_dir report_path so downstream parsing works
                import json as _json_fallback

                report_path.parent.mkdir(parents=True, exist_ok=True)
                with report_path.open("w", encoding="utf-8") as _fh:
                    _json_fallback.dump(_minimal, _fh, indent=2)
                worker.emit_step("OK", "Minimal report.json produced for failed run")
            except Exception as _fallback_exc:
                worker.emit_step(
                    "Failed", f"Could not write fallback report.json: {_fallback_exc}"
                )

        if report_path.exists():
            try:
                report_json = load_report(report_path)
                scoring = score_report(report_json)
                payload.update(scoring)
                payload["report_json"] = report_json
                payload["success"] = not bool(error_text)
            except Exception as exc:
                parse_text = f"Failed to parse report.json: {exc}"
                error_text = (
                    f"{error_text} | {parse_text}" if error_text else parse_text
                )
                worker.emit_step("Failed", parse_text)
                payload.update(
                    {
                        "verdict": "Inconclusive",
                        "score": 0,
                        "summary": parse_text,
                        "highlights": [],
                    }
                )
        else:
            if not error_text:
                error_text = "Guest report.json was not produced before timeout."
            payload.update(
                {
                    "verdict": "Inconclusive",
                    "score": 0,
                    "summary": error_text,
                    "highlights": [],
                }
            )

        payload["error"] = error_text
        # ── Always include run_dir + guest diagnostic snippet in payload ─────────
        payload["run_dir_path"] = str(self._run_dir) if self._run_dir else ""
        # Collect guest_error_content from disk if not already populated
        if not payload.get("guest_error_content") and self._run_dir:
            _gec = ""
            for _art in ("guest_error.txt", "guest_transcript.txt"):
                _ap = self._run_dir / _art
                if _ap.exists():
                    try:
                        _lines = _ap.read_text(
                            encoding="utf-8", errors="replace"
                        ).splitlines()
                        _gec = "\n".join([l for l in _lines if l.strip()][:20])
                    except Exception:
                        pass
                    if _gec.strip():
                        break
            if _gec.strip():
                payload["guest_error_content"] = _gec
        worker.emit_progress(100)
        if not error_text:
            worker.emit_step("OK", "Automation Completed ✅")
        return payload

    # ─────────────────────────────────────────── Guest UI Runner integration

    def _run_ui_automation(
        self,
        worker: VmwareTaskWorker,
        guest_sample_path: str,
    ) -> dict:
        """Run visible GUI automation in the guest interactive session.

        Only executes when ``allowRun`` is True in the current run options.
        Non-fatal: any failure emits a warning step and returns an empty dict.

        Returns:
            dict with keys:
              frames           – list of host-side key-frame paths (≤ 10)
              automation_visible – bool: True when frames changed and >0 captured
              ui_steps         – list[str]: step-marker content from guest
              frames_dir       – str: host-side frames directory
        """
        from .guest_ui_runner import GuestUIRunner, GuestUIRunnerError  # local import

        _empty: dict = {"frames": [], "automation_visible": False, "ui_steps": [], "frames_dir": "", "uac_secure_desktop": None}

        if not self._run_options.get("allowRun"):
            worker.emit_step(
                "Running",
                "[UI-runner] Skipped (inspect-only mode — enable 'Allow execution' to see GUI automation)",
            )
            return _empty

        if self._cancel_event.is_set():
            return _empty

        interactive_gui = bool(self._run_options.get("interactiveGui", True))
        inspect_only    = not interactive_gui   # inspect_only=True → no button clicks, no visible intent

        job_id         = self._run_dir.name if self._run_dir else f"job_{int(time.time())}"
        _guest_base    = self._config.guest_in_dir.rsplit("\\", 1)[0].rstrip("\\")
        guest_job_base = f"{_guest_base}\\jobs\\{job_id}"
        monitor_secs   = int(self._run_options.get("monitorSeconds", 60))

        ui_runner = GuestUIRunner(
            self._client,
            self._config,
            step_cb=worker.emit_step,
            cancel_check=lambda: self._cancel_event.is_set(),
        )

        # ── 1. Preflight ──────────────────────────────────────────────────────
        try:
            ui_runner.preflight_check_desktop()
        except GuestUIRunnerError as exc:
            first_line = str(exc).splitlines()[0]
            worker.emit_step("Failed", f"[UI-runner] Preflight: {first_line}")
            self._set_ui_runner_status(first_line)
            return _empty

        # ── 2. Deploy runner scripts ──────────────────────────────────────────
        try:
            ui_runner.deploy(job_id, guest_job_base)
            # Also deploy the unified top-level entry-point (ui_runner.ps1)
            _top_runner_src = _GUEST_SCRIPTS_DIR / "ui_runner.ps1"
            if _top_runner_src.exists():
                _guest_top_runner = f"{guest_job_base}\\tools\\ui_runner.ps1"
                self._client.copy_file_from_host_to_guest(_top_runner_src, _guest_top_runner)
            # Deploy the AHK detonation helper if present (optional)
            _ahk_src = _GUEST_SCRIPTS_DIR / "detonate.ahk"
            if _ahk_src.exists():
                _guest_ahk = f"{guest_job_base}\\tools\\detonate.ahk"
                self._client.copy_file_from_host_to_guest(_ahk_src, _guest_ahk)
                worker.emit_step("OK", "[UI-runner] Deployed detonate.ahk companion")
            # Deploy the Python visual-agent script if present (optional)
            _py_agent_src = _GUEST_SCRIPTS_DIR / "detonate.py"
            if _py_agent_src.exists():
                _guest_py_agent = f"{guest_job_base}\\tools\\detonate.py"
                self._client.copy_file_from_host_to_guest(
                    _py_agent_src, _guest_py_agent
                )
                worker.emit_step("OK", "[UI-runner] Deployed detonate.py visual agent")
        except Exception as exc:
            worker.emit_step("Failed", f"[UI-runner] Deploy failed: {exc}")
            return _empty

        # ── 3. Launch in interactive session ─────────────────────────────────
        self._set_automation_visible(True)
        mode_label = "interactive GUI" if interactive_gui else "inspect-only"
        worker.emit_step("Running", f"[UI-runner] Starting {mode_label} session…")
        try:
            ui_runner.run(
                job_id=job_id,
                guest_job_base=guest_job_base,
                sample_guest_path=guest_sample_path,
                monitor_seconds=monitor_secs,
                inspect_only=inspect_only,
            )
        except Exception as exc:
            worker.emit_step("Failed", f"[UI-runner] Run error: {exc}")
        finally:
            self._set_automation_visible(False)

        # ── 4. Collect frames + behavior.json + ui_step markers ───────────────
        if not self._run_dir:
            return _empty
        try:
            key_frames = ui_runner.collect_output(
                self._run_dir, job_id, max_frames=10
            )
            automation_visible = ui_runner.last_automation_visible
            ui_steps           = ui_runner.last_ui_steps
            frames_dir         = ui_runner.last_frames_dir
            uac_secure_desktop = ui_runner.last_uac_secure_desktop

            if key_frames:
                worker.emit_step(
                    "OK",
                    f"[UI-runner] {len(key_frames)} key frame(s) collected for replay "
                    f"({'automation visible ✅' if automation_visible else 'no visible changes ⚠'} )",
                )
                # Update persistent status so live UI badge reflects reality
                if not automation_visible:
                    self._set_ui_runner_status(
                        "Automation ran in background / no interactive desktop detected"
                    )
            else:
                self._set_ui_runner_status(
                    "Guest desktop session not active — enable auto-login to see GUI automation"
                )
                worker.emit_step(
                    "Failed",
                    "[UI-runner] No frames captured — check if interactive desktop is available",
                )
            return {
                "frames":             key_frames,
                "automation_visible": automation_visible,
                "ui_steps":           ui_steps,
                "frames_dir":         frames_dir,
                "uac_secure_desktop": uac_secure_desktop,
            }
        except Exception as exc:
            worker.emit_step("Failed", f"[UI-runner] Frame collection error: {exc}")
            return _empty

    def _set_automation_visible(self, visible: bool) -> None:
        if visible != self._automation_visible:
            self._automation_visible = visible
            self.automationVisibleChanged.emit()

    def _set_ui_runner_status(self, text: str) -> None:
        self._ui_runner_status = text
        self.uiRunnerStatusChanged.emit(text)

    def _poll_report_from_guest(self, host_report_path: Path) -> None:
        guest_report_path = self._guest_path(self._config.guest_out_dir, "report.json")
        deadline = time.time() + max(15, self._config.report_poll_seconds)
        last_error = ""
        while time.time() < deadline:
            if self._cancel_event.is_set():
                raise VmrunError("Run cancelled by user.")
            try:
                if host_report_path.exists():
                    host_report_path.unlink()
                self._client.copy_file_from_guest_to_host(
                    guest_report_path, host_report_path, timeout=30
                )
                if host_report_path.exists() and host_report_path.stat().st_size > 0:
                    return
            except VmrunError:
                raise
            except Exception as exc:
                last_error = str(exc)
            time.sleep(2)
        if last_error:
            raise VmrunError(
                f"Timed out waiting for report.json. Last vmrun error: {last_error}"
            )
        raise VmrunError("Timed out waiting for report.json from the guest sandbox.")

    def _export_media(
        self, frames_dir: Path, run_dir: Path, worker: VmwareTaskWorker
    ) -> dict[str, Any]:
        frames = sorted(frames_dir.glob("frame_*.png"))
        if not frames:
            return {
                "proof_gif": "",
                "proof_mp4": "",
                "frames_saved": False,
                "media_exported": False,
                "mp4_note": "No frames were captured.",
            }

        gif_path = run_dir / "proof.gif"
        mp4_path = run_dir / "proof.mp4"
        gif_saved = False
        mp4_saved = False
        mp4_note = ""

        try:
            import imageio.v2 as imageio

            images = [imageio.imread(frame) for frame in frames]
            imageio.mimsave(
                gif_path,
                images,
                duration=max(0.4, self._config.capture_interval_ms / 1000.0),
            )
            gif_saved = gif_path.exists()
            if gif_saved:
                worker.emit_step("OK", f"Exported {gif_path.name}")
        except ImportError:
            worker.emit_step("Failed", "GIF export skipped: imageio is not installed")
        except Exception as exc:
            worker.emit_step("Failed", f"GIF export failed: {exc}")

        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            try:
                import imageio_ffmpeg  # bundled by imageio[ffmpeg]

                ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                ffmpeg_path = None
        if ffmpeg_path:
            result = subprocess.run(
                [
                    ffmpeg_path,
                    "-y",
                    "-framerate",
                    "2",
                    "-i",
                    str(frames_dir / "frame_%06d.png"),
                    "-pix_fmt",
                    "yuv420p",
                    str(mp4_path),
                ],
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            if result.returncode == 0 and mp4_path.exists():
                mp4_saved = True
                worker.emit_step("OK", f"Exported {mp4_path.name}")
            else:
                mp4_note = "ffmpeg failed; GIF export kept."
                worker.emit_step("Failed", mp4_note)
        else:
            mp4_note = "ffmpeg not installed; MP4 export skipped."
            worker.emit_step("Failed", mp4_note)

        return {
            "proof_gif": str(gif_path) if gif_saved else "",
            "proof_mp4": str(mp4_path) if mp4_saved else "",
            "frames_saved": True,
            "media_exported": bool(gif_saved or mp4_saved),
            "mp4_note": mp4_note,
        }

    def _build_prompt(self, report_path: str = "") -> str:
        try:
            if report_path:
                report_json = load_report(report_path)
            elif self._last_report_path and Path(self._last_report_path).exists():
                report_json = load_report(self._last_report_path)
            elif isinstance(self._result_summary.get("report_json"), dict):
                report_json = self._result_summary["report_json"]
            else:
                return ""
            self._last_prompt = build_llm_prompt(report_json, self.steps)
            return self._last_prompt
        except Exception as exc:
            self._set_last_error(f"Failed to build AI prompt: {exc}")
            return ""

    def _write_meta(self) -> None:
        if self._run_dir is None:
            return
        payload = {
            "started_at": self._run_started_at,
            "finished_at": datetime.now().isoformat(),
            "mode": self._run_mode,
            "target": self._run_target,
            "options": dict(self._run_options),
            "vmx": self._config.vmx_path,
            "sample_name": Path(self._run_target).name if self._run_target else "",
            "steps": self._steps_model,
            "report_path": self._last_report_path,
            "proof_gif": self._proof_gif_path,
            "proof_mp4": self._proof_mp4_path,
            "report_saved": self._report_saved,
            "frames_saved": self._frames_saved,
            "verdict_computed": self._verdict_computed,
            "media_exported": self._media_exported,
            "last_error": self._last_error,
            "verdict_summary": self._verdict_summary,
        }
        try:
            with (self._run_dir / "meta.json").open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except OSError as exc:
            logger.warning("Could not write Sandbox Lab meta.json: %s", exc)

    def _sync_capture_state(self) -> None:
        should_capture = (
            self._config.capture_enabled
            and self._vm_running
            and not self._abort_capture.is_set()
            and (self._capture_for_run or self._live_view_enabled)
        )
        if should_capture and not self._capture_timer.isActive():
            self._capture_timer.start()
            # ── Start SandboxPreviewStream for live image://sandboxpreview/ feed ──
            if self._preview_stream is None or not self._preview_stream.running:
                _out = str(
                    (self._frames_dir or self._config.host_frames_dir)
                    / "_live_preview.png"
                )
                # Build frame_callback that feeds the image provider directly
                _frame_cb = None
                try:
                    from ..ui.sandbox_preview_provider import get_preview_provider, get_preview_controller
                    _provider = get_preview_provider()
                    def _on_frame(data: bytes, w: int, h: int) -> None:   # noqa: E306
                        _provider.update_frame(data, w, h)
                    _frame_cb = _on_frame
                except Exception:
                    pass

                def _on_file_update(path: str, ts_ms: int) -> None:
                    url = QUrl.fromLocalFile(path).toString() + "?ts=" + str(ts_ms)
                    self._captureFrameReady.emit(url)

                self._preview_stream = SandboxPreviewStream(
                    vmrun_path=self._config.vmrun_path,
                    vmx_path=self._config.vmx_path,
                    out_path=_out,
                    interval_sec=max(0.3, self._config.capture_interval_ms / 1000.0),
                    on_update=_on_file_update,
                    frame_callback=_frame_cb,
                    guest_user=self._config.guest_user,
                    guest_pass=self._config.guest_pass,
                )
                self._preview_stream.start()
                logger.debug("SandboxPreviewStream started alongside capture timer")

            # Start the global SandboxPreviewController refresh timer
            try:
                from ..ui.sandbox_preview_provider import get_preview_controller
                ctrl = get_preview_controller()
                ctrl.set_status("Streaming VMware guest desktop…")
                ctrl.start()
            except Exception:
                pass
        elif not should_capture and self._capture_timer.isActive():
            self._capture_timer.stop()
            # Stop the preview stream when capture is no longer needed
            if self._preview_stream is not None:
                self._preview_stream.stop()
                self._preview_stream = None
                logger.debug("SandboxPreviewStream stopped")
            try:
                from ..ui.sandbox_preview_provider import get_preview_controller
                get_preview_controller().stop()
            except Exception:
                pass

        if not self._vm_running:
            self._set_live_state("VM not running")
        elif self._live_view_enabled:
            self._set_live_state("Capturing...")
        else:
            self._set_live_state("Paused")

    def _capture_live_frame(self) -> None:
        # Abort flag is set synchronously in the pipeline finally block before VM stop.
        # Checking here (main thread) prevents new capture jobs from being dispatched
        # even if the timer fires once more before the queued vmRunningChanged signal
        # is processed by _on_worker_vm_running.
        if (
            self._capture_in_flight
            or not self._vm_running
            or self._abort_capture.is_set()
        ):
            return
        frame_dir = (
            self._frames_dir
            if self._capture_for_run and self._frames_dir is not None
            else self._config.host_frames_dir
        )
        frame_dir.mkdir(parents=True, exist_ok=True)
        self._capture_in_flight = True
        self._capture_index += 1
        frame_path = frame_dir / f"frame_{self._capture_index:06d}.png"
        # Capture a local reference so the closure doesn't hold self strongly
        abort_ev = self._abort_capture

        def job() -> None:
            try:
                # Second check inside the thread: abort may have been set between
                # dispatch and execution (thread scheduling delay).
                if abort_ev.is_set():
                    return
                self._client.capture_screen(frame_path, timeout=5)
                if not abort_ev.is_set():
                    self._captureFrameReady.emit(
                        QUrl.fromLocalFile(str(frame_path)).toString()
                    )
                    # Also push the frame into the image://sandboxpreview/ provider
                    # so both SandboxLabPage and ScanCenter can use it.
                    try:
                        from ..ui.sandbox_preview_provider import get_preview_provider
                        provider = get_preview_provider()
                        img = QImage(str(frame_path))
                        if not img.isNull():
                            img = img.convertToFormat(QImage.Format.Format_ARGB32)
                            data = bytes(img.bits())
                            provider.update_frame(data, img.width(), img.height())
                    except Exception:
                        pass  # Non-critical: file:/// fallback still works
            except Exception as exc:
                if not abort_ev.is_set():
                    self._captureFailure.emit(str(exc))
            finally:
                self._capture_in_flight = False

        threading.Thread(target=job, daemon=True).start()

    def _apply_capture_frame(self, frame_url: str) -> None:
        self._live_frame_path = frame_url
        self.liveFramePath.emit(frame_url)
        if self._frames_dir is not None:
            self._frames_saved = True
            self.evidenceChanged.emit()
        if self._capture_for_run and frame_url not in self._replay_frames:
            self._replay_frames.append(frame_url)
            self.replayFramesModelChanged.emit()
            if self._replay_index < 0:
                self._replay_index = 0
                self.replayIndexChanged.emit()
            if self._replay_mode:
                self.setReplayIndex(len(self._replay_frames) - 1)

    def _apply_capture_failure(self, error_text: str) -> None:
        now = time.time()
        if now - self._last_capture_failure_at < 8:
            return
        self._last_capture_failure_at = now
        self._append_step("Failed", f"Capture failed (non-fatal): {error_text}")
        self._set_live_state("Capture failed (non-fatal)")

    def _on_worker_progress(self, value: int) -> None:
        self._progress_value = value
        self.progress.emit(value)

    def _on_worker_step(self, entry: dict[str, str]) -> None:
        message = str(entry.get("message", ""))
        self._step_text = message
        self.step.emit(message)
        self._append_step(
            str(entry.get("status", "Running")), message, str(entry.get("time", ""))
        )

    def _on_worker_vm_running(self, running: bool) -> None:
        self._vm_running = bool(running)
        self._sync_capture_state()

    def _on_worker_finished(self, payload: dict[str, Any]) -> None:
        self._busy = False
        self.isBusy.emit(False)
        self._vm_running = False
        self._capture_for_run = False
        self._sync_capture_state()

        # Diagnostics path: delegate and return early
        if payload.get("operation") == "diagnostics":
            cb = getattr(self, "_pending_diag_finish", None)
            if cb:
                del self._pending_diag_finish
                cb(payload)
            return

        operation = payload.get("operation")
        if operation in {"start", "stop", "reset"}:
            self._set_status(f"VMware action completed: {operation}")
            return

        self._last_report_path = str(payload.get("report_path", ""))
        self._proof_gif_path = str(payload.get("proof_gif", ""))
        self._proof_mp4_path = str(payload.get("proof_mp4", ""))
        self._report_saved = bool(
            self._last_report_path and Path(self._last_report_path).exists()
        )
        self._frames_saved = bool(
            payload.get("frames_saved", False) or self._replay_frames
        )
        self._verdict_computed = bool(payload.get("verdict"))
        self._media_exported = bool(payload.get("media_exported", False))
        self.evidenceChanged.emit()
        self.proofMediaChanged.emit()

        if payload.get("error"):
            self._set_last_error(str(payload.get("error")))
        elif payload.get("mp4_note"):
            self._set_last_error(str(payload.get("mp4_note")))

        # Surface guest-side error detail as a dedicated property
        _gec = str(payload.get("guest_error_content", "")).strip()
        if _gec != self._guest_error_content:
            self._guest_error_content = _gec
            self.guestErrorContentChanged.emit()

        report_json = (
            payload.get("report_json")
            if isinstance(payload.get("report_json"), dict)
            else None
        )
        self._result_summary = {
            "verdict": payload.get("verdict", "Inconclusive"),
            "score": int(payload.get("score", 0) or 0),
            "summary": payload.get("summary", ""),
            "highlights": list(payload.get("highlights", [])),
            "report_path": self._last_report_path,
            "run_dir_path": payload.get("run_dir_path", str(self._last_run_folder)),
            "guest_error_content": payload.get("guest_error_content", ""),
            "proof_gif": self._proof_gif_path,
            "proof_mp4": self._proof_mp4_path,
            "report_json": report_json,
            "sentinel_report": payload.get("sentinel_report"),
            "sentinel_report_path": payload.get("sentinel_report_path", ""),
            "error": payload.get("error", ""),
        }
        self.resultSummaryChanged.emit()

        self._verdict_summary = str(payload.get("summary", payload.get("verdict", "")))
        self.verdictSummaryChanged.emit()
        self._set_status(self._verdict_summary or "Sandbox run completed.")

        if self._frames_dir is not None and self._frames_dir.exists():
            frame_urls = [
                QUrl.fromLocalFile(str(frame)).toString()
                for frame in sorted(self._frames_dir.glob("frame_*.png"))
            ]
            if frame_urls:
                self._replay_frames = frame_urls
                self.replayFramesModelChanged.emit()

        if self._replay_frames:
            self.setReplayIndex(len(self._replay_frames) - 1)

        # Merge UI runner key frames (captured inside the guest) into replay model
        _ui_key_frames = list(payload.get("ui_key_frames") or [])
        if _ui_key_frames:
            for _kf in _ui_key_frames:
                _kf_url = QUrl.fromLocalFile(_kf).toString()
                if _kf_url not in self._replay_frames:
                    self._replay_frames.append(_kf_url)
            self.replayFramesModelChanged.emit()
            # Seek to first UI frame so user immediately sees the automation
            self.setReplayIndex(len(self._replay_frames) - len(_ui_key_frames))
        # Reset automation-visible flag (should already be False from worker)
        if self._automation_visible:
            self._automation_visible = False
            self.automationVisibleChanged.emit()

        self._last_prompt = self._build_prompt()
        self._write_meta()
        self._run_dir = None
        self._frames_dir = None

    def _on_worker_failed(self, error_text: str) -> None:
        self._busy = False
        self.isBusy.emit(False)
        self._vm_running = False
        self._capture_for_run = False
        self._sync_capture_state()
        self._append_step("Failed", error_text)
        self._set_last_error(error_text)
        # Try to read guest_error.txt from the run folder if it was already copied
        _gec = ""
        if self._last_run_folder:
            for _art in ("guest_error.txt", "guest_transcript.txt"):
                _ap = Path(self._last_run_folder) / _art
                if _ap.exists():
                    try:
                        _lines = _ap.read_text(
                            encoding="utf-8", errors="replace"
                        ).splitlines()
                        _gec = "\n".join([l for l in _lines if l.strip()][:20])
                    except Exception:
                        pass
                    if _gec.strip():
                        break
        if _gec != self._guest_error_content:
            self._guest_error_content = _gec
            self.guestErrorContentChanged.emit()
        self._set_status(error_text)
        # Populate result summary so QML panels reflect the failure state
        self._result_summary = {
            "verdict": "Failed",
            "score": 0,
            "summary": error_text,
            "highlights": [],
            "report_path": self._last_report_path,
            "run_dir_path": self._last_run_folder,
            "guest_error_content": self._guest_error_content,
            "proof_gif": "",
            "proof_mp4": "",
            "report_json": None,
            "sentinel_report": None,
            "sentinel_report_path": "",
            "error": error_text,
        }
        self.resultSummaryChanged.emit()
        self._verdict_summary = error_text
        self.verdictSummaryChanged.emit()
        self._write_meta()
        self._run_dir = None
        self._frames_dir = None

    def _append_step(
        self, status: str, message: str, step_time: str | None = None
    ) -> None:
        self._steps_model.append(
            {
                "time": step_time or datetime.now().strftime("%H:%M:%S"),
                "status": status,
                "message": message,
            }
        )
        self.stepsModelChanged.emit()

    def _set_status(self, message: str) -> None:
        self._status_text = message
        self.status.emit(message)

    def _set_last_error(self, message: str) -> None:
        self._last_error = message
        self.lastErrorChanged.emit()

    def _set_live_state(self, state: str) -> None:
        self._live_view_state = state
        self.liveViewStateChanged.emit()

    def _reset_evidence(self) -> None:
        self._report_saved = False
        self._frames_saved = False
        self._verdict_computed = False
        self._media_exported = False
        self.evidenceChanged.emit()

    def _open_in_explorer(self, path: Path) -> None:
        try:
            if path.is_file():
                subprocess.Popen(["explorer", f"/select,{path}"])
            else:
                subprocess.Popen(["explorer", str(path)])
        except Exception as exc:
            self._set_last_error(f"Could not open Explorer: {exc}")

    @staticmethod
    def _guest_path(base_path: str, name: str) -> str:
        return base_path.rstrip("\\/") + "\\" + name
