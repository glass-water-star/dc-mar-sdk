from pathlib import Path

import httpx
import pytest

from dc_mar_sdk.client.mar import MARClient
from dc_mar_sdk.dashboard.app import app
from dc_mar_sdk.settings import get_settings
from dc_mar_sdk.telemetry import TelemetryDB


def _seed_telemetry(db_path: Path) -> None:
    telemetry = TelemetryDB(db_path=db_path)
    telemetry.record_request(
        endpoint="/autocomplete",
        status_code=200,
        response_time_ms=120.0,
        bytes_received=1024,
        cached=False,
    )
    telemetry.record_request(
        endpoint="/autocomplete",
        status_code=500,
        response_time_ms=180.0,
        bytes_received=256,
        error_message="boom",
    )
    telemetry.record_request(
        endpoint="/locations/{address}/{zones}/{geo}",
        status_code=200,
        response_time_ms=95.0,
        bytes_received=2048,
        cached=True,
    )


@pytest.mark.asyncio
async def test_insights_endpoints(tmp_path):
    db_path = tmp_path / "telemetry.db"
    _seed_telemetry(db_path)

    settings = get_settings()
    settings.telemetry_db_path = str(db_path)
    MARClient._SETTINGS.telemetry_db_path = str(db_path)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        home = await client.get("/")
        assert home.status_code == 200
        assert "DC MAR SDK Insights Dashboard" in home.text

        overview = await client.get("/api/insights/overview?hours=24")
        assert overview.status_code == 200
        overview_json = overview.json()
        assert "api_stats" in overview_json
        assert "cache_stats" in overview_json
        assert "data_summary" in overview_json
        assert "anomalies" in overview_json
        assert overview_json["api_stats"]["total_requests"] >= 3

        timeseries = await client.get("/api/insights/timeseries?hours=24&bucket=hour")
        assert timeseries.status_code == 200
        timeseries_json = timeseries.json()
        assert timeseries_json["bucket"] == "hour"
        assert len(timeseries_json["points"]) >= 1

        endpoints = await client.get("/api/insights/endpoints?hours=24&limit=20&sort_by=request_count")
        assert endpoints.status_code == 200
        rows = endpoints.json()["rows"]
        assert len(rows) >= 1
        assert "endpoint" in rows[0]
        assert "error_rate" in rows[0]

        anomalies = await client.get("/api/insights/anomalies?hours=24")
        assert anomalies.status_code == 200
        assert "anomalies" in anomalies.json()


@pytest.mark.asyncio
async def test_dashboard_autocomplete_uses_configured_api_key(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "mar_api_key", "dashboard-key")
    monkeypatch.setattr(MARClient._SETTINGS, "mar_api_key", "dashboard-key")
    observed_keys = []

    async def fake_autocomplete(self, address):
        observed_keys.append(self.api_key)
        return [address]

    monkeypatch.setattr(MARClient, "autocomplete", fake_autocomplete)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/autocomplete", json={"address": "1600 Pennsylvania"})

    assert response.status_code == 200
    assert response.json() == {"suggestions": ["1600 Pennsylvania"]}
    assert observed_keys == ["dashboard-key"]
