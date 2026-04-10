"""
Scanner Engine — YARA-powered Malware Scanner for Sentinel.

Wraps the existing ``YaraEngine`` (``yara_engine.py``) into a simple,
high-level ``MalwareScanner`` façade that the AI Agent tools and the
REST of the application can call.

Usage
~~~~~
    scanner = MalwareScanner()
    result  = scanner.scan_file(r"C:\\Users\\user\\Downloads\\suspect.exe")
    if result["is_malicious"]:
        for rule in result["matched_rules"]:
            print(rule["rule_name"], rule["severity"])
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MalwareScanner:
    """High-level malware scanner backed by YARA rules.

    This class loads compiled or source YARA rules and scans individual
    files, returning a structured dictionary with the verdict
    and matched-rule details.

    Parameters
    ----------
    rules_dir
        Path to the directory containing ``.yar`` / ``.yara`` source
        rules **or** a pre-compiled ``.yarc`` file.  Defaults to
        ``app/scanning/yara_rules/``.
    """

    def __init__(self, rules_dir: Path | str | None = None) -> None:
        self._rules_dir = Path(rules_dir) if rules_dir else self._default_rules_dir()
        self._yara_engine = None
        self._fallback_scanner = None
        self._initialised = False
        self._init_engine()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _default_rules_dir() -> Path:
        return Path(__file__).parent / "yara_rules"

    def _init_engine(self) -> None:
        """Try loading the real YARA engine; fall back to pattern scanner."""
        try:
            from .yara_engine import YaraEngine

            self._yara_engine = YaraEngine(rules_dir=self._rules_dir)
            if self._yara_engine.is_available:
                logger.info(
                    "MalwareScanner: YARA engine initialised (rules_dir=%s)",
                    self._rules_dir,
                )
                self._initialised = True
                return

            # YARA lib found but rules failed to load — fall through
            logger.warning("MalwareScanner: YARA engine available but rules did not load")
        except Exception as exc:
            logger.warning("MalwareScanner: YARA engine not available (%s)", exc)

        # Fallback to pattern-based scanner
        try:
            from .yara_engine import FallbackPatternScanner

            self._fallback_scanner = FallbackPatternScanner()
            self._initialised = True
            logger.info("MalwareScanner: using FallbackPatternScanner")
        except Exception as exc:
            logger.error("MalwareScanner: no scanner available (%s)", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """Return ``True`` if any scanner backend is loaded."""
        return self._initialised

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

        if self._yara_engine and self._yara_engine.is_available:
            result["scanner_mode"] = "yara"
            matches = self._yara_engine.scan_file(str(file_path))
            result["matched_rules"] = self._yara_engine.get_findings(matches)
            result["score"] = self._yara_engine.calculate_score(matches)

        elif self._fallback_scanner:
            result["scanner_mode"] = "fallback_patterns"
            findings = self._fallback_scanner.scan_data(file_bytes)
            result["matched_rules"] = findings
            result["score"] = self._fallback_scanner.calculate_score(findings)

        else:
            result["error"] = "No scanner backend available"
            return result

        result["scan_time_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        result["is_malicious"] = len(result["matched_rules"]) > 0

        if result["is_malicious"]:
            logger.warning(
                "MALICIOUS: %s — %d rule(s) matched, score=%d",
                file_path.name,
                len(result["matched_rules"]),
                result["score"],
            )
        else:
            logger.info(
                "CLEAN: %s (scanned in %.1fms)",
                file_path.name,
                result["scan_time_ms"],
            )

        return result

    def scan_file_quick(self, file_path: str | Path) -> bool:
        """Quick boolean check — returns ``True`` if file is malicious."""
        return self.scan_file(file_path)["is_malicious"]


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
