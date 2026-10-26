"""
Telemetry system for tracking API usage, cache metrics, and data analytics.
Stores metrics in SQLite for local analysis.
"""

import asyncio
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Any, Self


class TelemetryDB:
    """SQLite-backed telemetry database for API usage tracking"""

    def __init__(self, db_path: Path | None = None, retention_days: int = 30):
        if db_path is None:
            db_path = Path.home() / ".cache" / "dc_mar_sdk" / "telemetry.db"

        self.db_path = Path(db_path)
        self.retention_days = retention_days
        self._last_prune_at = 0.0
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize telemetry database schema"""
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    endpoint TEXT NOT NULL,
                    method TEXT NOT NULL,
                    status_code INTEGER,
                    response_time_ms REAL,
                    bytes_sent INTEGER,
                    bytes_received INTEGER,
                    cached BOOLEAN DEFAULT 0,
                    error_message TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    backend TEXT NOT NULL,
                    hits INTEGER,
                    misses INTEGER,
                    entries INTEGER,
                    size_bytes INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS endpoint_popularity (
                    endpoint TEXT PRIMARY KEY,
                    call_count INTEGER DEFAULT 0,
                    total_response_time_ms REAL DEFAULT 0.0,
                    avg_response_time_ms REAL DEFAULT 0.0,
                    error_count INTEGER DEFAULT 0,
                    last_called REAL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS data_summary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    total_requests INTEGER,
                    total_bytes_received INTEGER,
                    cache_hit_rate REAL,
                    avg_response_time_ms REAL
                )
                """
            )
            self._prune_retained_data(conn)
            conn.commit()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Open a short-lived connection that is always closed after each operation."""
        conn = sqlite3.connect(self.db_path, timeout=5)
        try:
            conn.execute("PRAGMA busy_timeout = 5000")
            yield conn
        finally:
            conn.close()

    def _prune_retained_data(self, conn: sqlite3.Connection) -> None:
        """Bound historical metric storage while retaining recent operational data."""
        cutoff = time.time() - (self.retention_days * 86400)
        for table in ("api_requests", "cache_metrics", "data_summary"):
            conn.execute(f"DELETE FROM {table} WHERE timestamp < ?", (cutoff,))
        conn.execute("DELETE FROM endpoint_popularity WHERE last_called < ?", (cutoff,))

    def record_request(
        self,
        endpoint: str,
        method: str = "GET",
        status_code: int | None = None,
        response_time_ms: float | None = None,
        bytes_sent: int = 0,
        bytes_received: int = 0,
        cached: bool = False,
        error_message: str | None = None,
    ) -> None:
        """Record an API request"""
        with self._connection() as conn:
            now = time.time()
            if now - self._last_prune_at >= 3600:
                self._prune_retained_data(conn)
                self._last_prune_at = now
            conn.execute(
                """
                INSERT INTO api_requests
                (timestamp, endpoint, method, status_code, response_time_ms,
                 bytes_sent, bytes_received, cached, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    endpoint,
                    method,
                    status_code,
                    response_time_ms,
                    bytes_sent,
                    bytes_received,
                    cached,
                    error_message,
                ),
            )

            # Update endpoint popularity
            conn.execute(
                """
                INSERT INTO endpoint_popularity
                (endpoint, call_count, total_response_time_ms, avg_response_time_ms, last_called, error_count)
                VALUES (?, 1, ?, ?, ?, ?)
                ON CONFLICT(endpoint) DO UPDATE SET
                    call_count = call_count + 1,
                    total_response_time_ms = total_response_time_ms + excluded.total_response_time_ms,
                    avg_response_time_ms =
                        (total_response_time_ms + excluded.total_response_time_ms) / (call_count + 1),
                    last_called = ?,
                    error_count = error_count + ?
                """,
                (
                    endpoint,
                    response_time_ms or 0,
                    response_time_ms or 0,
                    now,
                    1 if error_message else 0,
                    now,
                    1 if error_message else 0,
                ),
            )

            conn.commit()

    async def async_record_request(
        self,
        endpoint: str,
        method: str = "GET",
        status_code: int | None = None,
        response_time_ms: float | None = None,
        bytes_sent: int = 0,
        bytes_received: int = 0,
        cached: bool = False,
        error_message: str | None = None,
    ) -> None:
        """Record request telemetry without blocking an async caller."""
        await asyncio.to_thread(
            self.record_request,
            endpoint,
            method,
            status_code,
            response_time_ms,
            bytes_sent,
            bytes_received,
            cached,
            error_message,
        )

    def record_cache_metrics(
        self,
        backend: str,
        hits: int,
        misses: int,
        entries: int,
        size_bytes: int = 0,
    ) -> None:
        """Record cache metrics snapshot"""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO cache_metrics
                (timestamp, backend, hits, misses, entries, size_bytes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (time.time(), backend, hits, misses, entries, size_bytes),
            )
            conn.commit()

    def get_api_stats(self, hours: int = 24) -> dict[str, Any]:
        """Get API statistics for the last N hours"""
        cutoff_time = time.time() - (hours * 3600)

        with self._connection() as conn:
            cursor = conn.cursor()

            # Total requests
            cursor.execute(
                "SELECT COUNT(*) FROM api_requests WHERE timestamp > ?",
                (cutoff_time,),
            )
            total_requests = cursor.fetchone()[0]

            # Cached requests
            cursor.execute(
                "SELECT COUNT(*) FROM api_requests WHERE timestamp > ? AND cached = 1",
                (cutoff_time,),
            )
            cached_requests = cursor.fetchone()[0]

            # Total bytes
            cursor.execute(
                "SELECT SUM(bytes_received) FROM api_requests WHERE timestamp > ?",
                (cutoff_time,),
            )
            total_bytes = cursor.fetchone()[0] or 0

            # Average response time
            cursor.execute(
                "SELECT AVG(response_time_ms) FROM api_requests WHERE timestamp > ? AND response_time_ms IS NOT NULL",
                (cutoff_time,),
            )
            avg_response_time = cursor.fetchone()[0] or 0

            # Error count
            cursor.execute(
                "SELECT COUNT(*) FROM api_requests WHERE timestamp > ? AND error_message IS NOT NULL",
                (cutoff_time,),
            )
            error_count = cursor.fetchone()[0]

            cache_hit_rate = (cached_requests / total_requests * 100) if total_requests > 0 else 0

            return {
                "period_hours": hours,
                "total_requests": total_requests,
                "cached_requests": cached_requests,
                "cache_hit_rate": cache_hit_rate,
                "total_bytes_received": total_bytes,
                "avg_response_time_ms": avg_response_time,
                "error_count": error_count,
            }

    async def async_get_api_stats(self, hours: int = 24) -> dict[str, Any]:
        """Read API statistics without blocking an async caller."""
        return await asyncio.to_thread(self.get_api_stats, hours)

    def get_endpoint_popularity(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get most frequently called endpoints"""
        with self._connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    endpoint,
                    call_count,
                    avg_response_time_ms,
                    error_count,
                    datetime(last_called, 'unixepoch') as last_called_dt
                FROM endpoint_popularity
                ORDER BY call_count DESC
                LIMIT ?
                """,
                (limit,),
            )

            return [dict(row) for row in cursor.fetchall()]

    async def async_get_endpoint_popularity(self, limit: int = 10) -> list[dict[str, Any]]:
        """Read endpoint popularity without blocking an async caller."""
        return await asyncio.to_thread(self.get_endpoint_popularity, limit)

    def get_endpoint_error_rates(self, hours: int = 24, limit: int = 20) -> list[dict[str, Any]]:
        """Get endpoint-level request, error, and latency metrics for a recent window."""
        cutoff_time = time.time() - (hours * 3600)
        with self._connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    endpoint,
                    COUNT(*) AS request_count,
                    SUM(CASE WHEN error_message IS NOT NULL THEN 1 ELSE 0 END) AS error_count,
                    AVG(response_time_ms) AS avg_response_time_ms,
                    SUM(bytes_received) AS total_bytes_received
                FROM api_requests
                WHERE timestamp > ?
                GROUP BY endpoint
                ORDER BY request_count DESC
                LIMIT ?
                """,
                (cutoff_time, limit),
            )
            rows = []
            for row in cursor.fetchall():
                request_count = row["request_count"] or 0
                error_count = row["error_count"] or 0
                error_rate = (error_count / request_count * 100) if request_count > 0 else 0.0
                rows.append(
                    {
                        "endpoint": row["endpoint"],
                        "request_count": request_count,
                        "error_count": error_count,
                        "error_rate": round(error_rate, 2),
                        "avg_response_time_ms": row["avg_response_time_ms"] or 0.0,
                        "total_bytes_received": row["total_bytes_received"] or 0,
                    }
                )
            return rows

    async def async_get_endpoint_error_rates(self, hours: int = 24, limit: int = 20) -> list[dict[str, Any]]:
        """Read endpoint error rates without blocking an async caller."""
        return await asyncio.to_thread(self.get_endpoint_error_rates, hours, limit)

    def get_timeseries_stats(self, hours: int = 24, bucket: str = "hour") -> list[dict[str, Any]]:
        """Get request and error trends over time."""
        cutoff_time = time.time() - (hours * 3600)
        bucket_fmt_map = {
            "hour": "%Y-%m-%dT%H:00:00Z",
            "day": "%Y-%m-%d",
        }
        if bucket not in bucket_fmt_map:
            raise ValueError("bucket must be one of: hour, day")
        bucket_fmt = bucket_fmt_map[bucket]

        with self._connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    strftime(?, timestamp, 'unixepoch') AS bucket_start,
                    COUNT(*) AS request_count,
                    SUM(CASE WHEN error_message IS NOT NULL THEN 1 ELSE 0 END) AS error_count,
                    SUM(CASE WHEN cached = 1 THEN 1 ELSE 0 END) AS cached_count,
                    AVG(response_time_ms) AS avg_response_time_ms,
                    SUM(bytes_received) AS total_bytes_received
                FROM api_requests
                WHERE timestamp > ?
                GROUP BY bucket_start
                ORDER BY bucket_start ASC
                """,
                (bucket_fmt, cutoff_time),
            )
            return [dict(row) for row in cursor.fetchall()]

    async def async_get_timeseries_stats(self, hours: int = 24, bucket: str = "hour") -> list[dict[str, Any]]:
        """Read timeseries statistics without blocking an async caller."""
        return await asyncio.to_thread(self.get_timeseries_stats, hours, bucket)

    def detect_anomalies(self, hours: int = 24) -> list[dict[str, Any]]:
        """Return lightweight anomaly signals from recent telemetry."""
        stats = self.get_api_stats(hours)
        anomalies: list[dict[str, Any]] = []

        total_requests = stats.get("total_requests", 0) or 0
        error_count = stats.get("error_count", 0) or 0
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0.0
        if total_requests >= 20 and error_rate >= 5.0:
            anomalies.append(
                {
                    "kind": "high_error_rate",
                    "severity": "warning",
                    "message": f"Error rate is {error_rate:.1f}% over the last {hours}h",
                    "value": round(error_rate, 2),
                    "threshold": 5.0,
                }
            )

        avg_response_time_ms = stats.get("avg_response_time_ms", 0) or 0.0
        if total_requests >= 20 and avg_response_time_ms >= 1200.0:
            anomalies.append(
                {
                    "kind": "high_latency",
                    "severity": "warning",
                    "message": f"Average latency is {avg_response_time_ms:.0f}ms over the last {hours}h",
                    "value": round(avg_response_time_ms, 2),
                    "threshold": 1200.0,
                }
            )

        cache_hit_rate = stats.get("cache_hit_rate", 0) or 0.0
        if total_requests >= 20 and cache_hit_rate <= 5.0:
            anomalies.append(
                {
                    "kind": "low_cache_hit_rate",
                    "severity": "info",
                    "message": f"Cache hit rate is low at {cache_hit_rate:.1f}% over the last {hours}h",
                    "value": round(cache_hit_rate, 2),
                    "threshold": 5.0,
                }
            )

        return anomalies

    async def async_detect_anomalies(self, hours: int = 24) -> list[dict[str, Any]]:
        """Detect anomalies without blocking an async caller."""
        return await asyncio.to_thread(self.detect_anomalies, hours)

    def get_cache_efficiency(self, hours: int = 24) -> dict[str, Any]:
        """Analyze cache efficiency metrics"""
        cutoff_time = time.time() - (hours * 3600)

        with self._connection() as conn:
            cursor = conn.cursor()

            # Get latest cache metrics
            cursor.execute(
                """
                SELECT backend, hits, misses, entries, size_bytes
                FROM cache_metrics
                WHERE timestamp > ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (cutoff_time,),
            )

            row = cursor.fetchone()
            if not row:
                return {"message": "No cache metrics available"}

            backend, hits, misses, entries, size_bytes = row
            total_requests = hits + misses
            hit_rate = (hits / total_requests * 100) if total_requests > 0 else 0

            return {
                "backend": backend,
                "cache_hits": hits,
                "cache_misses": misses,
                "cache_entries": entries,
                "cache_size_bytes": size_bytes,
                "hit_rate": hit_rate,
                "total_cache_requests": total_requests,
            }

    def get_data_summary(self) -> dict[str, Any]:
        """Get overall data collection summary"""
        with self._connection() as conn:
            cursor = conn.cursor()

            # All-time stats
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_requests,
                    SUM(bytes_received) as total_bytes,
                    COUNT(CASE WHEN cached = 1 THEN 1 END) as cached_count,
                    AVG(response_time_ms) as avg_response_time
                FROM api_requests
                """
            )

            stats = cursor.fetchone()
            total_requests = stats[0] or 0
            total_bytes = stats[1] or 0
            cached_count = stats[2] or 0
            avg_response_time = stats[3] or 0

            hit_rate = (cached_count / total_requests * 100) if total_requests > 0 else 0

            cursor.execute("SELECT COUNT(DISTINCT endpoint) FROM api_requests")
            unique_endpoints = cursor.fetchone()[0]

            return {
                "total_api_requests": total_requests,
                "total_data_received_bytes": total_bytes,
                "total_data_received_mb": round(total_bytes / (1024 * 1024), 2),
                "cache_hit_rate": hit_rate,
                "avg_response_time_ms": avg_response_time,
                "unique_endpoints": unique_endpoints,
                "db_path": str(self.db_path),
            }

    async def async_get_data_summary(self) -> dict[str, Any]:
        """Read data summary without blocking an async caller."""
        return await asyncio.to_thread(self.get_data_summary)

    def clear_old_records(self, days: int = 30) -> int:
        """Remove records older than N days"""
        cutoff_time = time.time() - (days * 86400)

        with self._connection() as conn:
            cursor = conn.cursor()

            cursor.execute("DELETE FROM api_requests WHERE timestamp < ?", (cutoff_time,))
            cursor.execute("DELETE FROM cache_metrics WHERE timestamp < ?", (cutoff_time,))

            deleted = cursor.rowcount
            conn.commit()

            return deleted


