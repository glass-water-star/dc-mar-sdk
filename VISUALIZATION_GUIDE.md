# Phase 6: Visualization & Analytics Implementation Guide

## Quick Start: Build Your First Visualization

### 1. Real Estate Dashboard (30 minutes)

```python
import asyncio
from dc_mar_sdk import MARClient

async def build_real_estate_dashboard():
    """Query MAR for property data and export for visualization."""
    
    # Initialize client with your API key
    client = MARClient(api_key="YOUR_API_KEY_HERE")
    
    # Batch query addresses (example: properties in a specific area)
    test_addresses = [
        "1600 Pennsylvania Avenue NW",
        "1 Constitution Avenue NE",
        "555 Pennsylvania Avenue NW",
    ]
    
    results = []
    for addr in test_addresses:
        try:
            matches = await client.autocomplete(addr)
            results.append({"address": addr, "matches": matches})
        except ValueError as e:
            print(f"Error: {e}")
            break
    
    # Export to GeoJSON for web mapping
    import json
    with open("properties.geojson", "w") as f:
        json.dump(results, f)
    
    print("✓ Data exported to properties.geojson")
    print(f"✓ Queried {len(results)} locations")
    
    # View telemetry
    stats = await client.get_data_summary()
    print(f"\n📊 Data collected:")
    print(f"   • Bytes: {stats['total_data_received_mb']} MB")
    print(f"   • Requests: {stats['total_api_requests']}")

asyncio.run(build_real_estate_dashboard())
```

### 2. Cache Performance Monitoring

```python
async def monitor_cache_efficiency():
    """Track cache effectiveness for cost optimization."""
    
    client = MARClient(api_key="YOUR_API_KEY")
    
    # Run repeated queries (tests cache)
    addresses = ["1600 Pennsylvania"] * 10
    
    for _ in addresses:
        await client.autocomplete("1600 Pennsylvania")
    
    stats = await client.get_cache_stats()
    print(f"Cache Hit Rate: {stats['hit_rate']:.1f}%")
    print(f"Cache Entries: {stats['entries']}")
    print(f"Size: {stats['size_bytes']} bytes")
```

### 3. Batch Geocoding Export

```python
import csv
import asyncio

async def bulk_geocode_export(input_csv, output_geojson):
    """Geocode a CSV file and export as GeoJSON."""
    
    client = MARClient(api_key="YOUR_API_KEY")
    results = []
    
    # Read input CSV
    with open(input_csv) as f:
        for row in csv.DictReader(f):
            address = row['address']
            try:
                matches = await client.autocomplete(address)
                results.append({
                    "original": address,
                    "standardized": matches[0] if matches else None,
                    "alternatives": matches[1:3] if len(matches) > 1 else [],
                })
            except Exception as e:
                results.append({"original": address, "error": str(e)})
            
            # Respect API limits
            await asyncio.sleep(0.1)
    
    # Export results
    with open(output_geojson, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"✓ Geocoded {len(results)} addresses")
```

---

## Visualization Tools & Integrations

### Option 1: Interactive Web Dashboard (FastAPI + Folium)

```python
# dashboard/geospatial.py
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import folium
import io

app = FastAPI()

@app.get("/map/heatmap")
async def render_heatmap():
    """Render heatmap of queried addresses."""
    
    m = folium.Map(location=[38.9, -77.0], zoom_start=12)
    
    # Add data points (would query from cache/telemetry DB)
    heat_data = [
        [38.8951, -77.0369],  # Example: 1600 Pennsylvania Ave
        [38.8870, -77.0235],  # Example: Capitol
    ]
    
    folium.plugins.HeatLayer(heat_data).add_to(m)
    
    return HTMLResponse(m._repr_html_())
```

### Option 2: Export to PowerBI/Tableau

```python
import pandas as pd

async def export_to_tableau(output_csv):
    """Export telemetry and address data for BI tools."""
    
    client = MARClient(api_key="YOUR_API_KEY")
    
    # Get summary data
    summary = await client.get_data_summary()
    endpoints = await client.get_endpoint_popularity(20)
    
    # Create DataFrame
    df = pd.DataFrame(endpoints)
    df.to_csv(output_csv, index=False)
    
    print(f"✓ Exported {len(df)} endpoints to {output_csv}")
    print("  Import into Tableau/PowerBI for visualization")
```

### Option 3: Postbox Integration

