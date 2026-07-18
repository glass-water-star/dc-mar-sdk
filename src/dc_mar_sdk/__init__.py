"""DC MAR SDK for DC DataGate Master Address Repository (MAR).

Provides caching, telemetry, dashboard, and CLI helpers for data collection.
"""

try:
    # Prefer installed package metadata when available
    from importlib.metadata import version as _pkg_version, PackageNotFoundError
except Exception:  # importlib.metadata should be available on py311, but guard just in case
    _pkg_version = None
    PackageNotFoundError = Exception

__version__ = "0.0.0"

if _pkg_version is not None:
    try:
        __version__ = _pkg_version("dc-mar-sdk")
    except PackageNotFoundError:
        # When running from source (not installed), read pyproject.toml if present.
        try:
            import pathlib
            import tomllib

            _py = pathlib.Path(__file__).resolve().parents[2] / "pyproject.toml"
            if _py.exists():
                with _py.open("rb") as _f:
                    _data = tomllib.load(_f)
                    __version__ = _data.get("project", {}).get("version", __version__)
        except Exception:
            # leave fallback version
            pass

from dc_mar_sdk.cache import CacheManager, InMemoryCache, RedisCache, SQLiteCache
from dc_mar_sdk.client import DCMarClient, MARClient
from dc_mar_sdk.models import (
    AddressInput,
    AddressMatch,
    AutocompleteResponse,
    MARResponseEnvelope,
    SearchResponse,
)
from dc_mar_sdk.telemetry import RequestMetrics, TelemetryDB

__all__ = [
    "MARClient",
    "DCMarClient",
    "CacheManager",
    "InMemoryCache",
    "SQLiteCache",
    "RedisCache",
    "TelemetryDB",
    "RequestMetrics",
    "AddressInput",
    "AddressMatch",
    "SearchResponse",
    "AutocompleteResponse",
    "MARResponseEnvelope",
]
