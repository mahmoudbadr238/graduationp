"""QObject controller for the VMware Sandbox Lab UI."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, Property, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication

from .config import SandboxConfig, load_sandbox_config
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

    def __init__(self, task: Callable[["VmwareTaskWorker"], dict[str, Any]]):
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
    availabilityChanged = Signal()
    guestReadyChanged = Signal()
    evidenceChanged = Signal()
    proofMediaChanged = Signal()
    resultSummaryChanged = Signal()
    liveViewStateChanged = Signal()

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

    @Property("QVariantList", notify=stepsModelChanged)
    def stepsModel(self) -> list[dict[str, str]]:
        return list(self._steps_model)

    @Property("QVariantList", notify=stepsModelChanged)
    def steps(self) -> list[str]:
        return [f"{item['time']} [{item['status']}] {item['message']}" for item in self._steps_model]

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

    @Slot(str, int, bool, bool)
    def runFileInSandbox(self, host_file_path: str, monitor_seconds: int = 30, disable_network: bool = False, kill_on_finish: bool = True) -> None:
        host_path = Path(host_file_path)
        if not host_file_path or not host_path.exists() or not host_path.is_file():
            self._set_last_error(f"Selected file was not found: {host_file_path}")
            return
        self._prepare_run_context("file", str(host_path), monitor_seconds, disable_network, kill_on_finish)
        self._start_task("Running file detonation", self._task_run_file)

    @Slot(str, int, bool, bool)
    def runFile(self, host_file_path: str, monitor_seconds: int = 30, disable_network: bool = False, kill_on_finish: bool = True) -> None:
        self.runFileInSandbox(host_file_path, monitor_seconds, disable_network, kill_on_finish)

    @Slot(str)
    def runUrlInSandbox(self, url: str) -> None:
        cleaned = url.strip()
        if not cleaned:
            self._set_last_error("Enter a URL before starting URL detonation.")
            return
        self._prepare_run_context("url", cleaned, 45, True, True)
        self._start_task("Running URL detonation", self._task_run_url)

    @Slot(str, int, bool, bool)
    def runUrl(self, url: str, monitor_seconds: int = 45, disable_network: bool = True, kill_on_finish: bool = True) -> None:
        cleaned = url.strip()
        if not cleaned:
            self._set_last_error("Enter a URL before starting URL detonation.")
            return
        self._prepare_run_context("url", cleaned, monitor_seconds, disable_network, kill_on_finish)
        self._start_task("Running URL detonation", self._task_run_url)

    @Slot()
    def openLastRunFolder(self) -> None:
        if not self._last_run_folder:
            self._set_last_error("No completed Sandbox Lab run folder is available yet.")
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
            messages.append("Guest credentials missing; set SANDBOX_GUEST_USER and SANDBOX_GUEST_PASS.")
        self._availability_message = " ".join(messages)
        self.availabilityChanged.emit()
        self.guestReadyChanged.emit()
        self._set_status(self._availability_message)

    def _prepare_run_context(self, mode: str, target: str, monitor_seconds: int, disable_network: bool, kill_on_finish: bool) -> None:
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
            "killOnFinish": bool(kill_on_finish),
        }
        self._run_started_at = datetime.now().isoformat()
        self._capture_index = 0
        self._capture_for_run = True
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
        self._reset_evidence()

    def _start_task(self, label: str, task: Callable[[VmwareTaskWorker], dict[str, Any]]) -> None:
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
        worker.emit_step("Running", f"Reverting to snapshot '{self._config.snapshot_name}'")
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
        worker.emit_step("Running", f"Static analysis: hashing, PE, YARA, IOC extraction…")
        try:
            from ..scanning.static_scanner import StaticScanner
            scanner = StaticScanner()
            result = scanner.scan_file(str(sample_path), run_clamav=False)
            raw: dict[str, Any] = result.to_dict() if hasattr(result, "to_dict") else (
                asdict(result) if is_dataclass(result) else {}
            )
            static_info = raw
            sha_short   = str(raw.get("sha256", ""))[:16]
            yara_count  = len(raw.get("yara_matches") or [])
            entropy_val = float((raw.get("static") or {}).get("entropy") or 0)
            iocs_dict   = raw.get("iocs") or {}
            ioc_count   = sum(
                len(v) if isinstance(v, list) else (1 if v else 0)
                for v in (iocs_dict.values() if isinstance(iocs_dict, dict) else [])
            )
            pe_sus      = bool((raw.get("pe_analysis") or {}).get("suspicious_imports"))
            parts = [f"SHA256={sha_short}…", f"entropy={entropy_val:.2f}", f"YARA={yara_count}"]
            if pe_sus:
                parts.append("suspicious PE imports")
            if ioc_count:
                parts.append(f"{ioc_count} IOCs")
            worker.emit_step("OK", "Static: " + "  |  ".join(parts))
        except Exception as exc:
            worker.emit_step("Failed", f"Static analysis error (continuing): {exc}")

        guest_path = self._guest_path(self._config.guest_in_dir, sample_path.name)
        args = [
            "-ExecutionPolicy", "Bypass",
            "-File", self._config.guest_runner_path,
            "-SamplePath", guest_path,
            "-MonitorSeconds", str(self._run_options["monitorSeconds"]),
        ]
        if self._run_options["disableNetwork"]:
            args.append("-DisableNetwork")
        if self._run_options["killOnFinish"]:
            args.append("-KillOnFinish")

        payload = self._task_run_pipeline(worker, sample_path, guest_path, args)

        # ── Merge static + behavioral for richer verdict ─────────────────
        if static_info:
            payload["static_analysis"] = static_info
            yara_count = len(static_info.get("yara_matches") or [])
            iocs_dict  = static_info.get("iocs") or {}
            ioc_count  = sum(
                len(v) if isinstance(v, list) else (1 if v else 0)
                for v in (iocs_dict.values() if isinstance(iocs_dict, dict) else [])
            )
            base_score = int(payload.get("score") or 0)
            boost      = min(30, yara_count * 10 + ioc_count * 3)
            if boost:
                payload["score"] = min(100, base_score + boost)
                highlights = list(payload.get("highlights") or [])
                if yara_count:
                    highlights.insert(0, f"YARA: {yara_count} rule(s) matched on host static scan.")
                if ioc_count:
                    highlights.insert(0, f"IOCs: {ioc_count} indicator(s) extracted from host file.")
                payload["highlights"] = highlights
            # Escalate verdict if static says Malicious and behavioral was lower
            if static_info.get("verdict") == "Malicious" and payload.get("verdict") not in ("Malicious",):
                payload["verdict"] = "Malicious"
                payload["summary"] = f"[Static: Malicious] {payload.get('summary', '')}"

        return payload

    def _task_run_url(self, worker: VmwareTaskWorker) -> dict[str, Any]:
        args = [
            "-ExecutionPolicy", "Bypass",
            "-File", self._config.guest_open_url_path,
            "-Url", self._run_target,
            "-MonitorSeconds", str(self._run_options["monitorSeconds"]),
        ]
        if self._run_options["disableNetwork"]:
            args.append("-DisableNetwork")
        if self._run_options["killOnFinish"]:
            args.append("-KillOnFinish")
        return self._task_run_pipeline(worker, None, None, args)

    def _task_run_pipeline(self, worker: VmwareTaskWorker, sample_path: Path | None, guest_sample_path: str | None, guest_args: list[str]) -> dict[str, Any]:
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
            worker.emit_step("Running", "Starting VM in nogui mode")
            self._client.start(nogui=True)
            worker.set_vm_running(True)
            worker.emit_step("OK", "VM started")

            worker.emit_progress(25)
            worker.emit_step("Running", "Waiting for guest OS to become responsive")
            time.sleep(10)
            worker.emit_step("OK", "Guest OS is ready")

            # ── Create sandbox directories in guest ───────────────────────
            worker.emit_progress(30)
            worker.emit_step("Running", "Preparing C:\\Sandbox directories in guest")
            try:
                self._client.run_program_in_guest(
                    _GUEST_POWERSHELL,
                    ["-ExecutionPolicy", "Bypass", "-Command",
                     "New-Item -ItemType Directory -Force -Path 'C:\\Sandbox\\in','C:\\Sandbox\\out' | Out-Null"],
                    wait=True,
                    timeout=60,
                )
                worker.emit_step("OK", "Guest sandbox directories ready")
            except Exception as _mkdir_exc:
                worker.emit_step("Failed", f"Guest mkdir failed (continuing): {_mkdir_exc}")

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
                worker.emit_step("Running", f"Copying {sample_path.name} into guest")
                self._client.copy_file_from_host_to_guest(sample_path, guest_sample_path)
                worker.emit_step("OK", f"Copied {sample_path.name} into guest")

            worker.emit_progress(50)
            worker.emit_step("Running", "Launching guest PowerShell automation")
            self._client.run_program_in_guest(
                _GUEST_POWERSHELL,
                guest_args,
                wait=True,
                timeout=max(120, int(self._run_options["monitorSeconds"]) + 180),
            )
            worker.emit_step("OK", "Guest automation finished")

            worker.emit_progress(70)
            worker.emit_step("Running", "Polling for guest report.json")
            self._poll_report_from_guest(report_path)
            worker.emit_step("OK", "report.json copied to host")

            worker.emit_progress(82)
        except Exception as exc:
            error_text = str(exc)
            worker.emit_step("Failed", error_text)
        finally:
            # Stop capture BEFORE powering off so screenshot timer doesn't fire on a dead VM
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
        export_result = self._export_media(self._frames_dir, self._run_dir, worker)
        payload.update(export_result)

        if report_path.exists():
            try:
                report_json = load_report(report_path)
                scoring = score_report(report_json)
                payload.update(scoring)
                payload["report_json"] = report_json
                payload["success"] = not bool(error_text)
            except Exception as exc:
                parse_text = f"Failed to parse report.json: {exc}"
                error_text = f"{error_text} | {parse_text}" if error_text else parse_text
                worker.emit_step("Failed", parse_text)
                payload.update({"verdict": "Inconclusive", "score": 0, "summary": parse_text, "highlights": []})
        else:
            if not error_text:
                error_text = "Guest report.json was not produced before timeout."
            payload.update({
                "verdict": "Inconclusive",
                "score": 0,
                "summary": error_text,
                "highlights": [],
            })

        payload["error"] = error_text
        worker.emit_progress(100)
        if not error_text:
            worker.emit_step("OK", "Automation Completed ✅")
        return payload

    def _poll_report_from_guest(self, host_report_path: Path) -> None:
        guest_report_path = self._guest_path(self._config.guest_out_dir, "report.json")
        deadline = time.time() + max(15, self._config.report_poll_seconds)
        last_error = ""
        while time.time() < deadline:
            try:
                if host_report_path.exists():
                    host_report_path.unlink()
                self._client.copy_file_from_guest_to_host(guest_report_path, host_report_path, timeout=30)
                if host_report_path.exists() and host_report_path.stat().st_size > 0:
                    return
            except Exception as exc:
                last_error = str(exc)
            time.sleep(2)
        if last_error:
            raise VmrunError(f"Timed out waiting for report.json. Last vmrun error: {last_error}")
        raise VmrunError("Timed out waiting for report.json from the guest sandbox.")

    def _export_media(self, frames_dir: Path, run_dir: Path, worker: VmwareTaskWorker) -> dict[str, Any]:
        frames = sorted(frames_dir.glob("frame_*.png"))
        if not frames:
            return {"proof_gif": "", "proof_mp4": "", "frames_saved": False, "media_exported": False, "mp4_note": "No frames were captured."}

        gif_path = run_dir / "proof.gif"
        mp4_path = run_dir / "proof.mp4"
        gif_saved = False
        mp4_saved = False
        mp4_note = ""

        try:
            import imageio.v2 as imageio

            images = [imageio.imread(frame) for frame in frames]
            imageio.mimsave(gif_path, images, duration=max(0.4, self._config.capture_interval_ms / 1000.0))
            gif_saved = gif_path.exists()
            if gif_saved:
                worker.emit_step("OK", f"Exported {gif_path.name}")
        except ImportError:
            worker.emit_step("Failed", "GIF export skipped: imageio is not installed")
        except Exception as exc:
            worker.emit_step("Failed", f"GIF export failed: {exc}")

        ffmpeg_path = shutil.which("ffmpeg")
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
        should_capture = self._vm_running and (self._capture_for_run or self._live_view_enabled)
        if should_capture and not self._capture_timer.isActive():
            self._capture_timer.start()
        elif not should_capture and self._capture_timer.isActive():
            self._capture_timer.stop()

        if not self._vm_running:
            self._set_live_state("VM not running")
        elif self._live_view_enabled:
            self._set_live_state("Capturing...")
        else:
            self._set_live_state("Paused")

    def _capture_live_frame(self) -> None:
        if self._capture_in_flight or not self._vm_running:
            return
        frame_dir = self._frames_dir if self._capture_for_run and self._frames_dir is not None else self._config.host_frames_dir
        frame_dir.mkdir(parents=True, exist_ok=True)
        self._capture_in_flight = True
        self._capture_index += 1
        frame_path = frame_dir / f"frame_{self._capture_index:06d}.png"

        def job() -> None:
            try:
                self._client.capture_screen(frame_path, timeout=20)
                self._captureFrameReady.emit(QUrl.fromLocalFile(str(frame_path)).toString())
            except Exception as exc:
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
        self._append_step(str(entry.get("status", "Running")), message, str(entry.get("time", "")))

    def _on_worker_vm_running(self, running: bool) -> None:
        self._vm_running = bool(running)
        self._sync_capture_state()

    def _on_worker_finished(self, payload: dict[str, Any]) -> None:
        self._busy = False
        self.isBusy.emit(False)
        self._vm_running = False
        self._capture_for_run = False
        self._sync_capture_state()

        operation = payload.get("operation")
        if operation in {"start", "stop", "reset"}:
            self._set_status(f"VMware action completed: {operation}")
            return

        self._last_report_path = str(payload.get("report_path", ""))
        self._proof_gif_path = str(payload.get("proof_gif", ""))
        self._proof_mp4_path = str(payload.get("proof_mp4", ""))
        self._report_saved = bool(self._last_report_path and Path(self._last_report_path).exists())
        self._frames_saved = bool(payload.get("frames_saved", False) or self._replay_frames)
        self._verdict_computed = bool(payload.get("verdict"))
        self._media_exported = bool(payload.get("media_exported", False))
        self.evidenceChanged.emit()
        self.proofMediaChanged.emit()

        if payload.get("error"):
            self._set_last_error(str(payload.get("error")))
        elif payload.get("mp4_note"):
            self._set_last_error(str(payload.get("mp4_note")))

        report_json = payload.get("report_json") if isinstance(payload.get("report_json"), dict) else None
        self._result_summary = {
            "verdict": payload.get("verdict", "Inconclusive"),
            "score": int(payload.get("score", 0) or 0),
            "summary": payload.get("summary", ""),
            "highlights": list(payload.get("highlights", [])),
            "report_path": self._last_report_path,
            "proof_gif": self._proof_gif_path,
            "proof_mp4": self._proof_mp4_path,
            "report_json": report_json,
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
        self._set_status(error_text)
        self._write_meta()
        self._run_dir = None
        self._frames_dir = None

    def _append_step(self, status: str, message: str, step_time: str | None = None) -> None:
        self._steps_model.append({
            "time": step_time or datetime.now().strftime("%H:%M:%S"),
            "status": status,
            "message": message,
        })
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
