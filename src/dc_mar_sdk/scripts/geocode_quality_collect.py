"""Collect challenging geocode samples with robots.txt compliance.

Outputs:
- raw sample rows (JSON)
- summary metrics (JSON)
- optional map layer (GeoJSON) for points with coordinates
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.robotparser import RobotFileParser

import httpx

from dc_mar_sdk.client.mar import MARClient
from dc_mar_sdk.settings import get_settings

SETTINGS = get_settings()


BASE_ADDRESSES = [
    "1600 Pennsylvania Ave NW",
    "2000 14th St NW",
    "600 H St NE",
    "300 M St SE",
    "1234 Good Hope Rd SE",
    "700 7th St SW",
    "1300 U St NW",
    "1100 4th St SW",
    "500 Florida Ave NW",
    "3500 Connecticut Ave NW",
]


@dataclass
class RobotsPolicy:
    allowed: bool
    crawl_delay_seconds: int


def normalize_score(raw_score: float | None) -> float | None:
    if raw_score is None:
        return None
    score = float(raw_score)
    # Handle either [0,1] or [0,100] formats.
    if 0.0 <= score <= 1.0:
        return score * 100.0
    return score


def quality_bucket(score_100: float | None, match_count: int, error: str | None) -> str:
    if error:
        return "error"
    if match_count <= 0:
        return "no_match"
    if score_100 is None:
        return "unknown_score"
    if score_100 < 80.0:
        return "low"
    if score_100 < 95.0:
        return "medium"
    return "high"


def perturb_address(address: str) -> list[str]:
    """Generate intentionally messy/ambiguous variants for first-pass QA."""
    variants = {address}
    words = address.split()
    lowered = address.lower()
    variants.add(lowered)

    # Remove quadrant if present.
    if words and words[-1] in {"NW", "NE", "SW", "SE"}:
        variants.add(" ".join(words[:-1]))

    # Expand/contract common street type tokens.
    replacements = {
        "Street": "St",
        "St": "Street",
        "Avenue": "Ave",
        "Ave": "Avenue",
        "Road": "Rd",
        "Rd": "Road",
    }
    for src, dst in replacements.items():
        if src in address:
            variants.add(address.replace(src, dst))

    # Add unit noise.
    variants.add(f"{address} Apt 2")

    # Remove punctuation and compact spacing.
    variants.add(address.replace(".", "").replace(",", ""))
    variants.add(" ".join(address.split()))

    # Drop one character from the longest token (basic typo simulation).
    longest = max(words, key=len) if words else ""
    if len(longest) > 4:
        typo = longest[:-1]
        variants.add(address.replace(longest, typo, 1))

    return sorted(v for v in variants if v.strip())


def load_addresses(input_file: Path | None) -> list[str]:
    if input_file is None:
        return BASE_ADDRESSES
    if input_file.suffix.lower() == ".json":
        data = json.loads(input_file.read_text())
        if isinstance(data, list):
            return [str(x) for x in data]
        raise ValueError("JSON input must be an array of address strings")
    if input_file.suffix.lower() == ".csv":
        out: list[str] = []
        with input_file.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                value = row.get("address") or row.get("Address")
                if value:
                    out.append(value)
        return out
    raise ValueError("Unsupported input format. Use .json or .csv")


def build_sample_pool(addresses: list[str], perturb: bool, seed: int) -> list[str]:
    pool: list[str] = []
    for addr in addresses:
        if perturb:
            pool.extend(perturb_address(addr))
        else:
            pool.append(addr)
    # dedupe, shuffle deterministically
    unique = sorted(set(pool))
    rnd = random.Random(seed)
    rnd.shuffle(unique)
    return unique


async def fetch_robots_policy(base_url: str, user_agent: str) -> RobotsPolicy:
    robots_url = SETTINGS.robots_url
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(robots_url, headers={"User-Agent": user_agent})
        res.raise_for_status()
        txt = res.text

    crawl_delay = 60
    for line in txt.splitlines():
        if line.lower().startswith("crawl-delay:"):
            try:
                crawl_delay = int(line.split(":", 1)[1].strip())
            except ValueError:
                continue

    parser = RobotFileParser()
    parser.parse(txt.splitlines())
    probe_url = f"{base_url}/locations/test/false/false"
    allowed = parser.can_fetch(user_agent, probe_url)
    return RobotsPolicy(allowed=allowed, crawl_delay_seconds=crawl_delay)


def write_outputs(rows: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "geocode_quality_samples.json"
    summary_path = output_dir / "geocode_quality_summary.json"
    geojson_path = output_dir / "geocode_quality_points.geojson"

    raw_path.write_text(json.dumps(rows, indent=2))

    total = len(rows)
    buckets: dict[str, int] = {}
    usable_scores = []
    for row in rows:
        bucket = row["quality_bucket"]
        buckets[bucket] = buckets.get(bucket, 0) + 1
        if row["score_100"] is not None:
            usable_scores.append(float(row["score_100"]))

    summary = {
        "total_samples": total,
        "quality_buckets": buckets,
        "avg_score_100": round(sum(usable_scores) / len(usable_scores), 3) if usable_scores else None,
    }
    summary_path.write_text(json.dumps(summary, indent=2))

    features = []
    for row in rows:
        lat = row.get("latitude")
        lon = row.get("longitude")
        if lat is None or lon is None:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "address": row["address"],
                    "matched_address": row.get("matched_address"),
                    "score_100": row.get("score_100"),
                    "match_count": row.get("match_count"),
                    "quality_bucket": row.get("quality_bucket"),
                    "error": row.get("error"),
                },
            }
        )
    geojson = {"type": "FeatureCollection", "features": features}
    geojson_path.write_text(json.dumps(geojson, indent=2))

    print(f"Saved: {raw_path}")
    print(f"Saved: {summary_path}")
    print(f"Saved: {geojson_path}")
    print(f"Summary: {summary}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect robots-safe geocode quality samples.")
    parser.add_argument("--api-key", default=SETTINGS.mar_api_key, help="MAR API key (or DC_MAR_API_KEY env).")
    parser.add_argument("--input-file", type=Path, default=None, help="Optional .json/.csv source of base addresses.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/geocode-quality"),
        help="Directory for sample outputs.",
    )
    parser.add_argument("--max-samples", type=int, default=20, help="Maximum number of sampled addresses.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for deterministic sampling order.")
    parser.add_argument(
        "--delay-seconds",
        type=int,
        default=None,
        help="Optional minimum delay override; effective delay is max(robots, this).",
    )
    parser.add_argument("--user-agent", default=SETTINGS.default_user_agent, help="User-Agent for robots/API calls.")
    parser.add_argument(
        "--no-perturb",
        action="store_true",
        help="Use raw addresses only (disable messy variant generation).",
    )
    return parser.parse_args()


async def run_collection(args: argparse.Namespace) -> int:
    if not args.api_key:
        print("Error: API key required. Set DC_MAR_API_KEY or pass --api-key.")
        return 2

    base_url = f"{SETTINGS.mar_base_url}{SETTINGS.mar_api_base_path}"
    policy = await fetch_robots_policy(base_url, args.user_agent)
    if not policy.allowed:
        print("Error: robots.txt disallows sampling endpoint; aborting.")
        return 3

    effective_delay = policy.crawl_delay_seconds
    if args.delay_seconds is not None:
        effective_delay = max(effective_delay, args.delay_seconds)

    base_addresses = load_addresses(args.input_file)
    pool = build_sample_pool(base_addresses, perturb=(not args.no_perturb), seed=args.seed)
    sample_addresses = pool[: args.max_samples]

    print(f"robots crawl-delay: {policy.crawl_delay_seconds}s")
    print(f"effective delay: {effective_delay}s")
    print(f"sample count: {len(sample_addresses)}")

    rows: list[dict[str, Any]] = []
    client = MARClient(api_key=args.api_key)
    try:
        for idx, address in enumerate(sample_addresses, start=1):
            started = time.time()
            row = {
                "address": address,
                "timestamp": started,
                "matched_address": None,
                "score_raw": None,
                "score_100": None,
                "latitude": None,
                "longitude": None,
                "match_count": 0,
                "quality_bucket": None,
                "error": None,
            }
            try:
                result = await client.search(address, use_cache=False, refresh=True)
                row["match_count"] = result.total_matches
                if result.matches:
                    top = result.matches[0]
                    row["matched_address"] = top.MatchedAddress
                    row["score_raw"] = top.Score
                    row["score_100"] = normalize_score(top.Score)
                    row["latitude"] = top.Latitude
                    row["longitude"] = top.Longitude
            except Exception as exc:
                row["error"] = str(exc)

            score_100 = row["score_100"]
            match_count = row["match_count"]
            error = row["error"]
            if not isinstance(score_100, (float, type(None))):
                raise TypeError("score_100 must be a float or None")
            if not isinstance(match_count, int):
                raise TypeError("match_count must be an integer")
            if not isinstance(error, (str, type(None))):
                raise TypeError("error must be a string or None")
            row["quality_bucket"] = quality_bucket(score_100, match_count, error)
            rows.append(row)
            print(
                f"[{idx}/{len(sample_addresses)}] {address} -> "
                f"matches={row['match_count']} score={row['score_100']} bucket={row['quality_bucket']}"
            )
            if idx < len(sample_addresses):
                await asyncio.sleep(effective_delay)
    finally:
        await client.close()

    write_outputs(rows, args.output_dir)
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(run_collection(args))


if __name__ == "__main__":
    raise SystemExit(main())
