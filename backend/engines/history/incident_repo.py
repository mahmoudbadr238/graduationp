"""Persistent incident history for RTP threat events."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.platform.paths import resolve_legacy_compatible_data_path

logger = logging.getLogger(__name__)

_DB_TIMEOUT = 5


class IncidentHistoryRepo:
    """Store and read structured RTP incidents from ``sentinel.db``."""

    TABLE_DDL = """
        CREATE TABLE IF NOT EXISTS incident_history (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            occurred_at       TEXT NOT NULL DEFAULT '',
            process_name      TEXT NOT NULL DEFAULT '',
            executable_path   TEXT NOT NULL DEFAULT '',
            pid               INTEGER NOT NULL DEFAULT 0,
            threat_score      INTEGER NOT NULL DEFAULT 0,
            decision_verdict  TEXT NOT NULL DEFAULT '',
            decision_action   TEXT NOT NULL DEFAULT '',
            process_action    TEXT NOT NULL DEFAULT '',
            file_action       TEXT NOT NULL DEFAULT '',
            action_reason     TEXT NOT NULL DEFAULT '',
            action_taken      TEXT NOT NULL DEFAULT '',
            file_action_taken TEXT NOT NULL DEFAULT '',
            sha256            TEXT NOT NULL DEFAULT '',
            publisher         TEXT NOT NULL DEFAULT '',
            signature_valid   INTEGER,
            matched_rules     TEXT NOT NULL DEFAULT '[]',
            raw_message       TEXT NOT NULL DEFAULT ''
        )
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = (
            Path(db_path)
            if db_path is not None
            else resolve_legacy_compatible_data_path("sentinel.db")
        )
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(self._db_path), timeout=_DB_TIMEOUT)
        con.row_factory = sqlite3.Row
        return con

    def _ensure_table(self) -> None:
        try:
            with self._connect() as con:
                con.execute(self.TABLE_DDL)
                con.commit()
        except Exception as exc:
            logger.warning("incident_history table init failed: %s", exc)

    def append(self, event: dict[str, Any], raw_message: str = "") -> None:
        """Persist one structured RTP incident."""
        if not isinstance(event, dict):
            return

        matched_rules = event.get("matched_rules") or []
        signature_valid = event.get("signature_valid")
        occurred_at = str(
            event.get("occurred_at")
            or datetime.now(timezone.utc).isoformat(timespec="seconds")
        )

        try:
            with self._connect() as con:
                con.execute(
                    """INSERT INTO incident_history
                       (occurred_at, process_name, executable_path, pid, threat_score,
                        decision_verdict, decision_action, process_action, file_action,
                        action_reason, action_taken, file_action_taken, sha256,
                        publisher, signature_valid, matched_rules, raw_message)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        occurred_at,
                        str(event.get("process_name") or ""),
                        str(event.get("executable_path") or ""),
                        int(event.get("pid") or 0),
                        int(event.get("threat_score") or 0),
                        str(event.get("decision_verdict") or ""),
                        str(event.get("decision_action") or ""),
                        str(event.get("process_action") or ""),
                        str(event.get("file_action") or ""),
                        str(event.get("action_reason") or ""),
                        str(event.get("action_taken") or ""),
                        str(event.get("file_action_taken") or ""),
                        str(event.get("sha256") or ""),
                        str(event.get("publisher") or ""),
                        (
                            None
                            if signature_valid is None
                            else 1 if bool(signature_valid) else 0
                        ),
                        json.dumps(list(matched_rules)),
                        str(raw_message or event.get("display_message") or ""),
                    ),
                )
                con.commit()
        except Exception as exc:
            logger.warning("incident_history append failed: %s", exc)

    def list_recent(self, limit: int = 200) -> list[dict[str, Any]]:
        """Return the most recent incidents newest-first."""
        try:
            with self._connect() as con:
                rows = con.execute(
                    """SELECT * FROM incident_history
                       ORDER BY occurred_at DESC, id DESC
                       LIMIT ?""",
                    (max(1, int(limit)),),
                ).fetchall()
        except Exception as exc:
            logger.warning("incident_history list failed: %s", exc)
            return []

        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["matched_rules"] = json.loads(item.get("matched_rules") or "[]")
            except (TypeError, ValueError, json.JSONDecodeError):
                item["matched_rules"] = []

            signature_value = item.get("signature_valid")
            if signature_value is None:
                item["signature_valid"] = None
            else:
                item["signature_valid"] = bool(signature_value)
            result.append(item)
        return result