```python
# Send data to PostGIS for advanced geospatial queries
import psycopg2

async def load_addresses_to_postgis(addresses):
    """Load geocoded addresses into PostGIS database."""
    
    conn = psycopg2.connect("dbname=dc_geo user=postgres")
    cur = conn.cursor()
    
    for addr_data in addresses:
        cur.execute("""
            INSERT INTO addresses_geocoded 
            (address, latitude, longitude, geom)
            VALUES (%s, %s, %s, ST_PointFromText(%s))
        """, (
            addr_data['address'],
            addr_data['lat'],
            addr_data['lon'],
            f"POINT({addr_data['lon']} {addr_data['lat']})"
        ))
    
    conn.commit()
    print(f"✓ Loaded {len(addresses)} addresses to PostGIS")
```

---

## Advanced Analytics Patterns

### 1. Neighborhood Analysis

```python
async def analyze_neighborhood(neighborhood_name):
    """Get statistics for all addresses in a neighborhood."""
    
    client = MARClient(api_key="YOUR_API_KEY")
    
    # Query zone endpoint for neighborhood
    # matches = await client.get_zone(neighborhood_name)
    
    stats = await client.get_api_stats(hours=24)
    print(f"Requests in {neighborhood_name}: {stats['total_requests']}")
```

### 2. Time-Series Address Changes

```python
async def track_address_changes(address):
    """Monitor how an address is standardized over time."""
    
    client = MARClient(api_key="YOUR_API_KEY")
    
    # Query telemetry database directly
    # from dc_mar_sdk.telemetry import TelemetryDB
    # db = TelemetryDB()
    # changes = db.get_address_changes(address)
    
    print("Address standardization history:")
    # for change in changes:
    #     print(f"  {change['date']}: {change['value']}")
```

### 3. Cache Performance by Endpoint

```python
async def analyze_cache_patterns():
    """Identify which endpoints benefit most from caching."""
    
    client = MARClient(api_key="YOUR_API_KEY")
    
    endpoints = await client.get_endpoint_popularity(limit=20)
    
    cache_efficiency = []
    for ep in endpoints:
        efficiency = ep['hit_rate'] * ep['call_count']
        cache_efficiency.append({
            'endpoint': ep['endpoint'],
            'efficiency_score': efficiency,
            'hit_rate': ep['hit_rate'],
        })
    
    # Sort by efficiency
    cache_efficiency.sort(key=lambda x: x['efficiency_score'], reverse=True)
    
    print("🏆 Best cache ROI endpoints:")
    for ep in cache_efficiency[:5]:
        print(f"  {ep['endpoint']}: {ep['efficiency_score']:.0f}")
```

---

## Deployment Options

### Option A: Standalone Python Application
- **Best for**: Individual analysis, research
- **Setup**: `export DC_MAR_API_KEY="your_api_key"` then `uv run python explore_api.py`
- **Scalability**: Single machine, limited concurrency
- **Cost**: Free (only API costs)

### Option B: FastAPI Web Service
- **Best for**: Team dashboards, web access
- **Setup**: `uvicorn dashboard.app:app`
- **Scalability**: Containerizable, cloud-ready
- **Cost**: API costs + hosting

### Option C: Scheduled Batch Jobs
- **Best for**: Regular data collection, analytics
- **Setup**: Cron + Python script
- **Scalability**: Parallel batch processing
- **Cost**: API costs + compute

### Option D: Real-time Data Pipeline
- **Best for**: Dashboard updates, streaming analysis
- **Setup**: Event-driven architecture (AWS Lambda, Kafka)
- **Scalability**: Serverless autoscaling
- **Cost**: API costs + cloud services

---

## Cost Optimization Tips

1. **Aggressive Caching**: TTL = 24 hours for reference data
   - **Savings**: 80-90% reduction in API calls

2. **Batch Processing**: Use `/locationbatch` endpoint
   - **Savings**: 50-70% fewer API calls vs. individual requests

3. **Off-peak Queries**: Schedule batch jobs at night
   - **Savings**: Avoid peak-hour congestion

4. **Deduplicate Addresses**: Cache standardized forms
   - **Savings**: Eliminate redundant queries

---

## Success Metrics

Track these KPIs:
- **API Efficiency**: Bytes per query
- **Cache ROI**: Saved API calls vs. storage
- **Query Latency**: P50/P95/P99 response times
- **Data Quality**: Error rates by endpoint
- **Cost per Insight**: API costs per useful data point

---

## Next Steps

1. **Get API Key**: Request from DC Data Dev Team (data.dev@dc.gov)
2. **Test Integration**: Run `explore_api.py` with your key
3. **Choose Tier 1 Use Case**: Real Estate or Public Safety
4. **Build MVP**: Start with dashboard prototype
5. **Iterate**: Gather feedback, add features

---

See **ANALYSIS.md** for business use case details.
