"""Dynamic analysis orchestrator.

Drives the 14-step VMware sandbox pipeline for file analysis.

Usage (from a background thread):
    from app.sandbox.analyzer_dynamic import run_file_analysis

    result = run_file_analysis(
        file_path="/path/to/sample.exe",
        step_cb=lambda status, msg: ...,
        progress_cb=lambda pct: ...,
        cancel_event=threading.Event(),
    )
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from .analyzer_static import analyze_file_full
from .artifacts import parse_artifacts
from .job_schema import SandboxJobResult
from .report_builder import build_report
from .vmware_runner import VMwareRunner, load_runner_config

logger = logging.getLogger(__name__)


def _elapsed(t0: float) -> str:
    """Return elapsed seconds since *t0* in a terse form: e.g. '3.4s'."""
    return f"{time.monotonic() - t0:.1f}s"


# ── Guest paths (persistent-agent architecture) ───────────────────────────────
_GUEST_PS = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
_GUEST_AGENT_DIR = r"C:\Sandbox\agent"
_GUEST_JOB_FILE = r"C:\Sandbox\job.json"
_GUEST_OUT_DIR = r"C:\Sandbox\out"
_GUEST_DONE_FLAG = r"C:\Sandbox\out\done.flag"
_GUEST_SUMMARY = r"C:\Sandbox\out\summary.json"
_TASK_NAME = "SentinelSandboxAgent"

# ── Host paths to agent scripts (in tools/sandbox_agent/) ─────────────────────
_TOOLS_DIR = Path(__file__).parent.parent.parent / "tools" / "sandbox_agent"
_AGENT_PS1 = _TOOLS_DIR / "agent.ps1"  # legacy fallback
_AGENT_WRAPPER = _TOOLS_DIR / "run_ui_wrapper.ps1"  # ONLOGON interactive runner
_AGENT_AHK_NEW = _TOOLS_DIR / "run_ui.ahk"  # visible AHK interaction
_AGENT_AHK = _TOOLS_DIR / "ui.ahk"  # legacy
_INSTALL_PS1 = _TOOLS_DIR / "install_agent.ps1"

_GUEST_IN_DIR = r"C:\Sandbox\in"  # simple sample drop directory in guest

# ── Artifact filenames written by the guest agent ─────────────────────────────
_ARTIFACT_FILES = [
    "summary.json",
    "steps.jsonl",
    "processes_before.json",
    "processes_after.json",
    "connections.txt",
    "new_files.json",
    "errors.txt",
]

_CAPTURE_INTERVAL = 0.7  # seconds between captureScreen calls (700 ms)


class JobState:
    """Job state constants for sandboxStateChanged signal."""

    IDLE = "IDLE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    COLLECTING = "COLLECTING_ARTIFACTS"
    CLEANUP = "CLEANUP"
    FINISHED = "FINISHED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


def _host_artifacts_dir() -> Path:
    """Resolve the host-side artifacts output directory."""
    from .vmware_runner import load_runner_config

    _, extras = load_runner_config()
    raw = extras.get("host_artifacts_dir", "") or ""
    p = Path(raw) if raw else Path("data") / "artifacts"
    p.mkdir(parents=True, exist_ok=True)
    return p


def run_file_analysis(
    file_path: str,
    *,
    monitor_seconds: int = 30,
    disable_network: bool = False,
    step_cb: Callable[[str, str], None] | None = None,
    progress_cb: Callable[[int], None] | None = None,
    cancel_event: threading.Event | None = None,
    screenshot_cb: Callable[[str], None] | None = None,
    state_cb: Callable[[str], None] | None = None,
) -> SandboxJobResult:
    """
    Run the full 14-step VMware sandbox analysis pipeline for a file sample.

    Steps:
      1  Validate input
      2  Static analysis (hashes, filetype, strings, Defender)
      3  Validate vmrun + VMX
      4  Revert to clean snapshot
      5  Start VM
      6  Ensure guest ready + auth OK
      7  Create guest job folder
      8  Copy sample to guest
      9  Deploy guest agent
     10  Collect monitoring baseline
     11  Execute sample
     12  Collect post-execution state
     13  Fetch artifacts to host
     14  Parse report and compute verdict

    Args:
        file_path: Absolute path to the suspicious file.
        monitor_seconds: How long (in seconds) to monitor execution.
        disable_network: Whether to disable guest network before detonation.
        step_cb: Callback(status, message) – "Running"/"OK"/"Failed".
        progress_cb: Callback(0–100) for progress bar.
        cancel_event: If set, pipeline aborts cleanly when the event fires.

    Returns:
        SandboxJobResult with all fields populated.
    """
    _step = step_cb or (lambda s, m: None)
    _progress = progress_cb or (lambda p: None)
    _cancel = cancel_event or threading.Event()
    _state = state_cb or (lambda s: None)

    job_t0 = time.monotonic()  # wall-clock reference for all milestone lines

    job_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_") + str(uuid.uuid4())[:8]
    started_at = datetime.now().isoformat()

    # Host job directory for artifacts
    artifacts_root = _host_artifacts_dir()
    host_job_dir = artifacts_root / job_id
    host_job_dir.mkdir(parents=True, exist_ok=True)

    result: SandboxJobResult = {
        "job_id": job_id,
        "sample_path": file_path,
        "sample_name": Path(file_path).name,
        "run_dir": str(host_job_dir),
        "started_at": started_at,
        "success": False,
        "error": "",
        "verdict": "Inconclusive",
        "score": 0,
        "summary": "Analysis did not complete.",
        "highlights": [],
        "steps": [],
    }

    # Save step log to disk as we go
    steps_log_path = host_job_dir / "host_steps.jsonl"

    def emit_step(status: str, msg: str) -> None:
        """Emit to callback AND write to local step log."""
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "status": status,
            "message": msg,
        }
        _step(status, msg)
        try:
            with steps_log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    def _aborted() -> bool:
        return _cancel.is_set()

    def _milestone(tag: str, detail: str = "") -> None:
        """Emit one MILESTONE log line with elapsed time since job start."""
        body = f"MILESTONE +{_elapsed(job_t0)} {tag}" + (
            f" — {detail}" if detail else ""
        )
        logger.info(body)
        emit_step("OK", body)

    config, extras = load_runner_config()
    if config is None:
        raise ValueError(
            "VMware config not initialized — check vmware.json / .env settings"
        )
    runner = VMwareRunner(config=config, extras=extras, step_cb=emit_step)

    try:
        # ── Step 1: Validate input ───────────────────────────────────────────
        _progress(2)
        emit_step("Running", f"[1/14] Validating input: {Path(file_path).name}")
        sample = Path(file_path)
        if not sample.exists():
            raise FileNotFoundError(f"Sample not found: {file_path}")
        if not sample.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
        if sample.stat().st_size == 0:
            raise ValueError("Sample file is empty.")
        emit_step("OK", f"Input valid: {sample.name} ({sample.stat().st_size:,} bytes)")
        if _aborted():
            raise InterruptedError("Cancelled after step 1.")

        # ── Step 2: Static analysis (all engines) ─────────────────────────────
        _progress(5)
        _state(JobState.RUNNING)
        emit_step(
            "Running",
            "[2/14] Running static analysis (hashes, entropy, strings, Defender, YARA, ClamAV)",
        )
        static_result = {}
        engine_results: list = []
        try:
            static_result, engine_results = analyze_file_full(
                sample,
                extract_strings=True,
            )
            parts = [
                f"SHA256={str(static_result.get('sha256', ''))[:16]}…",
                f"entropy={static_result.get('entropy', 0):.2f}",
                f"type={static_result.get('file_type', 'unknown')[:30]}",
            ]
            det_engines = [
                e
                for e in engine_results
                if e.get("status") in ("malicious", "suspicious")
            ]
            if det_engines:
                parts.append(
                    "DETECTIONS: "
                    + ", ".join(f"{e['name']}:{e['status']}" for e in det_engines)
                )
            emit_step("OK", "Static: " + "  |  ".join(parts))
            for eng in engine_results:
                status_sym = {
                    "malicious": "⚠️ MALICIOUS",
                    "suspicious": "⚠️ suspicious",
                    "clean": "✓ clean",
                    "not_installed": "– not installed",
                    "error": "! error",
                }.get(eng["status"], eng["status"])
                emit_step(
                    "OK",
                    f"  Engine {eng['name']}: {status_sym} — {eng.get('details', '')[:60]}",
                )
        except Exception as exc:
            emit_step("Failed", f"Static analysis error (continuing): {exc}")
            logger.exception("Static analysis error")
        if _aborted():
            raise InterruptedError("Cancelled after step 2.")

        # ── Step 3: Validate vmrun + VMX ─────────────────────────────────────
        _progress(8)
        emit_step("Running", "[3/14] Checking vmrun.exe and VMX path")
        config.ensure_directories()
        runner._client.validate_host_requirements()
        runner._client.ensure_guest_credentials()
        emit_step("OK", f"vmrun: {config.vmrun_path}")
        emit_step("OK", f"VMX: {config.vmx_path}")
        if _aborted():
            raise InterruptedError("Cancelled after step 3.")

        # ── Check interactive agent script files exist on host ────────────────
        if not _AGENT_WRAPPER.exists():
            raise FileNotFoundError(
                f"ONLOGON runner not found: {_AGENT_WRAPPER}\n"
                "Ensure tools/sandbox_agent/run_ui_wrapper.ps1 is present."
            )
        if not _INSTALL_PS1.exists():
            raise FileNotFoundError(
                f"install_agent.ps1 not found: {_INSTALL_PS1}\n"
                "Ensure tools/sandbox_agent/install_agent.ps1 is present."
            )

        # ── Step 4: Revert to clean snapshot ─────────────────────────────────
        _progress(12)
        emit_step(
            "Running", f"[4/14] Reverting VM to clean snapshot '{config.snapshot_name}'"
        )
        runner.revert_snapshot(timeout=180)
        if _aborted():
            raise InterruptedError("Cancelled after step 4.")

        # ── Step 5: Start VM ──────────────────────────────────────────────────
        _progress(18)
        emit_step("Running", "[5/14] Starting VM in headless mode")
        runner.start_vm(nogui=True, timeout=180)
        if _aborted():
            raise InterruptedError("Cancelled after step 5.")

        # ── Step 6: Ensure guest ready ────────────────────────────────────────
        _progress(28)
        emit_step("Running", "[6/14] Waiting for guest OS + VMware Tools + auth")
        runner.ensure_guest_ready(retries=12, retry_delay=5.0)
        _milestone("tools_ready")
        if _aborted():
            raise InterruptedError("Cancelled after step 6.")

        # ── Step 7: Create guest directories ──────────────────────────────────
        _progress(35)
        emit_step("Running", "[7/14] Ensuring guest sandbox directories exist")
        for gdir in (
            _GUEST_IN_DIR,
            _GUEST_AGENT_DIR,
            _GUEST_OUT_DIR,
            _GUEST_OUT_DIR + r"\shots",
        ):
            runner.run_in_guest(
                _GUEST_PS,
                [
                    "-NoProfile",
                    "-NonI",
                    "-Command",
                    f"New-Item -ItemType Directory -Force -Path '{gdir}' | Out-Null",
                ],
                timeout=30,
            )
        emit_step("OK", "[7/14] Guest directories ready")
        _milestone(
            "guest_mkdir_done",
            f"dirs: {_GUEST_IN_DIR}, {_GUEST_AGENT_DIR}, {_GUEST_OUT_DIR}",
        )
        if _aborted():
            raise InterruptedError("Cancelled after step 7.")

        # ── Step 8: Copy sample to C:\Sandbox\in\ ─────────────────────────────
        _progress(42)
        guest_in_sample = _GUEST_IN_DIR + "\\" + sample.name
        emit_step("Running", f"[8/14] Copying sample to guest: {guest_in_sample}")
        runner.copy_to_guest(sample, guest_in_sample, timeout=120)
        _milestone("copy_sample_done", f"{sample.name} → guest {guest_in_sample}")
        if _aborted():
            raise InterruptedError("Cancelled after step 8.")

        # ── Step 9: Ensure persistent sandbox agent (ONLOGON runner) in guest ─
        _progress(47)
        emit_step(
            "Running",
            "[9/14] Ensuring ONLOGON sandbox agent (run_ui_wrapper.ps1) is deployed",
        )
        runner.ensure_sandbox_agent(
            agent_ps1=_AGENT_WRAPPER,
            ui_ahk=_AGENT_AHK_NEW if _AGENT_AHK_NEW.exists() else None,
            install_ps1=_INSTALL_PS1,
            guest_agent_dir=_GUEST_AGENT_DIR,
            guest_agent_ps1=_GUEST_AGENT_DIR + "\\run_ui_wrapper.ps1",
            timeout=180,
        )
        emit_step(
            "OK",
            f"[9/14] Agent ready | AHK: {_AGENT_AHK_NEW.exists()} | "
            f"Task: {_TASK_NAME} (ONLOGON — fires automatically on VM login)",
        )
        if _aborted():
            raise InterruptedError("Cancelled after step 9.")

        # ── Step 10: Write job.json into guest ────────────────────────────────
        _progress(52)
        job_dict = {
            "job_id": job_id,
            "sample_path": guest_in_sample,  # simple C:\Sandbox\in\<name> path
            "monitor_seconds": int(monitor_seconds),
            "disable_network": disable_network,
        }
        emit_step(
            "Running",
            f"[10/14] Writing job manifest → guest {_GUEST_JOB_FILE}\n"
            f"  sample={Path(file_path).name}  monitor={monitor_seconds}s  "
            f"disable_network={disable_network}",
        )
        runner.write_job_file(job_dict, guest_dest=_GUEST_JOB_FILE, timeout=30)
        emit_step("OK", "[10/14] job.json deposited for agent")
        if _aborted():
            raise InterruptedError("Cancelled after step 10.")

        # ── Step 11: ONLOGON task fires automatically — no explicit /Run ────
        _progress(56)
        emit_step(
            "OK",
            f"[11/14] '{_TASK_NAME}' is registered as ONLOGON — "
            "will fire automatically on VM login (triggered by snapshot revert+start).\n"
            "  job.json is now in guest; wrapper will pick it up within 5 minutes.",
        )
        _milestone(
            "guest_run_started",
            "job.json deposited; ONLOGON task will fire automatically",
        )
        if _aborted():
            raise InterruptedError("Cancelled after step 11.")

        # ── Step 12: Capture thread + done.flag poll ──────────────────────────
        _progress(60)
        # Cap the agent wait: no longer than min(monitor_seconds+180, 300) to avoid
        # the pipeline hanging indefinitely when the ONLOGON task never fires.
        agent_timeout = min(int(monitor_seconds) + 180, 300)
        emit_step(
            "Running",
            f"[12/14] Monitoring — captureScreen every {_CAPTURE_INTERVAL:.1f}s, "
            f"waiting for {_GUEST_DONE_FLAG} (timeout {agent_timeout}s)",
        )
        _milestone("wait_for_summary_started", f"deadline={agent_timeout}s")

        shots_dir = host_job_dir / "live_shots"
        shots_dir.mkdir(parents=True, exist_ok=True)

        # Shared state for capture thread
        _capture_stop = threading.Event()
        shot_counter_lock = threading.Lock()
        shot_counter_box = [0]  # mutable reference

        def _capture_loop() -> None:
            while not _capture_stop.is_set():
                with shot_counter_lock:
                    idx = shot_counter_box[0]
                shot_path = shots_dir / f"shot_{idx:04d}.png"
                try:
                    runner._client.capture_screen(shot_path, timeout=10)
                    if shot_path.exists() and shot_path.stat().st_size > 0:
                        with shot_counter_lock:
                            shot_counter_box[0] += 1
                        if screenshot_cb:
                            screenshot_cb(str(shot_path))
                except Exception as cap_exc:
                    logger.debug("captureScreen error (non-fatal): %s", cap_exc)
                _capture_stop.wait(timeout=_CAPTURE_INTERVAL)

        capture_thread = threading.Thread(
            target=_capture_loop, name="sandbox-capture", daemon=True
        )
        capture_thread.start()

        deadline = time.time() + agent_timeout
        agent_done = False
        local_done_flag = host_job_dir / "done.flag"

        try:
            while time.time() < deadline:
                if _aborted():
                    break
                try:
                    runner.copy_from_guest(
                        _GUEST_DONE_FLAG,
                        local_done_flag,
                        timeout=8,
                        skip_missing=True,
                    )
                    if local_done_flag.exists():
                        with shot_counter_lock:
                            n_shots = shot_counter_box[0]
                        agent_done = True
                        _milestone(
                            "guest_run_finished",
                            f"done.flag received; {n_shots} screenshots captured",
                        )
                        emit_step(
                            "OK",
                            f"[12/14] Agent completed (done.flag received; "
                            f"{n_shots} screenshots captured)",
                        )
                        break
                except Exception:
                    pass
                remaining = int(deadline - time.time())
                if remaining % 30 == 0 and remaining > 0:
                    with shot_counter_lock:
                        n_shots = shot_counter_box[0]
                    emit_step(
                        "Running",
                        f"[12/14] Waiting — {remaining}s left, {n_shots} screenshots",
                    )
                time.sleep(2)
        finally:
            # Stop capture BEFORE any VM power-off
            _capture_stop.set()
            capture_thread.join(timeout=5)

        if not agent_done:
            emit_step(
                "Running",
                "[12/14] done.flag not received within timeout — "
                "continuing with partial artifacts",
            )
        _milestone("wait_for_summary_finished", f"found={agent_done}")

        _progress(75)
        if _aborted():
            raise InterruptedError("Cancelled after step 12.")

        # ── Step 13: Fetch artifacts from C:\Sandbox\out\ to host ────────────
        _progress(80)
        emit_step("Running", f"[13/14] Fetching artifacts from guest {_GUEST_OUT_DIR}")

        for artifact in _ARTIFACT_FILES:
            guest_artifact = _GUEST_OUT_DIR + "\\" + artifact
            host_artifact = host_job_dir / artifact
            runner.copy_from_guest(
                guest_artifact,
                host_artifact,
                timeout=60,
                skip_missing=True,
            )

        # Fetch in-guest screenshots written by agent (C:\Sandbox\out\shots\)
        host_guest_shots = host_job_dir / "guest_shots"
        host_guest_shots.mkdir(parents=True, exist_ok=True)
        fetched_shots = 0
        for shot_idx in range(1, 201):  # up to 200 guest-side shots
            gp = f"{_GUEST_OUT_DIR}\\shots\\ahk_final_{shot_idx:04d}.png"
            if runner.copy_from_guest(
                gp,
                host_guest_shots / f"ahk_{shot_idx:04d}.png",
                timeout=20,
                skip_missing=True,
            ):
                fetched_shots += 1
            gp2 = f"{_GUEST_OUT_DIR}\\shots\\shot_{shot_idx:04d}.png"
            hp = host_guest_shots / f"shot_{shot_idx:04d}.png"
            ok = runner.copy_from_guest(gp2, hp, timeout=20, skip_missing=True)
            if ok:
                fetched_shots += 1
                if screenshot_cb:
                    screenshot_cb(str(hp))
            elif shot_idx > 1:
                break  # assume no more sequential shots

        if fetched_shots:
            emit_step("OK", f"[13/14] {fetched_shots} in-guest screenshots fetched")
        emit_step("OK", f"[13/14] Artifacts saved to: {host_job_dir}")
        _milestone("copy_artifacts_done", f"dir={host_job_dir.name}")
        if _aborted():
            raise InterruptedError("Cancelled after step 13.")

        # ── Step 13b: Collect artifacts state signal ──────────────────────────────
        _state(JobState.COLLECTING)

        # ── Step 14: Parse report (legacy) + build VirusTotal-style report.json ───
        _progress(90)
        emit_step("Running", "[14/14] Parsing artifacts and computing final report")
        parsed = parse_artifacts(
            host_job_dir,
            job_id=job_id,
            sample_path=str(sample),
            static_result=static_result or None,  # type: ignore[arg-type]
        )
        result.update(parsed)

        # Build the canonical VirusTotal-style report.json
        finished_now = datetime.now().isoformat()
        guest_summary = parsed.get("dynamic") or {}
        try:
            vt_report = build_report(
                job_id=job_id,
                started_at=started_at,
                finished_at=finished_now,
                sample_path=str(sample),
                static_raw=static_result or {},
                engine_results=engine_results,
                guest_summary=guest_summary if guest_summary else None,
                host_job_dir=host_job_dir,
            )
            result["report_path"] = str(host_job_dir / "report.json")  # type: ignore[typeddict-unknown-key]
            result["report"] = vt_report  # type: ignore[typeddict-unknown-key]
            emit_step(
                "OK",
                f"[14/14] Verdict: {vt_report['verdict']['risk']} "
                f"(confidence {vt_report['verdict']['confidence']}%) "
                f"| report.json saved",
            )
        except Exception as exc:
            logger.exception("build_report failed: %s", exc)
            emit_step(
                "Failed", f"[14/14] report.json build failed (non-critical): {exc}"
            )
            emit_step(
                "OK",
                f"[14/14] Legacy verdict: {result.get('verdict', '?')} "
                f"(score {result.get('score', 0)}/100)",
            )
        _progress(100)
        _milestone(
            "emit_finished",
            f"verdict={result.get('verdict', '?')} score={result.get('score', 0)}",
        )

    except InterruptedError as exc:
        msg = str(exc)
        emit_step("Failed", f"Job cancelled: {msg}")
        result["error"] = msg
        result["success"] = False
        result["summary"] = f"Cancelled: {msg}"
        _state(JobState.CANCELLED)

    except Exception as exc:
        msg = str(exc)
        logger.exception("Sandbox pipeline failed: %s", msg)
        emit_step("Failed", f"Pipeline error: {msg}")
        result["error"] = msg
        result["success"] = False
        result["summary"] = f"Error: {msg}"
        _state(JobState.FAILED)

    finally:
        # Stop the capture thread FIRST — must happen before VM power-off
        # (_capture_stop may already be set from step 12's inner finally, which is fine)
        try:
            _capture_stop.set()
            capture_thread.join(timeout=5)
        except NameError:
            pass  # step 12 was never reached
        except Exception:
            pass

        # Revert VM to clean state
        _state(JobState.CLEANUP)
        emit_step("Running", "Cleanup: reverting VM to clean snapshot")
        try:
            runner.stop_vm(hard=True, timeout=60)
        except Exception:
            pass
        try:
            runner._client.revert_to_snapshot(timeout=120)
            emit_step("OK", "Cleanup completed — VM reverted to clean snapshot")
        except Exception as exc:
            emit_step("Failed", f"Cleanup revert failed (non-critical): {exc}")

    result["finished_at"] = datetime.now().isoformat()

    # Persist final result JSON on host
    try:
        with (host_job_dir / "final_result.json").open("w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, default=str)
    except OSError:
        pass

    if not result.get("error"):
        _state(JobState.FINISHED)

    return result
