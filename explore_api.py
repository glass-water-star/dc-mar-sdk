"""
Data exploration script for DC MAR API.
Queries various endpoints to understand API capabilities and identify
business/visualization opportunities.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dc_mar_sdk import MARClient


async def explore_api():
    """Explore DC MAR API capabilities and data patterns."""

    client = MARClient(enable_telemetry=True)

    results = {
        "exploration_date": datetime.now().isoformat(),
        "tests": [],
    }

    print("\n" + "="*60)
    print("🔍 DC MAR API EXPLORATION")
    print("="*60 + "\n")

    # Test 1: Basic autocomplete
    print("Test 1: Basic Autocomplete")
    print("-" * 40)
    try:
        test_addresses = [
            "1600 Pennsylvania",
            "1 Constitution",
            "3000 Martin",
        ]

        for addr in test_addresses:
            suggestions = await client.autocomplete(addr)
            print(f"  • Query: '{addr}'")
            print(f"    → {len(suggestions)} suggestions returned")
            if suggestions:
                print(f"    → Examples: {', '.join(suggestions[:3])}")

            results["tests"].append({
                "type": "autocomplete",
                "query": addr,
                "suggestion_count": len(suggestions),
                "first_suggestions": suggestions[:3] if suggestions else [],
            })
    except Exception as e:
        print(f"  ✗ Error: {e}")
        results["tests"].append({
            "type": "autocomplete",
            "error": str(e),
        })

    print()

    # Test 2: Cache effectiveness
    print("Test 2: Cache Effectiveness")
    print("-" * 40)
    try:
        # Query same address twice to test caching
        addr = "1600 Pennsylvania Avenue"

        result1 = await client.autocomplete(addr)
        cache_stats_before = await client.get_cache_stats()

        result2 = await client.autocomplete(addr)
        cache_stats_after = await client.get_cache_stats()

        print(f"  • Query: '{addr}'")
        print(f"    → First call: {len(result1)} suggestions")
        print(f"    → Second call (cached): {len(result2)} suggestions")
        print(f"    → Results identical: {result1 == result2}")
        print("  • Cache Stats:")
        print(f"    → Hits: {cache_stats_after.get('hits', 0)}")
        print(f"    → Misses: {cache_stats_after.get('misses', 0)}")
        print(f"    → Hit Rate: {cache_stats_after.get('hit_rate', 0):.1f}%")

        results["tests"].append({
            "type": "cache_effectiveness",
            "query": addr,
            "cache_stats": cache_stats_after,
        })
    except Exception as e:
        print(f"  ✗ Error: {e}")

    print()

    # Test 3: Response time analysis
    print("Test 3: Response Time Analysis")
    print("-" * 40)
    try:
        import time

        queries = [
            "1",
            "10",
            "100",
            "1000",
            "martin luther king",
            "pennsylvania avenue",
            "constitution ave",
        ]

        times = []
        for query in queries:
            start = time.time()
            result = await client.autocomplete(query)
            elapsed = (time.time() - start) * 1000
            times.append(elapsed)
            print(f"  • '{query}' → {elapsed:.1f}ms ({len(result)} results)")

        avg_time = sum(times) / len(times)
        print(f"\n  ✓ Average response time: {avg_time:.1f}ms")

        results["tests"].append({
            "type": "response_time",
            "queries": queries,
            "response_times_ms": times,
            "avg_response_time_ms": avg_time,
        })
    except Exception as e:
        print(f"  ✗ Error: {e}")

    print()

    # Test 4: Data pattern analysis
    print("Test 4: Data Pattern Analysis")
    print("-" * 40)
    try:
        # Explore patterns in results
        pattern_tests = {
            "Street Names": ["M Street", "K Street", "H Street"],
            "Quadrants": ["NW", "NE", "SW", "SE"],
            "Numbered Streets": ["1st", "2nd", "3rd", "Constitution"],
        }

        for category, queries in pattern_tests.items():
            print(f"\n  • {category}:")
            for query in queries:
                result = await client.autocomplete(query)
                if result:
                    print(f"    - '{query}': {len(result)} results")
                    # Print first few to see patterns
                    for addr in result[:2]:
                        print(f"      • {addr}")
    except Exception as e:
        print(f"  ✗ Error: {e}")

    print()

    # Get telemetry summary
    print("="*60)
    print("📊 TELEMETRY SUMMARY")
    print("="*60 + "\n")

    try:
        api_stats = await client.get_api_stats(hours=1)
        cache_stats = await client.get_cache_stats()
        data_summary = await client.get_data_summary()
        endpoints = await client.get_endpoint_popularity(limit=5)

        print("API Usage Statistics (last hour):")
        for key, value in api_stats.items():
            if isinstance(value, float):
                print(f"  • {key}: {value:.2f}")
            else:
                print(f"  • {key}: {value}")

        print("\nCache Statistics:")
        for key, value in cache_stats.items():
            if isinstance(value, float):
                print(f"  • {key}: {value:.2f}")
            else:
                print(f"  • {key}: {value}")

        print("\nData Collection Summary:")
        for key, value in data_summary.items():
            if isinstance(value, float):
                print(f"  • {key}: {value:.2f}")
            else:
                print(f"  • {key}: {value}")

        print("\nTop Endpoints:")
        for ep in endpoints:
            print(f"  • {ep.get('endpoint')}: {ep.get('call_count')} calls")

        results["telemetry"] = {
            "api_stats": api_stats,
            "cache_stats": cache_stats,
            "data_summary": data_summary,
            "endpoints": endpoints,
        }
    except Exception as e:
        print(f"  ✗ Error fetching telemetry: {e}")

    print()

    # Save results
    output_file = Path(__file__).parent.parent / "exploration_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"✓ Results saved to: {output_file}")
    print()


if __name__ == "__main__":
    asyncio.run(explore_api())
