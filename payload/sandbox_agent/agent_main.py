"""Compatibility shim for older entrypoint imports.

Primary implementation now lives in payload.sandbox_agent.sentinel_agent.
"""

from __future__ import annotations

try:
    from payload.sandbox_agent.sentinel_agent import (
        execute_action_verified,
        main,
        react_loop,
        run_agent,
    )
except Exception:  # pragma: no cover - direct script fallback
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from payload.sandbox_agent.sentinel_agent import (
        execute_action_verified,
        main,
        react_loop,
        run_agent,
    )

__all__ = ["run_agent", "react_loop", "execute_action_verified", "main"]


if __name__ == "__main__":
    main()
