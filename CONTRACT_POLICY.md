CONTRACT POLICY: Model & API Compatibility

Purpose

This document describes the transport envelope used by the DC MAR API and the stable domain models the library returns. It defines semantic compatibility rules and the user-facing guarantees consumers may rely upon.

Definitions

- Transport envelope (MARResponseEnvelope): the wire-level wrapper returned by API endpoints and represented by dc_mar_sdk.models.core.MARResponseEnvelope. Fields:
  - Result: optional payload (Any) containing the endpoint-specific data
  - Success: boolean indicating high-level success
  - Message: optional human-readable message or error

- Domain models: Pydantic models in dc_mar_sdk.models (AutocompleteResponse, SearchResponse, AddressMatch, etc.). These are the library's public contract and stable API surface.

How the client maps envelope -> domain models

- Autocomplete: the client reads MARResponseEnvelope.Result. If Result is a list, it is treated as suggestions (List[str]) and validated into AutocompleteResponse.suggestions. Non-list Results become an empty suggestions list. On validation failure the client logs a model-break diagnostic and raises.

- Search: the client accepts multiple Result shapes: either a list of address entries or a dict containing keys like "addresses" or "blockAddresses". For each entry the client extracts properties from one of these locations:
  - entry["address"]["properties"] (preferred)
  - entry["properties"]

  Fields mapped into AddressMatch:
  - Score: from _Score or Score
  - MatchedAddress: from FullAddress or MatchedAddress
  - MarId, AddressId, Latitude, Longitude mapped from their respective keys when present.

Caching and normalization

- The library caches normalized, validated domain objects (AutocompleteResponse.suggestions and SearchResponse.model_dump()). Cache entries are schema-validated on read; invalid cache entries cause a model-break log and raise.

Compatibility rules (semantic)

1) Non-breaking (safe) changes:
   - Adding new optional fields anywhere in the envelope or domain models (new keys that client ignores).
   - Adding new fields inside Result entries that are not used by the client mapping.
   - Adding new endpoints or returning extra metadata in MARResponseEnvelope.Message or APIMetadata.

2) Potentially breaking (requires caution):
   - Changing the type of an existing field (e.g., Score from number to string). Clients may fail validation and raise.
   - Changing where fields are nested inside Result entries (e.g., moving properties from entry.address.properties to a different path) without preserving one of the recognized shapes.
   - Changing Result from a list to a dict (or vice versa) in an endpoint where the client expects the other shape.

3) Breaking changes (major):
   - Removing fields that the client maps into domain models (MarId, FullAddress, _Score/Score, AddressId, Latitude/Longitude).
   - Renaming keys used by the mapping (e.g., FullAddress -> FullAddr) without providing aliases or maintaining backwards-compatible keys.
   - Removing Success or changing its semantics (the client depends on Success to determine errors).

Versioning guidance

- Follow a semver-like approach for API changes affecting the contract exposed by this library:
  - Patch: non-breaking additions or metadata-only changes.
  - Minor: additions that may be optionally consumed by clients (add optional fields, new endpoints).
  - Major: any removal/rename/type-change of mapped fields or envelope semantics; bump major and announce migration guidance.

User-facing guarantees

- Stability: Domain model shapes (AutocompleteResponse, SearchResponse, AddressMatch) are the library's stable interface. The library will aim to preserve these shapes across non-major releases.

- Validation: Responses are validated against Pydantic models. If validation fails, the client logs details (via _log_model_break) and raises an exception. Enable DEBUG logs to see payload previews and failure reasons.

- Mapping heuristics: The client applies tolerant mapping rules (multiple possible property locations and alias fields like _Score/Score). These heuristics aim to absorb small API inconsistencies without breaking callers.

- Caching semantics: The library stores normalized domain objects in the cache and validates them on read. Corrupt or schema-incompatible cache entries will be detected and treated as model-breaks.

Examples

1) Autocomplete example

API payload (Result as list):
{
  "Result": ["1600 Pennsylvania Ave NW", "1600 Pennsylvania Ave NE"],
  "Success": true
}

Client result: AutocompleteResponse(suggestions=["1600 Pennsylvania Ave NW", "1600 Pennsylvania Ave NE"]) -> returned List[str]

2) Search example (Result as dict with addresses)

API payload:
{
  "Result": {
    "addresses": [
      {
        "address": {"properties": {"_Score": 0.92, "FullAddress": "1600 Pennsylvania Ave NW", "MarId": "B123"}}
      }
    ]
  },
  "Success": true
}

Client mapping:
- AddressMatch.Score <- 0.92 (from _Score)
- AddressMatch.MatchedAddress <- "1600 Pennsylvania Ave NW" (from FullAddress)
- AddressMatch.MarId <- "B123"

Returned value: SearchResponse(matches=[AddressMatch(...)] , total_matches=1)

When to consider a change breaking

If you change or remove any keys that the mapping logic reads (see Mapping heuristics), treat the change as breaking. Prefer adding aliases (e.g., keep old key present alongside new key) and communicate the deprecation schedule.

Contact / Maintenance

If you plan to change the MAR API payloads in any way that could affect mapping, please open an issue in this repository describing the change and intended timeline so the client library can be updated in advance.

