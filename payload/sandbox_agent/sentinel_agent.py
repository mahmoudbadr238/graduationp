"""Sentinel Unified Sandbox Agent.

Primary automation entrypoint for sandbox UI interaction.

Design goals:
- deliberate, state-aware behavior
- deterministic decisioning first, LLM fallback second
- strict target resolution with threshold enforcement
- post-action verification and retry/loop guards
- report compatibility with C:\\Sandbox\\report.json pipeline
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyautogui

from .classifier import classify_screen
from .decision import decide
from .executor import execute
from .hud import hud, start_hud, stop_hud
from .human_sim import (
    create_honeypot_files,
    generate_browser_history,
    maybe_extract_archive,
    simulate_human_activity,
)
from .memory import ActionMemory
from .models import ActionDecision, ActionRecord, ActionType, Observation
from .monitor import BehavioralMonitor, write_report
from .observer import observe
from .resolver import resolve
from .telemetry import TraceEvent, TraceRecorder
from .verifier import verify

LOG_DIR = Path(os.environ.get("SENTINEL_LOG_DIR", r"C:\Sandbox"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)-7s] %(funcName)-28s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_DIR / "sentinel_agent.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("sentinel_agent")

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.3
SCREEN_W, SCREEN_H = pyautogui.size()

MIN_EXEC_CONFIDENCE = 0.62


@dataclass
class ExecutionResult:
    """Execution + verification result for one cycle."""

    executed: bool
    verification: str
    state_changed: bool
    match_score: float
    match_method: str
    refusal_reason: str = ""
    after_observation: Observation | None = None


def execute_action_verified(
    decision: ActionDecision,
    before: Observation,
) -> ExecutionResult:
    """Resolve, execute, and verify one action."""
    if decision.action == ActionType.WAIT:
        return ExecutionResult(
            executed=False,
            verification="skipped",
            state_changed=False,
            match_score=0.0,
            match_method="none",
            refusal_reason=decision.reason or "wait",
        )

    match = None
    if decision.action in (ActionType.CLICK, ActionType.CHECK):
        match = resolve(decision)
        if match is None:
            return ExecutionResult(
                executed=False,
                verification="unresolved",
                state_changed=False,
                match_score=0.0,
                match_method="none",
                refusal_reason=f"target not confidently resolved: {decision.target}",
            )

    executed = execute(decision, match)
    if not executed:
        return ExecutionResult(
            executed=False,
            verification="not_executed",
            state_changed=False,
            match_score=match.score if match else 0.0,
            match_method=match.method if match else "none",
            refusal_reason="executor returned false",
        )

    after_obs, verdict = verify(before)
    return ExecutionResult(
        executed=True,
        verification=verdict,
        state_changed=(verdict == "changed"),
        match_score=match.score if match else 1.0,
        match_method=match.method if match else "direct",
        after_observation=after_obs,
    )


def react_loop(
    api_key: str,
    duration: int = 120,
) -> tuple[list[dict[str, Any]], ActionMemory, dict[str, Any]]:
    """Observe -> classify -> decide -> resolve -> execute -> verify -> record."""
    log.info("=== ReAct Loop START (duration=%ds) ===", duration)
    hud("ReAct loop active")

    memory = ActionMemory()
    recorder = TraceRecorder()
    start = time.monotonic()
    cycle = 0

    while (time.monotonic() - start) < duration:
        cycle += 1
        remaining = max(0, int(duration - (time.monotonic() - start)))
        hud(f"Cycle {cycle} - {remaining}s left")

        obs = observe()
        classification = classify_screen(obs)

        cycle_record: dict[str, Any] = {
            "cycle": cycle,
            "remaining_s": remaining,
            "observed_state": classification.state.value,
            "state_confidence": round(classification.confidence, 3),
            "state_explanation": classification.explanation,
            "active_window": obs.active_window.title if obs.active_window else "",
            "window_count": len(obs.windows),
        }

        if memory.detect_loop():
            decision = ActionDecision.wait("loop detected; backing off")
            cycle_record["refusal_reason"] = "loop_guard"
        elif not obs.windows:
            decision = ActionDecision.wait("no observable windows")
            cycle_record["refusal_reason"] = "no_windows"
        else:
            decision = decide(obs, classification, api_key, memory)

        if (
            decision.action != ActionType.WAIT
            and decision.confidence < MIN_EXEC_CONFIDENCE
        ):
            cycle_record["refusal_reason"] = (
                f"decision confidence {decision.confidence:.2f} below threshold"
            )
            decision = ActionDecision.wait("low confidence decision")

        if (
            decision.action != ActionType.WAIT
            and decision.target
            and memory.is_suppressed(decision.action.value, decision.target)
        ):
            cycle_record["refusal_reason"] = "suppressed by retry guard"
            decision = ActionDecision.wait("suppressed repeated ineffective action")

        cycle_record["chosen_action"] = decision.action.value
        cycle_record["action_target"] = decision.target
        cycle_record["action_confidence"] = round(decision.confidence, 3)
        cycle_record["action_reason"] = decision.reason

        result = execute_action_verified(decision, obs)
        cycle_record["match_confidence"] = round(result.match_score, 3)
        cycle_record["match_method"] = result.match_method
        cycle_record["verification_result"] = result.verification
        cycle_record["executed"] = result.executed
        if result.refusal_reason:
            cycle_record["refusal_reason"] = result.refusal_reason

        memory.record(
            ActionRecord(
                cycle=cycle,
                timestamp=time.monotonic(),
                decision=decision,
                executed=result.executed,
                state_changed=result.state_changed,
                match_score=result.match_score,
                verification=result.verification,
            )
        )

        recorder.record(
            TraceEvent(
                cycle=cycle,
                remaining_s=remaining,
                observed_state=cycle_record["observed_state"],
                state_confidence=cycle_record["state_confidence"],
                state_explanation=cycle_record["state_explanation"],
                chosen_action=cycle_record["chosen_action"],
                action_target=cycle_record["action_target"],
                action_confidence=cycle_record["action_confidence"],
                action_reason=cycle_record["action_reason"],
                match_confidence=cycle_record["match_confidence"],
                match_method=cycle_record["match_method"],
                verification_result=cycle_record["verification_result"],
                executed=cycle_record["executed"],
                active_window=cycle_record["active_window"],
                window_count=cycle_record["window_count"],
                refusal_reason=cycle_record.get("refusal_reason", ""),
            )
        )

        if result.state_changed:
            time.sleep(random.uniform(1.2, 2.0))
        else:
            _idle_pause(memory)

    log.info("=== ReAct Loop END (%d cycles) ===", cycle)
    return recorder.to_list(), memory, recorder.summary()


def _idle_pause(memory: ActionMemory) -> None:
    """Adaptive pause that favors observe/wait over random clicking."""
    waits = memory.consecutive_waits()
    if waits > 6:
        pause = random.uniform(4.5, 7.0)
    elif waits > 3:
        pause = random.uniform(3.0, 5.0)
    else:
        pause = random.uniform(1.8, 3.0)
    time.sleep(pause)


def _handle_initial_uac_once() -> None:
    """One-shot UAC shortcut immediately after launch."""
    log.info("Attempting one-shot UAC acceptance")
    hud("Handling possible UAC prompt")
    time.sleep(1.2)
    pyautogui.hotkey("alt", "y")
    time.sleep(0.8)


def run_agent(
    target: Path,
    *,
    timeout: int = 120,
    enable_hud: bool = True,
) -> None:
    """Execute setup -> detonate -> react loop -> report."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        log.warning("GROQ_API_KEY not set; using deterministic decisions unless needed")

    if enable_hud:
        start_hud()

    log.info("=" * 60)
    log.info("SENTINEL UNIFIED AGENT STARTED")
    log.info("Target: %s", target)
    log.info("Timeout: %ds | API key: %s", timeout, "present" if api_key else "missing")
    log.info("Screen: %dx%d", SCREEN_W, SCREEN_H)
    log.info("=" * 60)

    if not target.exists():
        log.error("TARGET NOT FOUND: %s", target)
        hud(f"ERROR target not found: {target}")
        time.sleep(2.0)
        if enable_hud:
            stop_hud()
        return

    monitor = BehavioralMonitor()
    monitor.capture_baseline()
    monitor.start_monitoring()

    try:
        hud("Preparing realistic environment")
        create_honeypot_files()
        generate_browser_history()
        simulate_human_activity()

        target = maybe_extract_archive(target)

        target_dir = str(target.parent)
        hud(f"Opening folder: {target_dir}")
        try:
            os.startfile(target_dir)  # noqa: S606
        except Exception as exc:
            log.error("Explorer launch failed: %s", exc)
        time.sleep(2.0)

        hud(f"Executing: {target.name}")
        try:
            os.startfile(str(target))  # noqa: S606
        except AttributeError:
            subprocess.Popen([str(target)], shell=True)  # noqa: S603
        time.sleep(3.0)

        _handle_initial_uac_once()

        trace, memory, trace_summary = react_loop(api_key, duration=timeout)

        write_report(
            monitor,
            target,
            agent_trace=trace,
            agent_trace_summary=trace_summary,
            agent_memory_summary=memory.get_summary(),
        )

        summary = monitor.get_report().get("summary", {})
        log.info(
            "Behavioral summary: procs=%d files_created=%d files_modified=%d files_deleted=%d registry=%d net=%d",
            summary.get("new_processes", 0),
            summary.get("files_created", 0),
            summary.get("files_modified", 0),
            summary.get("files_deleted", 0),
            summary.get("registry_changes", 0),
            summary.get("network_connections", 0),
        )
        log.info(
            "Agent summary: actions=%d effective=%d",
            memory.total_actions,
            memory.total_effective,
        )

        hud("Analysis complete")
        time.sleep(1.5)

    finally:
        monitor.stop_monitoring()
        if enable_hud:
            stop_hud()
        log.info("=" * 60)
        log.info("SENTINEL UNIFIED AGENT FINISHED")
        log.info("=" * 60)


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Sentinel Unified Agent - state-aware sandbox automation",
    )
    parser.add_argument(
        "target",
        type=Path,
        help="Path to sample file (e.g. C:\\Sandbox\\malware.exe)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Seconds for interaction loop (default: 120)",
    )
    parser.add_argument(
        "--no-hud",
        action="store_true",
        help="Disable floating status overlay",
    )
    args = parser.parse_args()

    if not args.target.exists():
        print(f"[!] Target not found: {args.target}", file=sys.stderr)
        raise SystemExit(1)

    run_agent(args.target, timeout=args.timeout, enable_hud=not args.no_hud)


if __name__ == "__main__":
    main()
