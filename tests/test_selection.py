"""Tests for the request budget of a station selection."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from homeassistant.config_entries import ConfigEntryDisabler

from custom_components.urban_weather.const import (
    CONF_TEMPERATURE_SENSORS,
    NO_WIND_SENSOR,
    Environment,
)
from custom_components.urban_weather.hub import requests_per_hour
from custom_components.urban_weather.selection import StationSelection

from .common import HOME, add_location, make_station, mannheim_provider

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

WIND = "s0-w"
STATIONS = [make_station(f"s{i}", 400 + i * 100, wind=i == 0) for i in range(7)]


def sensor_ids(count: int) -> list[str]:
    """Return the temperature sensor ids of the nearest stations."""
    return [f"s{i}-t" for i in range(count)]


def make_selection(
    hass: HomeAssistant,
    stations: list | None = None,
    *,
    entry_id: str | None = None,
    min_interval: int = 15,
) -> StationSelection:
    """Return the selection for HOME (the hub is only needed for wind options)."""
    return StationSelection(
        hass,
        MagicMock(provider=mannheim_provider()),
        STATIONS if stations is None else stations,
        (*HOME, 3000.0, Environment.OPEN_BUILT),
        entry_id=entry_id,
        min_interval=min_interval,
    )


@pytest.mark.parametrize(
    ("sensors", "interval", "expected"), [(7, 20, 21), (5, 15, 20), (1, 30, 2)]
)
def test_requests_per_hour(sensors: int, interval: int, expected: int) -> None:
    """Each sensor is requested once per interval."""
    assert requests_per_hour(sensors, interval) == expected


async def test_planned_requests_count_wind_sensor(hass: HomeAssistant) -> None:
    """The wind sensor costs requests like a temperature sensor."""
    selection = make_selection(hass)
    assert selection.planned_requests(4, WIND, 15) == 20
    assert selection.planned_requests(4, NO_WIND_SENSOR, 15) == 16


async def test_planned_requests_include_other_locations(hass: HomeAssistant) -> None:
    """Other enabled locations share the budget; disabled ones do not."""
    add_location(hass, 4, 15)
    add_location(hass, 6, 10, disabled_by=ConfigEntryDisabler.USER)
    selection = make_selection(hass)
    assert selection.others == 20
    assert selection.planned_requests(1, NO_WIND_SENSOR, 30) == 22


async def test_planned_requests_exclude_reconfigured_location(
    hass: HomeAssistant,
) -> None:
    """When editing a location, its current options are not counted twice."""
    own = add_location(hass, 4, 15)
    assert make_selection(hass, entry_id=own.entry_id).others == 0


@pytest.mark.parametrize(
    ("count", "wind", "min_interval", "expected"),
    [
        (4, WIND, 15, 15),  # 5 sensors: 20/h
        (6, WIND, 15, 20),  # 7 sensors: 28/h at 15 min, 21/h at 20 min
        (1, NO_WIND_SENSOR, 15, 15),  # 10 min would fit but is below the minimum
        (1, NO_WIND_SENSOR, 10, 10),
    ],
)
async def test_fitting_interval(
    hass: HomeAssistant, count: int, wind: str, min_interval: int, expected: int
) -> None:
    """The shortest allowed interval within 24 requests per hour is used."""
    selection = make_selection(hass, min_interval=min_interval)
    assert selection.fitting_interval(count, wind) == expected


async def test_no_fitting_interval_when_others_use_the_budget(
    hass: HomeAssistant,
) -> None:
    """Another location using 21 of 24 requests leaves room for one sensor only."""
    add_location(hass, 6, 20)
    selection = make_selection(hass)
    assert selection.fitting_interval(1, NO_WIND_SENSOR) == 20
    assert selection.fitting_interval(1, WIND) is None
    assert selection.max_stations(NO_WIND_SENSOR) == 1
    assert selection.max_stations(WIND) == 0


@pytest.mark.parametrize(
    ("interval", "expected"),
    [(None, 6), (15, 5), (10, 3)],
)
async def test_max_stations(
    hass: HomeAssistant, interval: int | None, expected: int
) -> None:
    """Stations that fit with wind: any interval (capped at 6) or a fixed one."""
    assert make_selection(hass).max_stations(WIND, interval) == expected


async def test_map_counts_one_request_per_sensor(hass: HomeAssistant) -> None:
    """The map page gets the cost per refresh of up to 6 stations and wind."""
    payload = await make_selection(hass).async_map_payload(sensor_ids(1), WIND)
    assert payload["budget"]["requests"] == list(range(8))


@pytest.mark.parametrize(
    ("selected", "wind", "interval", "expected"),
    [
        ([], WIND, None, {CONF_TEMPERATURE_SENSORS: "no_station_selected"}),
        (["unknown-t"], WIND, None, {"base": "unknown_station"}),
        (sensor_ids(2), "unknown-w", None, {"base": "unknown_station"}),
        (
            sensor_ids(7),
            NO_WIND_SENSOR,
            None,
            {CONF_TEMPERATURE_SENSORS: "too_many_stations"},
        ),
        (sensor_ids(6), WIND, 10, {"base": "over_budget"}),
        (sensor_ids(4), WIND, None, {}),
        (sensor_ids(6), NO_WIND_SENSOR, 15, {}),
    ],
    ids=[
        "empty",
        "unknown_temperature_sensor",
        "unknown_wind_sensor",
        "too_many",
        "over_budget",
        "valid_auto_interval",
        "valid_fixed_interval",
    ],
)
async def test_validate(
    hass: HomeAssistant,
    selected: list[str],
    wind: str,
    interval: int | None,
    expected: dict[str, str],
) -> None:
    """Form errors of a selection."""
    assert make_selection(hass).validate(selected, wind, interval) == expected


async def test_recommendation_fits_budget(hass: HomeAssistant) -> None:
    """The recommended station and wind sensor fit an otherwise empty budget."""
    selection = make_selection(hass)
    assert selection.recommended_sensor_ids() == ["s0-t"]
    assert selection.recommended_wind_sensor_id() == WIND
    assert selection.recommendation_fits()


async def test_recommendation_does_not_fit_used_budget(hass: HomeAssistant) -> None:
    """Station + wind need 4 requests per hour at least, only 3 are left."""
    add_location(hass, 6, 20)
    assert not make_selection(hass).recommendation_fits()


async def test_no_recommendation_without_stations(hass: HomeAssistant) -> None:
    """Without stations there is nothing to recommend or fit."""
    selection = make_selection(hass, [])
    assert selection.recommended_sensor_ids() == []
    assert selection.recommended_wind_sensor_id() == NO_WIND_SENSOR
    assert not selection.recommendation_fits()
