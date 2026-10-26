import pytest

from dc_mar_sdk.telemetry import TelemetryDB


@pytest.mark.asyncio
async def test_async_telemetry_recording_uses_worker_thread(tmp_path, monkeypatch):
    telemetry = TelemetryDB(tmp_path / "telemetry.db")
    dispatched = []

    async def controlled_to_thread(function, /, *args, **kwargs):
        dispatched.append(function.__name__)
        return function(*args, **kwargs)

    monkeypatch.setattr("dc_mar_sdk.telemetry.tracking.asyncio.to_thread", controlled_to_thread)

    await telemetry.async_record_request("/autocomplete", status_code=200)

    assert dispatched == ["record_request"]
    assert telemetry.get_api_stats()["total_requests"] == 1
