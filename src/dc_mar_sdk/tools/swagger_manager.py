#!/usr/bin/env python3
"""
Swagger Version Management System

Handles versioning, fixing, and resetting Swagger specifications based on
actual API responses vs documented behavior.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx


class SwaggerManager:
    """Manages Swagger spec versions and generates updated specs from actual API"""

    def __init__(self, swagger_dir: Path, api_key: str):
        self.swagger_dir = Path(swagger_dir)
        self.api_key = api_key
        from dc_mar_sdk.settings import get_settings

        _SETTINGS = get_settings()
        self.base_url = _SETTINGS.mar_base_url  # Endpoints include api path in settings
        self.swagger_dir.mkdir(parents=True, exist_ok=True)
        self.swagger_file_name = _SETTINGS.swagger_file_name
        self.current_spec = self._load_swagger(self.swagger_dir / self.swagger_file_name)

    def _load_swagger(self, path: Path) -> Optional[Dict[str, Any]]:
        """Load Swagger spec from file"""
        if not path.exists():
            return None
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load {path}: {e}")
            return None

    def _save_swagger(self, spec: Dict[str, Any], path: Path) -> None:
        """Save Swagger spec to file"""
        with open(path, "w") as f:
            json.dump(spec, f, indent=2)
        print(f"✓ Saved: {path}")

    def validate_swagger_file(self, path: Optional[Path] = None) -> tuple[bool, List[str]]:
        """Validate basic Swagger/OpenAPI structure."""
        target = path or (self.swagger_dir / self.swagger_file_name)
        issues: List[str] = []

        if not target.exists():
            return False, [f"Missing file: {target}"]

        try:
            spec = self._load_swagger(target)
        except Exception as exc:  # pragma: no cover - defensive
            return False, [f"Failed to parse JSON: {exc}"]

        if not spec:
            return False, [f"Empty or invalid JSON: {target}"]

        if "paths" not in spec or not isinstance(spec["paths"], dict):
            issues.append("Missing or invalid 'paths' object")
        if "components" not in spec:
            issues.append("Missing 'components' object")
        if "openapi" not in spec and "swagger" not in spec:
            issues.append("Missing OpenAPI/Swagger version field")

        return len(issues) == 0, issues

    def list_versions(self) -> List[Dict[str, str]]:
        """List all available Swagger versions"""
        versions = []

        # Check for versioned files
        for path in sorted(self.swagger_dir.glob("swagger.v*.json")):
            match = path.stem.replace("swagger.v", "")
            if match.isdigit():
                stat = path.stat()
                versions.append({
                    "version": int(match),
                    "path": str(path),
                    "size": f"{stat.st_size / 1024:.1f} KB",
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

        # Add current (unversioned)
        current_path = self.swagger_dir / self.swagger_file_name
        if current_path.exists():
            stat = current_path.stat()
            versions.append({
                "version": "current",
                "path": str(current_path),
                "size": f"{stat.st_size / 1024:.1f} KB",
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

        return versions

    def _infer_schema_from_response(self, response: Any, param_name: str = None) -> Dict[str, Any]:
        """Generate JSON schema from actual API response"""
        if response is None:
            # OpenAPI 3.0-friendly nullable fallback without forcing a concrete type.
            return {"nullable": True}
        if isinstance(response, str):
            return {"type": "string"}
        if isinstance(response, bool):
            return {"type": "boolean"}
        if isinstance(response, int):
            return {"type": "integer"}
        if isinstance(response, float):
            return {"type": "number"}
        if isinstance(response, list):
            if not response:
                return {"type": "array", "items": {}}
            # Infer from up to first 5 items, merging to capture shape variation.
            item_schemas = [self._infer_schema_from_response(item) for item in response[:5]]
            item_schema = item_schemas[0]
            for schema in item_schemas[1:]:
                item_schema = self._merge_schemas(item_schema, schema)
            return {"type": "array", "items": item_schema}
        if isinstance(response, dict):
            properties = {}
            for key, value in response.items():
                properties[key] = self._infer_schema_from_response(value, key)
            schema: Dict[str, Any] = {
                "type": "object",
                "properties": properties,
            }
            return schema
        return {"type": "string"}

    def _merge_type(self, left: Optional[Any], right: Optional[Any]) -> Optional[Any]:
        left_types = left if isinstance(left, list) else ([left] if left else [])
        right_types = right if isinstance(right, list) else ([right] if right else [])
        merged = []
        for t in left_types + right_types:
            if t not in merged:
                merged.append(t)
        if not merged:
            return None
        return merged[0] if len(merged) == 1 else merged

    def _merge_schemas(self, left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
        if not left:
            return right
        if not right:
            return left

        merged_type = self._merge_type(left.get("type"), right.get("type"))
        merged_nullable = bool(left.get("nullable")) or bool(right.get("nullable"))

        merged: Dict[str, Any] = {}
        if merged_type is not None:
            merged["type"] = merged_type
        if merged_nullable:
            merged["nullable"] = True

        left_type = left.get("type")
        right_type = right.get("type")
        left_is_object = left_type == "object"
        right_is_object = right_type == "object"
        left_is_array = left_type == "array"
        right_is_array = right_type == "array"

        if left_is_object or right_is_object:
            left_props = left.get("properties", {}) if left_is_object else {}
            right_props = right.get("properties", {}) if right_is_object else {}
            all_keys = sorted(set(left_props.keys()) | set(right_props.keys()))
            props: Dict[str, Any] = {}
            for key in all_keys:
                if key in left_props and key in right_props:
                    props[key] = self._merge_schemas(left_props[key], right_props[key])
                elif key in left_props:
                    props[key] = left_props[key]
                else:
                    props[key] = right_props[key]
            merged["properties"] = props

        if left_is_array or right_is_array:
            left_items = left.get("items", {}) if left_is_array else {}
            right_items = right.get("items", {}) if right_is_array else {}
            merged["items"] = self._merge_schemas(left_items, right_items)

        return merged

    def _iter_operations(self, spec: Dict[str, Any]) -> List[tuple[str, str, Dict[str, Any]]]:
        operations: List[tuple[str, str, Dict[str, Any]]] = []
        for endpoint_path, path_item in spec.get("paths", {}).items():
            for method in ("get", "post", "put", "patch", "delete"):
                if method in path_item:
                    operations.append((endpoint_path, method, path_item[method]))
        return operations

    def _build_request_payload(self, operation: Dict[str, Any]) -> Optional[Any]:
        body = operation.get("requestBody", {})
        content = body.get("content", {})
        for content_type in (
            "application/json",
            "application/json-patch+json",
            "application/*+json",
            "text/json",
            "text/plain",
        ):
            if content_type in content:
                schema = content[content_type].get("schema", {})
                return self._sample_from_schema(schema)
        return None

    def _resolve_schema_ref(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        ref = schema.get("$ref")
        if not ref or not ref.startswith("#/components/schemas/"):
            return schema
        name = ref.split("/")[-1]
        return self.current_spec.get("components", {}).get("schemas", {}).get(name, schema)

    def _sample_from_schema(self, schema: Dict[str, Any]) -> Any:
        if not schema:
            return {}
        schema = self._resolve_schema_ref(schema)
        schema_type = schema.get("type")
        if schema.get("nullable"):
            return None
        if isinstance(schema_type, list):
            schema_type = next((t for t in schema_type if t != "null"), None)
        if schema_type == "object":
            props = schema.get("properties", {})
            return {k: self._sample_from_schema(v) for k, v in props.items()}
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

    async def _test_endpoint(
        self, endpoint_path: str, method: str, operation: Dict[str, Any], test_params: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Call an endpoint and get actual response"""
        try:
            # Substitute path parameters with test values
            url = f"{self.base_url}{endpoint_path}"

            # Extract parameters from the path
            params = re.findall(r'\{(\w+)\}', endpoint_path)
            for param_name in params:
                if param_name in test_params:
                    value = test_params[param_name]
                else:
                    # Use default value
                    value = f"test_{param_name}"

                url = url.replace(f"{{{param_name}}}", quote(str(value), safe=""))

            payload = self._build_request_payload(operation)
            from dc_mar_sdk.settings import get_settings

            _SETTINGS = get_settings()
            async with httpx.AsyncClient(timeout=_SETTINGS.default_timeout_seconds) as client:
                response = await client.request(
                    method.upper(),
                    url,
                    headers={"apiKey": self.api_key, "Accept": "application/json"},
                    json=payload if payload is not None else None,
                )

                if response.status_code == 200:
                    return response.json()
                return None
        except Exception:
            return None

    async def generate_corrected_swagger(self, verbose: bool = False) -> tuple[Dict[str, Any], Dict[str, int]]:
        """Generate a new Swagger spec based on actual API responses"""
        if not self.current_spec:
            raise ValueError("No current Swagger spec loaded")

        print("🔄 Generating corrected Swagger spec from actual API responses...")
        print()

        corrected = json.loads(json.dumps(self.current_spec))  # Deep copy

        # Test parameters for common endpoints
        test_params = {
            "address": "1600",
            "marid": "0000000",
            "zone": "Ward 1",
            "latlong": "-77.0369,38.8951",
            "count": "10",
            "distance": "500",
            "geo": "true",
            "ssl": "1",
            "type": "Unit",
            "address_base64": "dGVzdA==",
            "address_separator": ",",
            "chunkSequnce_separator": "|",
            "parallel": "false",
        }

        tested = 0
        updated = 0
        successful = 0

        # Test each operation
        for endpoint_path, method, operation in self._iter_operations(corrected):
            if verbose:
                print(f"Testing: {method.upper()} {endpoint_path}")

            # Call operation
            response = await self._test_endpoint(endpoint_path, method, operation, test_params)
            tested += 1

            if response is None:
                if verbose:
                    print("  ✗ Failed to get response")
                continue

            successful += 1
            if verbose:
                print(f"  ✓ Got response (type: {type(response).__name__})")

            # Update the 200 response schema
            responses = operation.get("responses", {})
            response_200 = responses.get("200", {})
            content = response_200.get("content", {})

            # Generate schema from actual response
            inferred_schema = self._infer_schema_from_response(response)

            # Update all content types with the inferred schema
            for content_type in content.keys():
                old_schema = content[content_type].get("schema", {})
                old_schema_str = json.dumps(old_schema)
                new_schema_str = json.dumps(inferred_schema)

                if old_schema_str != new_schema_str:
                    content[content_type]["schema"] = inferred_schema
                    updated += 1
                    if verbose:
                        print(f"  ✓ Updated schema for {content_type}")
        print(f"✓ Tested {tested} endpoints")
        print(f"  Successful: {successful}")
        print(f"  Failed: {tested - successful}")
        print(f"  Schemas updated: {updated}")
        return corrected, {"tested": tested, "successful": successful, "updated": updated}

    def _next_version_number(self) -> int:
        existing_versions = []
        for path in self.swagger_dir.glob("swagger.v*.json"):
            try:
                existing_versions.append(int(path.stem.replace("swagger.v", "")))
            except ValueError:
                continue
        return (max(existing_versions) + 1) if existing_versions else 1

    def backup_current(self) -> int:
        """Backup current swagger as a versioned copy"""
        current_path = self.swagger_dir / self.swagger_file_name
        if not current_path.exists():
            raise ValueError(f"No current {self.swagger_file_name} found")

        next_version = self._next_version_number()
        backup_path = self.swagger_dir / f"swagger.v{next_version}.json"

        # Copy current to versioned backup
        spec = self._load_swagger(current_path)
        if not spec:
            raise ValueError(f"Current {self.swagger_file_name} could not be loaded")
        spec["x-version"] = next_version
        spec["x-backup-date"] = datetime.now().isoformat()
        self._save_swagger(spec, backup_path)

        print(f"✓ Backed up as: swagger.v{next_version}.json")
        return next_version

    def apply_corrected_spec(self, corrected_spec: Dict[str, Any]) -> int:
        """Backup current and apply corrected spec as new current"""
        # Backup current
        version = self.backup_current()

        # Save corrected as new current
        current_path = self.swagger_dir / self.swagger_file_name
        corrected_spec["x-generated-date"] = datetime.now().isoformat()
        corrected_spec["x-from-version"] = version
        self._save_swagger(corrected_spec, current_path)

        print(f"✓ Applied corrected spec as new current ({self.swagger_file_name})")
        print(f"  Previous spec backed up as: swagger.v{version}.json")
        return version

    def reset_to_version(self, version: int) -> None:
        """Reset to a specific versioned swagger"""
        backup_path = self.swagger_dir / f"swagger.v{version}.json"
        if not backup_path.exists():
            raise ValueError(f"Version {version} not found")

        # Backup current
        current_path = self.swagger_dir / self.swagger_file_name
        if current_path.exists():
            next_version = self._next_version_number()
            backup_current = self.swagger_dir / f"swagger.v{next_version}.json"
            spec = self._load_swagger(current_path)
            if not spec:
                raise ValueError(f"Current {self.swagger_file_name} could not be loaded")
            self._save_swagger(spec, backup_current)
            print(f"✓ Backed up current as: swagger.v{next_version}.json")

        # Restore from version
        spec = self._load_swagger(backup_path)
        if not spec:
            raise ValueError(f"Version {version} could not be loaded")
        self._save_swagger(spec, current_path)
        print(f"✓ Restored from: swagger.v{version}.json")

    async def run_fix_workflow(self, verbose: bool = False) -> Dict[str, Any]:
        """Complete workflow: test API, generate corrected spec, apply it"""
        # Generate corrected spec
        corrected, stats = await self.generate_corrected_swagger(verbose=verbose)

        # Apply it
        backup_version = self.apply_corrected_spec(corrected)
        valid, issues = self.validate_swagger_file()
        if not valid:
            raise ValueError(f"Generated swagger.json failed validation: {', '.join(issues)}")

        print()
        print("✓ Swagger drift fix complete!")
        print(f"  Old spec: swagger.v{backup_version}.json")
        print(f"  New spec: {self.swagger_file_name}")
        return {
            "backup_version": backup_version,
            "valid": valid,
            "validation_issues": issues,
            **stats,
        }
