"""SQLite repository for scan records and events."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from ..core.interfaces import IEventRepository, IScanRepository
from ..core.types import EventItem, ScanRecord, ScanType


class SqliteRepo(IScanRepository, IEventRepository):
    """SQLite-based repository for scans and events."""

    def __init__(self):
        # Store database in user profile
        db_dir = Path.home() / ".sentinel"
        db_dir.mkdir(exist_ok=True)

        self.db_path = db_dir / "sentinel.db"
        self.init()

    def init(self) -> None:
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Scans table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    status TEXT NOT NULL,
                    findings TEXT,
                    meta TEXT
                )
            """)

            # Events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    source TEXT NOT NULL,
                    message TEXT NOT NULL
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scans_type ON scans(type)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_scans_started ON scans(started_at)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)"
            )

            conn.commit()

    # IScanRepository implementation

    def add(self, rec: ScanRecord) -> int:
        """Add a scan record and return its ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO scans (started_at, finished_at, type, target, status, findings, meta)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    rec.started_at.isoformat(),
                    rec.finished_at.isoformat() if rec.finished_at else None,
                    rec.type.value,
                    rec.target,
                    rec.status,
                    json.dumps(rec.findings) if rec.findings else None,
                    json.dumps(rec.meta) if rec.meta else None,
                ),
            )

            conn.commit()
            return cursor.lastrowid

    def all(self, limit: int = 100) -> list[ScanRecord]:
        """Get all scan records (most recent first)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, started_at, finished_at, type, target, status, findings, meta
                FROM scans
                ORDER BY started_at DESC
                LIMIT ?
            """,
                (limit,),
            )

            records = []
            for row in cursor.fetchall():
                records.append(
                    ScanRecord(
                        id=row[0],
                        started_at=datetime.fromisoformat(row[1]),
                        finished_at=datetime.fromisoformat(row[2]) if row[2] else None,
                        type=ScanType(row[3]),
                        target=row[4],
                        status=row[5],
                        findings=json.loads(row[6]) if row[6] else None,
                        meta=json.loads(row[7]) if row[7] else None,
                    )
                )

            return records

    def get_all(self) -> list[ScanRecord]:
        """Get all scan records."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, started_at, finished_at, type, target, status, findings, meta
                FROM scans
                ORDER BY started_at DESC
            """
            )

            records = []
            for row in cursor.fetchall():
                records.append(
                    ScanRecord(
                        id=row[0],
                        started_at=datetime.fromisoformat(row[1]),
                        finished_at=datetime.fromisoformat(row[2]) if row[2] else None,
                        type=ScanType(row[3]),
                        target=row[4],
                        status=row[5],
                        findings=json.loads(row[6]) if row[6] else None,
                        meta=json.loads(row[7]) if row[7] else None,
                    )
                )

            return records

    # IEventRepository implementation

    def add_many(self, items: list[EventItem]) -> None:
        """Add multiple event items."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.executemany(
                """
                INSERT INTO events (timestamp, level, source, message)
                VALUES (?, ?, ?, ?)
            """,
                [
                    (item.timestamp.isoformat(), item.level, item.source, item.message)
                    for item in items
                ],
            )

            conn.commit()

    def recent(self, limit: int = 100) -> list[EventItem]:
        """Get recent event items."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT timestamp, level, source, message
                FROM events
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (limit,),
            )

            items = []
            for row in cursor.fetchall():
                items.append(
                    EventItem(
                        timestamp=datetime.fromisoformat(row[0]),
                        level=row[1],
                        source=row[2],
                        message=row[3],
                    )
                )

            return items
