"""
DC MAR API Client with caching and telemetry integration.
Provides high-level interface to autocomplete, search, and geocoding endpoints.
"""

import hashlib
import json
import logging
import random
import time
from asyncio import sleep
from collections.abc import Mapping
from pathlib import Path
from types import TracebackType
from typing import Any, Self, TypeVar
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ValidationError

from dc_mar_sdk.cache import CacheBackend, CacheManager, CacheStats, SQLiteCache
from dc_mar_sdk.client.cache_policy import CachePolicy
from dc_mar_sdk.client.contracts import ContractValidationError
from dc_mar_sdk.models import (
    AddressBase64,
    AddressInput,
    AddressMatch,
    AutocompleteResponse,
    GeoAddressWithZonesListServiceResponse,
    LocationBatchResponse,
    LocationResultServiceResponse,
    MARResponseEnvelope,
    SearchResponse,
    SSLInput,
    UnitInput,
)
from dc_mar_sdk.operations import API_OPERATIONS, build_operation_path
from dc_mar_sdk.settings import get_settings
from dc_mar_sdk.telemetry import RequestMetrics, TelemetryDB


class DCMarClient:
    """Master Address Repository (MAR) SDK client."""

    _SETTINGS = get_settings()
    BASE_URL = f"{_SETTINGS.mar_base_url}{_SETTINGS.mar_api_base_path}"
    logger = logging.getLogger(__name__)
    _ResponseModel = TypeVar("_ResponseModel", bound=BaseModel)

    def __init__(
        self,
        api_key: str | None = None,
        cache_backend: CacheBackend | None = None,
        enable_telemetry: bool = True,
        cache_ttl_seconds: int | None = None,
        timeout: int | None = None,
        cache_policy: CachePolicy | None = None,
    ) -> None:
        """
        Initialize MAR API client.

        Args:
            api_key: API key for authentication (required for production)
            cache_backend: Cache backend (defaults to SQLite)
            enable_telemetry: Enable usage tracking
            cache_ttl_seconds: Default cache TTL (default 1 hour)
            timeout: HTTP request timeout in seconds
        """
        self.api_key = api_key or self._SETTINGS.mar_api_key or None
        self.cache_manager = CacheManager(cache_backend or SQLiteCache())
        self.enable_telemetry = enable_telemetry
        # prefer explicit args, otherwise use settings defaults (legacy fallback TTL)
        self.cache_ttl_seconds = cache_ttl_seconds or self._SETTINGS.default_cache_ttl_seconds
        self.timeout = timeout or self._SETTINGS.default_timeout_seconds
        self.retry_max_attempts: int = self._SETTINGS.retry_max_attempts
        self.retry_backoff_initial_seconds: float = self._SETTINGS.retry_backoff_initial_seconds
        self.retry_backoff_max_seconds: float = self._SETTINGS.retry_backoff_max_seconds
        self._http_client: httpx.AsyncClient | None = None

        # Cache policy: prefer explicit model, otherwise build from settings (non-breaking)
        if cache_policy is not None:
            self.cache_policy = cache_policy
        else:
            # settings fields are optional - when unset we keep legacy behavior
            self.cache_policy = CachePolicy(
                default_use_cache=getattr(self._SETTINGS, "default_cache_use", True),
                autocomplete_ttl_seconds=getattr(self._SETTINGS, "autocomplete_cache_ttl_seconds", None),
                search_ttl_seconds=getattr(self._SETTINGS, "search_cache_ttl_seconds", None),
                stale_while_revalidate=False,
            )

        self.telemetry_db: TelemetryDB | None
        if enable_telemetry:
            telemetry_db_path = self._SETTINGS.telemetry_db_path
            self.telemetry_db = (
                TelemetryDB(Path(telemetry_db_path), self._SETTINGS.telemetry_retention_days)
                if telemetry_db_path
                else TelemetryDB(retention_days=self._SETTINGS.telemetry_retention_days)
            )
        else:
            self.telemetry_db = None

    def _make_cache_key(self, endpoint: str, params: Mapping[str, Any]) -> str:
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
        api_scope_hash = hashlib.sha256(self.api_key.encode("utf-8")).hexdigest() if self.api_key else "no_key"

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

    def _retry_delay_seconds(self, response: httpx.Response | None, attempt: int) -> float:
        """Return the bounded retry delay, honoring a numeric Retry-After value."""
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return min(float(retry_after), float(self.retry_backoff_max_seconds))
                except ValueError:
                    pass
        backoff = min(
            float(self.retry_backoff_initial_seconds) * (2**attempt),
            float(self.retry_backoff_max_seconds),
        )
        return random.uniform(0, backoff)

    async def _send_request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, str | int | float | bool | None] | None = None,
        json_body: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        """Send a MAR request with bounded retry handling for transient failures."""
        client = await self._get_http_client()
        last_transport_error: httpx.TransportError | None = None
        for attempt in range(self.retry_max_attempts):
            response: httpx.Response | None = None
            try:
                response = await client.request(method, url, params=params, json=json_body, headers=headers)
            except httpx.TransportError as error:
                last_transport_error = error
            else:
                if response.status_code != 429 and response.status_code < 500:
                    return response

            if attempt + 1 < self.retry_max_attempts:
                await sleep(self._retry_delay_seconds(response, attempt))

        if last_transport_error is not None:
            raise last_transport_error
        assert response is not None
        return response

    def _log_model_break(
        self,
        *,
        model_name: str,
        endpoint: str,
        payload: Any,
        error: Exception,
        status_code: int | None = None,
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
        use_cache: bool | None = None,
        refresh: bool = False,
        ttl_seconds: int | None = None,
    ) -> list[str]:
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
                if isinstance(cached, list) and all(isinstance(suggestion, str) for suggestion in cached):
                    if self.enable_telemetry:
                        assert self.telemetry_db is not None
                        async with RequestMetrics(self.telemetry_db, endpoint) as metrics:
                            metrics.cached = True
                    return cached
                await self.cache_manager.delete(cache_key)

        if self.enable_telemetry:
            assert self.telemetry_db is not None
            async with RequestMetrics(self.telemetry_db, endpoint) as metrics:
                response = await self._send_request(
                    "GET",
                    f"{self.BASE_URL}{endpoint}/{quote(address, safe='')}",
                    headers={
                        "Accept": "application/json",
                        "apiKey": self.api_key,
                    },
                )
                metrics.status_code = response.status_code
                metrics.bytes_received = len(response.content)
                response.raise_for_status()
        else:
            response = await self._send_request(
                "GET",
                f"{self.BASE_URL}{endpoint}/{quote(address, safe='')}",
                headers={
                    "Accept": "application/json",
                    "apiKey": self.api_key,
                },
            )
            response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and "Success" not in data:
            raise ValueError("Autocomplete response is missing required MAR envelope field: Success")
        envelope = MARResponseEnvelope.model_validate(
            data if isinstance(data, dict) else {"Result": data, "Success": True}
        )
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

    async def request_operation(
        self,
        method: str,
        operation: str,
        *,
        path_parameters: Mapping[str, object] | None = None,
        query_parameters: Mapping[str, str | int | float | bool | None] | None = None,
        json_body: Any = None,
    ) -> Any:
        """Call any operation published in the authoritative MAR v2.2 contract.

        ``operation`` must be the Swagger path template, for example
        ``/api/v2.2/units/{marid}``. This deliberately returns the unmodified
        API JSON so callers retain all fields from endpoints without complete
        response schemas in the upstream contract.
        """
        if not self.api_key:
            raise ValueError("API key is required. Initialize client with api_key parameter.")

        normalized_method = method.upper()
        if (normalized_method, operation) not in API_OPERATIONS:
            raise ValueError(f"Unsupported MAR v2.2 operation: {normalized_method} {operation}")

        endpoint = build_operation_path(operation, path_parameters)
        started_at = time.perf_counter()
        response: httpx.Response | None = None
        try:
            response = await self._send_request(
                normalized_method,
                f"{self.BASE_URL}{endpoint}",
                params=query_parameters,
                json_body=json_body,
                headers={"Accept": "application/json", "apiKey": self.api_key},
            )
            response.raise_for_status()
            return response.json()
        except Exception as error:
            if self.enable_telemetry:
                assert self.telemetry_db is not None
                await self.telemetry_db.async_record_request(
                    endpoint=operation,
                    method=normalized_method,
                    status_code=response.status_code if response is not None else None,
                    response_time_ms=(time.perf_counter() - started_at) * 1000,
                    bytes_received=len(response.content) if response is not None else 0,
                    error_message=str(error),
                )
            raise
        finally:
            if self.enable_telemetry and response is not None and response.status_code < 400:
                assert self.telemetry_db is not None
                await self.telemetry_db.async_record_request(
                    endpoint=operation,
                    method=normalized_method,
                    status_code=response.status_code,
                    response_time_ms=(time.perf_counter() - started_at) * 1000,
                    bytes_received=len(response.content),
                )

    async def _request_typed_operation(
        self,
        method: str,
        operation: str,
        response_model: type[_ResponseModel],
        *,
        path_parameters: Mapping[str, object] | None = None,
        query_parameters: Mapping[str, str | int | float | bool | None] | None = None,
        json_body: Any = None,
    ) -> _ResponseModel:
        payload = await self.request_operation(
            method,
            operation,
            path_parameters=path_parameters,
            query_parameters=query_parameters,
            json_body=json_body,
        )
        try:
            return response_model.model_validate(payload)
        except ValidationError as error:
            raise ContractValidationError(method, operation, str(error)) from error

    async def autocomplete_by_body(self, request: AddressInput) -> MARResponseEnvelope:
        """Autocomplete using the documented JSON-body POST operation."""
        return await self._request_typed_operation(
            "POST",
            "/api/v2.2/autocomplete",
            MARResponseEnvelope,
            json_body=request.model_dump(),
        )

    async def locate_address(
        self, address: str, *, zones: str | None = None, geo: bool = False, method: str = "GET"
    ) -> LocationResultServiceResponse:
        """Look up an address and validate the complete location response."""
        operation = "/api/v2.2/locations/{address}/{zones}/{geo}"
        return await self._request_typed_operation(
            method.upper(),
            operation,
            LocationResultServiceResponse,
            path_parameters={"address": address, "zones": zones or "false", "geo": str(geo).lower()},
        )

    async def locate_coordinates(
        self,
        longitude: float,
        latitude: float,
        *,
        count: int | None = None,
        distance: float | None = None,
        zones: str | None = None,
        geo: bool = False,
        method: str = "GET",
    ) -> GeoAddressWithZonesListServiceResponse:
        """Look up addresses near coordinates using a documented GET/POST route."""
        latlong = f"{longitude},{latitude}"
        if distance is not None:
            operation = "/api/v2.2/locations/{latlong}/{distance}/{zones}/{geo}"
            parameters = {
                "latlong": latlong,
                "distance": distance,
                "zones": zones or "false",
                "geo": str(geo).lower(),
            }
        elif count is not None:
            operation = "/api/v2.2/locations/{latlong}/{count}/{zones}/{geo}"
            parameters = {
                "latlong": latlong,
                "count": count,
                "zones": zones or "false",
                "geo": str(geo).lower(),
            }
        else:
            operation = "/api/v2.2/locations/{latlong}/{zones}/{geo}"
            parameters = {"latlong": latlong, "zones": zones or "false", "geo": str(geo).lower()}
        return await self._request_typed_operation(
            method.upper(), operation, GeoAddressWithZonesListServiceResponse, path_parameters=parameters
        )

    async def location_batch(
        self,
        request: AddressBase64,
        *,
        address_separator: str = ",",
        sequence_separator: str = "|",
        parallel: bool = False,
    ) -> LocationBatchResponse:
        """Run the documented body-based location batch operation."""
        return await self._request_typed_operation(
            "POST",
            "/api/v2.2/locationbatch/{address_separator}/{chunkSequnce_separator}/{parallel}",
            LocationBatchResponse,
            path_parameters={
                "address_separator": address_separator,
                "chunkSequnce_separator": sequence_separator,
                "parallel": str(parallel).lower(),
            },
            json_body=request.model_dump(),
        )

    async def lookup_ssl(self, request: SSLInput) -> MARResponseEnvelope:
        """Look up SSL data through the documented POST body operation."""
        return await self._request_typed_operation(
            "POST", "/api/v2.2/ssls", MARResponseEnvelope, json_body=request.model_dump(exclude_none=True)
        )

    async def lookup_units(self, request: UnitInput) -> MARResponseEnvelope:
        """Look up unit data through the documented POST body operation."""
        return await self._request_typed_operation(
            "POST", "/api/v2.2/units", MARResponseEnvelope, json_body=request.model_dump(exclude_none=True)
        )

    async def lookup_zone(self, zone: str) -> MARResponseEnvelope:
        """Look up a zone through the documented GET operation."""
        return await self._request_typed_operation(
            "GET", "/api/v2.2/zone/{zone}", MARResponseEnvelope, path_parameters={"zone": zone}
        )

    def _build_search_response_from_result(self, result: Any) -> SearchResponse:
        """Map MAR result payload into domain-level SearchResponse."""
        addresses: list[Any] = []
        if isinstance(result, dict):
            raw_addresses = result.get("addresses") or result.get("blockAddresses") or []
            if isinstance(raw_addresses, list):
                addresses = raw_addresses
        elif isinstance(result, list):
            addresses = result

        matches: list[AddressMatch] = []
        for entry in addresses:
            if not isinstance(entry, dict):
                continue
            props: dict[str, Any] = {}
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
        radius: float | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        *,
        use_cache: bool | None = None,
        refresh: bool = False,
        ttl_seconds: int | None = None,
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
                    assert self.telemetry_db is not None
                    await self.telemetry_db.async_record_request(endpoint, cached=True)
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

        if self.enable_telemetry:
            assert self.telemetry_db is not None
            async with RequestMetrics(self.telemetry_db, endpoint) as metrics:
                response = await self._send_request(
                    "GET",
                    f"{self.BASE_URL}{endpoint_path}",
                    headers={
                        "Accept": "application/json",
                        "apiKey": self.api_key,
                    },
                )
                metrics.status_code = response.status_code
                metrics.bytes_received = len(response.content)
                response.raise_for_status()
        else:
            response = await self._send_request(
                "GET",
                f"{self.BASE_URL}{endpoint_path}",
                headers={
                    "Accept": "application/json",
                    "apiKey": self.api_key,
                },
            )
            response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and "Success" not in data:
            raise ValueError("Search response is missing required MAR envelope field: Success")
        envelope = MARResponseEnvelope.model_validate(
            data if isinstance(data, dict) else {"Result": data, "Success": True}
        )
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

    async def get_cache_stats(self) -> CacheStats:
        """Get cache statistics"""
        return await self.cache_manager.get_stats()

    async def get_api_stats(self, hours: int = 24) -> dict[str, Any]:
        """Get API usage statistics"""
        if not self.enable_telemetry:
            return {"error": "Telemetry not enabled"}
        assert self.telemetry_db is not None
        return await self.telemetry_db.async_get_api_stats(hours)

    async def get_endpoint_popularity(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get most popular endpoints"""
        if not self.enable_telemetry:
            return []
        assert self.telemetry_db is not None
        return await self.telemetry_db.async_get_endpoint_popularity(limit)

    async def get_data_summary(self) -> dict[str, Any]:
        """Get summary of all data collected from API"""
        if not self.enable_telemetry:
            return {"error": "Telemetry not enabled"}
        assert self.telemetry_db is not None
        return await self.telemetry_db.async_get_data_summary()

    async def clear_cache(self) -> None:
        """Clear all cache entries"""
        await self.cache_manager.clear()

    async def close(self) -> None:
        """Close any open connections"""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self) -> Self:
        """Async context manager entry"""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit"""
        await self.close()


MARClient = DCMarClient
