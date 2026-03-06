"""SQLite repository for scan records and events with connection pooling and optimization."""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from ..core.interfaces import IEventRepository, IScanRepository
from ..core.types import EventItem, ScanRecord, ScanType

logger = logging.getLogger(__name__)

# Connection pool configuration
MAX_POOL_SIZE = 5
CONNECTION_TIMEOUT = 30  # seconds


class SqliteRepo(IScanRepository, IEventRepository):
    """SQLite-based repository for scans and events with connection pooling and optimizations."""

    def __init__(self):
        # Store database in user profile
        db_dir = Path.home() / ".sentinel"
        db_dir.mkdir(exist_ok=True)

        self.db_path = db_dir / "sentinel.db"
        self._connections: list[sqlite3.Connection] = []
        self._connection_pool_size = 0
        self.init()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection from pool or create new one"""
        # For now, use a simple approach (thread-safe SQLite connections)
        conn = sqlite3.connect(
            str(self.db_path), timeout=CONNECTION_TIMEOUT, check_same_thread=False
        )
        conn.row_factory = sqlite3.Row  # Better performance with row factories
        conn.execute(
            "PRAGMA journal_mode=WAL"
        )  # Write-Ahead Logging for better concurrency
        conn.execute("PRAGMA synchronous=NORMAL")  # Balance between safety and speed
        conn.execute("PRAGMA cache_size=5000")  # Increase page cache
        return conn

    def init(self) -> None:
        """Initialize database tables with optimizations."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Scans table with better indexing
            cursor.execute(
                """
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
            """
            )

            # Events table with better indexing
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    source TEXT NOT NULL,
                    message TEXT NOT NULL,
                    event_id INTEGER DEFAULT 0,
                    friendly_message TEXT
                )
            """
            )

            # Add event_id column if it doesn't exist (migration for existing DBs)
            try:
                cursor.execute(
                    "ALTER TABLE events ADD COLUMN event_id INTEGER DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                cursor.execute("ALTER TABLE events ADD COLUMN friendly_message TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Create optimized indexes (avoiding duplicates)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scans_type ON scans(type)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_scans_started ON scans(started_at DESC)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_scans_status ON scans(status)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_level ON events(level)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_source ON events(source)"
            )

            # Event summaries cache table (for AI-generated explanations)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS event_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    signature TEXT NOT NULL,
                    table_summary TEXT NOT NULL,
                    title TEXT NOT NULL,
                    severity_label TEXT NOT NULL,
                    what_happened TEXT NOT NULL,
                    what_you_can_do TEXT NOT NULL,
                    tech_notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (source, event_id, signature)
                )
            """
            )

            # Index for fast lookups
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_event_summaries_lookup "
                "ON event_summaries(source, event_id, signature)"
            )

            # Event explanations cache (new 2-level system for Groq AI)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS event_explanations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    detail_level TEXT NOT NULL DEFAULT 'full',
                    locale TEXT NOT NULL DEFAULT 'en',
                    message_hash TEXT NOT NULL,
                    title TEXT NOT NULL,
                    what_happened TEXT NOT NULL,
                    why_it_happened TEXT,
                    what_it_affects TEXT,
                    is_normal INTEGER DEFAULT 1,
                    risk_level TEXT DEFAULT 'low',
                    what_to_do TEXT,
                    when_to_worry TEXT,
                    technical_brief TEXT,
                    simplified_text TEXT,
                    ai_provider TEXT DEFAULT 'groq',
                    token_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    ttl_seconds INTEGER DEFAULT 86400,
                    UNIQUE (provider, event_id, detail_level, locale, message_hash)
                )
            """
            )

            # Indexes for event_explanations
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_explanations_lookup "
                "ON event_explanations(provider, event_id, detail_level, message_hash)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_explanations_created "
                "ON event_explanations(created_at)"
            )

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
        finally:
            conn.close()

    # IScanRepository implementation

    def add(self, rec: ScanRecord) -> int:
        """Add a scan record and return its ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Handle both datetime objects and ISO strings for started_at/finished_at
            started_str = (
                rec.started_at.isoformat()
                if hasattr(rec.started_at, "isoformat")
                else str(rec.started_at)
            )
            finished_str = None
            if rec.finished_at:
                finished_str = (
                    rec.finished_at.isoformat()
                    if hasattr(rec.finished_at, "isoformat")
                    else str(rec.finished_at)
                )

            cursor.execute(
                """
                INSERT INTO scans (started_at, finished_at, type, target, status, findings, meta)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    started_str,
                    finished_str,
                    rec.type.value,
                    rec.target,
                    rec.status,
                    json.dumps(rec.findings) if rec.findings else None,
                    json.dumps(rec.meta) if rec.meta else None,
                ),
            )

            conn.commit()
            record_id = cursor.lastrowid
            logger.debug(f"Added scan record {record_id}")
            return record_id
        except Exception as e:
            logger.error(f"Error adding scan record: {e}")
            raise
        finally:
            conn.close()

    def all(self, limit: int = 100) -> list[ScanRecord]:
        """Get all scan records (most recent first) with optimized query."""
        conn = self._get_connection()
        try:
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
                try:
                    records.append(
                        ScanRecord(
                            id=row[0],
                            started_at=datetime.fromisoformat(row[1]),
                            finished_at=(
                                datetime.fromisoformat(row[2]) if row[2] else None
                            ),
                            type=ScanType(row[3]),
                            target=row[4],
                            status=row[5],
                            findings=json.loads(row[6]) if row[6] else None,
                            meta=json.loads(row[7]) if row[7] else None,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Error parsing scan record {row[0]}: {e}")
                    continue

            return records
        except Exception as e:
            logger.error(f"Error querying scans: {e}")
            return []
        finally:
            conn.close()

    def get_all(self) -> list[ScanRecord]:
        """Get all scan records (use with caution for large datasets)."""
        return self.all(limit=10000)  # Reasonable limit to prevent memory issues

    def get_by_id(self, scan_id: int) -> ScanRecord | None:
        """Get a specific scan record by ID"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, started_at, finished_at, type, target, status, findings, meta
                FROM scans
                WHERE id = ?
            """,
                (scan_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            return ScanRecord(
                id=row[0],
                started_at=datetime.fromisoformat(row[1]),
                finished_at=datetime.fromisoformat(row[2]) if row[2] else None,
                type=ScanType(row[3]),
                target=row[4],
                status=row[5],
                findings=json.loads(row[6]) if row[6] else None,
                meta=json.loads(row[7]) if row[7] else None,
            )
        except Exception as e:
            logger.error(f"Error getting scan by ID {scan_id}: {e}")
            return None
        finally:
            conn.close()

    def get_by_type(self, scan_type: ScanType, limit: int = 100) -> list[ScanRecord]:
        """Get scans filtered by type"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, started_at, finished_at, type, target, status, findings, meta
                FROM scans
                WHERE type = ?
                ORDER BY started_at DESC
                LIMIT ?
            """,
                (scan_type.value, limit),
            )

            records = []
            for row in cursor.fetchall():
                try:
                    records.append(
                        ScanRecord(
                            id=row[0],
                            started_at=datetime.fromisoformat(row[1]),
                            finished_at=(
                                datetime.fromisoformat(row[2]) if row[2] else None
                            ),
                            type=ScanType(row[3]),
                            target=row[4],
                            status=row[5],
                            findings=json.loads(row[6]) if row[6] else None,
                            meta=json.loads(row[7]) if row[7] else None,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Error parsing scan record: {e}")
                    continue

            return records
        except Exception as e:
            logger.error(f"Error querying scans by type: {e}")
            return []
        finally:
            conn.close()

    # IEventRepository implementation

    def add_many(self, items: list[EventItem]) -> None:
        """Add multiple event items in a transaction for better performance."""
        if not items:
            return

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Use transaction for better performance
            cursor.execute("BEGIN TRANSACTION")
            try:
                cursor.executemany(
                    """
                    INSERT INTO events (timestamp, level, source, message, event_id, friendly_message)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    [
                        (
                            item.timestamp.isoformat()
                            if hasattr(item.timestamp, "isoformat")
                            else str(item.timestamp),
                            item.level,
                            item.source,
                            item.message,
                            getattr(item, "event_id", 0),
                            getattr(item, "friendly_message", None),
                        )
                        for item in items
                    ],
                )
                conn.commit()
                logger.debug(f"Added {len(items)} event items")
            except Exception as e:
                conn.rollback()
                logger.error(f"Error adding events: {e}")
                raise
        except Exception as e:
            logger.error(f"Error in add_many: {e}")
            raise
        finally:
            conn.close()

    def recent(self, limit: int = 100) -> list[EventItem]:
        """Get recent event items with optimized query."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT timestamp, level, source, message, event_id, friendly_message
                FROM events
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (limit,),
            )

            items = []
            for row in cursor.fetchall():
                try:
                    items.append(
                        EventItem(
                            timestamp=datetime.fromisoformat(row[0]),
                            level=row[1],
                            source=row[2],
                            message=row[3],
                            event_id=row[4] if row[4] else 0,
                            friendly_message=row[5] if len(row) > 5 else None,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Error parsing event: {e}")
                    continue

            return items
        except Exception as e:
            logger.error(f"Error querying recent events: {e}")
            return []
        finally:
            conn.close()

    def get_by_level(self, level: str, limit: int = 100) -> list[EventItem]:
        """Get events filtered by level"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT timestamp, level, source, message, event_id, friendly_message
                FROM events
                WHERE level = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (level, limit),
            )

            items = []
            for row in cursor.fetchall():
                try:
                    items.append(
                        EventItem(
                            timestamp=datetime.fromisoformat(row[0]),
                            level=row[1],
                            source=row[2],
                            message=row[3],
                            event_id=row[4] if row[4] else 0,
                            friendly_message=row[5] if len(row) > 5 else None,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Error parsing event: {e}")
                    continue

            return items
        except Exception as e:
            logger.error(f"Error querying events by level: {e}")
            return []
        finally:
            conn.close()

    def get_by_source(self, source: str, limit: int = 100) -> list[EventItem]:
        """Get events filtered by source"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT timestamp, level, source, message, event_id, friendly_message
                FROM events
                WHERE source = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (source, limit),
            )

            items = []
            for row in cursor.fetchall():
                try:
                    items.append(
                        EventItem(
                            timestamp=datetime.fromisoformat(row[0]),
                            level=row[1],
                            source=row[2],
                            message=row[3],
                            event_id=row[4] if row[4] else 0,
                            friendly_message=row[5] if len(row) > 5 else None,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Error parsing event: {e}")
                    continue

            return items
        except Exception as e:
            logger.error(f"Error querying events by source: {e}")
            return []
        finally:
            conn.close()

    # ============ Event Summary Cache ============

    def get_event_summary(
        self, source: str, event_id: int, signature: str
    ) -> dict | None:
        """
        Get a cached event summary from the database.

        Args:
            source: Event source/provider
            event_id: Windows event ID
            signature: SHA256 hash prefix of the event message

        Returns:
            dict with summary fields if found, None otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT table_summary, title, severity_label, what_happened, 
                       what_you_can_do, tech_notes
                FROM event_summaries
                WHERE source = ? AND event_id = ? AND signature = ?
                LIMIT 1
                """,
                (source, event_id, signature),
            )

            row = cursor.fetchone()
            if row:
                return {
                    "table_summary": row[0],
                    "title": row[1],
                    "severity_label": row[2],
                    "what_happened": row[3],
                    "what_you_can_do": row[4],
                    "tech_notes": row[5] or "",
                    "event_id": event_id,
                    "source": source,
                }
            return None
        except Exception as e:
            logger.error(f"Error getting event summary: {e}")
            return None
        finally:
            conn.close()

    def save_event_summary(
        self, source: str, event_id: int, signature: str, summary: dict
    ) -> bool:
        """
        Save an event summary to the database cache.

        Args:
            source: Event source/provider
            event_id: Windows event ID
            signature: SHA256 hash prefix of the event message
            summary: dict or EventSummary with summary fields

        Returns:
            True if saved successfully, False otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Handle both dict and EventSummary objects
            if hasattr(summary, "to_dict"):
                data = summary.to_dict()
            else:
                data = summary

            cursor.execute(
                """
                INSERT OR REPLACE INTO event_summaries 
                (source, event_id, signature, table_summary, title, severity_label,
                 what_happened, what_you_can_do, tech_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source,
                    event_id,
                    signature,
                    data.get("table_summary", ""),
                    data.get("title", ""),
                    data.get("severity_label", "Minor"),
                    data.get("what_happened", ""),
                    data.get("what_you_can_do", ""),
                    data.get("tech_notes", ""),
                ),
            )
            conn.commit()
            logger.debug(f"Saved event summary: source={source}, event_id={event_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving event summary: {e}")
            return False
        finally:
            conn.close()

    # ===========================================================================
    # Event Explanations Cache (2-level: full and simplified)
    # ===========================================================================

    def get_event_explanation(
        self,
        provider: str,
        event_id: int,
        message_hash: str,
        detail_level: str = "full",
        locale: str = "en",
    ) -> dict | None:
        """
        Get cached event explanation.

        Args:
            provider: Event provider/source
            event_id: Windows event ID
            message_hash: Hash of event message (first 12 chars of MD5)
            detail_level: "full" or "simple"
            locale: Language code

        Returns:
            Cached explanation dict or None if not found/expired
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT title, what_happened, why_it_happened, what_it_affects,
                       is_normal, risk_level, what_to_do, when_to_worry,
                       technical_brief, simplified_text, ai_provider, created_at, ttl_seconds
                FROM event_explanations
                WHERE provider = ? AND event_id = ? AND detail_level = ? 
                      AND locale = ? AND message_hash = ?
                LIMIT 1
                """,
                (provider, event_id, detail_level, locale, message_hash),
            )

            row = cursor.fetchone()
            if row:
                # Check TTL
                created_at = (
                    datetime.fromisoformat(row[11]) if row[11] else datetime.now()
                )
                ttl = row[12] or 86400
                age_seconds = (datetime.now() - created_at).total_seconds()

                if age_seconds > ttl:
                    # Expired, delete and return None
                    cursor.execute(
                        "DELETE FROM event_explanations WHERE provider = ? AND event_id = ? "
                        "AND detail_level = ? AND locale = ? AND message_hash = ?",
                        (provider, event_id, detail_level, locale, message_hash),
                    )
                    conn.commit()
                    return None

                return {
                    "title": row[0],
                    "what_happened": row[1],
                    "why_it_happened": json.loads(row[2]) if row[2] else [],
                    "what_it_affects": json.loads(row[3]) if row[3] else [],
                    "is_normal": bool(row[4]),
                    "risk_level": row[5],
                    "what_to_do": json.loads(row[6]) if row[6] else [],
                    "when_to_worry": json.loads(row[7]) if row[7] else [],
                    "technical_brief": row[8],
                    "simplified_text": row[9],
                    "ai_provider": row[10],
                    "cached": True,
                }
            return None
        except Exception as e:
            logger.error(f"Error getting event explanation: {e}")
            return None
        finally:
            conn.close()

    def save_event_explanation(
        self,
        provider: str,
        event_id: int,
        message_hash: str,
        explanation: dict,
        detail_level: str = "full",
        locale: str = "en",
        ai_provider: str = "groq",
        token_count: int = 0,
        ttl_seconds: int = 86400,
    ) -> bool:
        """
        Save event explanation to cache.

        Args:
            provider: Event provider/source
            event_id: Windows event ID
            message_hash: Hash of event message
            explanation: Explanation dict with all fields
            detail_level: "full" or "simple"
            locale: Language code
            ai_provider: Which AI generated this
            token_count: Tokens used
            ttl_seconds: Cache TTL (default 24 hours)

        Returns:
            True if saved successfully
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO event_explanations 
                (provider, event_id, detail_level, locale, message_hash,
                 title, what_happened, why_it_happened, what_it_affects,
                 is_normal, risk_level, what_to_do, when_to_worry,
                 technical_brief, simplified_text, ai_provider, token_count, ttl_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider,
                    event_id,
                    detail_level,
                    locale,
                    message_hash,
                    explanation.get("title", ""),
                    explanation.get("what_happened", explanation.get("answer", "")),
                    json.dumps(explanation.get("why_it_happened", [])),
                    json.dumps(explanation.get("what_it_affects", [])),
                    1 if explanation.get("is_normal", True) else 0,
                    explanation.get("risk_level", "low"),
                    json.dumps(
                        explanation.get(
                            "what_to_do", explanation.get("what_to_do_now", [])
                        )
                    ),
                    json.dumps(
                        explanation.get(
                            "when_to_worry",
                            explanation.get("follow_up_suggestions", []),
                        )
                    ),
                    explanation.get("technical_brief", ""),
                    explanation.get("simplified_text", ""),
                    ai_provider,
                    token_count,
                    ttl_seconds,
                ),
            )
            conn.commit()
            logger.debug(
                f"Saved event explanation: {provider}:{event_id} ({detail_level})"
            )
            return True
        except Exception as e:
            logger.error(f"Error saving event explanation: {e}")
            return False
        finally:
            conn.close()

    def cleanup_expired_explanations(self, max_age_days: int = 7) -> int:
        """
        Remove expired explanations from cache.

        Args:
            max_age_days: Maximum age in days

        Returns:
            Number of rows deleted
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM event_explanations 
                WHERE julianday('now') - julianday(created_at) > ?
                """,
                (max_age_days,),
            )
            deleted = cursor.rowcount
            conn.commit()
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} expired event explanations")
            return deleted
        except Exception as e:
            logger.error(f"Error cleaning up explanations: {e}")
            return 0
        finally:
            conn.close()

    def cleanup(self) -> None:
        """Cleanup resources"""
        logger.info("SQLite repository cleanup complete")
