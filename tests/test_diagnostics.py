"""Tests for the diagnostics download."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE

from custom_components.urban_weather.const import (
    CONF_TEMPERATURE_SENSORS,
    CONF_WIND_SENSOR,
    Field,
)
from custom_components.urban_weather.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .common import (
    CATALOG_SENSOR,
    NEAREST_SENSOR,
    NEAREST_WIND_SENSOR,
    SECOND_SENSOR,
    add_home_entry,
    respond,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

SENSORS = [NEAREST_SENSOR, SECOND_SENSOR, CATALOG_SENSOR]


async def test_location_cannot_be_derived(hass: HomeAssistant, api: MagicMock) -> None:
    """Coordinates are redacted and no station reveals its distance to them."""
    api.async_get_measurements.side_effect = respond(
        {
            NEAREST_SENSOR: {Field.TEMPERATURE: 12.0},
            SECOND_SENSOR: {Field.TEMPERATURE: 13.0},
            CATALOG_SENSOR: {Field.TEMPERATURE: 14.0},
            NEAREST_WIND_SENSOR: {Field.WIND_SPEED: 3.0},
        }
    )
    entry = add_home_entry(
        hass,
        **{CONF_TEMPERATURE_SENSORS: SENSORS, CONF_WIND_SENSOR: NEAREST_WIND_SENSOR},
    )
    assert await hass.config_entries.async_setup(entry.entry_id)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["data"][CONF_LATITUDE] == REDACTED
    assert diagnostics["entry"]["data"][CONF_LONGITUDE] == REDACTED
    stations = diagnostics["stations"]
    assert len(stations) == len(SENSORS)
    leaking = [s["code"] for s in stations if "distance_m" in s]
    assert not leaking, f"distances allow trilateration of the location: {leaking}"
