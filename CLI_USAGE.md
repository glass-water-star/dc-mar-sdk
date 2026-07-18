# Option A: Standalone CLI Usage Guide

The `analyze` command implements **Option A: Standalone Python Application** for individual analysis and research. Here's how to use it:

## Setup: Set Your API Key

### Option 1: Environment Variable (Recommended)
```bash
export DC_MAR_API_KEY="your_api_key_here"
```

Then all commands will automatically use your key:
```bash
uv run dc-mar-sdk-cli analyze
```

### Option 2: Command-line Flag
```bash
uv run dc-mar-sdk-cli analyze --api-key "your_api_key_here"
# Or short form:
uv run dc-mar-sdk-cli analyze -k "your_api_key_here"
```

---

## Usage Examples

### 1. Single Address Query

Note: The CLI's `autocomplete` command supports `--no-cache` to bypass local cache for that single invocation (it does not clear the global cache).
```bash
uv run dc-mar-sdk-cli analyze -q "1600 Pennsylvania Avenue"
```

Output:
```
Reading addresses from None...
Analyzing 1 address(es)...

✓ Analysis Complete

┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┓
┃ Original Address        ┃ Standardized       ┃ Matches ┃ Status   ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━┩
│ 1600 Pennsylvania Ave   │ 1600 Pennsylvania  │ 3      │ ✓ Found  │
└─────────────────────────┴────────────────────┴────────┴──────────┘

📊 Data Collection Summary:
  • Total Requests: 1
  • Data Received: 0.00 MB
  • Avg Response: 150ms
```

### 2. Batch Analysis from CSV File

Create `addresses.csv`:
```csv
address
1600 Pennsylvania Avenue
1 Constitution Avenue
555 Pennsylvania Avenue
```

Then analyze:
```bash
uv run dc-mar-sdk-cli analyze --file addresses.csv --output results.csv
```

Output:
```
Reading addresses from addresses.csv...
Analyzing 3 address(es)...

✓ Analysis Complete

┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┓
┃ Original Address     ┃ Standardized   ┃ Matches ┃ Status   ┃
├──────────────────────┼────────────────┼────────┼──────────┤
│ 1600 Pennsylvania...  │ 1600 Pennsylva │ 3      │ ✓ Found  │
│ 1 Constitution Ave    │ 1 Constitution │ 2      │ ✓ Found  │
│ 555 Pennsylvania Ave  │ 555 Pennsylva  │ 1      │ ✓ Found  │
└──────────────────────┴────────────────┴────────┴──────────┘

✓ CSV exported to results.csv
```

### 3. Batch Analysis from JSON File

Create `addresses.json`:
```json
[
  "1600 Pennsylvania Avenue",
  "1 Constitution Avenue",
  "555 Pennsylvania Avenue"
]
```

Then analyze and export as GeoJSON:
```bash
uv run dc-mar-sdk-cli analyze --file addresses.json --output results.geojson
```

### 4. Export to Multiple Formats

**CSV Export:**
```bash
uv run dc-mar-sdk-cli analyze --file addresses.json --output results.csv
```

**GeoJSON Export:**
```bash
uv run dc-mar-sdk-cli analyze --file addresses.json --output results.geojson
```

---

## Full Command Reference

### Basic Usage
```bash
# Single query with default address
uv run dc-mar-sdk-cli analyze

# Custom single query
uv run dc-mar-sdk-cli analyze --query "1600 Pennsylvania"

# With API key flag
uv run dc-mar-sdk-cli analyze --query "1600 Pennsylvania" --api-key "YOUR_KEY"
```

### Batch Processing
```bash
# From CSV file
uv run dc-mar-sdk-cli analyze --file addresses.csv

# From JSON file
uv run dc-mar-sdk-cli analyze --file addresses.json

# With output export
uv run dc-mar-sdk-cli analyze --file addresses.csv --output results.geojson
```

### Options
```
--file     -f    Input file (CSV or JSON with addresses)
--query    -q    Single address query (default: "1600 Pennsylvania")
--api-key  -k    API key (or use DC_MAR_API_KEY env var)
--output   -o    Output file (.csv or .geojson)
--help           Show help message
```

---

## Output Format

### Result Table
Shows each address with:
- **Original Address**: What you searched for
- **Standardized**: The normalized/canonical form
- **Matches**: Number of alternative matches found
- **Status**: ✓ Found, ✗ Error, or ? No match