class RequestMetrics:
    """Context manager for tracking individual request metrics"""

    def __init__(self, telemetry_db: TelemetryDB, endpoint: str, method: str = "GET"):
        self.telemetry_db = telemetry_db
        self.endpoint = endpoint
        self.method = method
        self.start_time: float | None = None
        self.bytes_sent: int = 0
        self.bytes_received: int = 0
        self.cached: bool = False
        self.status_code: int | None = None
        self.error_message: str | None = None

    def __enter__(self) -> Self:
        self.start_time = time.time()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        response_time_ms = (time.time() - self.start_time) * 1000 if self.start_time else 0

        if exc_type is not None:
            self.error_message = str(exc_val)

        self.telemetry_db.record_request(
            endpoint=self.endpoint,
            method=self.method,
            status_code=self.status_code,
            response_time_ms=response_time_ms,
            bytes_sent=self.bytes_sent,
            bytes_received=self.bytes_received,
            cached=self.cached,
            error_message=self.error_message,
        )

    async def __aenter__(self) -> Self:
        self.start_time = time.time()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        response_time_ms = (time.time() - self.start_time) * 1000 if self.start_time else 0

        if exc_type is not None:
            self.error_message = str(exc_val)

        await self.telemetry_db.async_record_request(
            endpoint=self.endpoint,
            method=self.method,
            status_code=self.status_code,
            response_time_ms=response_time_ms,
            bytes_sent=self.bytes_sent,
            bytes_received=self.bytes_received,
            cached=self.cached,
            error_message=self.error_message,
        )
