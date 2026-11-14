"""Builders shared by the tests."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
)
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import MockConfigEntry

from custom_components.urban_weather.const import (
    CONF_DEW_POINT_OFFSET,
    CONF_ENVIRONMENT,
    CONF_SCAN_INTERVAL,
    CONF_TEMPERATURE_SENSORS,
    CONF_WIND_SENSOR,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
    Environment,
    Field,
    MountZone,
)
from custom_components.urban_weather.provider import ApiSensor, Measurement
from custom_components.urban_weather.providers.mannheim import (
    MANNHEIM,
    MannheimProvider,
)
from custom_components.urban_weather.stations import LczSource, Station

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    from homeassistant.config_entries import ConfigEntryDisabler, ConfigFlowResult
    from homeassistant.core import HomeAssistant

    from custom_components.urban_weather.provider import Network

FIXTURES = Path(__file__).parent / "fixtures"
HOME = (49.472, 8.565)
HOME_UNIQUE_ID = "49.472_8.565"
HOME_DATA = {
    CONF_LATITUDE: HOME[0],
    CONF_LONGITUDE: HOME[1],
    CONF_RADIUS: 3000,
    CONF_ENVIRONMENT: Environment.OPEN_BUILT,
}
METRES_PER_DEGREE_LATITUDE = 111_320
LCZ_OPEN_BUILT = 6

TEMPERATURE_PARAMETERS = frozenset({Field.TEMPERATURE, Field.HUMIDITY})
WIND_PARAMETERS = frozenset({Field.WIND_SPEED, Field.WIND_GUST, Field.WIND_DIRECTION})

MEASURED_AT = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
MEASUREMENTS = [Measurement(MEASURED_AT, {Field.TEMPERATURE: 12.3})]

# Sensors in sensors.json; recommended for HOME: 2507LH096 alone, wind from 2507LW182.
NEAREST_SENSOR = "e7c188f7-6f3e-490d-8c67-a2e132870e17"  # 2507LH096, 444 m
NEAREST_WIND_SENSOR = "b825a7c5-4509-4a45-aced-51e94831aad3"  # 2507LW182, 444 m
SECOND_SENSOR = "1ec2c428-9677-425b-85bb-46fb6391aac7"  # 2507LH051, 575 m
CATALOG_SENSOR = "0004A30B01082C6E"  # 0101-046-21, 958 m
MEASUREMENT_AGE = timedelta(minutes=10)


def sensors_payload() -> dict[str, Any]:
    """
    Return a real /sensors response of 2026-10-20.

    Trimmed to the 52 sensors within 3 km of HOME plus 2303LH085 (no position) and
    2306LH126 (swapped coordinates).
    """
    return json.loads((FIXTURES / "sensors.json").read_text("utf-8"))


def mannheim_provider(network: Network = MANNHEIM) -> MannheimProvider:
    """Return the Mannheim provider without reference data (API client per `api`)."""
    return MannheimProvider(network, MagicMock(), MagicMock())


def store_sensor_list(
    hass_storage: dict[str, Any], age: timedelta, *, new: str | None = None
) -> None:
    """
    Put a sensor list fetched `age` ago into the mocked storage.

    Without `new` the list has no history yet, as after an update. With `new` all
    other sensors are known, so `new` counts as added with the next refresh.
    """
    payload = sensors_payload()
    data: dict[str, Any] = {
        "fetched_at": (dt_util.utcnow() - age).isoformat(),
        "payload": payload,
    }
    if new:
        data["first_seen"] = {
            sensor["id"]: None for sensor in payload["sensors"] if sensor["id"] != new
        }
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": data,
    }


def offset(distance_m: float, bearing_deg: float) -> tuple[float, float]:
    """Return the coordinate distance_m away from HOME (good enough for a few km)."""
    latitude, longitude = HOME
    bearing = math.radians(bearing_deg)
    metres_per_degree_longitude = METRES_PER_DEGREE_LATITUDE * math.cos(
        math.radians(latitude)
    )
    return (
        latitude + distance_m * math.cos(bearing) / METRES_PER_DEGREE_LATITUDE,
        longitude + distance_m * math.sin(bearing) / metres_per_degree_longitude,
    )


def make_station(  # noqa: PLR0913
    code: str,
    distance_m: float,
    *,
    bearing_deg: float = 0.0,
    lcz: int | None = LCZ_OPEN_BUILT,
    zone: MountZone | None = MountZone.STREET,
    height_above_ground: int | None = 0,
    temperature: bool = True,
    wind: bool = False,
) -> Station:
    """
    Return a station distance_m away from HOME.

    Sensor ids are "<code>-t" (temperature) and "<code>-w" (wind).
    """
    latitude, longitude = offset(distance_m, bearing_deg)

    def sensor(suffix: str, parameters: frozenset[str]) -> ApiSensor:
        return ApiSensor(
            id=f"{code}-{suffix}",
            name=code,
            latitude=latitude,
            longitude=longitude,
            parameters=parameters,
        )

    return Station(
        code=code,
        latitude=latitude,
        longitude=longitude,
        temperature_sensor=sensor("t", TEMPERATURE_PARAMETERS) if temperature else None,
        wind_sensor=sensor("w", WIND_PARAMETERS) if wind else None,
        district=None,
        lcz=lcz,
        lcz_source=LczSource.CATALOG if lcz else None,
        zone=zone,
        height_above_ground=height_above_ground,
        temperature_height=None,
    )


def add_location(
    hass: HomeAssistant,
    stations: int,
    interval: int,
    *,
    disabled_by: ConfigEntryDisabler | None = None,
) -> MockConfigEntry:
    """Add another configured location using stations + 1 wind sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_TEMPERATURE_SENSORS: [f"other{i}-t" for i in range(stations)],
            CONF_WIND_SENSOR: "other-w",
            CONF_SCAN_INTERVAL: interval,
        },
        disabled_by=disabled_by,
    )
    entry.add_to_hass(hass)
    return entry


def add_home_entry(hass: HomeAssistant, **options: Any) -> MockConfigEntry:
    """Add a location at HOME (catalogue station, 30 min, offset -1.3 K by default)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Seckenheim",
        unique_id=HOME_UNIQUE_ID,
        data=HOME_DATA,
        options={
            CONF_TEMPERATURE_SENSORS: [CATALOG_SENSOR],
            CONF_WIND_SENSOR: None,
            CONF_SCAN_INTERVAL: 30,
            CONF_DEW_POINT_OFFSET: -1.3,
            **options,
        },
    )
    entry.add_to_hass(hass)
    return entry


def location(latitude: float, longitude: float, radius: float = 3000) -> dict:
    """Return the input of the location step."""
    return {
        CONF_LOCATION: {
            CONF_LATITUDE: latitude,
            CONF_LONGITUDE: longitude,
            CONF_RADIUS: radius,
        }
    }


async def configure(
    hass: HomeAssistant, result: ConfigFlowResult, user_input: dict | None = None
) -> ConfigFlowResult:
    """Submit a step of a running config flow."""
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input)


def respond(
    values: Mapping[str, Mapping[str, float] | Exception],
) -> Callable[[str], Awaitable[list[Measurement]]]:
    """Return an API side effect: one recent measurement or an error per sensor."""

    async def measurements(sensor_id: str) -> list[Measurement]:
        value = values[sensor_id]
        if isinstance(value, Exception):
            raise value
        return [Measurement(dt_util.utcnow() - MEASUREMENT_AGE, value)]

    return measurements
