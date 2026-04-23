"""Unit tests for SQLite repositories."""

# nosec B101 - assert statements are expected in pytest test files

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from backend.core.types import EventItem, ScanRecord, ScanType
from backend.infra.sqlite_repo import SqliteRepo
from backend.platform import paths as paths_mod


@pytest.fixture
def temp_repo():
    """Create a temporary repository for testing."""
    # Create temp database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Create repo with temp path
    repo = SqliteRepo()
    repo.db_path = db_path
    repo.init()

    yield repo

    # Cleanup - Windows requires explicit connection closure before file deletion
    # Force garbage collection to close any lingering SQLite connections
    import gc

    repo = None  # Release reference to repo object
    gc.collect()  # Force garbage collection

    # On Windows, SQLite may keep file locks - retry deletion with small delay
    import time

    max_retries = 3
    for attempt in range(max_retries):
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
            break
        except PermissionError:
            if attempt < max_retries - 1:
                time.sleep(0.1)  # Wait 100ms before retry
                gc.collect()  # Try GC again
            # On final attempt, just pass - temp files will be cleaned by OS eventually


def test_sqlite_repo_uses_platform_data_dir(tmp_path, monkeypatch):
    home = tmp_path / "home"
    xdg_data = tmp_path / "xdg-data"

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(paths_mod.Path, "home", staticmethod(lambda: home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data))
    paths_mod.get_app_paths.cache_clear()

    repo = SqliteRepo()

    assert Path(repo.db_path) == xdg_data / "sentinel" / "sentinel.db"
    paths_mod.get_app_paths.cache_clear()


class TestSqliteRepo:
    """Test SQLite repository functionality."""

    def test_init_creates_tables(self, temp_repo):
        """Test that init() creates required tables."""
        import sqlite3

        with sqlite3.connect(temp_repo.db_path) as conn:
            cursor = conn.cursor()

            # Check scans table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='scans'"
            )
            assert cursor.fetchone() is not None

            # Check events table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
            )
            assert cursor.fetchone() is not None

    def test_add_scan_record(self, temp_repo):
        """Test adding a scan record."""
        record = ScanRecord(
            id=None,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            type=ScanType.NETWORK,
            target="192.168.1.0/24",
            status="completed",
            findings={"hosts": [{"ip": "192.168.1.1"}]},
            meta={"fast": True},
        )

        scan_id = temp_repo.add(record)
        assert scan_id is not None
        assert scan_id > 0

    def test_all_returns_scan_records(self, temp_repo):
        """Test retrieving all scan records."""
        # Add multiple records
        for i in range(3):
            record = ScanRecord(
                id=None,
                started_at=datetime.now(),
                finished_at=datetime.now(),
                type=ScanType.FILE,
                target=f"file{i}.exe",
                status="completed",
                findings={},
                meta={},
            )
            temp_repo.add(record)

        # Retrieve all
        records = temp_repo.all()
        assert len(records) == 3
        assert all(isinstance(r, ScanRecord) for r in records)

    def test_add_many_events(self, temp_repo):
        """Test adding multiple events."""
        events = [
            EventItem(
                timestamp=datetime.now(),
                level="INFO",
                source="System",
                message=f"Test event {i}",
            )
            for i in range(5)
        ]

        temp_repo.add_many(events)

        # Retrieve and verify
        retrieved = temp_repo.recent(limit=10)
        assert len(retrieved) == 5
        assert all(isinstance(e, EventItem) for e in retrieved)

    def test_recent_events_limit(self, temp_repo):
        """Test that recent() respects limit parameter."""
        # Add 10 events
        events = [
            EventItem(
                timestamp=datetime.now(),
                level="INFO",
                source="System",
                message=f"Event {i}",
            )
            for i in range(10)
        ]
        temp_repo.add_many(events)

        # Retrieve with limit
        retrieved = temp_repo.recent(limit=5)
        assert len(retrieved) == 5

    def test_scan_records_ordered_by_date(self, temp_repo):
        """Test that scan records are returned in descending order."""
        import time

        # Add records with slight delay
        for i in range(3):
            record = ScanRecord(
                id=None,
                started_at=datetime.now(),
                finished_at=None,
                type=ScanType.URL,
                target=f"http://example{i}.com",
                status="pending",
                findings=None,
                meta=None,
            )
            temp_repo.add(record)
            time.sleep(0.01)  # Small delay to ensure different timestamps

        # Retrieve all
        records = temp_repo.all()

        # Check order (most recent first)
        for i in range(len(records) - 1):
            assert records[i].started_at >= records[i + 1].started_at
