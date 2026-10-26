"""Authoritative MAR v2.2 operation templates."""

from __future__ import annotations

import re
from collections.abc import Mapping
from urllib.parse import quote

API_PREFIX = "/api/v2.2"

API_OPERATIONS = frozenset(
    {
        ("GET", "/api/v2.2/autocomplete/{address}"),
        ("POST", "/api/v2.2/autocomplete/{address}"),
        ("POST", "/api/v2.2/autocomplete"),
        ("GET", "/api/v2.2/locationbatch/{address_base64}/{address_separator}/{chunkSequnce_separator}/{parallel}"),
        ("GET", "/api/v2.2/locationbatch/{address_base64}"),
        ("POST", "/api/v2.2/locationbatch"),
        ("POST", "/api/v2.2/locationbatch/{address_separator}/{chunkSequnce_separator}/{parallel}"),
        ("GET", "/api/v2.2/locations/{address}/{zones}/{geo}"),
        ("POST", "/api/v2.2/locations/{address}/{zones}/{geo}"),
        ("POST", "/api/v2.2/locations/{zones}/{geo}"),
        ("POST", "/api/v2.2/locations/{geo}"),
        ("GET", "/api/v2.2/locations/{latlong}/{distance}/{zones}/{geo}"),
        ("POST", "/api/v2.2/locations/{latlong}/{distance}/{zones}/{geo}"),
        ("POST", "/api/v2.2/locations/{distance}/{geo}"),
        ("GET", "/api/v2.2/locations/{latlong}/{zones}/{geo}"),
        ("POST", "/api/v2.2/locations/{latlong}/{zones}/{geo}"),
        ("GET", "/api/v2.2/locations/{latlong}"),
        ("POST", "/api/v2.2/locations/{latlong}"),
        ("GET", "/api/v2.2/locations/{latlong}/{count}/{zones}/{geo}"),
        ("POST", "/api/v2.2/locations/{latlong}/{count}/{zones}/{geo}"),
        ("POST", "/api/v2.2/locations/{count}/{geo}"),
        ("GET", "/api/v2.2/ssls/{ssl}"),
        ("POST", "/api/v2.2/ssls/{ssl}"),
        ("GET", "/api/v2.2/ssls"),
        ("POST", "/api/v2.2/ssls"),
        ("GET", "/api/v2.2/units/{marid}"),
        ("POST", "/api/v2.2/units/{marid}"),
        ("GET", "/api/v2.2/units/{marid}/{type}"),
        ("POST", "/api/v2.2/units/{marid}/{type}"),
        ("GET", "/api/v2.2/units"),
        ("POST", "/api/v2.2/units"),
        ("GET", "/api/v2.2/zone/{zone}"),
        ("POST", "/api/v2.2/zone/{zone}"),
    }
)

_PATH_PARAMETER = re.compile(r"\{([^{}]+)\}")


def build_operation_path(template: str, path_parameters: Mapping[str, object] | None = None) -> str:
    """Validate and render an authoritative operation template."""
    parameters = path_parameters or {}
    required = set(_PATH_PARAMETER.findall(template))
    provided = set(parameters)

    if required != provided:
        missing = ", ".join(sorted(required - provided))
        unexpected = ", ".join(sorted(provided - required))
        details = []
        if missing:
            details.append(f"missing path parameter(s): {missing}")
        if unexpected:
            details.append(f"unexpected path parameter(s): {unexpected}")
        raise ValueError("; ".join(details))

    rendered = _PATH_PARAMETER.sub(lambda match: quote(str(parameters[match.group(1)]), safe=""), template)
    if not rendered.startswith(f"{API_PREFIX}/") and rendered != API_PREFIX:
        raise ValueError(f"Operation must begin with {API_PREFIX}: {template}")
    return rendered.removeprefix(API_PREFIX)
