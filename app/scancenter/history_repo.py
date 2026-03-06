"""ScanCenter history – thin SQLite CRUD over scancenter_history table.

Intentionally kept simple: one write per job, one read for the list.
The table lives alongside the existing scan_history in sentinel.db,
prefixed with ``scancenter_`` to avoid collisions.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DB_TIMEOUT = 5  # seconds


def _db_path() -> Path:
    return Path.home() / ".sentinel" / "sentinel.db"


def _connect() -> sqlite3.Connection:
    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db), timeout=_DB_TIMEOUT)
    con.row_factory = sqlite3.Row
    return con


class HistoryRepo:
    """Read/write scancenter_history rows in sentinel.db."""

    TABLE_DDL = """
        CREATE TABLE IF NOT EXISTS scancenter_history (
            job_id          TEXT PRIMARY KEY,
            file_name       TEXT NOT NULL DEFAULT '',
            sha256          TEXT NOT NULL DEFAULT '',
            file_type       TEXT NOT NULL DEFAULT '',
            verdict_risk    TEXT NOT NULL DEFAULT 'Unknown',
            verdict_label   TEXT NOT NULL DEFAULT '',
            confidence      INTEGER NOT NULL DEFAULT 0,
            score           INTEGER NOT NULL DEFAULT 0,
            mode            TEXT NOT NULL DEFAULT 'static',
            created_at      TEXT NOT NULL DEFAULT '',
            duration_sec    REAL NOT NULL DEFAULT 0,
            report_path     TEXT NOT NULL DEFAULT '',
            engines_summary TEXT NOT NULL DEFAULT ''
        )
    """

    def __init__(self) -> None:
        self._ensure_table()

    def _ensure_table(self) -> None:
        try:
            with _connect() as con:
                con.execute(self.TABLE_DDL)
                con.commit()
        except Exception as exc:
            logger.warning("scancenter_history table init failed: %s", exc)

    # ── Writes ───────────────────────────────────────────────────────────────

    def upsert(
        self,
        job_id: str,
        file_name: str,
        sha256: str,
        file_type: str,
        verdict_risk: str,
        verdict_label: str,
        confidence: int,
        score: int,
        mode: str,
        created_at: str,
        duration_sec: float,
        report_path: str,
        engines_summary: str = "",
    ) -> None:
        """Insert or replace a scan history row."""
        try:
            with _connect() as con:
                con.execute(
                    """INSERT OR REPLACE INTO scancenter_history
                       (job_id, file_name, sha256, file_type, verdict_risk, verdict_label,
                        confidence, score, mode, created_at, duration_sec, report_path,
                        engines_summary)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        job_id or "",
                        file_name or "",
                        sha256 or "",
                        file_type or "",
                        verdict_risk or "Unknown",
                        verdict_label or "",
                        int(confidence or 0),
                        int(score or 0),
                        mode or "static",
                        created_at or "",
                        float(duration_sec or 0),
                        report_path or "",
                        engines_summary or "",
                    ),
                )
                con.commit()
        except Exception as exc:
            logger.warning("scancenter_history upsert failed: %s", exc)

    def delete(self, job_id: str) -> None:
        try:
            with _connect() as con:
                con.execute("DELETE FROM scancenter_history WHERE job_id = ?", (job_id,))
                con.commit()
        except Exception as exc:
            logger.warning("scancenter_history delete failed: %s", exc)

    # ── Reads ────────────────────────────────────────────────────────────────

    def list_recent(self, limit: int = 200) -> list[dict[str, Any]]:
        """Return up to *limit* rows newest-first."""
        try:
            with _connect() as con:
                rows = con.execute(
                    """SELECT * FROM scancenter_history
                       ORDER BY created_at DESC LIMIT ?""",
                    (max(1, int(limit)),),
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as exc:
            logger.warning("scancenter_history list failed: %s", exc)
            return []

    def get(self, job_id: str) -> dict[str, Any] | None:
        try:
            with _connect() as con:
                row = con.execute(
                    "SELECT * FROM scancenter_history WHERE job_id = ?", (job_id,)
                ).fetchone()
                return dict(row) if row else None
        except Exception as exc:
            logger.warning("scancenter_history get failed: %s", exc)
            return None
