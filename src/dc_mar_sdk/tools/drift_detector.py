#!/usr/bin/env python3
"""
Swagger Drift Detection System

Compares actual API responses against the Swagger spec to detect:
- Response format changes
- Missing fields
- Type mismatches
- Status code changes
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote
from urllib.robotparser import RobotFileParser

import httpx

HTTP_METHODS = ("get", "post", "put", "patch", "delete")

KNOWN_ENVELOPE_OPERATIONS = {
    ("get", "/api/v2.2/autocomplete/{address}"),
    ("post", "/api/v2.2/autocomplete/{address}"),
    ("post", "/api/v2.2/autocomplete"),
    ("post", "/api/v2.2/locations/{address}/{zones}/{geo}"),
}
KNOWN_DYNAMIC_JTOKEN_OPERATION = ("post", "/api/v2.2/locations/{geo}")
LOCATION_BATCH_PREFIX = "/api/v2.2/locationbatch"


@dataclass
class DriftIssue:
    """Represents a drift between spec and actual response."""

    endpoint: str
    method: str
    status_code: int
    issue_type: str
    spec_format: str
    actual_format: str
    location: str = ""
    severity: str = "info"


@dataclass
class EndpointTest:
    """Test result for a single endpoint operation."""

    endpoint: str
    method: str
    status_code: int
    success: bool
    issues: list[DriftIssue] = field(default_factory=list)
    actual_response: Any | None = None


class SwaggerValidator:
    def __init__(self, swagger_path: str, api_key: str):
        from dc_mar_sdk.settings import get_settings

        _SETTINGS = get_settings()

        self.swagger_path = swagger_path
        self.api_key = api_key
        self.base_url = _SETTINGS.mar_base_url
        self.robots_url = _SETTINGS.robots_url
        self.spec = self._load_swagger()
        self.components = self.spec.get("components", {}).get("schemas", {})
        self.test_params = {
            "address": "1600",
            "marid": "0000000",
            "zone": "Ward 1",
            "latlong": "-77.0369,38.8951",
            "count": "10",
            "distance": "500",
            "geo": "true",
            "ssl": "1",
            "type": "Unit",
            "address_base64": "MTYwMCBQZW5uc3lsdmFuaWE=",
            "address_separator": ",",
            "chunkSequnce_separator": "|",
            "parallel": "false",
        }

    def _load_swagger(self) -> dict[str, Any]:
        with open(self.swagger_path) as f:
            loaded = json.load(f)
        if not isinstance(loaded, dict):
            raise ValueError("Swagger specification root must be a JSON object")
        return loaded

    def _parse_operation_allowlist(self, operation_allowlist: list[str] | None) -> set[tuple[str, str]] | None:
        if not operation_allowlist:
            return None
        parsed: set[tuple[str, str]] = set()
        for item in operation_allowlist:
            value = item.strip()
            if not value:
                continue
            if " " not in value:
                continue
            method, path = value.split(" ", 1)
            parsed.add((path.strip(), method.strip().lower()))
        return parsed or None

    def _iter_operations(
        self,
        include_unsafe_methods: bool = False,
        operation_allowlist: list[str] | None = None,
    ) -> list[tuple[str, str, dict[str, Any]]]:

        operations: list[tuple[str, str, dict[str, Any]]] = []
        allowset = self._parse_operation_allowlist(operation_allowlist)
        for endpoint_path, path_item in self.spec.get("paths", {}).items():
            for method in HTTP_METHODS:
                if method in path_item:
                    if not include_unsafe_methods and method != "get":
                        continue
                    if allowset and (endpoint_path, method) not in allowset:
                        continue
                    operations.append((endpoint_path, method, path_item[method]))
        return operations

    def _resolve_ref(self, schema: dict[str, Any]) -> dict[str, Any]:
        ref = schema.get("$ref")
        if not ref:
            return schema
        if not ref.startswith("#/components/schemas/"):
            return schema
        name = ref.split("/")[-1]
        if name == "JToken":
            # JToken is intentionally untyped/dynamic payload in this API.
            return {}
        resolved = self.components.get(name, schema)
        return resolved if isinstance(resolved, dict) else schema

    def _build_url(self, endpoint_path: str) -> str:
        params = re.findall(r"\{(\w+)\}", endpoint_path)
        built = endpoint_path
        for param in params:
            value = self.test_params.get(param, f"test_{param}")
            built = built.replace(f"{{{param}}}", quote(str(value), safe=""))
        return f"{self.base_url}{built}"

    async def check_robots_txt(
        self,
        user_agent: str | None = None,
        include_unsafe_methods: bool = False,
        operation_allowlist: list[str] | None = None,
    ) -> tuple[bool, list[str], str | None]:
        """
        Check robots.txt and verify all drift-check URLs are allowed.

        Returns (allowed, disallowed_operations, note_or_error).
        """
        from dc_mar_sdk.settings import get_settings

        _SETTINGS = get_settings()
        user_agent = user_agent or _SETTINGS.drift_user_agent

        try:
            async with httpx.AsyncClient(timeout=_SETTINGS.default_timeout_seconds) as client:
                response = await client.get(self.robots_url, headers={"User-Agent": user_agent})
        except Exception as exc:
            return True, [], f"robots.txt unavailable ({exc}); proceeding without explicit policy."

        if response.status_code >= 400:
            return (
                True,
                [],
                f"robots.txt unavailable (HTTP {response.status_code}); proceeding without explicit policy.",
            )

        parser = RobotFileParser()
        parser.parse(response.text.splitlines())

        disallowed: list[str] = []
        for endpoint_path, method, _ in self._iter_operations(
            include_unsafe_methods=include_unsafe_methods,
            operation_allowlist=operation_allowlist,
        ):
            url = self._build_url(endpoint_path)
            if not parser.can_fetch(user_agent, url):
                disallowed.append(f"{method.upper()} {endpoint_path}")

        return len(disallowed) == 0, disallowed, None

    def _sample_from_schema(self, schema: dict[str, Any]) -> Any:
        if not schema:
            return {}
        schema = self._resolve_ref(schema)
        schema_type = schema.get("type")
        if isinstance(schema_type, list):
            non_null = [t for t in schema_type if t != "null"]
            schema_type = non_null[0] if non_null else None
        if schema.get("nullable") and not schema_type:
            return None
        if schema_type == "object":
            out: dict[str, Any] = {}
            props = schema.get("properties", {})
            required = set(schema.get("required", []))
            for key, value_schema in props.items():
                if required and key not in required:
                    continue
                out[key] = self._sample_from_schema(value_schema)
            return out
        if schema_type == "array":
            return []
        if schema_type == "string":
            return "example"
        if schema_type == "integer":
            return 1
        if schema_type == "number":
            return 1.0
        if schema_type == "boolean":
            return True
        return {}

    def _build_request_payload(self, operation: dict[str, Any]) -> Any | None:
        body = operation.get("requestBody", {})
        content = body.get("content", {})
        for content_type in ("application/json", "text/json", "text/plain"):
            if content_type in content:
                schema = content[content_type].get("schema", {})
                if schema.get("$ref") == "#/components/schemas/JToken":
                    # The source contract declares JToken as a recursive array,
                    # but live location POST operations require an address object.
                    return {"address": "1600 Pennsylvania"}
                if schema.get("$ref") == "#/components/schemas/AddressBase64":
                    return {"address_base64": self.test_params["address_base64"]}
                return self._sample_from_schema(schema)
        return None

    def _get_response_schema(self, endpoint: str, method: str, status_code: int) -> dict[str, Any] | None:
        path_item = self.spec.get("paths", {}).get(endpoint, {})
        operation = path_item.get(method, {})
        responses = operation.get("responses", {})
        response_info = responses.get(str(status_code)) or responses.get("default")
        if response_info is None and 200 <= status_code < 300:
            response_info = responses.get("200")
        if not response_info:
            return None

        content = response_info.get("content", {})
        for content_type in ("application/json", "text/json", "text/plain"):
            if content_type in content:
                schema = content[content_type].get("schema", {})
                return self._resolve_ref(schema)
        return {}

    def _is_type_match(self, value: Any, schema: dict[str, Any]) -> bool:
        if value is None:
            if schema.get("nullable"):
                return True
            schema_type = schema.get("type")
            return isinstance(schema_type, list) and "null" in schema_type

        schema_type = schema.get("type")
        if isinstance(schema_type, list):
            return any(self._is_type_match(value, {"type": t, "nullable": schema.get("nullable")}) for t in schema_type)
        if schema_type == "object":
            return isinstance(value, dict)
        if schema_type == "array":
            return isinstance(value, list)
        if schema_type == "string":
            return isinstance(value, str)
        if schema_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if schema_type == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if schema_type == "boolean":
            return isinstance(value, bool)
        return True

    def _validate_type(self, value: Any, schema: dict[str, Any], path: str = "$") -> list[dict[str, str]]:
        issues: list[dict[str, str]] = []
        if not schema:
            return issues

        if not self._is_type_match(value, schema):
            issues.append(
                {
                    "location": path,
                    "severity": "error",
                    "type_error": f"Expected {schema.get('type')} at {path}, got {type(value).__name__}",
                }
            )
            return issues

        if value is None:
            return issues

        schema_type = schema.get("type")
        if isinstance(schema_type, list):
            schema_type = next((t for t in schema_type if t != "null"), None)

        if schema_type == "array":
            items_schema = self._resolve_ref(schema.get("items", {}))
            for i, item in enumerate(value[:5]):
                issues.extend(self._validate_type(item, items_schema, f"{path}[{i}]"))
        elif schema_type == "object":
            properties = schema.get("properties", {})
            required = schema.get("required", []) or []
            additional_properties = schema.get("additionalProperties")
            for field_name in required:
                if field_name not in value:
                    issues.append(
                        {
                            "location": f"{path}.{field_name}",
                            "severity": "error",
                            "type_error": f"Missing required field '{field_name}'",
                        }
                    )
            for field_name, field_value in value.items():
                if field_name in properties:
                    issues.extend(
                        self._validate_type(
                            field_value,
                            self._resolve_ref(properties[field_name]),
                            f"{path}.{field_name}",
                        )
                    )
                elif isinstance(additional_properties, dict):
                    issues.extend(
                        self._validate_type(
                            field_value,
                            self._resolve_ref(additional_properties),
                            f"{path}.{field_name}",
                        )
                    )
                elif additional_properties is True:
                    # Any shape is allowed.
                    continue
                else:
                    issues.append(
                        {
                            "location": f"{path}.{field_name}",
                            "severity": "warning",
                            "type_error": f"Extra field '{field_name}' not in spec schema",
                        }
                    )
        return issues

    def _validate_response(
        self, actual: Any, schema: dict[str, Any] | None, endpoint: str, method: str, status_code: int
    ) -> list[DriftIssue]:
        operation = (method.lower(), endpoint)
        if operation in KNOWN_ENVELOPE_OPERATIONS and self._is_live_envelope(
            actual, result_is_list=endpoint.startswith("/api/v2.2/autocomplete")
        ):
            return []
        if operation == KNOWN_DYNAMIC_JTOKEN_OPERATION and self._is_live_envelope(actual, result_is_object=True):
            return []
        if endpoint.startswith(LOCATION_BATCH_PREFIX) and self._is_live_batch_response(actual):
            return []
        if schema is None:
            return [
                DriftIssue(
                    endpoint=endpoint,
                    method=method,
                    status_code=status_code,
                    issue_type="status_code_mismatch",
                    spec_format="Documented response status",
                    actual_format=f"Undocumented status: {status_code}",
                    location=endpoint,
                    severity="error",
                )
            ]
        if schema == {}:
            return []

        issues: list[DriftIssue] = []
        spec_type = schema.get("type", "unknown")
        if isinstance(actual, dict) and spec_type == "array":
            issues.append(
                DriftIssue(
                    endpoint=endpoint,
                    method=method,
                    status_code=status_code,
                    issue_type="schema_mismatch",
                    spec_format=f"array of {schema.get('items', {}).get('type', 'unknown')}",
                    actual_format=f"object with keys: {list(actual.keys())}",
                    location=endpoint,
                    severity="error",
                )
            )
        elif isinstance(actual, list) and spec_type != "array":
            issues.append(
                DriftIssue(
                    endpoint=endpoint,
                    method=method,
                    status_code=status_code,
                    issue_type="schema_mismatch",
                    spec_format=str(spec_type),
                    actual_format="array",
                    location=endpoint,
                    severity="error",
                )
            )
        for issue in self._validate_type(actual, schema):
            issues.append(
                DriftIssue(
                    endpoint=endpoint,
                    method=method,
                    status_code=status_code,
                    issue_type="type_error",
                    spec_format=str(schema.get("type", "unknown")),
                    actual_format=str(type(actual).__name__),
                    location=issue["location"],
                    severity=issue["severity"],
                )
            )
        return issues

    @staticmethod
    def _is_live_envelope(response: Any, *, result_is_list: bool = False, result_is_object: bool = False) -> bool:
        if not isinstance(response, dict) or not {"Result", "Success", "Message"}.issubset(response):
            return False
        if not isinstance(response["Success"], bool):
            return False
        if response["Message"] is not None and not isinstance(response["Message"], str):
            return False
        if result_is_list:
            return isinstance(response["Result"], list)
        if result_is_object:
            return isinstance(response["Result"], dict)
        return True

    @classmethod
    def _is_live_batch_response(cls, response: Any) -> bool:
        if not isinstance(response, dict):
            return False
        if not isinstance(response.get("ChunkNumber"), int) or not isinstance(response.get("ProcessTime"), str):
            return False
        results = response.get("Results")
        return isinstance(results, list) and all(cls._is_live_envelope(item, result_is_object=True) for item in results)

    async def _test_operation(
        self, endpoint_path: str, method: str, operation: dict[str, Any], user_agent: str
    ) -> EndpointTest:
        url = self._build_url(endpoint_path)
        payload = self._build_request_payload(operation)
        headers = {
            "apiKey": self.api_key,
            "Accept": "application/json",
            "User-Agent": user_agent,
        }

        try:
            from dc_mar_sdk.settings import get_settings

            _SETTINGS = get_settings()
            async with httpx.AsyncClient(timeout=_SETTINGS.default_timeout_seconds) as client:
                response = await client.request(
                    method.upper(),
                    url,
                    headers=headers,
                    json=payload if payload is not None else None,
                )

            try:
                actual: Any = response.json()
            except ValueError:
                actual = response.text

            if response.status_code >= 400:
                error_text = ""
                if isinstance(actual, dict):
                    msg = actual.get("Message") or actual.get("message") or actual.get("error")
                    error_text = str(msg) if msg is not None else str(actual)
                else:
                    error_text = str(actual)
                return EndpointTest(
                    endpoint=endpoint_path,
                    method=method,
                    status_code=response.status_code,
                    success=False,
                    issues=[
                        DriftIssue(
                            endpoint=endpoint_path,
                            method=method,
                            status_code=response.status_code,
                            issue_type="http_error",
                            spec_format="2xx contract response",
                            actual_format=f"HTTP {response.status_code}: {error_text}",
                            location=endpoint_path,
                            severity="error",
                        )
                    ],
                    actual_response=actual,
                )

            schema = self._get_response_schema(endpoint_path, method, response.status_code)
            issues = self._validate_response(actual, schema, endpoint_path, method, response.status_code)

            return EndpointTest(
                endpoint=endpoint_path,
                method=method,
                status_code=response.status_code,
                success=len([i for i in issues if i.severity == "error"]) == 0,
                issues=issues,
                actual_response=actual,
            )
        except Exception as exc:
            return EndpointTest(
                endpoint=endpoint_path,
                method=method,
                status_code=500,
                success=False,
                issues=[
                    DriftIssue(
                        endpoint=endpoint_path,
                        method=method,
                        status_code=500,
                        issue_type="request_failed",
                        spec_format="<expected response>",
                        actual_format=f"Exception: {exc}",
                        location=endpoint_path,
                        severity="error",
                    )
                ],
            )

    async def test_all(
        self,
        user_agent: str | None = None,
        include_unsafe_methods: bool = False,
        operation_allowlist: list[str] | None = None,
    ) -> list[EndpointTest]:

        from dc_mar_sdk.settings import get_settings

        _SETTINGS = get_settings()
        user_agent = user_agent or _SETTINGS.drift_user_agent

        results: list[EndpointTest] = []
        for endpoint_path, method, operation in self._iter_operations(
            include_unsafe_methods=include_unsafe_methods,
            operation_allowlist=operation_allowlist,
        ):
            results.append(await self._test_operation(endpoint_path, method, operation, user_agent))
        return results


async def main() -> None:
    from dc_mar_sdk.settings import get_settings

    _SETTINGS = get_settings()
    api_key = "REPLACE_WITH_KEY"
    swagger_path = f"{_SETTINGS.swagger_dir}/{_SETTINGS.swagger_file_name}"
    validator = SwaggerValidator(swagger_path, api_key)
    results = await validator.test_all()

    total_errors = sum(1 for r in results for i in r.issues if i.severity == "error")
    print(f"Tested operations: {len(results)}")
    print(f"Critical errors: {total_errors}")
    for result in results:
        if result.issues:
            print(f"- {result.method.upper()} {result.endpoint}: {len(result.issues)} issue(s)")


if __name__ == "__main__":
    asyncio.run(main())
