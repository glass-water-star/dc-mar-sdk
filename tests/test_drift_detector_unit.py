import json

from dc_mar_sdk.tools.drift_detector import SwaggerValidator


def _make_swagger(paths: dict, components: dict | None = None) -> dict:
    return {"openapi": "3.0.0", "paths": paths, "components": {"schemas": components or {}}}


def test_parse_operation_allowlist_and_iter_operations(tmp_path):
    # Construct a small swagger with GET and POST
    paths = {
        "/p": {"get": {"responses": {"200": {"content": {"application/json": {"schema": {"type": "array"}}}}}}},
        "/q": {"post": {"responses": {"200": {"content": {"application/json": {"schema": {"type": "object"}}}}}}},
    }
    spec = _make_swagger(paths)
    p = tmp_path / "s.json"
    p.write_text(json.dumps(spec))

    validator = SwaggerValidator(str(p), api_key="k")

    # No allowlist: include unsafe methods True
    ops = validator._iter_operations(include_unsafe_methods=True)
    assert ("/p", "get", spec["paths"]["/p"]["get"]) in ops
    assert ("/q", "post", spec["paths"]["/q"]["post"]) in ops

    # exclude unsafe methods should drop POST
    ops2 = validator._iter_operations(include_unsafe_methods=False)
    methods = [m for _, m, _ in ops2]
    assert "post" not in methods
    assert "get" in methods

    # allowlist should restrict to specified
    allow = ["GET /p"]
    ops3 = validator._iter_operations(include_unsafe_methods=True, operation_allowlist=allow)
    assert len(ops3) == 1
    assert ops3[0][0] == "/p"


def test_resolve_ref_and_jtoken(tmp_path):
    components = {
        "Simple": {"type": "object", "properties": {"a": {"type": "string"}}},
        "JToken": {"type": "object"},
    }
    spec = _make_swagger({}, components)
    p = tmp_path / "s2.json"
    p.write_text(json.dumps(spec))

    v = SwaggerValidator(str(p), api_key="k")

    # non-ref returns as-is
    assert v._resolve_ref({"type": "string"}) == {"type": "string"}

    # ref resolves to component
    resolved = v._resolve_ref({"$ref": "#/components/schemas/Simple"})
    assert isinstance(resolved, dict)
    assert resolved.get("type") == "object"

    # JToken special-case returns empty dict
    jt = v._resolve_ref({"$ref": "#/components/schemas/JToken"})
    assert jt == {}


def test_validate_type_and_missing_fields(tmp_path):
    # Simple schema requiring fields and typed
    components = {
        "Thing": {
            "type": "object",
            "required": ["id", "name"],
            "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
            "additionalProperties": False,
        }
    }
    paths = {
        "/t": {
            "get": {
                "responses": {
                    "200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/Thing"}}}}
                }
            }
        }
    }
    spec = _make_swagger(paths, components)
    p = tmp_path / "s3.json"
    p.write_text(json.dumps(spec))

    v = SwaggerValidator(str(p), api_key="k")

    schema = v._get_response_schema("/t", "get", 200)
    assert schema is not None

    # Missing required fields
    issues = v._validate_type({}, schema, path="$")
    # Should report two missing required fields (id and name)
    missing = [i for i in issues if "Missing required" in i.get("type_error", "")]
    assert len(missing) == 2

    # Extra field when additionalProperties False should be warning
    issues2 = v._validate_type({"id": 1, "name": "ok", "x": 5}, schema, path="$")
    extra = [i for i in issues2 if "Extra field" in i.get("type_error", "")]
    assert len(extra) == 1
    assert extra[0]["severity"] == "warning"

    # Type mismatch
    issues3 = v._validate_type({"id": "notint", "name": "ok"}, schema, path="$")
    type_errs = [i for i in issues3 if i.get("type_error") and "Expected integer" in i.get("type_error")]
    assert len(type_errs) == 1


def test_known_live_contract_shapes_conform_without_warnings(tmp_path):
    p = tmp_path / "s4.json"
    p.write_text(json.dumps(_make_swagger({})))
    validator = SwaggerValidator(str(p), api_key="k")

    envelope_issues = validator._validate_response(
        {"Result": ["1600 PENNSYLVANIA AVENUE NW"], "Success": True, "Message": None},
        {"type": "array", "items": {"type": "string"}},
        "/api/v2.2/autocomplete/{address}",
        "get",
        200,
    )
    dynamic_issues = validator._validate_response(
        {"Result": {"addresses": []}, "Success": True, "Message": None},
        {"type": "object"},
        "/api/v2.2/locations/{geo}",
        "post",
        200,
    )

    assert envelope_issues == []
    assert dynamic_issues == []
