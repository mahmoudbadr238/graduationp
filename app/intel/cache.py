"""
Intel Cache - Thread-safe caching for threat intelligence results.

Stores lookup results to avoid repeated API calls.
Uses SQLite for persistence across sessions.
"""

import hashlib
import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached intelligence result."""
    key: str
    provider: str  # "virustotal", "abuseipdb", etc.
    lookup_type: str  # "file_hash", "url", "ip", "domain"
    result: dict
    verdict: str  # "clean", "suspicious", "malicious", "unknown"
    score: int  # 0-100
    timestamp: float
    ttl_hours: int = 24
    
    @property
    def is_expired(self) -> bool:
        age_hours = (time.time() - self.timestamp) / 3600
        return age_hours > self.ttl_hours


class IntelCache:
    """
    Thread-safe persistent cache for threat intelligence.
    
    Uses SQLite for durability and fast lookups.
    Default TTL: 24 hours for most results, 1 hour for "unknown".
    """
    
    _instance: Optional["IntelCache"] = None
    _lock = threading.Lock()
    
    DEFAULT_TTL_HOURS = 24
    UNKNOWN_TTL_HOURS = 1  # Re-check unknowns more frequently
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._db_path = self._get_db_path()
        self._init_db()
        self._initialized = True
        logger.info(f"IntelCache initialized: {self._db_path}")
    
    def _get_db_path(self) -> Path:
        """Get the database path in user's app data."""
        import sys
        if sys.platform == "win32":
            base = Path.home() / "AppData" / "Local" / "Sentinel"
        else:
            base = Path.home() / ".sentinel"
        base.mkdir(parents=True, exist_ok=True)
        return base / "intel_cache.db"
    
    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS intel_cache (
                    key TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    lookup_type TEXT NOT NULL,
                    result TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    ttl_hours INTEGER NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON intel_cache(timestamp)
            """)
            conn.commit()
    
    def _make_key(self, provider: str, lookup_type: str, value: str) -> str:
        """Create a unique cache key."""
        normalized = value.lower().strip()
        data = f"{provider}:{lookup_type}:{normalized}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def get(
        self, 
        provider: str, 
        lookup_type: str, 
        value: str
    ) -> Optional[CacheEntry]:
        """
        Get a cached result if available and not expired.
        
        Args:
            provider: Service name (virustotal, abuseipdb, etc.)
            lookup_type: Type of lookup (file_hash, url, ip, domain)
            value: The actual value looked up (hash, url, etc.)
        
        Returns:
            CacheEntry if found and valid, None otherwise
        """
        key = self._make_key(provider, lookup_type, value)
        
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM intel_cache WHERE key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                
                if row is None:
                    return None
                
                entry = CacheEntry(
                    key=row["key"],
                    provider=row["provider"],
                    lookup_type=row["lookup_type"],
                    result=json.loads(row["result"]),
                    verdict=row["verdict"],
                    score=row["score"],
                    timestamp=row["timestamp"],
                    ttl_hours=row["ttl_hours"],
                )
                
                if entry.is_expired:
                    # Delete expired entry
                    conn.execute("DELETE FROM intel_cache WHERE key = ?", (key,))
                    conn.commit()
                    return None
                
                return entry
                
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    def set(
        self,
        provider: str,
        lookup_type: str,
        value: str,
        result: dict,
        verdict: str,
        score: int,
        ttl_hours: Optional[int] = None,
    ) -> None:
        """
        Cache an intelligence result.
        
        Args:
            provider: Service name
            lookup_type: Type of lookup
            value: The value looked up
            result: Full result dict from provider
            verdict: Verdict string (clean, suspicious, malicious, unknown)
            score: Score 0-100
            ttl_hours: Override default TTL
        """
        key = self._make_key(provider, lookup_type, value)
        
        # Use shorter TTL for unknown results
        if ttl_hours is None:
            ttl_hours = (
                self.UNKNOWN_TTL_HOURS 
                if verdict == "unknown" 
                else self.DEFAULT_TTL_HOURS
            )
        
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO intel_cache 
                    (key, provider, lookup_type, result, verdict, score, timestamp, ttl_hours)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    key,
                    provider,
                    lookup_type,
                    json.dumps(result),
                    verdict,
                    score,
                    time.time(),
                    ttl_hours,
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of deleted."""
        try:
            with sqlite3.connect(self._db_path) as conn:
                # Delete entries where timestamp + (ttl_hours * 3600) < now
                cursor = conn.execute("""
                    DELETE FROM intel_cache 
                    WHERE timestamp + (ttl_hours * 3600) < ?
                """, (time.time(),))
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")
            return 0
    
    def clear(self) -> None:
        """Clear all cached entries."""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("DELETE FROM intel_cache")
                conn.commit()
        except Exception as e:
            logger.error(f"Cache clear error: {e}")


# Singleton getter
_cache: Optional[IntelCache] = None

def get_intel_cache() -> IntelCache:
    """Get the singleton intel cache instance."""
    global _cache
    if _cache is None:
        _cache = IntelCache()
    return _cache
