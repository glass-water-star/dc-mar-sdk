import pytest

from dc_mar_sdk.client.mar import MARClient
from dc_mar_sdk.cache.backends import InMemoryCache


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
