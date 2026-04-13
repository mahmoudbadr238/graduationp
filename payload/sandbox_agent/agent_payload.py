"""Legacy build entrypoint for Sentinel sandbox agent.

This file is intentionally thin so existing build scripts/spec files that
reference agent_payload.py continue to work unchanged.

Primary implementation: payload.sandbox_agent.sentinel_agent
"""

from __future__ import annotations

try:
    from payload.sandbox_agent.sentinel_agent import main, run_agent
except Exception:  # pragma: no cover - direct script fallback
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from payload.sandbox_agent.sentinel_agent import main, run_agent

__all__ = ["run_agent", "main"]


if __name__ == "__main__":
    main()
