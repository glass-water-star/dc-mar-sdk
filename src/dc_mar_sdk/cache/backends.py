"""
Cache abstraction layer supporting multiple backends.
Provides a common interface for SQLite, Redis, and in-memory caching.
"""

import json
import sqlite3
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional


class CacheBackend(ABC):
    """Abstract base class for cache backends"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from cache by key"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store a value in cache with optional TTL"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a key from cache"""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all entries from cache"""
        pass

    @abstractmethod
    async def get_stats(self) -> dict:
        """Get cache statistics (hits, misses, size, etc.)"""
        pass


class InMemoryCache(CacheBackend):
    """Simple in-memory cache backend with TTL support"""

    def __init__(self):
        self.store: dict[str, tuple[Any, Optional[float]]] = {}
        self.hits = 0
        self.misses = 0

    async def get(self, key: str) -> Optional[Any]:
        """Get value from memory, checking TTL"""
        if key not in self.store:
            self.misses += 1
            return None

        value, expiry = self.store[key]
        if expiry is not None and time.time() > expiry:
            del self.store[key]
            self.misses += 1
            return None

        self.hits += 1
        return value

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store value in memory with optional TTL"""
        expiry = None
        if ttl_seconds is not None:
            expiry = time.time() + ttl_seconds
        self.store[key] = (value, expiry)

    async def delete(self, key: str) -> None:
        """Delete key from memory"""
        self.store.pop(key, None)

    async def clear(self) -> None:
        """Clear all entries"""
        self.store.clear()

    async def get_stats(self) -> dict:
        """Return cache statistics"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "backend": "in_memory",
            "entries": len(self.store),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "total_requests": total_requests,
        }


class SQLiteCache(CacheBackend):
    """SQLite-backed cache backend with TTL support"""

    def __init__(self, db_path: Path = None):
        if db_path is None:
            db_path = Path.home() / ".cache" / "dc_mar_sdk" / "cache.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL,
                    hits INTEGER DEFAULT 0,
                    misses INTEGER DEFAULT 0
                )
                """
            )
            conn.commit()

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve value from SQLite cache"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if key exists and not expired
            cursor.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()

            if row is None:
                cursor.execute(
                    "UPDATE cache SET misses = misses + 1 WHERE key = ?",
                    (key,)
                )
                conn.commit()
                return None

            value_json, expires_at = row

            # Check expiry
            if expires_at is not None and time.time() > expires_at:
                cursor.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
                return None

            # Update hit count
            cursor.execute(
                "UPDATE cache SET hits = hits + 1 WHERE key = ?",
                (key,)
            )
            conn.commit()

            return json.loads(value_json)

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store value in SQLite cache"""
        with sqlite3.connect(self.db_path) as conn:
            expires_at = None
            if ttl_seconds is not None:
                expires_at = time.time() + ttl_seconds

            conn.execute(
                """
                INSERT OR REPLACE INTO cache (key, value, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (key, json.dumps(value), time.time(), expires_at)
            )
            conn.commit()

    async def delete(self, key: str) -> None:
        """Delete key from SQLite cache"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()

    async def clear(self) -> None:
        """Clear all entries from SQLite cache"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache")
            conn.commit()

    async def get_stats(self) -> dict:
        """Get cache statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM cache")
            entry_count = cursor.fetchone()[0]

            cursor.execute("SELECT SUM(hits), SUM(misses) FROM cache")
            hits, misses = cursor.fetchone()
            hits = hits or 0
            misses = misses or 0

            total_requests = hits + misses
            hit_rate = (hits / total_requests * 100) if total_requests > 0 else 0

            # Get database size
            size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0

            return {
                "backend": "sqlite",
                "db_path": str(self.db_path),
                "entries": entry_count,
                "hits": hits,
                "misses": misses,
                "hit_rate": hit_rate,
                "total_requests": total_requests,
                "size_bytes": size_bytes,
            }


class RedisCache(CacheBackend):
    """Redis cache backend (optional, requires redis package)"""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        try:
            import redis
            self.redis_client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
            self.redis_client.ping()
        except ImportError:
            raise ImportError("Redis backend requires 'redis' package. Install with: pip install redis")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Redis at {host}:{port}: {e}")

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve value from Redis"""
        value = self.redis_client.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store value in Redis"""
        value_json = json.dumps(value)
        if ttl_seconds is not None:
            self.redis_client.setex(key, ttl_seconds, value_json)
        else:
            self.redis_client.set(key, value_json)

    async def delete(self, key: str) -> None:
        """Delete key from Redis"""
        self.redis_client.delete(key)

    async def clear(self) -> None:
        """Clear all entries from Redis"""
        self.redis_client.flushdb()

    async def get_stats(self) -> dict:
        """Get Redis statistics"""
        info = self.redis_client.info()
        return {
            "backend": "redis",
            "entries": self.redis_client.dbsize(),
            "used_memory": info.get("used_memory_human", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "total_commands_processed": info.get("total_commands_processed", 0),
        }


class CacheManager:
    """High-level cache manager with invalidation tracking"""

    def __init__(self, backend: CacheBackend = None):
        """Initialize cache manager with optional backend (defaults to SQLite)"""
        self.backend = backend or SQLiteCache()

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        return await self.backend.get(key)

    async def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        """Set value in cache with TTL (default 1 hour)"""
        await self.backend.set(key, value, ttl_seconds)

    async def delete(self, key: str) -> None:
        """Delete value from cache"""
        await self.backend.delete(key)

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.

        Supported pattern syntax (compatible with Redis-style simple globs):
        - '*' matches any number of characters
        - '?' matches a single character
        - exact key (no wildcard) will delete that single key

        Behavior per backend:
        - Redis: Uses redis.keys(pattern) (unchanged)
        - InMemory: Matches keys using the same simple glob rules and deletes them
        - SQLite: Converts glob to SQL LIKE (with escaping) and deterministically deletes only matching rows

        Returns the number of keys deleted. Does NOT perform a full-table
        clear unless the pattern explicitly matches every key (for example
        '*').
        """
        if not pattern:
            raise ValueError("pattern must be a non-empty string")

        # Redis keeps existing behavior
        if isinstance(self.backend, RedisCache):
            keys = self.backend.redis_client.keys(pattern)
            for key in keys:
                await self.backend.delete(key)
            return len(keys)

        # Helper: compile simple glob pattern (Redis-style) to predicate
        def _glob_matches(pattern: str, key: str) -> bool:
            # Fast path for exact match
            if "*" not in pattern and "?" not in pattern:
                return pattern == key

            # Translate glob to regex in a safe way without importing re at module level
            # Escape regex metacharacters from pattern except our wildcards
            import re

            esc = re.escape(pattern)
            # re.escape will backslash '*' and '?', revert those so we can translate
            esc = esc.replace(r"\*", "*").replace(r"\?", "?")
            # now replace glob wildcards with regex
            esc = esc.replace("*", ".*").replace("?", ".")
            # anchor
            regex = f"^{esc}$"
            return re.match(regex, key) is not None

        # InMemory backend: iterate keys and delete matches
        if isinstance(self.backend, InMemoryCache):
            keys_to_delete = [k for k in list(self.backend.store.keys()) if _glob_matches(pattern, k)]
            for k in keys_to_delete:
                await self.backend.delete(k)
            return len(keys_to_delete)

        # SQLite backend: convert glob to SQL LIKE safely and delete only matching rows
        if isinstance(self.backend, SQLiteCache):
            # Convert glob pattern to SQL LIKE pattern
            # Escaping: escape existing '%' '_' and backslash in the pattern first
            sql_pattern = pattern.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            # translate wildcards
            sql_pattern = sql_pattern.replace("*", "%").replace("?", "_")

            # Use a deterministic two-step approach: select matching keys, then delete by exact key
            with sqlite3.connect(self.backend.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT key FROM cache WHERE key LIKE ? ESCAPE '\\'",
                    (sql_pattern,)
                )
                rows = cursor.fetchall()
                keys = [r[0] for r in rows]
                if not keys:
                    return 0

                cursor.executemany("DELETE FROM cache WHERE key = ?", [(k,) for k in keys])
                conn.commit()
                return len(keys)

        # Unknown backend: be conservative
        raise NotImplementedError(f"invalidate_pattern not implemented for backend type {type(self.backend)}")

    async def clear(self) -> None:
        """Clear all cache entries"""
        await self.backend.clear()

    async def get_stats(self) -> dict:
        """Get cache statistics with a normalized, client-facing shape.

        Normalized schema (stable for consumers):
          - backend: string identifier of backend (e.g., 'sqlite', 'redis', 'in_memory')
          - entries: int | None
          - hits: int
          - misses: int
          - total_requests: int
          - hit_rate: float (percentage 0-100)
          - size_bytes: int | None
          - backend_details: dict (any additional backend-specific fields)

        This function calls the backend's get_stats() and normalizes the
        result so consumers (and the MAR client) don't need to access
        backend internals and can rely on a stable shape.
        """
        raw = await self.backend.get_stats()

        # Defensive normalization with defaults
        backend = raw.get("backend") if isinstance(raw, dict) else None
        backend = backend or getattr(self.backend, "__class__", type(self.backend)).__name__.lower()

        def to_int(v):
            try:
                return int(v)
            except Exception:
                return None

        hits = to_int(raw.get("hits") if isinstance(raw, dict) else None) or 0
        misses = to_int(raw.get("misses") if isinstance(raw, dict) else None) or 0
        total_requests = to_int(raw.get("total_requests") if isinstance(raw, dict) else None)
        if total_requests is None:
            total_requests = hits + misses

        # hit_rate may be provided by backend, otherwise compute
        hit_rate = None
        if isinstance(raw, dict) and raw.get("hit_rate") is not None:
            try:
                hit_rate = float(raw.get("hit_rate"))
            except Exception:
                hit_rate = None

        if hit_rate is None:
            hit_rate = (hits / total_requests * 100) if total_requests > 0 else 0.0

        entries = to_int(raw.get("entries") if isinstance(raw, dict) else None)
        size_bytes = to_int(raw.get("size_bytes") if isinstance(raw, dict) else None)

        # Collect remaining backend-specific details
        backend_details = {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                if k in {"backend", "entries", "hits", "misses", "total_requests", "hit_rate", "size_bytes"}:
                    continue
                backend_details[k] = v

        normalized = {
            "backend": backend,
            "entries": entries,
            "hits": hits,
            "misses": misses,
            "total_requests": total_requests,
            "hit_rate": float(round(hit_rate, 2)) if hit_rate is not None else None,
            "size_bytes": size_bytes,
            "backend_details": backend_details,
        }

        return normalized
