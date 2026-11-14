"""Tests for the entities a location gets from what its network measures."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers import entity_registry as er

from custom_components.urban_weather.const import (
    CONF_TEMPERATURE_SENSORS,
    CONF_WIND_SENSOR,
    DOMAIN,
    Field,
)
from custom_components.urban_weather.provider import Measurement, Provider
from custom_components.urban_weather.sensor import SENSORS

from .common import (
    MEASURED_AT,
    NEAREST_SENSOR,
    NEAREST_WIND_SENSOR,
    add_home_entry,
    make_station,
    respond,
)
from .test_provider import FAKE_NETWORK

if TYPE_CHECKING:
    from collections.abc import Mapping
    from unittest.mock import MagicMock

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

    from custom_components.urban_weather.stations import Station

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

TEMPERATURE = {Field.TEMPERATURE: 20.0}
TEMPERATURE_HUMIDITY = {**TEMPERATURE, Field.HUMIDITY: 50.0}
DIAGNOSTIC = {"stations_used", "temperature_spread", "last_measurement"}
HUMIDITY_SENSORS = {"humidity", "dew_point", "absolute_humidity"}
WIND_SENSORS = {"wind_speed", "wind_gust", "wind_direction"}
WEATHER_FROM_HUMIDITY = {"humidity", "dew_point"}
# A sensor of the fake network without a wind sensor of its own.
TEMPERATURE_SENSOR = "fake-t"
WIND_SENSOR = "fake-w"
FULL_TEMPERATURE_VALUES = {
    Field.TEMPERATURE: 20.0,
    Field.MIN_TEMPERATURE: 18.0,
    Field.MAX_TEMPERATURE: 22.0,
    Field.HUMIDITY: 50.0,
    Field.DEW_POINT: 9.0,
    Field.PRESSURE: 1013.0,
    Field.IRRADIANCE: 500.0,
}
FULL_WIND_VALUES = {
    Field.WIND_SPEED: 3.0,
    Field.WIND_GUST: 5.0,
    Field.WIND_GUST_1S: 6.0,
    Field.WIND_DIRECTION: 90.0,
    Field.WIND_GUST_DIRECTION: 100.0,
}


class ValuesProvider(Provider):
    """One station of the fake network measuring exactly the given values."""

    def __init__(
        self, temperature: Mapping[str, float], wind: Mapping[str, float]
    ) -> None:
        """Set the values of the temperature and the wind sensor."""
        super().__init__(FAKE_NETWORK)
        self.values = {TEMPERATURE_SENSOR: temperature, WIND_SENSOR: wind}

    async def async_get_station_payload(self) -> dict[str, Any]:
        """Return an empty payload."""
        return {}

    def build_stations(self, payload: dict[str, Any]) -> list[Station]:  # noqa: ARG002
        """Return the station with sensors that measure what the values name."""
        station = make_station("fake", 500, wind=True)
        return [
            replace(
                station,
                temperature_sensor=replace(
                    station.temperature_sensor,
                    parameters=frozenset(self.values[TEMPERATURE_SENSOR]),
                ),
                wind_sensor=replace(
                    station.wind_sensor, parameters=frozenset(self.values[WIND_SENSOR])
                ),
            )
        ]

    async def async_get_measurements(self, sensor_id: str) -> list[Measurement]:
        """Return the values of the sensor."""
        return await respond(self.values)(sensor_id)


async def set_up_fake(
    hass: HomeAssistant,
    temperature: Mapping[str, float],
    wind: Mapping[str, float] | None = None,
) -> str:
    """Set up a location on the fake network and return its entry id."""
    provider = ValuesProvider(temperature, wind or {})
    entry = add_home_entry(
        hass,
        **{
            CONF_TEMPERATURE_SENSORS: [TEMPERATURE_SENSOR],
            CONF_WIND_SENSOR: WIND_SENSOR if wind else None,
        },
    )
    with patch(
        "custom_components.urban_weather.hub.async_create_provider",
        return_value=provider,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
    return entry.entry_id


def sensor_keys(entity_registry: er.EntityRegistry, entry_id: str) -> set[str]:
    """Return the keys of the sensors of a location."""
    prefix = f"{entry_id}_"
    return {
        entity.unique_id.removeprefix(prefix)
        for entity in er.async_entries_for_config_entry(entity_registry, entry_id)
        if entity.domain == "sensor"
    }


def weather_attributes(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entry_id: str
) -> dict[str, Any]:
    """Return the attributes of the weather entity of a location."""
    entity_id = entity_registry.async_get_entity_id(
        "weather", DOMAIN, f"{entry_id}_weather"
    )
    return dict(hass.states.get(entity_id).attributes)


async def test_temperature_only(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """A network that only measures temperature gets no derived values."""
    entry_id = await set_up_fake(hass, TEMPERATURE)
    assert sensor_keys(entity_registry, entry_id) == {"temperature", *DIAGNOSTIC}
    attributes = weather_attributes(hass, entity_registry, entry_id)
    assert attributes["temperature"] == 20.0
    assert not {"humidity", "dew_point", "apparent_temperature"} & attributes.keys()


async def test_temperature_and_humidity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Humidity brings dew point and absolute humidity, nothing else is derived."""
    freezer.move_to(MEASURED_AT)
    entry_id = await set_up_fake(hass, TEMPERATURE_HUMIDITY)
    assert sensor_keys(entity_registry, entry_id) == {
        "temperature",
        *HUMIDITY_SENSORS,
        *DIAGNOSTIC,
    }
    attributes = weather_attributes(hass, entity_registry, entry_id)
    assert attributes.keys() >= WEATHER_FROM_HUMIDITY
    assert "apparent_temperature" not in attributes, "needs wind"
    entity_id = entity_registry.async_get_entity_id(
        "weather", DOMAIN, f"{entry_id}_weather"
    )
    assert hass.states.get(entity_id).state == STATE_UNKNOWN, "no irradiance, no sun"


