"""Client for the Smart City Mannheim climate API (https://api.smartmannheim.de/doc)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from custom_components.urban_weather.const import LOGGER
from custom_components.urban_weather.provider import (
    ApiError,
    ApiSensor,
    Measurement,
    SensorNotFoundError,
)
from custom_components.urban_weather.providers.common import async_get_json, is_number

if TYPE_CHECKING:
    from collections.abc import Mapping

    import aiohttp

    from custom_components.urban_weather.const import Field
    from custom_components.urban_weather.provider import Network

POSITION_LENGTH = 2


def parse_sensors(payload: Any, fields: Mapping[str, Field]) -> list[ApiSensor]:
    """
    Parse the /sensors response, skipping entries without a usable position.

    Parameters in `fields` get the integration's names. Other parameters keep their
    API name: they still count for the hardware generation of a sensor.
    """
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
            or not all(is_number(value) for value in position)
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
                parameters=frozenset(fields.get(name, name) for name in parameters),
            )
        )
    return sensors


def parse_measurements(payload: Any, fields: Mapping[str, Field]) -> list[Measurement]:
    """Parse the /measurements response, newest first (names as in parse_sensors)."""
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
            fields.get(key, key): float(value)
            for key, value in raw.items()
            if key != "timestamp" and is_number(value)
        }
        measurements.append(Measurement(timestamp=timestamp, values=values))
    measurements.sort(key=lambda measurement: measurement.timestamp, reverse=True)
    return measurements


class MannheimClimateApi:
    """Thin async wrapper around the two API endpoints."""

    def __init__(self, session: aiohttp.ClientSession, network: Network) -> None:
        """Use the shared Home Assistant client session."""
        self._session = session
        self._network = network

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
        return parse_measurements(
            await self._get(f"/measurements/{sensor_id}"), self._network.fields
        )

    async def _get(self, path: str) -> Any:
        return await async_get_json(
            self._session,
            f"{self._network.endpoint}{path}",
            path,
            not_found=SensorNotFoundError,
        )
