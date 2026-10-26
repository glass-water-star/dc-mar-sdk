# Swagger Specification Versioning System

## Overview

The Swagger Versioning System automatically manages API specification versions, detects drift between documentation and implementation, and allows rolling back to previous versions.

**Key Features:**
- 🔧 Auto-fix drift by introspecting actual API responses
- 📋 Version management with automatic backups
- 🔄 Reset to any previous version instantly
- 📊 Track schema evolution over time
- 🎯 Generate accurate specs from real API behavior

---

## Quick Start

### View All Versions

```bash
uv run dc-mar-cli swagger-list
```

Output:
```
Available Swagger Versions
┏━━━━━━━━━┳━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━┓
┃ Version ┃ Size     ┃ Date ┃ Modified ┃
┡━━━━━━━━━╇━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━┩
│ 1       │ 210.5 KB │ ...  │ ...      │
│ 2       │ 210.5 KB │ ...  │ ...      │
│ current │ 210.5 KB │ ...  │ ...      │
└─────────┴──────────┴──────┴──────────┘
```

### Auto-Fix Drift

```bash
uv run dc-mar-cli swagger-fix --api-key YOUR_KEY
```

This will:
1. ✅ Back up current swagger as `swagger.v{N}.json`
2. 🔄 Call all endpoints and introspect actual responses
3. 📊 Generate corrected schemas from real data
4. 💾 Save as new `swagger.json`

### Reset to Previous Version

```bash
# See available versions
uv run dc-mar-cli swagger-reset

# Reset to specific version
uv run dc-mar-cli swagger-reset --version 1
```

---

## How It Works

### Drift Detection & Auto-Fix Workflow

```
┌─────────────────────────────────────────┐
│ 1. Load Current Swagger Spec            │
│    (e.g., swagger.json - 82 KB)         │
└──────────┬──────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 2. Back Up Current Version              │
│    (swagger.v1.json)                    │
└──────────┬──────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 3. Test Each Endpoint                   │
│    - Call GET /api/v2.2/autocomplete/..│
│    - Call GET /api/v2.2/units/...      │
│    - Call GET /api/v2.2/locations/...  │
│    (14 total endpoints)                │
└──────────┬──────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 4. Analyze Response Structure           │
│    API returns:                         │
│    {                                    │
│      "Result": [...],                   │
│      "Success": true,                   │
│      "Message": null                    │
│    }                                    │
└──────────┬──────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 5. Generate Inferred Schemas            │
│    From actual response structure       │
│    (infer types, required fields, etc)  │
└──────────┬──────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 6. Update Swagger Spec                  │
│    Replace old schemas with inferred    │
│    (21 schemas updated)                 │
└──────────┬──────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 7. Save as Current                      │
│    (swagger.json - now 210 KB)          │
└─────────────────────────────────────────┘
```

### Version Naming Convention

- **swagger.v1.json** - Version 1 (first backup)
- **swagger.v2.json** - Version 2 (second backup)
- **swagger.json** - Current working version

When you reset to v1, the current becomes v2, and v1 becomes current.

---

## Real Example: DC MAR API

### Before (Original Swagger)

```json
// /api/v2.2/autocomplete/{address}
"responses": {
  "200": {
    "schema": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

**Says it returns:** `["1600 PENNSYLVANIA AVENUE NW", ...]`

### After (Auto-Fixed Swagger)

```json
// /api/v2.2/autocomplete/{address}
"responses": {
  "200": {
    "schema": {
      "type": "object",
      "properties": {
        "Result": {
          "type": "array",
          "items": { "type": "string" }
        },
        "Success": { "type": "boolean" },
        "Message": { "type": ["string", "null"] }
      },
      "required": ["Result", "Success", "Message"]
    }
  }
}
```

**Now accurately reflects:** `{ "Result": [...], "Success": true, "Message": null }`

---

## Use Cases

### 1. API Updates

When DC Government updates their API:

```bash
# Detect changes
uv run dc-mar-cli drift-check --api-key KEY

# Auto-fix to match new API
uv run dc-mar-cli swagger-fix --api-key KEY

# Verify the fix
uv run dc-mar-cli drift-check --api-key KEY
```

### 2. Rollback on Bad Update

If an update breaks your code:

```bash
# See what versions are available
uv run dc-mar-cli swagger-list

# Restore to last known-good version
uv run dc-mar-cli swagger-reset --version 1