async def test_wind_alone_does_not_create_apparent_temperature(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Apparent temperature needs humidity as well as wind speed."""
    entry_id = await set_up_fake(hass, TEMPERATURE, {Field.WIND_SPEED: 3.0})
    assert "apparent_temperature" not in sensor_keys(entity_registry, entry_id)


@pytest.mark.parametrize(
    ("wind", "gust"),
    [
        ({Field.WIND_SPEED: 3.0}, False),
        ({Field.WIND_SPEED: 3.0, Field.WIND_GUST: 5.0}, True),
        ({Field.WIND_SPEED: 3.0, Field.WIND_GUST_1S: 6.0}, True),
    ],
)
async def test_wind_gust_needs_a_gust_field(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    wind: dict[str, float],
    *,
    gust: bool,
) -> None:
    """Wind speed alone does not create the gust sensor."""
    entry_id = await set_up_fake(hass, TEMPERATURE_HUMIDITY, wind)
    keys = sensor_keys(entity_registry, entry_id)
    assert ("wind_gust" in keys) is gust
    assert "apparent_temperature" in keys
    assert not {"wind_direction", "wind_gust_direction"} & keys


@pytest.mark.parametrize(
    ("values", "humidity"), [(TEMPERATURE, False), (TEMPERATURE_HUMIDITY, True)]
)
async def test_attributes_name_only_what_is_measured(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    values: dict[str, float],
    *,
    humidity: bool,
) -> None:
    """The temperature sensor lists humidity only if the network measures it."""
    entry_id = await set_up_fake(hass, values)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry_id}_temperature"
    )
    attributes = hass.states.get(entity_id).attributes
    assert set(attributes["stations"]["fake"]) == {
        "temperature",
        "distance_km",
        "timestamp",
        *(["humidity"] if humidity else []),
    }
    assert ("humidity_uncorrected" in attributes) is humidity


async def test_full_mannheim_set(
    hass: HomeAssistant, api: MagicMock, entity_registry: er.EntityRegistry
) -> None:
    """Mannheim stations measure everything, so every sensor exists."""
    api.async_get_measurements.side_effect = respond(
        {NEAREST_SENSOR: FULL_TEMPERATURE_VALUES, NEAREST_WIND_SENSOR: FULL_WIND_VALUES}
    )
    entry = add_home_entry(
        hass,
        **{
            CONF_TEMPERATURE_SENSORS: [NEAREST_SENSOR],
            CONF_WIND_SENSOR: NEAREST_WIND_SENSOR,
        },
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert sensor_keys(entity_registry, entry.entry_id) == {s.key for s in SENSORS}
    attributes = weather_attributes(hass, entity_registry, entry.entry_id)
    assert {
        "apparent_temperature",
        "dew_point",
        "humidity",
        "pressure",
        "wind_speed",
        "wind_gust_speed",
        "wind_bearing",
    } <= attributes.keys()
