from pathlib import Path

import pytest

from dc_mar_sdk.cache.backends import CacheManager, InMemoryCache, SQLiteCache


@pytest.mark.asyncio
async def test_inmemory_invalidation():
    backend = InMemoryCache()
    mgr = CacheManager(backend)

    await mgr.set("ns:item1", {"v": 1})
    await mgr.set("ns:item2", {"v": 2})
    await mgr.set("other:item", {"v": 3})

    # Invalidate namespace prefix
    deleted = await mgr.invalidate_pattern("ns:*")
    assert deleted == 2

    # Confirm deleted keys are gone and other remains
    assert await mgr.get("ns:item1") is None
    assert await mgr.get("ns:item2") is None
    assert await mgr.get("other:item") == {"v": 3}


@pytest.mark.asyncio
async def test_sqlite_invalidation(tmp_path: Path):
    db_path = tmp_path / "cache_test.db"

    backend = SQLiteCache(db_path=db_path)
    mgr = CacheManager(backend)

    await mgr.set("ns:item1", {"v": 1})
    await mgr.set("ns:item2", {"v": 2})
    await mgr.set("other:item", {"v": 3})

    # Invalidate pattern
    deleted = await mgr.invalidate_pattern("ns:*")
    assert deleted == 2

    assert await mgr.get("ns:item1") is None
    assert await mgr.get("ns:item2") is None
    assert await mgr.get("other:item") == {"v": 3}