# Verify stability
uv run dc-mar-cli drift-check --api-key KEY
```

### 3. Development Workflow

```bash
# 1. Make changes to client code
# 2. Run against new API version
# 3. Auto-fix the Swagger to match
uv run dc-mar-cli swagger-fix --api-key KEY

# 4. Commit the new swagger
git add swagger/swagger.json
git commit -m "Update Swagger spec to match API v2.2.5"

# 5. Run tests to ensure compatibility
uv run pytest tests/
```

---

## Schema Inference Rules

When auto-fixing, the system infers schemas by analyzing responses:

| Response Data | Inferred Schema |
|---|---|
| `"string"` | `{"type": "string"}` |
| `123` | `{"type": "integer"}` |
| `45.67` | `{"type": "number"}` |
| `true` | `{"type": "boolean"}` |
| `[1, 2, 3]` | `{"type": "array", "items": {"type": "integer"}}` |
| `{"a": 1}` | `{"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"]}` |
| `null` | `{}` (unknown) |

**Important:** Inference is best-effort. Complex types (unions, oneOf, etc.) are simplified to their inferred structure.

---

## Files

- **swagger/swagger.json** - Current working spec
- **swagger/swagger.v1.json** - First backup
- **swagger/swagger.v2.json** - Second backup
- **src/dc_mar_sdk/tools/swagger_manager.py** - Versioning system
- **src/dc_mar_sdk/cli/main.py** - CLI commands (swagger-list, swagger-fix, swagger-reset)

---

## Commands Reference

### swagger-list

List all available Swagger versions.

```bash
uv run dc-mar-cli swagger-list
```

Options: None

### swagger-fix

Auto-fix Swagger spec drift based on actual API responses.

```bash
uv run dc-mar-cli swagger-fix --api-key YOUR_KEY [--verbose]
```

Options:
- `--api-key KEY` - DC MAR API key (or DC_MAR_API_KEY env var)
- `--verbose` - Show detailed test results for each endpoint

### swagger-reset

Reset to a specific Swagger version.

```bash
uv run dc-mar-cli swagger-reset [--version N]
```

Options:
- `--version N` - Version number to reset to (omit to list versions)

---

## Workflow Best Practices

### For API Updates

1. **Run drift-check** to identify new issues
2. **Run swagger-fix** to auto-correct
3. **Review changes** to swagger.json
4. **Test thoroughly** with new spec
5. **Commit** if stable

### For Troubleshooting

1. **List versions** to see history
2. **Reset to last known good** version
3. **Run drift-check** to see what changed
4. **Make manual edits** if needed
5. **Commit** the fix

### For CI/CD

```yaml
# .github/workflows/swagger.yml
name: Swagger Management
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly

jobs:
  check-and-fix:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      
      - name: Check for drift
        run: uv run dc-mar-cli drift-check --api-key ${{ secrets.DC_MAR_API_KEY }}
      
      - name: Auto-fix if drifted
        if: failure()
        run: uv run dc-mar-cli swagger-fix --api-key ${{ secrets.DC_MAR_API_KEY }}
      
      - name: Create PR if changes
        if: success()
        uses: peter-evans/create-pull-request@v4
        with:
          commit-message: "chore: auto-update Swagger spec"
          title: "Swagger spec updated"
          body: "Auto-generated Swagger update from drift detection"
```

---

## Limitations & Considerations

✅ **Works Well For:**
- Simple types (strings, numbers, arrays, objects)
- Consistent response formats
- Well-behaved APIs

❌ **Limitations:**
- Cannot infer `oneOf`, `anyOf`, `allOf` (complex unions)
- Cannot detect field descriptions from responses
- Cannot infer enum values (only if all responses match)
- Requires valid API key for testing
- Timeouts on slow endpoints

---

## FAQ

**Q: Will swagger-fix break my code?**
A: No. It only updates the spec documentation. Your client code continues to work.

**Q: How often should I run swagger-fix?**
A: Weekly via CI/CD. Or whenever you detect drift with drift-check.

**Q: Can I edit swagger.json manually?**
A: Yes. Versioning doesn't prevent manual edits. Just back it up first.

**Q: What if an endpoint times out?**
A: swagger-fix skips it and logs a warning. Some endpoints may need longer timeouts.

**Q: Can I restore a very old version?**
A: Yes, as long as the swagger.vN.json file exists.

---

## See Also

- **DRIFT_DETECTION.md** - Detecting specification drift
- **CLI_USAGE.md** - Other CLI commands
- **README.md** - Project overview
