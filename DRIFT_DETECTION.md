# Swagger Drift Detection System

## Overview

The drift detection system automatically compares actual API responses against the official Swagger specification to identify when the implementation diverges from the documented contract.

**Purpose**: Catch API changes, undocumented behaviors, and documentation gaps before they break your application.

---

## What is API Drift?

API drift occurs when:
- ✗ API response structure doesn't match Swagger spec
- ✗ Required fields are missing from responses
- ✗ Field types change (e.g., string → object)
- ✗ Extra undocumented fields appear in responses
- ✗ Status codes differ from documentation

---

## Running Drift Detection

### Via CLI

```bash
# Basic usage (requires API key)
# NOTE: drift-check is safe-by-default and only probes GET operations. To allow write-style methods use --no-safe-read-only.
uv run dc-mar-cli drift-check --api-key YOUR_API_KEY

# Using environment variable
export DC_MAR_API_KEY=YOUR_API_KEY
uv run dc-mar-cli drift-check

# To explicitly include unsafe methods (POST/PUT/PATCH/DELETE):
uv run dc-mar-cli drift-check --api-key YOUR_API_KEY --no-safe-read-only
```

### Programmatically

```python
from dc_mar_sdk.tools.drift_detector import SwaggerValidator
import asyncio

async def check_drift():
    validator = SwaggerValidator(
        swagger_path="swagger/swagger.json",
        api_key="YOUR_API_KEY"
    )
    # By default validator.test_all() runs read-only GET probes. Pass include_unsafe_methods=True to opt into non-GET methods.
    results = await validator.test_all(include_unsafe_methods=False)
    
    for result in results:
        if not result.success:
            print(f"❌ {result.endpoint} has {len(result.issues)} issues")
            for issue in result.issues:
                print(f"  - {issue.issue_type}: {issue.location}")

asyncio.run(check_drift())
```

---

## Understanding the Report

### Severity Levels

| Level | Icon | Meaning | Action |
|-------|------|---------|--------|
| **Error** | 🔴 | Spec and API are incompatible | Fix required |
| **Warning** | 🟡 | Minor deviation detected | Review needed |
| **Info** | 🔵 | Informational detail | Optional |

### Issue Types

- **schema_mismatch**: Response type doesn't match spec (e.g., dict vs array)
- **type_error**: Field has wrong type (e.g., string where int expected)
- **missing_field**: Required field from spec is absent
- **request_failed**: API call failed or returned unparseable response

---

## Current Drift Issues

### ❌ CRITICAL: /autocomplete/{address}

**Problem**: API returns wrapped response format, not array

```json
// Swagger says:
["1600 PENNSYLVANIA AVENUE NW", "1600 PENNSYLVANIA AVENUE SE"]

// But API returns:
{
  "Result": ["1600 PENNSYLVANIA AVENUE NW", "1600 PENNSYLVANIA AVENUE SE"],
  "Success": true,
  "Message": null
}
```

**Status**: ✅ HANDLED - Client extracts `Result` field automatically

**Workaround in use**:
```python
# src/dc_mar_sdk/client/mar.py
if isinstance(data, dict) and "Result" in data:
    suggestions = data["Result"]  # Extract from wrapper
else:
    suggestions = data if isinstance(data, list) else []
```

### 🟡 WARNING: /units/{marid}, /ssls, /zone/{zone}

**Problem**: Swagger schema parsing issue (schema not in standard format)

**Status**: Not critical - endpoints return valid JSON

**Impact**: Low - these are reference/lookup endpoints with stable responses

---

## Handling Drift in Your Code

### Option 1: Trust the Swagger (Recommended initially)

Assume spec is correct, catch drift during testing:

```python
# Test suite integration
from dc_mar_sdk.tools.drift_detector import SwaggerValidator

async def test_api_contract():
    validator = SwaggerValidator("swagger/swagger.json", os.getenv("API_KEY"))
    results = await validator.test_all()
    
    errors = [r for r in results if r.status_code != 200]
    assert not errors, f"API drift detected: {errors}"
```

### Option 2: Defensive Parsing

Handle both spec and actual formats:

```python
response = await client.get(url)
data = response.json()

# Try both formats
if isinstance(data, dict) and "Result" in data:
    items = data["Result"]
elif isinstance(data, list):
    items = data
else:
    items = []  # Default to empty
```

### Option 3: Version Pinning

Lock to a specific API version known to be stable:

```python
BASE_URL = "https://datagate.dc.gov/mar/open/api/v2.2"  # Pin version
```

---

## Maintenance

### Running Drift Detection Regularly

Add to your CI/CD pipeline:

```yaml
# Example: .github/workflows/drift-check.yml
name: API Drift Check
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly

jobs:
  drift-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: uv run dc-mar-cli drift-check --api-key ${{ secrets.DC_MAR_API_KEY }}
```

### When Drift is Detected

1. **Check the report** - Understand what changed
2. **Update Swagger spec** OR **fix client code**
   - If API changed: Update swagger.json from API provider
   - If docs wrong: Add workaround to client
3. **Add defensive parsing** - Handle both old/new formats during transition
4. **Test thoroughly** - Verify fix doesn't break existing functionality
5. **Document change** - Update CHANGELOG or docs

---

## API Drift Timeline (This Project)

| Date | Endpoint | Issue | Status |
|------|----------|-------|--------|
| Initial | `/autocomplete/{address}` | Response wrapped in dict | ✅ Fixed |
| Initial | Swagger spec | Outdated (vs v2.2 API) | ⚠️ Incomplete docs |

---

## Assumptions & Limitations

✓ **Swagger spec is the source of truth** - We assume documented behavior is correct
✓ **Tests cover main endpoints** - Currently tests 4 key operations
✗ **Does not test all parameters** - Focuses on common use cases
✗ **Does not validate response content** - Only validates structure/types
✗ **Authentication may affect responses** - API key might gate features

---

## Next Steps

1. **Integrate into CI/CD** - Run drift detection on schedule
2. **Expand test coverage** - Add more endpoints from swagger.json
3. **Monitor for upstream changes** - Track DC Government API updates
4. **Document API quirks** - Keep this guide updated as drift is found

---

## Questions?

See:
- `src/dc_mar_sdk/tools/drift_detector.py` - Implementation
- `src/dc_mar_sdk/cli/main.py` - CLI integration (drift-check command)
- `IMPLEMENTATION_COMPLETE.md` - Project architecture