### CSV Export Format
```csv
address,standardized,match_count
1600 Pennsylvania Avenue,1600 Pennsylvania Avenue NW,3
1 Constitution Avenue,1 Constitution Avenue NE,2
```

### GeoJSON Export Format
```json
[
  {
    "address": "1600 Pennsylvania Avenue",
    "standardized": "1600 Pennsylvania Avenue NW",
    "alternatives": ["1600 PENNSYLVANIA AVENUE NW", "1600 PENNSYLVANIA AVE NW"],
    "match_count": 3
  }
]
```

---

## Real-World Workflows

### Workflow 1: Clean Up Address List
```bash
# 1. Create input file
echo "address
123 Main St
456 Oak Ave
789 Elm Rd" > messy_addresses.csv

# 2. Standardize and export
uv run dc-mar-sdk-cli analyze --file messy_addresses.csv --output clean_addresses.csv

# 3. Use the output for your application
cat clean_addresses.csv
```

### Workflow 2: Verify Multiple Locations
```bash
# 1. Query multiple addresses
uv run dc-mar-sdk-cli analyze --file locations.json --output verification.geojson

# 2. Import GeoJSON into mapping tool (QGIS, Mapbox, etc.)
# 3. Verify on map
```

### Workflow 3: Bulk Geocoding for Data Science
```bash
# 1. Analyze addresses
uv run dc-mar-sdk-cli analyze --file property_list.csv --output geocoded.csv

# 2. Import into pandas for further analysis
python3 << 'EOF'
import pandas as pd

# Read standardized addresses
df = pd.read_csv('geocoded.csv')

# Add to your original data
original = pd.read_csv('property_list.csv')
merged = original.merge(df, on='address')

# Save combined dataset
merged.to_csv('properties_with_standardized_addresses.csv', index=False)
print(merged.head())
EOF
```

---

## Telemetry & Monitoring

Each analyze run automatically tracks:
- **API Requests**: Count of queries made
- **Data Received**: Total bytes downloaded
- **Response Time**: Average latency

View cumulative stats:
```bash
uv run dc-mar-sdk-cli api-stats --hours 24
```

View cache effectiveness:
```bash
uv run dc-mar-sdk-cli cache-status
```

---

## Tips & Optimization

### 1. Use Environment Variable for Convenience
```bash
# Set once
export DC_MAR_API_KEY="your_key"

# Then use without flags
uv run dc-mar-sdk-cli analyze --file addresses.csv --output results.csv
```

### 2. Leverage Caching
- First run: API queries executed
- Second run with same data: Results come from cache (faster!)
- Clear cache if needed: `uv run dc-mar-sdk-cli cache-clear`

### 3. Rate Limiting
The CLI automatically includes 50ms delays between requests to be respectful of the API.

### 4. Large Files
For 1000+ addresses, consider:
- Breaking into multiple files
- Running at off-peak hours
- Checking cache first

---

## Error Handling

### No API Key
```
Error: API key required
  Set DC_MAR_API_KEY environment variable or use --api-key flag
```

**Fix**: Export the environment variable or add `--api-key` flag.

### File Not Found
```
Error reading file: [Errno 2] No such file or directory: 'addresses.csv'
```

**Fix**: Check file path and ensure it exists in current directory.

### Invalid Output Format
```
Error exporting: Output must end with .csv or .geojson
```

**Fix**: Use `--output results.csv` or `--output results.geojson`.

---

## Integration with Other Tools

### Use CSV with Excel/Google Sheets
```bash
uv run dc-mar-sdk-cli analyze --file input.csv --output output.csv
# Then open output.csv in Excel or Google Sheets
```

### Use GeoJSON with Web Maps
```bash
uv run dc-mar-sdk-cli analyze --file locations.csv --output map.geojson
# Then upload to Mapbox, Leaflet, or QGIS
```

### Use with Python/Pandas
```bash
uv run dc-mar-sdk-cli analyze --file addresses.csv --output standardized.csv

# In your Python script:
import pandas as pd
df = pd.read_csv('standardized.csv')
print(df.head())
```

---

## Next Steps

1. **Get API Key**: Request from DC Data Team (data.dev@dc.gov)
2. **Test**: Run single query: `uv run dc-mar-sdk-cli analyze`
3. **Batch Process**: Use CSV file with your addresses
4. **Export**: Save results as CSV or GeoJSON
5. **Analyze**: Use in your visualization or analysis tool

---

**Option A Complete**: You now have a standalone CLI for address analysis and standardization!
