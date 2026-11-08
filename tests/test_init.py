"""Tests for setting up, unloading and removing a location."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from custom_components.mannheim_climate.api import ApiConnectionError
from custom_components.mannheim_climate.const import (
    CONF_TEMPERATURE_SENSORS,
    CONF_WIND_SENSOR,
    DOMAIN,
    ISSUE_ENTRY_ID,
    ISSUE_SENSOR_ID,
    Field,
)
from custom_components.mannheim_climate.coordinator import issue_id

from .common import (
    NEAREST_SENSOR,
    NEAREST_WIND_SENSOR,
    SECOND_SENSOR,
    add_home_entry,
    respond,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

VALUES = {
    NEAREST_SENSOR: {
        Field.TEMPERATURE: 12.0,
        Field.MIN_TEMPERATURE: 11.0,
        Field.MAX_TEMPERATURE: 12.5,
    },
    SECOND_SENSOR: {
        Field.TEMPERATURE: 13.0,
        Field.MIN_TEMPERATURE: 12.0,
        Field.MAX_TEMPERATURE: 13.5,
    },
    NEAREST_WIND_SENSOR: {Field.WIND_SPEED: 3.0, Field.WIND_GUST_DIRECTION: 250.0},
}
OPTIONAL_SENSORS = {
    "min_temperature": "11.5",
    "max_temperature": "13.0",
    "wind_gust_direction": "250.0",
}


@pytest.fixture
def entry(hass: HomeAssistant, api: MagicMock) -> MockConfigEntry:
    """Return a location using two stations and a wind sensor."""
    api.async_get_measurements.side_effect = respond(VALUES)
    return add_home_entry(
        hass,
        **{
            CONF_TEMPERATURE_SENSORS: [NEAREST_SENSOR, SECOND_SENSOR],
            CONF_WIND_SENSOR: NEAREST_WIND_SENSOR,
        },
    )


async def test_setup_and_unload(
    hass: HomeAssistant, entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Setup fetches all sensors and creates the entities with values."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED

    temperature = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_temperature"
    )
    assert hass.states.get(temperature).state == "12.5"
    assert hass.states.get("weather.seckenheim") is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_optional_sensors_disabled_by_default(
    hass: HomeAssistant, entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Minimum, maximum and gust direction are created, but disabled."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    for key in OPTIONAL_SENSORS:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{key}"
        )
        assert entity_id is not None, f"{key} sensor not created"
        registered = entity_registry.async_get(entity_id)
        assert registered.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert hass.states.get(entity_id) is None


async def test_optional_sensor_values(
    hass: HomeAssistant, entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Enabled, they show the median minimum/maximum and the wind station's value."""
    enabled = {
        key: entity_registry.async_get_or_create(
            "sensor", DOMAIN, f"{entry.entry_id}_{key}", config_entry=entry
        ).entity_id
        for key in OPTIONAL_SENSORS
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    for key, expected in OPTIONAL_SENSORS.items():
        assert hass.states.get(enabled[key]).state == expected, key


async def test_setup_retried_without_station_list(
    hass: HomeAssistant, entry: MockConfigEntry, api: MagicMock
) -> None:
    """No station list (and no stored copy): try again later."""
    api.async_get_sensors_payload.side_effect = ApiConnectionError("timeout")
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_fails_when_no_selected_station_exists(
    hass: HomeAssistant, api: MagicMock
) -> None:
    """Stations removed from the API need a new selection, retrying won't help."""
    entry = add_home_entry(hass, **{CONF_TEMPERATURE_SENSORS: ["removed"]})
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    api.async_get_measurements.assert_not_awaited()


@pytest.mark.parametrize(
    "options",
    [
        {CONF_TEMPERATURE_SENSORS: [NEAREST_SENSOR, "removed"]},
        {CONF_TEMPERATURE_SENSORS: [NEAREST_SENSOR], CONF_WIND_SENSOR: "removed"},
    ],
    ids=["temperature", "wind"],
)
async def test_setup_reports_sensor_missing_from_station_list(
    hass: HomeAssistant,
    api: MagicMock,
    issue_registry: ir.IssueRegistry,
    options: dict[str, Any],
) -> None:
    """A selected sensor the station list no longer has raises a fixable issue."""
    api.async_get_measurements.side_effect = respond(VALUES)
    entry = add_home_entry(hass, **options)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    issue = issue_registry.async_get_issue(
        DOMAIN, issue_id(entry.entry_id, "station_removed", "removed")
    )
    assert issue is not None, "removed sensor dropped without a repair issue"
    assert issue.is_fixable


async def test_setup_deletes_issues_of_deselected_sensors(
    hass: HomeAssistant, api: MagicMock, issue_registry: ir.IssueRegistry
) -> None:
    """After a new selection, issues of sensors no longer selected go away."""
    api.async_get_measurements.side_effect = respond(VALUES)
    entry = add_home_entry(hass, **{CONF_TEMPERATURE_SENSORS: [NEAREST_SENSOR]})
    own = issue_id(entry.entry_id, "station_offline", SECOND_SENSOR)
    other = issue_id("other_entry", "station_offline", SECOND_SENSOR)
    for entry_id, issue in ((entry.entry_id, own), ("other_entry", other)):
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue,
            is_fixable=True,
            data={ISSUE_ENTRY_ID: entry_id, ISSUE_SENSOR_ID: SECOND_SENSOR},
            severity=ir.IssueSeverity.WARNING,
            translation_key="station_offline",
        )
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, own) is None, (
        "issue of a deselected sensor must not stay"
    )
    assert issue_registry.async_get_issue(DOMAIN, other) is not None


async def test_setup_retried_without_recent_data(
    hass: HomeAssistant, entry: MockConfigEntry, api: MagicMock
) -> None:
    """The first refresh must deliver values."""
    api.async_get_measurements.side_effect = ApiConnectionError("timeout")
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_remove_deletes_repair_issues(
    hass: HomeAssistant, entry: MockConfigEntry, issue_registry: ir.IssueRegistry
) -> None:
    """Repair issues of a removed location go away; others stay."""
    own = issue_id(entry.entry_id, "station_offline", NEAREST_SENSOR)
    other = issue_id("other_entry", "station_offline", NEAREST_SENSOR)
    for issue in (own, other):
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="station_offline",
        )
    await hass.config_entries.async_remove(entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, own) is None
    assert issue_registry.async_get_issue(DOMAIN, other) is not None
