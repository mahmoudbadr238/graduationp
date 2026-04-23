"""Scanner Engine facade backed by local static analysis.

Provides a compatibility wrapper that returns the legacy malware-scanner
contract while using the current ``StaticScanner`` + Groq NGAV pipeline.
"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Any

from .decision import decision_from_scan_result
from .static_scanner import StaticScanner

logger = logging.getLogger(__name__)


class MalwareScanner:
    """High-level malware scanner backed by StaticScanner + Groq NGAV."""

    def __init__(self) -> None:
        self._scanner = StaticScanner()

    @property
    def is_available(self) -> bool:
        """Return ``True`` when local scanning is available."""
        return self._scanner is not None

    def scan_file(self, file_path: str | Path) -> dict[str, Any]:
        """Scan a single file and return a structured verdict.

        Parameters
        ----------
        file_path
            Absolute or relative path to the file to scan.

        Returns
        -------
        dict
            ``is_malicious``  — bool, True if ≥ 1 rule matched.
            ``matched_rules`` — list[dict] with keys: ``rule_name``,
            ``description``, ``severity``, ``category``,
            ``matched_strings``, ``tags``.
            ``score``         — int 0-100, aggregate severity score.
            ``file_info``     — dict with file metadata (name, size, hashes).
            ``scan_time_ms``  — float, wall-clock time of the scan.
            ``scanner_mode``  — str, which backend was used.
            ``error``         — str | None, error message if scan failed.
        """
        file_path = Path(file_path)

        # Base result template
        result: dict[str, Any] = {
            "is_malicious": False,
            "matched_rules": [],
            "score": 0,
            "file_info": {},
            "scan_time_ms": 0.0,
            "scanner_mode": "none",
            "error": None,
        }

        # ---- Validate file ----
        if not file_path.exists():
            result["error"] = f"File not found: {file_path}"
            logger.warning(result["error"])
            return result

        if not file_path.is_file():
            result["error"] = f"Not a regular file: {file_path}"
            logger.warning(result["error"])
            return result

        # ---- Collect file info ----
        try:
            stat = file_path.stat()
            file_bytes = file_path.read_bytes()
            result["file_info"] = {
                "name": file_path.name,
                "path": str(file_path.resolve()),
                "size_bytes": stat.st_size,
                "sha256": hashlib.sha256(file_bytes).hexdigest(),
                "md5": hashlib.md5(file_bytes).hexdigest(),  # noqa: S324
            }
        except PermissionError:
            result["error"] = (
                f"Permission denied reading '{file_path}'. "
                "The file may be locked by a running process."
            )
            logger.error(result["error"])
            return result
        except Exception as exc:
            result["error"] = f"Error reading file: {exc}"
            logger.error(result["error"])
            return result

        # ---- Run scan ----
        t0 = time.perf_counter()

        try:
            scan_result = self._scanner.scan_file(str(file_path))
            scan_dict = scan_result.to_dict()
        except Exception as exc:
            result["error"] = f"Scan failed: {exc}"
            return result

        groq = scan_dict.get("groq_analysis", {})
        if not isinstance(groq, dict):
            groq = {}

        final_decision = decision_from_scan_result(scan_result).to_dict()

        result["scanner_mode"] = "groq_ngav"
        result["score"] = int(final_decision.get("score", 0) or 0)
        result["is_malicious"] = final_decision.get("action") == "block"
        result["verdict"] = final_decision.get("verdict_label", "Unknown")
        result["action"] = final_decision.get("action", "allow")
        result["action_reason"] = final_decision.get("action_reason", "")
        result["final_decision"] = final_decision

        if groq:
            result["matched_rules"] = [
                {
                    "rule_name": "Groq AI Verdict",
                    "description": str(
                        groq.get("explanation", final_decision.get("action_reason", "AI classification completed"))
                    ),
                    "severity": result["verdict"],
                    "category": "ai_analysis",
                    "matched_strings": [],
                    "tags": ["groq", "ngav"],
                }
            ]
        elif final_decision.get("triggered_rules"):
            result["matched_rules"] = [
                {
                    "rule_name": str(final_decision["triggered_rules"][0]),
                    "description": str(final_decision.get("action_reason", "Final decision normalized")),
                    "severity": result["verdict"],
                    "category": "final_decision",
                    "matched_strings": [],
                    "tags": ["decision"],
                }
            ]

        result["scan_time_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        if result["is_malicious"]:
            logger.warning(
                "MALICIOUS: %s — score=%d",
                file_path.name,
                result["score"],
            )
        else:
            logger.info(
                "CLEAN: %s (scanned in %.1fms)",
                file_path.name,
                result["scan_time_ms"],
            )

        return result

# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_scanner: MalwareScanner | None = None


def get_malware_scanner() -> MalwareScanner:
    """Return the singleton ``MalwareScanner`` instance."""
    global _scanner
    if _scanner is None:
        _scanner = MalwareScanner()
    return _scanner
