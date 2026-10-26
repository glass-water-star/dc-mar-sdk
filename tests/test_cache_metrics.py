import asyncio

import pytest

from dc_mar_sdk.cache.backends import CacheManager, InMemoryCache, RedisCache, SQLiteCache
from dc_mar_sdk.client.mar import MARClient


@pytest.mark.asyncio
async def test_normalized_cache_stats_shape_and_values(tmp_path):
    # Use in-memory cache to avoid filesystem
    cache = InMemoryCache()
    client = MARClient(api_key="fake", cache_backend=cache, enable_telemetry=False)

    # prime cache: set one key
    await client.cache_manager.set("k1", {"x": 1}, ttl_seconds=None)

    # one miss
    await client.cache_manager.get("no-such-key")
    # one hit
    await client.cache_manager.get("k1")

    stats = await client.get_cache_stats()

    # Basic normalized shape assertions
    assert isinstance(stats, dict)
    expected_keys = {
        "backend",
        "entries",
        "hits",
        "misses",
        "total_requests",
        "hit_rate",
        "size_bytes",
        "backend_details",
    }
    assert expected_keys.issubset(stats.keys())

    # Check values make sense
    assert stats["entries"] == 1
    assert stats["hits"] >= 1
    assert stats["misses"] >= 1
    assert stats["total_requests"] == stats["hits"] + stats["misses"]
    assert 0.0 <= stats["hit_rate"] <= 100.0


@pytest.mark.asyncio
async def test_cache_stats_without_requests_returns_zero_rates():
    cache = InMemoryCache()
    client = MARClient(api_key="fake", cache_backend=cache, enable_telemetry=False)

    # no gets performed
    stats = await client.get_cache_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["total_requests"] == 0
    assert stats["hit_rate"] == 0.0


@pytest.mark.asyncio
async def test_sqlite_cache_persists_hits_and_misses(tmp_path):
    cache = SQLiteCache(tmp_path / "cache.db")

    await cache.set("cached", {"value": 1})
    assert await cache.get("missing") is None
    assert await cache.get("cached") == {"value": 1}

    stats = await cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1


@pytest.mark.asyncio
async def test_sqlite_cache_public_operations_preserve_behavior(tmp_path):
    cache = SQLiteCache(tmp_path / "cache.db")

    await cache.set("keep", {"value": 1})
    await cache.set("delete", {"value": 2})
    await cache.delete("delete")

    assert await cache.get("delete") is None
    assert await cache.get("keep") == {"value": 1}

    await cache.clear()
    assert await cache.get("keep") is None
    assert (await cache.get_stats())["entries"] == 0


@pytest.mark.asyncio
async def test_sqlite_operations_dispatch_work_without_blocking_event_loop(tmp_path, monkeypatch):
    cache = SQLiteCache(tmp_path / "cache.db")
    manager = CacheManager(cache)
    worker_dispatched = asyncio.Event()
    release_worker = asyncio.Event()
    worker_functions: list[str] = []

    async def controlled_to_thread(function, /, *args, **kwargs):
        worker_functions.append(function.__name__)
        worker_dispatched.set()
        await release_worker.wait()
        return function(*args, **kwargs)

    monkeypatch.setattr("dc_mar_sdk.cache.backends.asyncio.to_thread", controlled_to_thread)

    pending_set = asyncio.create_task(cache.set("key", {"value": 1}))
    await worker_dispatched.wait()

    loop_progressed = asyncio.Event()

    async def mark_loop_progress() -> None:
        loop_progressed.set()

    await asyncio.create_task(mark_loop_progress())
    assert loop_progressed.is_set()
    assert not pending_set.done()

    release_worker.set()
    await pending_set
    assert await cache.get("key") == {"value": 1}
    await cache.delete("key")
    await cache.clear()
    await cache.get_stats()
    assert await manager.invalidate_pattern("key*") == 0

    assert worker_functions == ["_set", "_get", "_delete", "_clear", "_get_stats", "_invalidate_pattern"]


@pytest.mark.asyncio
async def test_redis_cache_operations_are_offloaded_to_worker_threads():
    class FakeRedis:
        def __init__(self):
            self.values = {}

        def get(self, key):
            return self.values.get(key)

        def set(self, key, value):
            self.values[key] = value

        def setex(self, key, ttl, value):
            self.values[key] = value

        def delete(self, key):
            self.values.pop(key, None)

        def flushdb(self):
            self.values.clear()

        def info(self):
            return {"used_memory_human": "1K", "connected_clients": 1, "total_commands_processed": 1}

        def dbsize(self):
            return len(self.values)

        def keys(self, pattern):
            return list(self.values)

    cache = RedisCache.__new__(RedisCache)
    cache.redis_client = FakeRedis()
    manager = CacheManager(cache)

    await cache.set("key", {"value": 1})
    assert await cache.get("key") == {"value": 1}
    assert (await cache.get_stats())["entries"] == 1
    assert await manager.invalidate_pattern("*") == 1
    assert await cache.get("key") is None
