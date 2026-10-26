"""Source-aligned Pydantic models for the DC MAR OpenAPI contract."""

from __future__ import annotations

from typing import Generic, TypeAlias, TypeVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue

T = TypeVar("T")


class RequestModel(BaseModel):
    """Base for documented JSON request bodies."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ResponseModel(BaseModel):
    """Base for fully documented response objects."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class StatusEnvelope(BaseModel, Generic[T]):
    """Common MAR status envelope, tolerant of undocumented live status fields."""

    Result: T | None = None
    Success: bool | None = None
    Message: str | None = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ServiceResponse(StatusEnvelope[T], Generic[T]):
    """Generic base for documented MAR service responses."""


class AddressInput(RequestModel):
    address: str


class AddressBase64(RequestModel):
    address_base64: str


class SSLInput(RequestModel):
    marid: str | None = None
    square: str | None = None
    suffix: str | None = None
    lot: str | None = None


class UnitInput(RequestModel):
    marid: str
    type: str | None = None


class GeoBlockProperties(ResponseModel):
    Score: float | None = Field(default=None, alias="_Score")
    MarId: str | None = None
    BlockKey: str | None = None
    LowerRange: int | None = None
    HigherRange: int | None = None
    StreetSegId: str | None = None
    Intersection1Id: str | None = None
    Intersection2Id: str | None = None
    OnStreetId: str | None = None
    FromStreetId: str | None = None
    ToStreetId: str | None = None
    TheORangeLL: str | None = None
    TheORangeLH: str | None = None
    TheORangeRL: str | None = None
    TheORangeRH: str | None = None
    ActualRangeLL: str | None = None
    ActualRangeLH: str | None = None
    ActualRangeRL: str | None = None
    ActualRangeRH: str | None = None
    FullBlock: str | None = None
    BlockName: str | None = None
    ONStName: str | None = None
    ONStType: str | None = None
    ONStQUAD: str | None = None
    OnStreetDisplay: str | None = None
    FromStName: str | None = None
    FromStType: str | None = None
    FromStQUAD: str | None = None
    FromStreetDisplay: str | None = None
    ToStName: str | None = None
    ToStType: str | None = None
    ToStQUAD: str | None = None
    ToStreetDisplay: str | None = None
    CentroidX: str | None = None
    CentroidY: str | None = None
    ExtentMinX: str | None = None
    ExtentMinY: str | None = None
    ExtentMaxX: str | None = None
    ExtentMaxY: str | None = None
    NationalGrid: str | None = None
    Latitude: float | None = None
    Longitude: float | None = None
    Ward: str | None = None
    FullAddress: str | None = None


class GeoBlockGeometry(ResponseModel):
    type: str | None = None
    coordinates: list[float] | None = None


class GeoBlock(ResponseModel):
    type: str | None = None
    properties: GeoBlockProperties | None = None
    geometry: GeoBlockGeometry | None = None


class GeoBlockObject(ResponseModel):
    block: GeoBlock | None = None


class GeoAddressProperties(ResponseModel):
    Score: float | None = Field(default=None, alias="_Score")
    MarId: str | None = None
    FullAddress: str | None = None
    SSL: str | None = None
    Alias: str | None = None
    Xcoord: float | None = None
    Ycoord: float | None = None
    Latitude: float | None = None
    Longitude: float | None = None
    AddrNum: str | None = None
    AddrNumSuffix: str | None = None
    StName: str | None = None
    StreetType: str | None = None
    Quadrant: str | None = None
    Zipcode: str | None = None
    BlockKey: str | None = None
    SubBlockKey: str | None = None
    Ward: str | None = None
    Anc: str | None = None
    CensusTract: str | None = None
    ResidenceType: str | None = None
    HasCondoUnit: str | None = None
    HasResUnit: str | None = None
    Status: str | None = None
    NationalGrid: str | None = None


class GeoAddressGeometry(ResponseModel):
    type: str | None = None
    coordinates: list[float] | None = None


class GeoAddress(ResponseModel):
    type: str | None = None
    properties: GeoAddressProperties | None = None
    geometry: GeoAddressGeometry | None = None


class GeoAddressWithZones(ResponseModel):
    address: GeoAddress | None = None
    distance: float | None = None
    units: str | None = None
    zones: dict[str, JsonValue] | None = None


