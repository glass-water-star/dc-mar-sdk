import pytest

from dc_mar_sdk.cache.backends import InMemoryCache
from dc_mar_sdk.client.mar import MARClient


@pytest.mark.asyncio
async def test_cache_key_determinism_same_scope():
    client1 = MARClient(api_key="SOMEKEY123", cache_backend=InMemoryCache(), enable_telemetry=False)
    client2 = MARClient(api_key="SOMEKEY123", cache_backend=InMemoryCache(), enable_telemetry=False)

    k1 = client1._make_cache_key("/test", {"a": 1, "b": 2})
    k2 = client2._make_cache_key("/test", {"b": 2, "a": 1})

    assert k1 == k2


@pytest.mark.asyncio
async def test_cache_key_isolation_different_keys_or_base():
    c_a = MARClient(api_key="KEY_ALPHA", cache_backend=InMemoryCache(), enable_telemetry=False)
    c_b = MARClient(api_key="KEY_BETA", cache_backend=InMemoryCache(), enable_telemetry=False)

    # Same endpoint/params but different api keys -> different namespaces
    k_a = c_a._make_cache_key("/search", {"q": "x"})
    k_b = c_b._make_cache_key("/search", {"q": "x"})
    assert k_a != k_b

    # Same key but different base URL should also differ
    c_c = MARClient(api_key="KEY_ALPHA", cache_backend=InMemoryCache(), enable_telemetry=False)
    # mutate client's BASE_URL to simulate different environment/version
    c_c.BASE_URL = c_c.BASE_URL + "/alt"
    k_c = c_c._make_cache_key("/search", {"q": "x"})
    assert k_a != k_c


@pytest.mark.asyncio
async def test_no_plaintext_api_key_in_key():
    secret = "SUPERSECRET_API_KEY"
    client = MARClient(api_key=secret, cache_backend=InMemoryCache(), enable_telemetry=False)
    key = client._make_cache_key("/x", {"p": "v"})
    assert secret not in key
