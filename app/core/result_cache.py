"""
Simple in-memory cache with TTL for expensive operations.
Prevents repeated API calls (VirusTotal, Nmap) and reduces latency.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class ResultCache:
    """
    Thread-safe in-memory cache with time-to-live (TTL) support.
    Optionally persists to JSON for cross-session caching.
    """

    def __init__(
        self, default_ttl_seconds: int = 3600, persist_path: str | None = None
    ):
        """
        Args:
            default_ttl_seconds: Default cache entry lifetime (1 hour)
            persist_path: Optional JSON file path for persistence
        """
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._lock = Lock()
        self._default_ttl = timedelta(seconds=default_ttl_seconds)
        self._persist_path = Path(persist_path) if persist_path else None

        if self._persist_path and self._persist_path.exists():
            self._load_from_disk()

    def get(self, key: str) -> Any | None:
        """
        Retrieve value from cache if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if expired/missing
        """
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if datetime.now() < expiry:
                    logger.debug("Cache HIT: %s", key)
                    return value
                # Expired - remove it
                logger.debug("Cache EXPIRED: %s", key)
                del self._cache[key]

        logger.debug("Cache MISS: %s", key)
        return None

    def set(self, key: str, value: Any, ttl_seconds: int | None = None):
        """
        Store value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable for persistence)
            ttl_seconds: Custom TTL (uses default if None)
        """
        ttl = timedelta(seconds=ttl_seconds) if ttl_seconds else self._default_ttl
        expiry = datetime.now() + ttl

        with self._lock:
            self._cache[key] = (value, expiry)
            logger.debug("Cache SET: %s (TTL: %ss)", key, ttl.total_seconds())

        # Persist to disk if configured
        if self._persist_path:
            self._save_to_disk()

    def invalidate(self, key: str):
        """Remove entry from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache INVALIDATE: {key}")

    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache CLEARED: {count} entries removed")

        if self._persist_path and self._persist_path.exists():
            self._persist_path.unlink()

    def cleanup_expired(self):
        """Remove expired entries (call periodically)"""
        now = datetime.now()
        with self._lock:
            expired_keys = [
                k for k, (_, expiry) in self._cache.items() if now >= expiry
            ]
            for key in expired_keys:
                del self._cache[key]

            if expired_keys:
                logger.info(
                    f"Cache cleanup: removed {len(expired_keys)} expired entries"
                )

    def _save_to_disk(self):
        """Persist cache to JSON (only serializable values)"""
        try:
            with self._lock:
                serializable = {}
                for key, (value, expiry) in self._cache.items():
                    try:
                        # Test if value is JSON-serializable
                        json.dumps(value)
                        serializable[key] = {
                            "value": value,
                            "expiry": expiry.isoformat(),
                        }
                    except (TypeError, ValueError):
                        # Skip non-serializable entries
                        pass

            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(serializable, f, indent=2)

        except Exception as e:
            logger.exception(f"Failed to save cache to disk: {e}")

    def _load_from_disk(self):
        """Load cache from JSON"""
        try:
            with open(self._persist_path, encoding="utf-8") as f:
                data = json.load(f)

            now = datetime.now()
            loaded = 0

            with self._lock:
                for key, entry in data.items():
                    expiry = datetime.fromisoformat(entry["expiry"])
                    if now < expiry:
                        self._cache[key] = (entry["value"], expiry)
                        loaded += 1

            logger.info(f"Cache loaded from disk: {loaded} entries")

        except Exception as e:
            logger.exception(f"Failed to load cache from disk: {e}")

    @staticmethod
    def make_key(*args, **kwargs) -> str:
        """
        Generate cache key from arguments.

        Example:
            key = ResultCache.make_key("virustotal", file_hash="abc123")
        """
        parts = [str(arg) for arg in args]
        parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_str = ":".join(parts)

        # Hash long keys to keep them manageable
        if len(key_str) > 100:
            return hashlib.sha256(key_str.encode()).hexdigest()[:16]

        return key_str


# Global cache instances for different subsystems
_scan_cache: ResultCache | None = None
_vt_cache: ResultCache | None = None


def get_scan_cache() -> ResultCache:
    """Get global scan results cache (30min TTL)"""
    global _scan_cache
    if _scan_cache is None:
        _scan_cache = ResultCache(
            default_ttl_seconds=1800,  # 30 minutes
            persist_path="data/cache/scans.json",
        )
    return _scan_cache


def get_vt_cache() -> ResultCache:
    """Get VirusTotal results cache (1 hour TTL, persisted)"""
    global _vt_cache
    if _vt_cache is None:
        _vt_cache = ResultCache(
            default_ttl_seconds=3600,  # 1 hour
            persist_path="data/cache/virustotal.json",
        )
    return _vt_cache
