# Dashboard Plan (Pure Python, current-state based)

## Goal
Build a production-usable insights dashboard using the existing Python stack only:
- FastAPI backend
- Server-rendered HTML/CSS + light vanilla JS (no Node/front-end build chain)
- Existing MAR client + telemetry/cache subsystems

This plan starts from current implementation in `dashboard/app.py` and current data sources in:
- `src/dc_mar_sdk/client/mar.py`
- `src/dc_mar_sdk/telemetry/tracking.py`
- `src/dc_mar_sdk/cache/backends.py`

## Current State (as-is)
- Dashboard exists at top-level `dashboard/app.py` (not under `src/dc_mar_sdk/...`).
- Endpoints implemented:
  - `GET /api/stats`
  - `GET /api/cache/stats`
  - `POST /api/cache/clear`
  - `GET /api/endpoints`
  - `GET /api/data-summary`
  - `POST /api/autocomplete`
- UI is single inline HTML string + fetch calls.
- Data is aggregate-only; no time-series drilldown, filtering, or insight narratives.
- Docs/run paths are inconsistent (`dc_mar_sdk.dashboard.app:app` vs actual `dashboard.app:app`).

## Constraints
- Pure Python for now.
- Reuse current telemetry tables and client methods first; avoid schema churn unless needed.
- Keep robots-safe behavior in any live data collection workflows.

## Product Scope (MVP Insights Dashboard)
1. **Operational health**
   - Requests, errors, avg latency, cache hit rate, bytes received.
2. **Usage insight**
   - Endpoint popularity trends and error-prone endpoints.
3. **Data collection progress**
   - Total data received, unique endpoints seen, last activity.
4. **Actionability**
   - Fast troubleshooting panel (e.g., "high 429 rate", "cache miss spike").

## Architecture Plan
### Phase 1 — Normalize and package the dashboard surface
1. Move dashboard into package path:
   - `src/dc_mar_sdk/dashboard/app.py`
   - `src/dc_mar_sdk/dashboard/templates/*` (Jinja2 templates)
2. Remove `sys.path` mutation in dashboard code.
3. Add canonical entrypoint docs:
   - `uv run uvicorn dc_mar_sdk.dashboard.app:app --reload`
4. Keep existing JSON API endpoints stable during migration.

### Phase 2 — Backend insight API expansion (still Python-only)
Add read-only endpoints focused on insight questions:
1. `GET /api/insights/overview?hours=24`
   - Combines existing stats + cache + data summary in one payload.
2. `GET /api/insights/timeseries?hours=24&bucket=hour`
   - Request count, error count, avg latency over time.
3. `GET /api/insights/endpoints?hours=24&limit=20`
   - Popularity + error-rate ordering modes.
4. `GET /api/insights/anomalies?hours=24`
   - Rule-based flags (simple Python heuristics):
     - error_rate > threshold
     - cache_hit_rate drop
     - latency spike

Implementation source: add query methods in `TelemetryDB` first, then expose via FastAPI routes.

### Phase 3 — UI/UX (server-rendered + vanilla JS only)
1. Replace inline HTML string with template files.
2. Add dashboard tabs:
   - Overview
   - Endpoint insights
   - Cache insights
   - Data growth
3. Add controls:
   - Time window selector (1h/24h/7d)
   - Auto-refresh toggle
4. Add simple charting options (pure Python-friendly):
   - Option A (recommended now): JSON + lightweight browser-side SVG rendering in vanilla JS
   - Option B: plotly via CDN (no build step) if acceptable

### Phase 4 — Insight quality hardening
1. Defensive handling for empty telemetry DB.
2. Add clear "no data yet" onboarding state.
3. Add endpoint-level error breakdowns.
4. Add API + UI tests for insight endpoints and key rendering states.

## Data Model / Query Additions (planned)
Telemetry tables already available:
- `api_requests`
- `endpoint_popularity`
- `cache_metrics`
- `data_summary`

Planned additions in code (not schema-first):
- Query helpers in `TelemetryDB`:
  - `get_timeseries_stats(hours, bucket)`
  - `get_endpoint_error_rates(hours, limit)`
  - `detect_anomalies(hours)`

Only add new tables if these queries prove insufficient.

## Milestones
1. **M1 (Packaging + parity):**
   - packaged dashboard path + docs fixed + old routes still working.
2. **M2 (Insight API):**
   - overview/timeseries/endpoints/anomalies endpoints added.
3. **M3 (Insight UI):**
   - multi-panel dashboard with filters + refresh.
4. **M4 (Quality):**
   - tests + docs + runbook.

## Acceptance Criteria
- Dashboard starts via packaged module path.
- No `sys.path` hacks in dashboard code.
- User can select a time window and see:
  - trend metrics
  - top endpoints
  - error/latency signals
- Dashboard remains pure Python + browser-native JS/CSS.
- Existing CLI/client telemetry features remain backward compatible.

## Immediate Next Steps (execution-ready)
1. Create `src/dc_mar_sdk/dashboard/` package and migrate `dashboard/app.py`.
2. Add Jinja2 template(s) and static file layout.
3. Implement `/api/insights/overview` and `/api/insights/timeseries`.
4. Update README run instructions to packaged path only.
5. Add targeted tests for new insight endpoints.

## Progress Update (2026-07-18)
- Product naming updated:
  - Published distribution: `dc-mar-sdk`
  - Python import path is `dc_mar_sdk`
- Completed:
  - Dashboard migrated to `src/dc_mar_sdk/dashboard/` with template/static assets.
  - New insights endpoints shipped:
    - `/api/insights/overview`
    - `/api/insights/timeseries`
    - `/api/insights/endpoints`
    - `/api/insights/anomalies`
  - README run path updated to packaged module.
  - Targeted dashboard insights tests added.
  - Full namespace cutover completed; legacy `dcdataapi` references removed.
  - Public console scripts renamed to `dc-mar-sdk-*`.
  - Packaging metadata now includes typed-package markers and project URLs.
  - Tag-based publish workflow added for PyPI.
- Next focus:
  - Geocoding quality heatmap first-pass workflow:
    - derive match-quality points from cached/search outputs,
    - add larger address sampling ingestion,
    - render map-friendly GeoJSON layer in dashboard.
  - Automation shipped:
    - `dc-mar-sdk-geocode-collect` entrypoint now collects robots-safe challenging samples
      and writes summary + GeoJSON artifacts for heatmap analysis.
  - Remaining OSS adoption gaps:
    - single-source versioning,
    - changelog/version bump enforcement,
    - GitHub Release automation,
    - maintainer/CODEOWNERS/deprecation policy,
    - pydantic deprecation cleanup.
