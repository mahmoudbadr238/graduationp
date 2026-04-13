# Sandbox Agent Migration Summary

## Base Selected
- Primary base file: `payload/sandbox_agent/sentinel_agent.py`.
- Reason: strongest observe -> think -> act foundation with model-pluggable flow.

## What Was Merged
- Groq/rule hybrid decision flow retained and hardened.
- Behavioral monitoring/report compatibility retained via `monitor.py` and `C:\Sandbox\report.json` output.
- Human-environment anti-evasion helpers retained via `human_sim.py`.
- HUD retained as a decoupled module via `hud.py`.

## What Was Removed/Isolated
- Blind generic prompt-smashing behavior was removed from active runtime paths.
- Legacy monolithic entrypoints were converted to compatibility shims:
  - `agent_payload.py`
  - `agent_main.py`
- Obsolete logic is isolated instead of duplicated in active code paths.

## Safety & Reliability Improvements
- State-aware classifier with confidence and explanation.
- Deterministic decisions first, LLM fallback second.
- LLM action grounding checks against current observation.
- Stricter target resolution (exact > contains > fuzzy) with threshold enforcement.
- Verified single-action execution flow (`execute_action_verified`).
- Retry guard suppresses repeated ineffective actions after two failures.
- Loop detection backs off to wait/observe.
- Trace telemetry now includes per-cycle action, confidence, match confidence, and verification result.

## Reporting Changes
- Existing report schema compatibility preserved.
- Added optional telemetry summary payload in report:
  - `agent_trace_summary`

## External Behavior Compatibility
- CLI preserved (`target`, `--timeout`, `--no-hud`).
- Build/runtime compatibility preserved through legacy shims.
- No new heavy dependencies introduced.
