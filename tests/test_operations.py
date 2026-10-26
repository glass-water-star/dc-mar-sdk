import asyncio
import json
from pathlib import Path

import pytest

from dc_mar_sdk import MARClient
from dc_mar_sdk.operations import API_OPERATIONS, build_operation_path


def test_operation_manifest_matches_authoritative_swagger():
    swagger_path = Path(__file__).parent.parent / "swagger" / "swagger.json"
    swagger = json.loads(swagger_path.read_text())
    documented_operations = {
        (method.upper(), path)
        for path, path_item in swagger["paths"].items()
        for method in ("get", "post")
        if method in path_item
    }

    assert documented_operations == API_OPERATIONS


def test_build_operation_path_requires_exact_path_parameters():
    assert (
        build_operation_path(
            "/api/v2.2/units/{marid}/{type}",
            {"marid": "123/456", "type": "Residential Unit"},
        )
        == "/units/123%2F456/Residential%20Unit"
    )

    with pytest.raises(ValueError, match="missing path parameter"):
        build_operation_path("/api/v2.2/units/{marid}", {})


def test_request_operation_dispatches_authoritative_path():
    requests: list[dict[str, object]] = []

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"Success": True, "Result": []}

    class HttpClient:
        async def request(self, method, url, **kwargs):
            requests.append({"method": method, "url": url, **kwargs})
            return Response()

    async def run():
        client = MARClient(api_key="test-key", enable_telemetry=False)
        client._http_client = HttpClient()
        return await client.request_operation(
            "GET",
            "/api/v2.2/units/{marid}",
            path_parameters={"marid": "123"},
            query_parameters={"type": "Residential"},
        )

    assert asyncio.run(run()) == {"Success": True, "Result": []}
    assert requests == [
        {
            "method": "GET",
            "url": "https://datagate.dc.gov/mar/open/api/v2.2/units/123",
            "params": {"type": "Residential"},
            "json": None,
            "headers": {"Accept": "application/json", "apiKey": "test-key"},
        }
    ]
