"""Helpers shared by the providers: HTTP requests and value checks."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import aiohttp

from custom_components.urban_weather.const import (
    DEFAULT_RETRY_AFTER_S,
    REQUEST_TIMEOUT_S,
)
from custom_components.urban_weather.provider import (
    ApiConnectionError,
    ApiError,
    ApiRateLimitError,
    TileLayer,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_TOO_MANY_REQUESTS = 429

# Official German basemap (BKG), open data under CC BY 4.0, no API key needed.
BASEMAP_DE = TileLayer(
    url=(
        "https://sgx.geodatenzentrum.de/wmts_basemapde/tile/1.0.0/"
        "de_basemapde_web_raster_farbe/default/GLOBAL_WEBMERCATOR/{z}/{y}/{x}.png"
    ),
    attribution="© basemap.de / BKG (CC BY 4.0)",
)

# OpenStreetMap in Swiss style, run by the Swiss OSM Association. Covers
# Switzerland only, no API key needed.
OSM_CH = TileLayer(
    url="https://tile.osm.ch/osm-swiss-style/{z}/{x}/{y}.png",
    attribution="© OpenStreetMap contributors (ODbL), tiles: osm.ch",
)

# Fallback for networks without an official basemap. Light use only, within the
# tile usage policy: https://operations.osmfoundation.org/policies/tiles/
OPENSTREETMAP = TileLayer(
    url="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution="© OpenStreetMap contributors (ODbL)",
)


def is_number(value: Any) -> bool:
    """Return True for a finite int or float (not a bool)."""
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


async def async_get_json(
    session: aiohttp.ClientSession,
    url: str,
    label: str,
    *,
    params: Mapping[str, str] | None = None,
    not_found: type[ApiError] | None = None,
) -> Any:
    """
    Return the JSON response of a GET request.

    `label` names the request in errors. A 404 raises `not_found` if given, else
    ApiError like other HTTP errors. Raises ApiRateLimitError, ApiConnectionError
    or ApiError.
    """
    try:
        async with session.get(
            url, params=params, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_S)
        ) as response:
            if response.status == HTTP_TOO_MANY_REQUESTS:
                raise ApiRateLimitError(retry_after(response.headers))
            if response.status == HTTP_NOT_FOUND and not_found:
                raise not_found(label)
            if response.status >= HTTP_BAD_REQUEST:
                msg = f"HTTP {response.status} for {label}"
                raise ApiError(msg)
            return await response.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError) as err:
        msg = f"Error fetching {label}: {err}"
        raise ApiConnectionError(msg) from err
    except ValueError as err:
        msg = f"Invalid JSON for {label}"
        raise ApiError(msg) from err


def retry_after(headers: Mapping[str, str]) -> float:
    """Return the seconds a 429 response asks to wait (at least 1)."""
    try:
        return max(float(headers.get("Retry-After", "")), 1.0)
    except ValueError:
        return DEFAULT_RETRY_AFTER_S
