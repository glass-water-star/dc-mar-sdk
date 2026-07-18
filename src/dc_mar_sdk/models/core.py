"""
Pydantic models for DC MAR API v2.2
Generated from OpenAPI specification at https://datagate.dc.gov/mar/open/swagger/v2.2/swagger.json
"""

from typing import Any, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class AddressInput(BaseModel):
    """Request body for address autocomplete/search operations"""
    address: str = Field(..., description="Address string value")


class GeoBlockProperties(BaseModel):
    """Geographic block boundary and range information"""
    Score: Optional[float] = Field(None, alias="_Score", description="Score to rate match against searched value")
    MarId: Optional[str] = Field(None, description="Unique ID for DC Block in MAR")
    BlockKey: Optional[str] = Field(None, description="Block Key")
    LowerRange: Optional[int] = Field(None, description="Lower Range")
    HigherRange: Optional[int] = Field(None, description="Higher Range")
    StreetSegId: Optional[str] = Field(None, description="Street Segment Identifier")
    Intersection1Id: Optional[str] = Field(None, description="Intersection 1 Identifier")
    Intersection2Id: Optional[str] = Field(None, description="Intersection 2 Identifier")
    OnStreetId: Optional[str] = Field(None, description="On Street Identifier")
    FromStreetId: Optional[str] = Field(None, description="From Street Identifier")
    ToStreetId: Optional[str] = Field(None, description="To Street Identifier")
    TheORangeLL: Optional[str] = Field(None, description="Theoretical Range Left Low")
    TheORangeLH: Optional[str] = Field(None, description="Theoretical Range Left High")
    TheORangeRL: Optional[str] = Field(None, description="Theoretical Range Right Low")
    TheORangeRH: Optional[str] = Field(None, description="Theoretical Range Right High")
    ActualRangeLL: Optional[str] = Field(None, description="Actual Range Left Low")
    ActualRangeLH: Optional[str] = Field(None, description="Actual Range Left High")
    ActualRangeRL: Optional[str] = Field(None, description="Actual Range Right Low")
    ActualRangeRH: Optional[str] = Field(None, description="Actual Range Right High")
    FullBlock: Optional[str] = Field(None, description="Full Block")
    BlockName: Optional[str] = Field(None, description="Block Name")
    ONStName: Optional[str] = Field(None, description="On Street Name")
    ONStType: Optional[str] = Field(None, description="On Street Type")
    ONStQUAD: Optional[str] = Field(None, description="On Street Quadrant")
    OnStreetDisplay: Optional[str] = Field(None, description="On Street Display Name")
    FromStName: Optional[str] = Field(None, description="From Street Name")
    FromStType: Optional[str] = Field(None, description="From Street Type")
    FromStQUAD: Optional[str] = Field(None, description="From Street Quadrant")
    FromStreetDisplay: Optional[str] = Field(None, description="From Street Display Name")
    ToStName: Optional[str] = Field(None, description="To Street Name")
    ToStType: Optional[str] = Field(None, description="To Street Type")
    ToStQUAD: Optional[str] = Field(None, description="To Street Quadrant")
    ToStreetDisplay: Optional[str] = Field(None, description="To Street Display Name")

    model_config = ConfigDict(populate_by_name=True)


class GeoBlockFeature(BaseModel):
    """GeoJSON Feature for geographic blocks"""
    type: str = Field(default="Feature", description="GeoJSON type")
    properties: GeoBlockProperties
    geometry: Optional[dict] = Field(None, description="GeoJSON geometry")


class AddressMatch(BaseModel):
    """Address search/match result"""
    Score: Optional[float] = Field(None, alias="_Score", description="Confidence score for match")
    MatchedAddress: Optional[str] = Field(None, description="Matched address string")
    MarId: Optional[str] = Field(None, description="MAR identifier")
    AddressId: Optional[str] = Field(None, description="Address ID")
    Latitude: Optional[float] = Field(None, description="Latitude coordinate")
    Longitude: Optional[float] = Field(None, description="Longitude coordinate")

    model_config = ConfigDict(populate_by_name=True)


class AutocompleteResponse(BaseModel):
    """Response from autocomplete endpoint"""
    suggestions: List[str] = Field(default_factory=list, description="List of address suggestions")


class SearchResponse(BaseModel):
    """Response from search/match endpoints"""
    matches: List[AddressMatch] = Field(default_factory=list, description="List of address matches")
    total_matches: int = Field(default=0, description="Total number of matches")


class MARResponseEnvelope(BaseModel):
    """Common MAR API response envelope."""
    Result: Optional[Any] = Field(default=None)
    Success: bool = Field(default=True)
    Message: Optional[str] = Field(default=None)


class APIMetadata(BaseModel):
    """Metadata about the API request/response"""
    endpoint: str = Field(..., description="API endpoint called")
    method: str = Field(..., description="HTTP method")
    status_code: int = Field(..., description="HTTP status code")
    timestamp: Optional[str] = Field(None, description="ISO 8601 timestamp")
    response_time_ms: Optional[float] = Field(None, description="Response time in milliseconds")
    cached: bool = Field(default=False, description="Whether response was cached")
    cache_key: Optional[str] = Field(None, description="Cache key used")


class APIRequest(BaseModel):
    """Wrapper for API requests with metadata"""
    endpoint: str
    method: str = Field(default="GET")
    parameters: Optional[dict] = Field(default=None)
    body: Optional[dict] = Field(default=None)
    timestamp: Optional[str] = Field(None)


class APIResponse(BaseModel):
    """Wrapper for API responses with metadata"""
    metadata: APIMetadata
    data: Optional[Any] = Field(None)
    error: Optional[str] = Field(None)
