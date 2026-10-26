"""DC MAR SDK for DC DataGate Master Address Repository (MAR).

Provides caching, telemetry, dashboard, and CLI helpers for data collection.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

__version__ = "0.0.0"

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
                version = _data.get("project", {}).get("version")
                if isinstance(version, str):
                    __version__ = version
    except (OSError, tomllib.TOMLDecodeError):
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
    "AddressInput",
    "AddressMatch",
    "AutocompleteResponse",
    "CacheManager",
    "DCMarClient",
    "InMemoryCache",
    "MARClient",
    "MARResponseEnvelope",
    "RedisCache",
    "RequestMetrics",
    "SQLiteCache",
    "SearchResponse",
    "TelemetryDB",
]
