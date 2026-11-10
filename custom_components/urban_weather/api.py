"""Client for the Smart City Mannheim climate API (https://api.smartmannheim.de/doc)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

import aiohttp

from .const import API_BASE_URL, DEFAULT_RETRY_AFTER_S, LOGGER, REQUEST_TIMEOUT_S

if TYPE_CHECKING:
    from collections.abc import Mapping

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_TOO_MANY_REQUESTS = 429
POSITION_LENGTH = 2


class ApiError(Exception):
    """Unexpected API response."""


class ApiConnectionError(ApiError):
    """The API could not be reached."""


class ApiRateLimitError(ApiError):
    """The API rejected the request because of its rate limit."""

    def __init__(self, retry_after: float) -> None:
        """Store how long the API asks us to wait."""
        super().__init__(f"Rate limited, retry after {retry_after:.0f} s")
        self.retry_after = retry_after


class SensorNotFoundError(ApiError):
    """The sensor does not exist (any more)."""


@dataclass(frozen=True, slots=True)
class ApiSensor:
    """A sensor as listed by the API."""

    id: str
    name: str
    latitude: float
    longitude: float
    parameters: frozenset[str]


@dataclass(frozen=True, slots=True)
class Measurement:
    """One timestamped set of values of a sensor."""

    timestamp: datetime
    values: Mapping[str, float]


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def parse_sensors(payload: Any) -> list[ApiSensor]:
    """Parse the /sensors response, skipping entries without a usable position."""
    if not isinstance(payload, dict):
        msg = "Unexpected sensor list format"
        raise ApiError(msg)
    param_sets = payload.get("paramSets") or []
    sensors = []
    for raw in payload.get("sensors") or []:
        sensor_id = str(raw.get("id") or "").strip()
        position = raw.get("position")
        if (
            not sensor_id
            or not isinstance(position, list)
            or len(position) != POSITION_LENGTH
            or not all(_is_number(value) for value in position)
        ):
            LOGGER.debug("Skipping sensor without usable position: %s", raw)
            continue
        longitude, latitude = position
        # Some sensors have swapped coordinates; in Germany latitude > longitude.
        if latitude < longitude:
            latitude, longitude = longitude, latitude
        param_set = raw.get("paramSet")
        parameters = (
            param_sets[param_set]
            if isinstance(param_set, int) and 0 <= param_set < len(param_sets)
            else []
        )
        sensors.append(
            ApiSensor(
                id=sensor_id,
                name=str(raw.get("name") or sensor_id).strip(),
                latitude=float(latitude),
                longitude=float(longitude),
                parameters=frozenset(parameters),
            )
        )
    return sensors


def parse_measurements(payload: Any) -> list[Measurement]:
    """Parse the /measurements response, newest first."""
    if not isinstance(payload, dict):
        msg = "Unexpected measurement format"
        raise ApiError(msg)
    measurements = []
    for raw in payload.get("data") or []:
        try:
            timestamp = datetime.fromisoformat(str(raw["timestamp"]))
        except KeyError, TypeError, ValueError:
            continue
        values = {
            key: float(value)
            for key, value in raw.items()
            if key != "timestamp" and _is_number(value)
        }
        measurements.append(Measurement(timestamp=timestamp, values=values))
    measurements.sort(key=lambda measurement: measurement.timestamp, reverse=True)
    return measurements


class MannheimClimateApi:
    """Thin async wrapper around the two API endpoints."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Use the shared Home Assistant client session."""
        self._session = session

    async def async_get_sensors_payload(self) -> dict[str, Any]:
        """Return the raw sensor list (cached as-is by the hub)."""
        payload = await self._get("/sensors")
        if not isinstance(payload, dict) or not isinstance(
            payload.get("sensors"), list
        ):
            msg = "Unexpected sensor list format"
            raise ApiError(msg)
        return payload

    async def async_get_measurements(self, sensor_id: str) -> list[Measurement]:
        """Return the measurements of the last 60 minutes, newest first."""
        return parse_measurements(await self._get(f"/measurements/{sensor_id}"))

    async def _get(self, path: str) -> Any:
        url = f"{API_BASE_URL}{path}"
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_S)
            ) as response:
                if response.status == HTTP_TOO_MANY_REQUESTS:
                    raise ApiRateLimitError(_retry_after(response.headers))
                if response.status == HTTP_NOT_FOUND:
                    raise SensorNotFoundError(path)
                if response.status >= HTTP_BAD_REQUEST:
                    msg = f"HTTP {response.status} for {path}"
                    raise ApiError(msg)
                return await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            msg = f"Error fetching {path}: {err}"
            raise ApiConnectionError(msg) from err
        except ValueError as err:
            msg = f"Invalid JSON for {path}"
            raise ApiError(msg) from err


def _retry_after(headers: Mapping[str, str]) -> float:
    try:
        return max(float(headers.get("Retry-After", "")), 1.0)
    except ValueError:
        return DEFAULT_RETRY_AFTER_S
