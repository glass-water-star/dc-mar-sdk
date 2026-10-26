import pytest

from dc_mar_sdk.cache.backends import InMemoryCache
from dc_mar_sdk.client.mar import MARClient


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.content = bytes(str(payload), "utf8")
        self.headers = {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class _FakeClient:
    def __init__(self, payload, status_code=200):
        self._resp = _FakeResponse(payload, status_code=status_code)

    async def request(self, *args, **kwargs):
        return self._resp


@pytest.mark.asyncio
async def test_use_cache_override_bypasses_cache(monkeypatch):
    cache = InMemoryCache()
    client = MARClient(api_key="dummy", cache_backend=cache, enable_telemetry=False)

    payload = {"Success": True, "Result": ["A"]}
    fake = _FakeClient(payload)

    async def _fake_get_http_client():
        return fake

    monkeypatch.setattr(client, "_get_http_client", _fake_get_http_client)

    # Prime the cache with first call
    first = await client.autocomplete("q")
    assert first == ["A"]

    # Now simulate a failing HTTP client but expect cached value when use_cache=True
    async def _error_get():
        raise RuntimeError("Should not be called when cached")

    monkeypatch.setattr(client, "_get_http_client", _error_get)

    cached = await client.autocomplete("q")
    assert cached == ["A"]

    # If we explicitly disable cache for the call, the HTTP client should be invoked (and fail)
    with pytest.raises(RuntimeError):
        await client.autocomplete("q", use_cache=False)


@pytest.mark.asyncio
async def test_refresh_forces_api_call_and_updates_cache(monkeypatch):
    cache = InMemoryCache()
    client = MARClient(api_key="dummy", cache_backend=cache, enable_telemetry=False)

    payload1 = {"Success": True, "Result": ["One"]}
    payload2 = {"Success": True, "Result": ["Two"]}

    fake1 = _FakeClient(payload1)
    fake2 = _FakeClient(payload2)

    async def _get1():
        return fake1

    async def _get2():
        return fake2

    # First call primes cache
    monkeypatch.setattr(client, "_get_http_client", _get1)
    r1 = await client.autocomplete("r")
    assert r1 == ["One"]

    # Now swap to client that returns different payload and call refresh=True
    monkeypatch.setattr(client, "_get_http_client", _get2)
    r2 = await client.autocomplete("r", refresh=True)
    assert r2 == ["Two"]

    # Subsequent cached call should return updated value
    monkeypatch.setattr(client, "_get_http_client", lambda: (_ for _ in ()).throw(RuntimeError("should not be called")))
    r3 = await client.autocomplete("r")
    assert r3 == ["Two"]


@pytest.mark.asyncio
async def test_ttl_override_respected(monkeypatch):
    cache = InMemoryCache()
    client = MARClient(api_key="dummy", cache_backend=cache, enable_telemetry=False)

    payload = {"Success": True, "Result": ["Z"]}
    fake = _FakeClient(payload)

    async def _fake_get_http_client():
        return fake

    monkeypatch.setattr(client, "_get_http_client", _fake_get_http_client)

    # call with a short TTL and ensure it is stored; InMemoryCache doesn't expose expiry but
    # we at least exercise the path and ensure no errors when a ttl override is provided.
    res = await client.autocomplete("ttl", ttl_seconds=2)
    assert res == ["Z"]
