from typing import Optional
from pydantic import BaseModel, Field


class CachePolicy(BaseModel):
    """Typed cache policy for MAR client.

    Notes:
    - default_use_cache controls whether operations consult / write the cache by default.
    - operation-specific TTLs, when set, override the client's legacy cache_ttl_seconds.
    - a `stale_while_revalidate` toggle is exposed for future use but not enabled by default.
    """

    default_use_cache: bool = Field(True, description="Whether to use cache by default for operations")
    autocomplete_ttl_seconds: Optional[int] = Field(None, description="Per-operation TTL for autocomplete")
    search_ttl_seconds: Optional[int] = Field(None, description="Per-operation TTL for search")
    stale_while_revalidate: bool = Field(False, description="Optional SWR behavior (not active by default)")
