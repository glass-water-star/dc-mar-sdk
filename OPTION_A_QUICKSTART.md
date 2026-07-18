# Option A: Standalone CLI Application - Quick Start

## What is Option A?

Option A is a **standalone Python application** for individual analysis and research. It includes:
- Command-line interface (CLI)
- Single address queries
- Batch processing from CSV/JSON files
- Export to CSV or GeoJSON formats
- Automatic caching and telemetry

## How to Use (3 Steps)

### Step 1: Set Your API Key
```bash
export DC_MAR_API_KEY="your_api_key_from_dc_data_team"
```

### Step 2: Query a Single Address
```bash
cd /Users/masonstoecker/Proj/dc-mar-sdk
uv run dc-mar-sdk-cli analyze --query "1600 Pennsylvania Avenue"
```

### Step 3: Batch Process from File
```bash
# CSV format
uv run dc-mar-sdk-cli analyze --file addresses.csv --output results.csv

# JSON format
uv run dc-mar-sdk-cli analyze --file addresses.json --output results.geojson
```

## Key Features

✅ **Single Query**
```bash
uv run dc-mar-sdk-cli analyze -q "your address"
```

✅ **Batch Processing**
```bash
uv run dc-mar-sdk-cli analyze -f input.csv -o output.csv
```

✅ **Export Options**
```bash
# Export as CSV
uv run dc-mar-sdk-cli analyze -f addresses.csv -o results.csv

# Export as GeoJSON
uv run dc-mar-sdk-cli analyze -f addresses.json -o results.geojson
```

✅ **Automatic Tracking**
- Cache statistics: `uv run dc-mar-sdk-cli cache-status`
- API stats: `uv run dc-mar-sdk-cli api-stats`
- Data summary: `uv run dc-mar-sdk-cli data-summary`

## Example CSV Input

**addresses.csv**:
```csv
address
1600 Pennsylvania Avenue
1 Constitution Avenue
555 Pennsylvania Avenue NW
```

## Example Output

**results.csv**:
```csv
address,standardized,match_count
1600 Pennsylvania Avenue,1600 Pennsylvania Avenue NW,3
1 Constitution Avenue,1 Constitution Avenue NE,2
555 Pennsylvania Avenue NW,555 Pennsylvania Avenue NW,1
```

## Common Commands

```bash
# Single query with API key flag
uv run dc-mar-sdk-cli analyze --api-key "KEY" --query "address"

# Batch from CSV
uv run dc-mar-sdk-cli analyze --file locations.csv --output results.csv

# Batch from JSON
uv run dc-mar-sdk-cli analyze --file locations.json --output results.geojson

# Show help
uv run dc-mar-sdk-cli analyze --help
```

## Full Documentation

See **CLI_USAGE.md** for comprehensive guide with:
- Detailed usage examples
- Error handling
- Integration with other tools
- Advanced workflows

---

**Ready to start?**
1. Get API key from DC Data Team (data.dev@dc.gov)
2. Run: `uv run dc-mar-sdk-cli analyze`
3. Export your results
