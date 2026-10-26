import pytest

from dc_mar_sdk.cache.backends import InMemoryCache
from dc_mar_sdk.client.mar import MARClient
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
    result2 = [{"properties": {"Score": 0.8, "MatchedAddress": "456 B St", "AddressId": "A2"}}]

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
    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.content = bytes(str(payload), "utf8")
        self.headers = headers or {}

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


class _RecordingTelemetry:
    def __init__(self):
        self.requests = []

    def record_request(self, **kwargs):
        self.requests.append(kwargs)

    async def async_record_request(self, **kwargs):
        self.record_request(**kwargs)


class _SequenceClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    async def request(self, *args, **kwargs):
        self.calls += 1
        return next(self.responses)


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
async def test_autocomplete_evicts_invalid_cached_payload(monkeypatch):
    cache = InMemoryCache()
    client = MARClient(api_key="dummy", cache_backend=cache, enable_telemetry=False)
    cache_key = client._make_cache_key("/autocomplete", {"address": "test"})
    await cache.set(cache_key, {"unexpected": "payload"})
    fake = _FakeClient({"Success": True, "Result": ["Fresh"]})

    async def _fake_get_http_client():
        return fake

    monkeypatch.setattr(client, "_get_http_client", _fake_get_http_client)

    assert await client.autocomplete("test") == ["Fresh"]
    assert await cache.get(cache_key) == ["Fresh"]


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


@pytest.mark.asyncio
async def test_autocomplete_rejects_response_missing_envelope_status(monkeypatch):
    client = MARClient(api_key="dummy", cache_backend=InMemoryCache(), enable_telemetry=False)
    fake = _FakeClient({"Result": ["unexpected"]})

    async def _fake_get_http_client():
        return fake

    monkeypatch.setattr(client, "_get_http_client", _fake_get_http_client)

    with pytest.raises(ValueError, match="missing required MAR envelope field"):
        await client.autocomplete("x")


@pytest.mark.asyncio
async def test_autocomplete_records_one_http_failure_with_actual_status(monkeypatch):
    client = MARClient(api_key="dummy", cache_backend=InMemoryCache(), enable_telemetry=False)
    client.enable_telemetry = True
    client.retry_max_attempts = 1
    telemetry = _RecordingTelemetry()
    client.telemetry_db = telemetry
    fake = _FakeClient({}, status_code=503)

    async def _fake_get_http_client():
        return fake

    monkeypatch.setattr(client, "_get_http_client", _fake_get_http_client)

    with pytest.raises(Exception, match="HTTP 503"):
        await client.autocomplete("x")

    assert len(telemetry.requests) == 1
    assert telemetry.requests[0]["status_code"] == 503
    assert telemetry.requests[0]["error_message"] == "HTTP 503"


@pytest.mark.asyncio
async def test_request_retries_transient_response_and_honors_retry_after(monkeypatch):
    client = MARClient(api_key="dummy", cache_backend=InMemoryCache(), enable_telemetry=False)
    fake = _SequenceClient(
        [
            _FakeResponse({}, status_code=503, headers={"Retry-After": "0.5"}),
            _FakeResponse({"Success": True, "Result": ["ok"]}),
        ]
    )
    delays = []

    async def _fake_get_http_client():
        return fake

    async def _record_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(client, "_get_http_client", _fake_get_http_client)
    monkeypatch.setattr("dc_mar_sdk.client.mar.sleep", _record_sleep)

    response = await client._send_request("GET", "https://example.test")

    assert response.status_code == 200
    assert fake.calls == 2
    assert delays == [0.5]
