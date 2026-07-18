"""FastAPI dashboard for telemetry and insights (pure Python + vanilla JS)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from dc_mar_sdk import MARClient
from dc_mar_sdk.settings import get_settings
from dc_mar_sdk.telemetry import TelemetryDB

app = FastAPI(
    title="DC MAR SDK Dashboard",
    description="Web dashboard for DC MAR API client telemetry and insights",
    version="0.2.0",
)

_BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(_BASE_DIR / "static")), name="static")


class AutocompleteRequest(BaseModel):
    address: str


def _get_telemetry_db() -> TelemetryDB:
    settings = get_settings()
    if settings.telemetry_db_path:
        return TelemetryDB(Path(settings.telemetry_db_path))
    return TelemetryDB()


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve dashboard home page."""
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/stats")
async def get_api_stats(hours: int = Query(24, ge=1, le=24 * 30)):
    """Get API usage statistics."""
    client = MARClient()
    return await client.get_api_stats(hours=hours)


@app.get("/api/cache/stats")
async def get_cache_stats():
    """Get cache statistics."""
    client = MARClient()
    return await client.get_cache_stats()


@app.post("/api/cache/clear")
async def clear_cache():
    """Clear the cache."""
    client = MARClient()
    await client.clear_cache()
    return {"status": "cleared"}


@app.get("/api/endpoints")
async def get_endpoints(limit: int = Query(10, ge=1, le=100)):
    """Get endpoint popularity."""
    client = MARClient()
    return await client.get_endpoint_popularity(limit=limit)


@app.get("/api/data-summary")
async def get_data_summary():
    """Get data collection summary."""
    client = MARClient()
    return await client.get_data_summary()


@app.post("/api/autocomplete")
async def autocomplete(request: AutocompleteRequest):
    """Query autocomplete endpoint."""
    client = MARClient()
    try:
        suggestions = await client.autocomplete(request.address)
        return {"suggestions": suggestions}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/insights/overview")
async def get_insights_overview(hours: int = Query(24, ge=1, le=24 * 30)):
    """Get consolidated insight payload for dashboard cards."""
    client = MARClient()
    telemetry = _get_telemetry_db()
    return {
        "hours": hours,
        "api_stats": await client.get_api_stats(hours=hours),
        "cache_stats": await client.get_cache_stats(),
        "data_summary": await client.get_data_summary(),
        "anomalies": telemetry.detect_anomalies(hours=hours),
    }


@app.get("/api/insights/timeseries")
async def get_insights_timeseries(
    hours: int = Query(24, ge=1, le=24 * 30),
    bucket: Literal["hour", "day"] = Query("hour"),
):
    """Get request and error trend series."""
    telemetry = _get_telemetry_db()
    return {
        "hours": hours,
        "bucket": bucket,
        "points": telemetry.get_timeseries_stats(hours=hours, bucket=bucket),
    }


@app.get("/api/insights/endpoints")
async def get_insights_endpoints(
    hours: int = Query(24, ge=1, le=24 * 30),
    limit: int = Query(20, ge=1, le=100),
    sort_by: Literal["request_count", "error_rate"] = Query("request_count"),
):
    """Get endpoint insight metrics with optional sorting mode."""
    telemetry = _get_telemetry_db()
    rows = telemetry.get_endpoint_error_rates(hours=hours, limit=limit)
    if sort_by == "error_rate":
        rows.sort(key=lambda row: (row["error_rate"], row["request_count"]), reverse=True)
    return {"hours": hours, "limit": limit, "sort_by": sort_by, "rows": rows}


@app.get("/api/insights/anomalies")
async def get_insights_anomalies(hours: int = Query(24, ge=1, le=24 * 30)):
    """Get anomaly signals derived from telemetry heuristics."""
    telemetry = _get_telemetry_db()
    return {"hours": hours, "anomalies": telemetry.detect_anomalies(hours=hours)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
