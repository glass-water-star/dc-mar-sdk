"""
DC MAR API Client with caching and telemetry integration.
Provides high-level interface to autocomplete, search, and geocoding endpoints.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from dc_mar_sdk.cache import CacheBackend, CacheManager, SQLiteCache
from dc_mar_sdk.models import (
    AddressMatch,
    AutocompleteResponse,
    MARResponseEnvelope,
    SearchResponse,
)
from dc_mar_sdk.telemetry import RequestMetrics, TelemetryDB
from dc_mar_sdk.client.cache_policy import CachePolicy


class DCMarClient:
    """Master Address Repository (MAR) SDK client."""

    from dc_mar_sdk.settings import get_settings

    _SETTINGS = get_settings()
    BASE_URL = f"{_SETTINGS.mar_base_url}{_SETTINGS.mar_api_base_path}"
    logger = logging.getLogger(__name__)

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_backend: Optional[CacheBackend] = None,
        enable_telemetry: bool = True,
        cache_ttl_seconds: Optional[int] = None,
        timeout: Optional[int] = None,
        cache_policy: Optional[CachePolicy] = None,
    ):
        """
        Initialize MAR API client.

        Args:
            api_key: API key for authentication (required for production)
            cache_backend: Cache backend (defaults to SQLite)
            enable_telemetry: Enable usage tracking
            cache_ttl_seconds: Default cache TTL (default 1 hour)
            timeout: HTTP request timeout in seconds
        """
        self.api_key = api_key
        self.cache_manager = CacheManager(cache_backend or SQLiteCache())
        self.enable_telemetry = enable_telemetry
        # prefer explicit args, otherwise use settings defaults (legacy fallback TTL)
        self.cache_ttl_seconds = cache_ttl_seconds or self._SETTINGS.default_cache_ttl_seconds
        self.timeout = timeout or self._SETTINGS.default_timeout_seconds
        self._http_client: Optional[httpx.AsyncClient] = None

        # Cache policy: prefer explicit model, otherwise build from settings (non-breaking)
        if cache_policy is not None:
            self.cache_policy = cache_policy
        else:
            # settings fields are optional - when unset we keep legacy behavior
            self.cache_policy = CachePolicy(
                default_use_cache=getattr(self._SETTINGS, "default_cache_use", True),
                autocomplete_ttl_seconds=getattr(self._SETTINGS, "autocomplete_cache_ttl_seconds", None),
                search_ttl_seconds=getattr(self._SETTINGS, "search_cache_ttl_seconds", None),
            )

        if enable_telemetry:
            telemetry_db_path = self._SETTINGS.telemetry_db_path
            self.telemetry_db = TelemetryDB(Path(telemetry_db_path)) if telemetry_db_path else TelemetryDB()
        else:
            self.telemetry_db = None

    def _make_cache_key(self, endpoint: str, params: dict) -> str:
        """Generate a deterministic, namespaced cache key.

        Namespacing formula (stable & non-reversible):
        - api_scope_hash = SHA256(api_key) if api_key provided else 'no_key'
        - namespace_source = "{BASE_URL}|{api_scope_hash}" (BASE_URL includes base path/version)
        - namespace = SHA256(namespace_source)[:16] (hex, truncated for brevity)
        - payload_hash = MD5(endpoint + sorted(params json)) (same as previous behavior)
        - final key = "dc-mar-sdk:v1:{namespace}:{payload_hash}"

        Notes:
        - The API key is never stored in plaintext; only its SHA256 digest is used.
        - The leading prefix includes a version marker (v1) to allow future migration.
        - This keeps keys deterministic across runs for the same BASE_URL+API key scope,
          and prevents collisions across different keys or base URLs.
        """
        # Normalize base URL (no trailing slash) from class-level BASE_URL
        base = getattr(self, "BASE_URL", "") or ""
        base_norm = base.rstrip("/")

        # Compute non-reversible API key scope hash
        if self.api_key:
            api_scope_hash = hashlib.sha256(self.api_key.encode("utf-8")).hexdigest()
        else:
            api_scope_hash = "no_key"

        # Namespace derived from base URL + api scope hash
        namespace_source = f"{base_norm}|{api_scope_hash}"
        namespace = hashlib.sha256(namespace_source.encode("utf-8")).hexdigest()[:16]

        # Payload-specific hash (preserve previous behavior deterministically)
        payload = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        payload_hash = hashlib.md5(payload.encode("utf-8")).hexdigest()

        return f"dc-mar-sdk:v1:{namespace}:{payload_hash}"

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or initialize a shared HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        return self._http_client

    def _log_model_break(
        self,
        *,
        model_name: str,
        endpoint: str,
        payload: Any,
        error: Exception,
        status_code: Optional[int] = None,
        source: str = "api",
    ) -> None:
        """Emit debug log when payload cannot be validated into expected model."""
        if isinstance(payload, dict):
            payload_shape = f"dict keys={list(payload.keys())}"
        elif isinstance(payload, list):
            payload_shape = f"list len={len(payload)}"
        else:
            payload_shape = type(payload).__name__

        try:
            preview = json.dumps(payload, default=str)[:600]
        except Exception:
            preview = str(payload)[:600]

        self.logger.debug(
            "Model validation failed (model=%s endpoint=%s source=%s status=%s shape=%s error=%s payload_preview=%s)",
            model_name,
            endpoint,
            source,
            status_code,
            payload_shape,
            str(error),
            preview,
        )

    async def autocomplete(
        self,
        address: str,
        *,
        use_cache: Optional[bool] = None,
        refresh: bool = False,
        ttl_seconds: Optional[int] = None,
    ) -> List[str]:
        """
        Get autocomplete suggestions for an address.

        Args:
            address: Partial address string

        Returns:
            List of suggested addresses
        """
        if not self.api_key:
            raise ValueError("API key is required. Initialize client with api_key parameter.")

        endpoint = "/autocomplete"
        cache_key = self._make_cache_key(endpoint, {"address": address})

        # determine effective cache behavior
        effective_use_cache = self.cache_policy.default_use_cache if use_cache is None else use_cache
        # TTL precedence: explicit ttl_seconds -> per-operation policy -> legacy client ttl
        effective_ttl = (
            ttl_seconds
            if ttl_seconds is not None
            else (
                self.cache_policy.autocomplete_ttl_seconds
                if self.cache_policy.autocomplete_ttl_seconds is not None
                else self.cache_ttl_seconds
            )
        )

        # Attempt read unless explicitly bypassed or refresh requested
        if effective_use_cache and not refresh:
            cached = await self.cache_manager.get(cache_key)
            if cached is not None:
                if self.enable_telemetry:
                    metrics = RequestMetrics(self.telemetry_db, endpoint)
                    metrics.cached = True
                    metrics.__enter__()
                    metrics.__exit__(None, None, None)
                return cached

        try:
            client = await self._get_http_client()
            if self.enable_telemetry:
                with RequestMetrics(self.telemetry_db, endpoint) as metrics:
                    response = await client.get(
                        f"{self.BASE_URL}{endpoint}/{quote(address, safe='')}",
                        headers={
                            "Accept": "application/json",
                            "apiKey": self.api_key,
                        },
                    )
                    metrics.status_code = response.status_code
                    metrics.bytes_received = len(response.content)
            else:
                response = await client.get(
                    f"{self.BASE_URL}{endpoint}/{quote(address, safe='')}",
                    headers={
                        "Accept": "application/json",
                        "apiKey": self.api_key,
                    },
                )

            response.raise_for_status()
            data = response.json()
            envelope = MARResponseEnvelope.model_validate(data if isinstance(data, dict) else {"Result": data})
            if not envelope.Success:
                raise ValueError(f"Autocomplete failed: {envelope.Message or 'Unknown error'}")
            suggestions = envelope.Result if isinstance(envelope.Result, list) else []

            try:
                validated = AutocompleteResponse.model_validate({"suggestions": suggestions})
            except ValidationError as err:
                self._log_model_break(
                    model_name="AutocompleteResponse",
                    endpoint=endpoint,
                    payload={"suggestions": suggestions},
                    error=err,
                    status_code=response.status_code,
                )
                raise

            # Cache result when caching enabled
            if effective_use_cache:
                await self.cache_manager.set(cache_key, validated.suggestions, effective_ttl)

            return validated.suggestions

        except Exception as e:
            if self.enable_telemetry:
                self.telemetry_db.record_request(
                    endpoint=endpoint,
                    status_code=500,
                    error_message=str(e),
                )
            raise

    def _build_search_response_from_result(self, result: Any) -> SearchResponse:
        """Map MAR result payload into domain-level SearchResponse."""
        addresses: List[Any] = []
        if isinstance(result, dict):
            raw_addresses = result.get("addresses") or result.get("blockAddresses") or []
            if isinstance(raw_addresses, list):
                addresses = raw_addresses
        elif isinstance(result, list):
            addresses = result

        matches: List[AddressMatch] = []
        for entry in addresses:
            if not isinstance(entry, dict):
                continue
            props = {}
            address_obj = entry.get("address")
            if isinstance(address_obj, dict):
                props = address_obj.get("properties") or {}
            elif isinstance(entry.get("properties"), dict):
                props = entry.get("properties") or {}

            if not isinstance(props, dict):
                continue
            if not props:
                continue

            matches.append(
                AddressMatch(
                    Score=props.get("_Score") if props.get("_Score") is not None else props.get("Score"),
                    MatchedAddress=props.get("FullAddress") or props.get("MatchedAddress"),
                    MarId=props.get("MarId"),
                    AddressId=props.get("AddressId"),
                    Latitude=props.get("Latitude"),
                    Longitude=props.get("Longitude"),
                )
            )

        return SearchResponse(matches=matches, total_matches=len(matches))

    async def search(
        self,
        address: str,
        radius: Optional[float] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        *,
        use_cache: Optional[bool] = None,
        refresh: bool = False,
        ttl_seconds: Optional[int] = None,
    ) -> SearchResponse:
        """
        Search for addresses matching criteria.

        Args:
            address: Address string to search
            radius: Search radius in miles (optional)
            latitude: Latitude for geographic search (optional)
            longitude: Longitude for geographic search (optional)

        Returns:
            SearchResponse with matching addresses
        """
        if not self.api_key:
            raise ValueError("API key is required. Initialize client with api_key parameter.")

        if latitude is not None and longitude is not None:
            latlong = f"{longitude},{latitude}"
            if radius is not None:
                endpoint = "/locations/{latlong}/{distance}/{zones}/{geo}"
                endpoint_path = endpoint.format(
                    latlong=quote(latlong, safe=""),
                    distance=quote(str(radius), safe=""),
                    zones="false",
                    geo="false",
                )
            else:
                endpoint = "/locations/{latlong}/{zones}/{geo}"
                endpoint_path = endpoint.format(
                    latlong=quote(latlong, safe=""),
                    zones="false",
                    geo="false",
                )
        else:
            endpoint = "/locations/{address}/{zones}/{geo}"
            endpoint_path = endpoint.format(
                address=quote(address, safe=""),
                zones="false",
                geo="false",
            )

        params = {
            "address": address,
            "radius": radius,
            "latitude": latitude,
            "longitude": longitude,
            "endpoint_path": endpoint_path,
        }

        cache_key = self._make_cache_key(endpoint, params)

        # effective behaviors
        effective_use_cache = self.cache_policy.default_use_cache if use_cache is None else use_cache
        effective_ttl = (
            ttl_seconds
            if ttl_seconds is not None
            else (
                self.cache_policy.search_ttl_seconds
                if self.cache_policy.search_ttl_seconds is not None
                else self.cache_ttl_seconds
            )
        )

        # Try cache read unless bypassed or refresh requested
        if effective_use_cache and not refresh:
            cached = await self.cache_manager.get(cache_key)
            if cached is not None:
                if self.enable_telemetry:
                    self.telemetry_db.record_request(endpoint, cached=True)
                try:
                    return SearchResponse.model_validate(cached)
                except ValidationError as err:
                    self._log_model_break(
                        model_name="SearchResponse",
                        endpoint=endpoint,
                        payload=cached,
                        error=err,
                        source="cache",
                    )
                    raise

        try:
            client = await self._get_http_client()
            if self.enable_telemetry:
                with RequestMetrics(self.telemetry_db, endpoint) as metrics:
                    response = await client.get(
                        f"{self.BASE_URL}{endpoint_path}",
                        headers={
                            "Accept": "application/json",
                            "apiKey": self.api_key,
                        },
                    )
                    metrics.status_code = response.status_code
                    metrics.bytes_received = len(response.content)
            else:
                response = await client.get(
                    f"{self.BASE_URL}{endpoint_path}",
                    headers={
                        "Accept": "application/json",
                        "apiKey": self.api_key,
                    },
                )

            response.raise_for_status()
            data = response.json()
            envelope = MARResponseEnvelope.model_validate(data if isinstance(data, dict) else {"Result": data})
            if not envelope.Success:
                raise ValueError(f"Search failed: {envelope.Message or 'Unknown error'}")

            try:
                mapped = self._build_search_response_from_result(envelope.Result)
                validated = SearchResponse.model_validate(mapped.model_dump())
            except ValidationError as err:
                self._log_model_break(
                    model_name="SearchResponse",
                    endpoint=endpoint,
                    payload=data,
                    error=err,
                    status_code=response.status_code,
                )
                raise

            # Cache normalized domain response when caching enabled
            if effective_use_cache:
                await self.cache_manager.set(cache_key, validated.model_dump(), effective_ttl)
            return validated

        except Exception as e:
            if self.enable_telemetry:
                self.telemetry_db.record_request(
                    endpoint=endpoint,
                    status_code=500,
                    error_message=str(e),
                )
            raise

    async def get_cache_stats(self) -> dict:
        """Get cache statistics"""
        return await self.cache_manager.get_stats()

    async def get_api_stats(self, hours: int = 24) -> dict:
        """Get API usage statistics"""
        if not self.enable_telemetry:
            return {"error": "Telemetry not enabled"}
        return self.telemetry_db.get_api_stats(hours)

    async def get_endpoint_popularity(self, limit: int = 10) -> List[dict]:
        """Get most popular endpoints"""
        if not self.enable_telemetry:
            return []
        return self.telemetry_db.get_endpoint_popularity(limit)

    async def get_data_summary(self) -> dict:
        """Get summary of all data collected from API"""
        if not self.enable_telemetry:
            return {"error": "Telemetry not enabled"}
        return self.telemetry_db.get_data_summary()

    async def clear_cache(self) -> None:
        """Clear all cache entries"""
        await self.cache_manager.clear()

    async def close(self) -> None:
        """Close any open connections"""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


MARClient = DCMarClient
