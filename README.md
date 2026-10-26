# DC MAR SDK

[![Lint](https://github.com/glass-water-star/dc-mar-sdk/actions/workflows/lint.yml/badge.svg)](https://github.com/glass-water-star/dc-mar-sdk/actions/workflows/lint.yml) [![Unit tests](https://github.com/glass-water-star/dc-mar-sdk/actions/workflows/tests.yml/badge.svg)](https://github.com/glass-water-star/dc-mar-sdk/actions/workflows/tests.yml) [![Smoke (manual)](https://github.com/glass-water-star/dc-mar-sdk/actions/workflows/smoke.yml/badge.svg)](https://github.com/glass-water-star/dc-mar-sdk/actions/workflows/smoke.yml)

A comprehensive Python SDK for the DC DataGate Master Address Repository (MAR) API with intelligent caching, telemetry tracking, and modern tooling.

The smoke badge points to a manual workflow_dispatch job and is not required to pass on pull requests by default.

## Features

- **Type-Safe API SDK** — Pydantic models generated from OpenAPI spec
- **Pluggable Caching** — SQLite (default), Redis, or in-memory backends with TTL and invalidation

Caching supports deterministic namespace/pattern invalidation across backends: Redis-style globbing is supported ("*" and "?" wildcards). SQLite and the in-memory backend perform safe, non-destructive pattern invalidation by matching keys (SQLite converts globs to SQL LIKE with proper escaping). Use CacheManager.invalidate_pattern(pattern) to remove keys matching a pattern. Note: pattern="*" will delete all entries (use clear() if you want an explicit full wipe).

Caching keys are namespaced deterministically by client scope to avoid cross-environment pollution: the namespace incorporates the effective API base URL (including API version/path) and a non-reversible SHA256 digest of the API key. Keys are prefixed with "dc-mar-sdk:v1" to keep cache scope deterministic by SDK version and API key scope.
- **Request Telemetry** — Track API usage, bytes transferred, cache hits/misses, endpoint popularity
- **Web Dashboard** — FastAPI-based interface for cache status, telemetry visualization, and queries
- **CLI Tool** — Command-line interface for querying, cache management, and data export
- **Modern Python Stack** — uv, pyproject.toml, Pydantic v2, FastAPI

## Quick Start

> New here? See ONBOARDING.md for a concise API-key quick start, common mistakes, and copy-paste verification commands.

Note: The public import namespace is `dc_mar_sdk`.



This project provides a CLI, a Python SDK, and a small FastAPI dashboard. The steps below get you up and running quickly; see Troubleshooting for common issues.

### Installation

```bash
# Install project dependencies & link package (recommended)
uv sync

# Or with pip for editable install
pip install -e .

# Or install the published SDK when released
pip install dc-mar-sdk
```

### Configure API key

Set your DC MAR API key in an environment variable used by the CLI and tests:

```bash
export DC_MAR_API_KEY="<your_api_key>"
```

The CLI also accepts --api-key on the command line for one-off runs.

### CLI Usage (common commands)

- Drift check (full comparison). By default drift-check probes every documented
  MAR operation and still respects robots.txt. Use `--safe-read-only` to limit
  a run to GET operations:

```bash
# Installed CLI:
 dc-mar-cli drift-check --api-key "$DC_MAR_API_KEY"
# Local/dev (no install):
 uv run dc-mar-cli drift-check --api-key "$DC_MAR_API_KEY"
 # To limit the check to GET operations:
 dc-mar-cli drift-check --api-key "$DC_MAR_API_KEY" --safe-read-only
# Local/dev equivalent:
 uv run dc-mar-cli drift-check --api-key "$DC_MAR_API_KEY" --safe-read-only
```

- Smoke drift (fast quick check):

```bash
# Installed CLI:
dc-mar-cli drift-smoke --api-key "$DC_MAR_API_KEY"
# Local/dev:
uv run dc-mar-cli drift-smoke --api-key "$DC_MAR_API_KEY"
```

- Call any authoritative v2.2 operation. Use the exact Swagger path template
  and provide each path value separately:

```bash
uv run dc-mar-cli api-request \
  --method GET \
  --operation '/api/v2.2/units/{marid}' \
  --path-parameter marid=1234567
```

- Use validated, typed commands for the common MAR API families. These reject
  malformed request data and fail if the live response violates its model:

```bash
uv run dc-mar-cli locations address "1600 Pennsylvania" --zones Ward
uv run dc-mar-cli locations coordinates --longitude -77.0365 --latitude 38.8977
uv run dc-mar-cli locations batch --address-base64 "MTYwMCBQZW5uc3lsdmFuaWE="
uv run dc-mar-cli ssl lookup --square 0766 --lot 0038
uv run dc-mar-cli units lookup --marid 308596
uv run dc-mar-cli zone lookup "Ward 2"
uv run dc-mar-cli autocomplete-body "1600 Pennsylvania"
```

- Target a specific swagger spec file:

```bash
# Installed CLI:
dc-mar-cli drift-check --api-key "$DC_MAR_API_KEY" --swagger-file swagger/swagger.v7.json
# Local/dev:
uv run dc-mar-cli drift-check --api-key "$DC_MAR_API_KEY" --swagger-file swagger/swagger.v7.json
```

Notes:
- Use --api-key to avoid relying on environment variables in CI.
- By default drift-check respects robots.txt. To override, use the --ignore-robots flag when you understand the consequences.

Caching notes:
- Client methods (autocomplete/search) now accept per-call cache overrides: use_cache (bool), refresh (bool), and ttl_seconds.
- CLI autocomplete supports --no-cache to bypass the cache for that invocation (does not clear global cache).

### Python Library (example)

```python
import logging
import os
from dc_mar_sdk import MARClient

logging.basicConfig(level=logging.DEBUG)  # helpful while developing

async with MARClient(api_key=os.environ.get("DC_MAR_API_KEY")) as client:
    results = await client.autocomplete("1600 Pennsylvania")
    print(results)
```

### Web Dashboard

Run the dashboard locally and open http://localhost:8000. It intentionally binds
to loopback only and is not designed for external or multi-user deployment.

```bash
uv run uvicorn dc_mar_sdk.dashboard.app:app --reload
```

Insights endpoints:
- `GET /api/insights/overview?hours=24`
- `GET /api/insights/timeseries?hours=24&bucket=hour`
- `GET /api/insights/endpoints?hours=24&limit=20`
- `GET /api/insights/anomalies?hours=24`

### Geocode quality sampling automation (robots-safe)

Collect a larger, intentionally messy address sample for quality heatmap analysis:

```bash
uv run dc-mar-sdk-geocode-collect --max-samples 20
```

Notes:
- Respects `robots.txt` and enforces crawl delay (currently 60s) between live calls.
- Uses `DC_MAR_API_KEY` or `--api-key`.
- Writes outputs to `artifacts/geocode-quality/`:
  - `geocode_quality_samples.json`
  - `geocode_quality_summary.json`
  - `geocode_quality_points.geojson`

### Troubleshooting (quick matrix)

Below are common symptoms, likely causes, and practical fixes. If an error includes an HTTP status code or exception message, include that in any issue you file.

Symptom -> Likely cause -> Fix

- Authentication errors (401 / "invalid api key") -> Missing or wrong DC_MAR_API_KEY -> Verify env var, try --api-key, ensure no surrounding quotes, confirm key with provider. If running tests, set DC_RUN_SMOKE_TESTS=1 only when key is valid.

- Rate limit / 429 responses -> API enforced throttling -> Retry with backoff; reduce concurrency; cache responses; contact API owner for higher limits.

- Drift run shows "skipped: respects robots.txt" or many skipped endpoints -> robots.txt prevented crawling -> This is expected: drift-check honors robots.txt by default. Re-run with --ignore-robots if you need to test anyway.

- Drift output shows many validation errors or model mismatches -> OpenAPI spec changed or responses differ from spec -> Point drift-check to the correct --swagger-file; enable DEBUG logging to see which endpoint/spec entry failed; update generated models or the spec.

- Drift summary shows large "differences" but no request failures -> Legitimate API surface changes -> Inspect per-endpoint diffs in the drift output; run with --verbose or check drift output files to determine whether changes are additions, removals, or parameter type changes.

- CLI hangs or slow startup -> Missing/slow dependency (network, auth provider), or event loop blocked -> Try running the same command with DEBUG logs (ENV PYTHONASYNCIODEBUG=1 may help); check network connectivity.

- Web dashboard shows empty or stale cache -> Cache backend misconfigured (SQLite file path, Redis not running) -> Verify configuration in settings, ensure cache file is writable, or start Redis and configure accordingly. For SQLite, check file permissions and path.

- "Connection reset" or TLS errors -> Network or certificate issues -> Confirm system trust store; try curl to the API endpoint to see TLS errors; check proxies/firewalls.

- Tests requiring live API fail in CI -> API key not set or network blocked -> Use CI secrets to set DC_MAR_API_KEY, or skip smoke tests by not setting DC_RUN_SMOKE_TESTS.

If you need to capture more detail for debugging, enable DEBUG logs and include the command, flags, and a minimal excerpt of the output when filing issues.

## Architecture

```
src/dc_mar_sdk/
├── client/     — API client wrapper, cache integration
├── cache/      — Backend implementations (SQLite, Redis, in-memory)
├── telemetry/  — Usage tracking and analytics
├── models/     — Pydantic models (generated + enhanced)
├── cli/        — CLI tool (Typer)
└── dashboard/  — Web dashboard (FastAPI + templates/static)
```

## Development

```bash
# Run tests
uv run pytest

# Run optional live smoke test
DC_RUN_SMOKE_TESTS=1 DC_MAR_API_KEY=... uv run pytest tests/test_drift_smoke.py

# Type checking
uv run mypy src/

# Formatting & linting
uv run ruff format .
uv run ruff check .
```

### Release checks

```bash
# Lint + unit tests (packaged entry point)
uv run dc-mar-sdk-release

# If hygiene artifacts exist (__pycache__, *.pyc, lint/test caches), clean first
uv run dc-mar-sdk-release --fix-hygiene

# Lint + unit tests + local smoke test
uv run dc-mar-sdk-release --smoke --api-key "$DC_MAR_API_KEY"
```

Release docs

- CHANGELOG: see CHANGELOG.md for a keep-a-changelog style history. Update the "Unreleased" section before tagging a release.
- Release policy & checklist: see RELEASE_POLICY.md for semantic versioning rules and a step-by-step release checklist (includes the `dc-mar-sdk-release` quality gates).


## CI cost controls

- Local-first: run the release and smoke checks locally. Use `uv run dc-mar-sdk-release` (add `--smoke --api-key` only when you want a live API check).
- When Actions run: workflows only trigger for pull requests targeting `main` and for pushes to `main`. Docs-only changes (`**/*.md`, `docs/**`) skip lint/tests to avoid unnecessary CI runs.
- Smoke tests: the smoke workflow is manual (workflow_dispatch) and supports an optional `allowed_actors` input to restrict who may run it.

Practical options to reduce CI spend further:
- Run tests/lint locally for fast feedback (zero CI cost).
- Move expensive checks to manual workflows or scheduled runs instead of per-PR.
- Use self-hosted runners for high-frequency, heavy jobs to lower GitHub bill (ops cost trades off).
- Batch or selective testing (only run tests for changed packages/files) to reduce runtime.

Tradeoffs: local-first and manual workflows reduce monetary cost but shift verification responsibility to contributors; self-hosted runners reduce GitHub charges but require maintenance.

## API Documentation

### Cache metrics (client-facing)

The MAR client exposes a normalized cache metrics API via MARClient.get_cache_stats(). This returns a stable dict suitable for downstream consumers with the following shape:

- backend: string (backend identifier)
- entries: int | null
- hits: int
- misses: int
- total_requests: int
- hit_rate: float (percentage 0-100, rounded to 2 decimals)
- size_bytes: int | null
- backend_details: dict (extra backend-specific fields)

Example usage:

```python
async with MARClient(api_key=...) as client:
    stats = await client.get_cache_stats()
    print(stats["hit_rate"], stats["entries"])  # 42.5, 123
```

This API is intentionally lightweight and does not require access to backend internals; the client normalizes backend-specific fields into the stable schema above.

## API Documentation

The DC MAR API provides geocoding and address matching services:
- **Autocomplete** — Get address suggestions from partial input
- **Search** — Advanced address search with filters
- **Reverse Geocoding** — Find addresses near coordinates

See `/swagger/swagger.json` for the full OpenAPI spec.

- **Model & API contract policy** — See CONTRACT_POLICY.md for transport envelope vs domain model rules, compatibility guidance, and examples.

## Roadmap

1. ✅ Phase 1: Infrastructure & Swagger fetch
2. ⬜ Phase 2: Generate client from Swagger, Pydantic models
3. ⬜ Phase 3: Cache & telemetry systems
4. ⬜ Phase 4: CLI and FastAPI dashboard
5. ⬜ Phase 5: Data exploration & business use cases

## Contributing

We welcome contributions! See CONTRIBUTING.md for setup, testing, linting, and PR expectations. Please follow the Code of Conduct in CODE_OF_CONDUCT.md. Use the issue and PR templates in .github/ to file bugs, feature requests, and pull requests.

## License

MIT
