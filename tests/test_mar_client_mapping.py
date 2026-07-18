import pytest

from dc_mar_sdk.client.mar import MARClient
from dc_mar_sdk.cache.backends import InMemoryCache
from dc_mar_sdk.models.core import SearchResponse


@pytest.mark.asyncio
async def test_build_search_response_various_shapes():
    client = MARClient(api_key="dummy", cache_backend=InMemoryCache(), enable_telemetry=False)

    # Case 1: result with nested address -> properties
    result1 = {
        "addresses": [
            {
                "address": {
                    "properties": {
                        "_Score": 0.9,
                        "FullAddress": "123 A St",
                        "MarId": "M1",
                        "AddressId": "A1",
                        "Latitude": 38.0,
                        "Longitude": -77.0,
                    }
                }
            }
        ]
    }

    resp1 = client._build_search_response_from_result(result1)
    assert isinstance(resp1, SearchResponse)
    assert resp1.total_matches == 1
    m = resp1.matches[0]
    assert m.MatchedAddress == "123 A St"
    assert m.Score == 0.9
    assert m.MarId == "M1"
    assert m.AddressId == "A1"
    assert m.Latitude == 38.0
    assert m.Longitude == -77.0

    # Case 2: result as list with properties directly
    result2 = [
        {"properties": {"Score": 0.8, "MatchedAddress": "456 B St", "AddressId": "A2"}}
    ]

    resp2 = client._build_search_response_from_result(result2)
    assert resp2.total_matches == 1
    m2 = resp2.matches[0]
    # Score aliasing: 'Score' should map to _Score field via aliasing behavior
    assert m2.MatchedAddress == "456 B St"
    assert m2.AddressId == "A2"

    # Case 3: malformed entries are ignored
    result3 = {"addresses": ["string", 123, {"properties": "notadict"}]}
    resp3 = client._build_search_response_from_result(result3)
    assert resp3.total_matches == 0
    assert resp3.matches == []


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.content = bytes(str(payload), "utf8")

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class _FakeClient:
    def __init__(self, payload, status_code=200):
        self._resp = _FakeResponse(payload, status_code=status_code)

    async def get(self, *args, **kwargs):
        return self._resp


@pytest.mark.asyncio
async def test_autocomplete_envelope_and_cache(monkeypatch):
    cache = InMemoryCache()
    client = MARClient(api_key="dummy", cache_backend=cache, enable_telemetry=False)

    # First response: Success envelope with list result
    payload = {"Success": True, "Result": ["One", "Two"]}
    fake = _FakeClient(payload)

    async def _fake_get_http_client():
        return fake

    monkeypatch.setattr(client, "_get_http_client", _fake_get_http_client)

    suggestions = await client.autocomplete("test")
    assert suggestions == ["One", "Two"]

    # Now ensure cached path returns without calling http client
    async def _error_get():
        raise RuntimeError("Should not be called when cached")

    monkeypatch.setattr(client, "_get_http_client", _error_get)

    suggestions2 = await client.autocomplete("test")
    assert suggestions2 == ["One", "Two"]


@pytest.mark.asyncio
async def test_autocomplete_envelope_failure(monkeypatch):
    cache = InMemoryCache()
    client = MARClient(api_key="dummy", cache_backend=cache, enable_telemetry=False)

    payload = {"Success": False, "Message": "bad"}
    fake = _FakeClient(payload)

    async def _fake_get_http_client():
        return fake

    monkeypatch.setattr(client, "_get_http_client", _fake_get_http_client)

    with pytest.raises(ValueError):
        await client.autocomplete("x")
