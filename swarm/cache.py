"""Search/extract result cache — SQLite-backed, keyed on backend + query.

Workers hit the same queries across runs (and across workers within a run),
so caching search + extract results cuts latency and Ollama cost. The cache
is transparent to workers: a cache hit still logs to the scratchpad exactly
like a live call.

Storage lives at ``~/.cache/swarm/cache.db`` (override with ``SWARM_CACHE_DIR``).
Disable entirely with ``SWARM_CACHE=0`` or per-call with ``no_cache=True``.

Usage:
    from swarm.cache import get_cache, cache_key

    cache = get_cache()
    key = cache_key("ddgs", "capital of france")
    hit = cache.get(key)          # None or the stored JSON string
    cache.set(key, result_json, ttl=86400)
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
import time
from pathlib import Path

_DEFAULT_DIR = Path.home() / ".cache" / "swarm"
_DEFAULT_TTL = int(os.environ.get("SWARM_CACHE_TTL", "86400"))
_MAX_ROWS = int(os.environ.get("SWARM_CACHE_MAX_ROWS", "10000"))

_GLOBAL_CACHE = None


def cache_enabled() -> bool:
    """True unless SWARM_CACHE=0 disables the cache."""
    return os.environ.get("SWARM_CACHE", "1") != "0"


def cache_dir() -> Path:
    """Resolve the cache directory (env override or default)."""
    return Path(os.environ.get("SWARM_CACHE_DIR", str(_DEFAULT_DIR)))


def cache_key(backend: str, query: str) -> str:
    """Deterministic key for a (backend, query) pair."""
    raw = f"{backend}|{query}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class Cache:
    """SQLite-backed key/value cache with TTL and a size sweep."""

    def __init__(self, path: Path | str | None = None, max_rows: int = _MAX_ROWS):
        self._path = Path(path) if path else (cache_dir() / "cache.db")
        self._max_rows = max_rows
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False, isolation_level=None)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at REAL NOT NULL,
                ttl INT NOT NULL
            )
        """)

    def get(self, key: str) -> str | None:
        """Return the cached value if present and unexpired, else None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT value, created_at, ttl FROM cache WHERE key = ?", (key,)
            ).fetchone()
            if not row:
                return None
            value, created_at, ttl = row
            if time.time() - created_at > ttl:
                self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                return None
            return value

    def set(self, key: str, value: str, ttl: int = _DEFAULT_TTL):
        """Store a value with a TTL in seconds."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, created_at, ttl) VALUES (?, ?, ?, ?)",
                (key, value, time.time(), ttl),
            )
            self._sweep()

    def _sweep(self):
        """Delete expired rows and cap total rows at max_rows."""
        self._conn.execute("DELETE FROM cache WHERE created_at + ttl < ?", (time.time(),))
        count = self._conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        if count > self._max_rows:
            self._conn.execute(
                "DELETE FROM cache WHERE key IN ("
                "SELECT key FROM cache ORDER BY created_at ASC LIMIT ?)",
                (count - self._max_rows,),
            )

    def clear(self):
        """Delete all cached entries."""
        with self._lock:
            self._conn.execute("DELETE FROM cache")
            self._conn.commit()

    def close(self):
        """Close the underlying SQLite connection."""
        self._conn.close()


def get_cache() -> Cache:
    """Return the process-wide cache instance (lazily created)."""
    global _GLOBAL_CACHE
    if _GLOBAL_CACHE is None:
        _GLOBAL_CACHE = Cache()
    return _GLOBAL_CACHE


def reset_cache():
    """Drop the process-wide cache instance (used by tests)."""
    global _GLOBAL_CACHE
    if _GLOBAL_CACHE is not None:
        _GLOBAL_CACHE.close()
        _GLOBAL_CACHE = None