class GeoIntersectionProperties(ResponseModel):
    Score: float | None = Field(default=None, alias="_Score")
    MarId: str | None = None
    IntersectionId: str | None = None
    Street1Id: str | None = None
    Street2Id: str | None = None
    St1Name: str | None = None
    St1Type: str | None = None
    St1Quad: str | None = None
    FullStreet1Display: str | None = None
    St2Name: str | None = None
    St2Type: str | None = None
    St2Quad: str | None = None
    FullStreet2Display: str | None = None
    FullIntersection: str | None = None
    RefX: float | None = None
    RefY: float | None = None
    xcoord: float | None = None
    ycoord: float | None = None
    Street1SegId: str | None = None
    Street2SegId: str | None = None
    NodeId: str | None = None
    Intersection_Type: str | None = None
    Source: str | None = None
    NationalGrid: str | None = None
    Latitude: float | None = None
    Longitude: float | None = None
    Ward: str | None = None


class GeoIntersectionGeometry(ResponseModel):
    type: str | None = None
    coordinates: list[float] | None = None


class GeoIntersection(ResponseModel):
    type: str | None = None
    properties: GeoIntersectionProperties | None = None
    geometry: GeoIntersectionGeometry | None = None


class GeoIntersectionObject(ResponseModel):
    intersection: GeoIntersection | None = None


class SSLObject(ResponseModel):
    MarId: str | None = None
    FullAddress: str | None = None
    SSL: str | None = None
    Square: str | None = None
    Suffix: str | None = None
    Lot: str | None = None
    Lot_type: str | None = None
    Col: str | None = None


class Unit(ResponseModel):
    MarId: str | None = None
    FullAddress: str | None = None
    UnitNum: str | None = None
    UnitType: str | None = None
    UnitSSL: str | None = None
    Status: str | None = None


class LocationResult(ResponseModel):
    blocks: list[GeoBlockObject] | None = None
    blockAddresses: list[GeoAddressWithZones] | None = None
    addresses: list[GeoAddressWithZones] | None = None
    intersections: list[GeoIntersectionObject] | None = None
    ssls: list[SSLObject] | None = None
    units: list[Unit] | None = None
    zones: dict[str, JsonValue] | None = None


class LocationResultServiceResponse(ServiceResponse[LocationResult]):
    Result: LocationResult | None = None


class GeoAddressWithZonesListServiceResponse(ServiceResponse[list[GeoAddressWithZones]]):
    Result: list[GeoAddressWithZones] | None = None


# The source contract models batch results as a generic service response, but
# the live API returns this stable processing summary with nested envelopes.
class LocationBatchResponse(ResponseModel):
    ChunkNumber: int
    ProcessTime: str
    Results: list[LocationResultServiceResponse]


# The source's recursive JToken declaration does not represent scalar or object
# zone values observed in MAR responses. JsonValue keeps those values lossless.
JToken: TypeAlias = JsonValue


# Backward-compatible SDK models that predate the complete OpenAPI component set.
class GeoBlockFeature(GeoBlock):
    """Legacy name for a GeoJSON block feature."""


class AddressMatch(ResponseModel):
    Score: float | None = Field(default=None, alias="_Score")
    MatchedAddress: str | None = None
    MarId: str | None = None
    AddressId: str | None = None
    Latitude: float | None = None
    Longitude: float | None = None


class AutocompleteResponse(ResponseModel):
    suggestions: list[str] = Field(default_factory=list)


class SearchResponse(ResponseModel):
    matches: list[AddressMatch] = Field(default_factory=list)
    total_matches: int = 0


class MARResponseEnvelope(StatusEnvelope[JsonValue]):
    """Drift-tolerant envelope used by legacy endpoints with untyped responses."""

    Result: JsonValue = None
    Success: bool = True


class APIMetadata(ResponseModel):
    endpoint: str
    method: str
    status_code: int
    timestamp: str | None = None
    response_time_ms: float | None = None
    cached: bool = False
    cache_key: str | None = None


class APIRequest(RequestModel):
    endpoint: str
    method: str = "GET"
    parameters: dict[str, JsonValue] | None = None
    body: dict[str, JsonValue] | None = None
    timestamp: str | None = None


class APIResponse(ResponseModel):
    metadata: APIMetadata
    data: JsonValue = None
    error: str | None = None
