import pytest

from dc_mar_sdk import MARClient
from dc_mar_sdk.client import ContractValidationError
from dc_mar_sdk.models import AddressInput


class Response:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class HttpClient:
    def __init__(self, payload):
        self.payload = payload

    async def request(self, *args, **kwargs):
        return Response(self.payload)


@pytest.mark.asyncio
async def test_typed_operation_returns_validated_location_response():
    client = MARClient(api_key="test-key", enable_telemetry=False)
    client._http_client = HttpClient({"Success": True, "Result": {"addresses": []}})

    response = await client.locate_address("1600 Pennsylvania", zones="Ward")

    assert response.Success is True
    assert response.Result.addresses == []


@pytest.mark.asyncio
async def test_typed_operation_fails_on_malformed_response():
    client = MARClient(api_key="test-key", enable_telemetry=False)
    client._http_client = HttpClient({"Success": {"not": "a boolean"}, "Result": []})

    with pytest.raises(ContractValidationError, match=r"POST /api/v2.2/autocomplete"):
        await client.autocomplete_by_body(AddressInput(address="1600 Pennsylvania"))
