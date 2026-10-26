import pytest
from pydantic import ValidationError

from dc_mar_sdk.models import (
    AddressBase64,
    AddressInput,
    GeoAddressProperties,
    LocationResultServiceResponse,
    MARResponseEnvelope,
    SSLInput,
    UnitInput,
)


def test_score_alias_is_accepted_and_serialized_as_documented():
    properties = GeoAddressProperties.model_validate({"_Score": 99.5, "FullAddress": "200 I STREET SE"})

    assert properties.Score == 99.5
    assert properties.model_dump(by_alias=True)["_Score"] == 99.5


def test_documented_response_models_reject_unexpected_keys():
    with pytest.raises(ValidationError, match="extra_forbidden"):
        GeoAddressProperties.model_validate({"FullAddress": "200 I STREET SE", "unexpected": True})


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (AddressInput, {"address": "200 I STREET SE", "unexpected": True}),
        (AddressBase64, {"address_base64": "MjAwIEkgU1RSRUVUIFNF", "unexpected": True}),
        (SSLInput, {"square": "0766", "unexpected": True}),
        (UnitInput, {"marid": "308596", "unexpected": True}),
    ],
)
def test_documented_request_models_reject_unexpected_keys(model, payload):
    with pytest.raises(ValidationError, match="extra_forbidden"):
        model.model_validate(payload)


def test_location_response_validates_representative_nested_payload():
    response = LocationResultServiceResponse.model_validate(
        {
            "Success": True,
            "Result": {
                "blocks": [
                    {
                        "block": {
                            "type": "Feature",
                            "properties": {"_Score": 100, "BlockKey": "block-key"},
                            "geometry": {"type": "Point", "coordinates": [-77.0032, 38.8793]},
                        }
                    }
                ],
                "addresses": [
                    {
                        "address": {
                            "type": "Feature",
                            "properties": {
                                "_Score": 99.5,
                                "MarId": "308596",
                                "FullAddress": "200 I STREET SE",
                            },
                            "geometry": {"type": "Point", "coordinates": [-77.0029, 38.8798]},
                        },
                        "distance": 0.38,
                        "units": "mi",
                    }
                ],
                "intersections": [
                    {
                        "intersection": {
                            "properties": {
                                "_Score": 98,
                                "IntersectionId": "13565",
                                "FullIntersection": "2ND STREET SE AND I STREET SE",
                            }
                        }
                    }
                ],
                "ssls": [{"MarId": "308596", "Square": "0766", "Lot": "0038"}],
                "units": [{"MarId": "145957", "UnitNum": "301", "UnitType": "CONDO"}],
            },
        }
    )

    assert response.Result is not None
    assert response.Result.addresses[0].address.properties.FullAddress == "200 I STREET SE"
    assert response.Result.blocks[0].block.properties.Score == 100
    assert response.Result.intersections[0].intersection.properties.IntersectionId == "13565"
    assert response.Result.ssls[0].Square == "0766"
    assert response.Result.units[0].UnitNum == "301"


def test_dynamic_zones_and_untyped_status_fields_are_preserved():
    response = LocationResultServiceResponse.model_validate(
        {
            "Success": True,
            "Result": {
                "zones": {
                    "school": {"name": "Example", "grades": ["K", 12]},
                    "district": None,
                }
            },
            "StatusCode": 200,
        }
    )
    envelope = MARResponseEnvelope.model_validate(
        {"Success": True, "Result": {"variable": [1, {"nested": False}]}, "TraceId": "trace-1"}
    )

    assert response.Result.zones["school"]["grades"] == ["K", 12]
    assert response.model_extra == {"StatusCode": 200}
    assert envelope.Result == {"variable": [1, {"nested": False}]}
    assert envelope.model_extra == {"TraceId": "trace-1"}
