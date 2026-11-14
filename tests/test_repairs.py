"""Tests for the fix flows of the station repair issues."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from custom_components.urban_weather.const import (
    CONF_SCAN_INTERVAL,
    CONF_TEMPERATURE_SENSORS,
    CONF_WIND_SENSOR,
    DOMAIN,
    ISSUE_ENTRY_ID,
    ISSUE_SENSOR_ID,
    NO_WIND_SENSOR,
    Field,
)
from custom_components.urban_weather.coordinator import issue_id
from custom_components.urban_weather.provider import SensorNotFoundError

from .common import (
    NEAREST_SENSOR,
    NEAREST_WIND_SENSOR,
    SECOND_SENSOR,
    add_home_entry,
    add_location,
    respond,
    store_sensor_list,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from aiohttp.test_utils import TestClient
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.common import MockConfigEntry
    from pytest_homeassistant.typing import ClientSessionGenerator

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

FIX_URL = "/api/repairs/issues/fix"


@pytest.fixture
async def client(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> TestClient:
    """Return a client for the repairs API."""
    assert await async_setup_component(hass, "repairs", {})
    return await hass_client()


async def set_up(
    hass: HomeAssistant, api: MagicMock, broken: str | None, **options: Any
) -> MockConfigEntry:
    """Set up a location at HOME; the broken sensor is unknown to the API."""
    values = defaultdict(
        lambda: {Field.TEMPERATURE: 12.0},
        {broken: SensorNotFoundError("gone")} if broken else {},
    )
    api.async_get_measurements.side_effect = respond(values)
    entry = add_home_entry(hass, **options)
    assert await hass.config_entries.async_setup(entry.entry_id)
    return entry


async def set_up_suggestion(
    hass: HomeAssistant, api: MagicMock, hass_storage: dict[str, Any]
) -> tuple[MockConfigEntry, str]:
    """Set up a location that is suggested the newly added recommended station."""
    store_sensor_list(hass_storage, timedelta(days=3), new=NEAREST_SENSOR)
    entry = await set_up(
        hass,
        api,
        None,
        **{
            CONF_TEMPERATURE_SENSORS: [SECOND_SENSOR],
            CONF_WIND_SENSOR: NEAREST_WIND_SENSOR,
        },
    )
    return entry, issue_id(entry.entry_id, "new_stations", NEAREST_SENSOR)


async def start_fix(client: TestClient, issue: str) -> dict[str, Any]:
    """Start the fix flow of an issue."""
    response = await client.post(FIX_URL, json={"handler": DOMAIN, "issue_id": issue})
    assert response.status == HTTPStatus.OK
    return await response.json()


async def fix_step(
    client: TestClient, result: dict[str, Any], user_input: dict[str, Any]
) -> dict[str, Any]:
    """Submit a step of a running fix flow."""
    response = await client.post(f"{FIX_URL}/{result['flow_id']}", json=user_input)
    assert response.status == HTTPStatus.OK
    return await response.json()


def default(result: dict[str, Any], name: str) -> Any:
    """Return the default of a field of a serialized form."""
    return next(
        field["default"] for field in result["data_schema"] if field["name"] == name
    )


@pytest.mark.parametrize(
    ("broken", "kept"),
    [(NEAREST_SENSOR, NEAREST_WIND_SENSOR), (NEAREST_WIND_SENSOR, NEAREST_SENSOR)],
    ids=["temperature", "wind"],
)
async def test_fix_uses_recommendation_without_sensor(  # noqa: PLR0913
    hass: HomeAssistant,
    api: MagicMock,
    client: TestClient,
    issue_registry: ir.IssueRegistry,
    broken: str,
    kept: str,
) -> None:
    """Accepting replaces only the broken sensor and keeps the interval."""
    entry = await set_up(
        hass,
        api,
        broken,
        **{
            CONF_TEMPERATURE_SENSORS: [NEAREST_SENSOR, SECOND_SENSOR],
            CONF_WIND_SENSOR: NEAREST_WIND_SENSOR,
        },
    )
    issue = issue_id(entry.entry_id, "station_removed", broken)

    result = await start_fix(client, issue)
    assert result["menu_options"] == ["accept", "list"]
    assert result["description_placeholders"]["entry"] == "Seckenheim"

    result = await fix_step(client, result, {"next_step_id": "accept"})
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()

    selected = [
        *entry.options[CONF_TEMPERATURE_SENSORS],
        entry.options[CONF_WIND_SENSOR],
    ]
    assert broken not in selected
    assert kept in selected, "the other sensor of the station must stay usable"
    assert entry.options[CONF_SCAN_INTERVAL] == 30
    assert issue_registry.async_get_issue(DOMAIN, issue) is None
    assert entry.state is ConfigEntryState.LOADED
    assert {sensor.id for sensor in entry.runtime_data.sensors} == set(selected), (
        "the location must be reloaded with the new stations"
    )


async def test_fix_list_preselects_current_stations_without_sensor(
    hass: HomeAssistant,
    api: MagicMock,
    client: TestClient,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The list starts with the other selected stations; errors keep it open."""
    entry = await set_up(
        hass, api, "removed", **{CONF_TEMPERATURE_SENSORS: [NEAREST_SENSOR, "removed"]}
    )
    issue = issue_id(entry.entry_id, "station_removed", "removed")

    result = await start_fix(client, issue)
    result = await fix_step(client, result, {"next_step_id": "list"})
    assert result["step_id"] == "list"
    assert default(result, CONF_TEMPERATURE_SENSORS) == [NEAREST_SENSOR]
    assert default(result, CONF_WIND_SENSOR) == NO_WIND_SENSOR

    result = await fix_step(
        client,
        result,
        {CONF_TEMPERATURE_SENSORS: [], CONF_WIND_SENSOR: NO_WIND_SENSOR},
    )
    assert result["errors"] == {CONF_TEMPERATURE_SENSORS: "no_station_selected"}

    result = await fix_step(
        client,
        result,
        {
            CONF_TEMPERATURE_SENSORS: [NEAREST_SENSOR, SECOND_SENSOR],
            CONF_WIND_SENSOR: NO_WIND_SENSOR,
        },
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert entry.options[CONF_TEMPERATURE_SENSORS] == [NEAREST_SENSOR, SECOND_SENSOR]
    assert entry.options[CONF_WIND_SENSOR] is None
    assert issue_registry.async_get_issue(DOMAIN, issue) is None


async def test_fix_menu_without_accept_when_recommendation_does_not_fit(
    hass: HomeAssistant, api: MagicMock, client: TestClient
) -> None:
    """Another location using 21 of 24 requests leaves only the list."""
    entry = await set_up(
        hass,
        api,
        SECOND_SENSOR,
        **{CONF_TEMPERATURE_SENSORS: [NEAREST_SENSOR, SECOND_SENSOR]},
    )
    add_location(hass, 6, 20)
    result = await start_fix(
        client, issue_id(entry.entry_id, "station_removed", SECOND_SENSOR)
    )
    assert result["menu_options"] == ["list"]


async def test_fix_aborts_for_unknown_location(
    hass: HomeAssistant, api: MagicMock, client: TestClient
) -> None:
    """An issue of a location that no longer exists cannot be fixed."""
    await set_up(hass, api, "removed")
    ir.async_create_issue(
        hass,
        DOMAIN,
        "station_offline_unknown",
        is_fixable=True,
        data={ISSUE_ENTRY_ID: "unknown", ISSUE_SENSOR_ID: NEAREST_SENSOR},
        severity=ir.IssueSeverity.WARNING,
        translation_key="station_offline",
    )
    result = await start_fix(client, "station_offline_unknown")
    assert result["type"] == "abort"
    assert result["reason"] == "entry_not_found"


async def test_fix_suggestion_uses_recommendation(
    hass: HomeAssistant,
    api: MagicMock,
    client: TestClient,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Accepting a suggestion switches to the recommendation with the new station."""
    entry, issue = await set_up_suggestion(hass, api, hass_storage)

    result = await start_fix(client, issue)
    assert result["menu_options"] == ["accept", "keep"]
    assert result["description_placeholders"]["stations"] == "Seckenheim (2507LH096)"

    result = await fix_step(client, result, {"next_step_id": "accept"})
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert entry.options[CONF_TEMPERATURE_SENSORS] == [NEAREST_SENSOR]
    assert entry.options[CONF_WIND_SENSOR] == NEAREST_WIND_SENSOR
    assert issue_registry.async_get_issue(DOMAIN, issue) is None


async def test_fix_suggestion_keeps_stations(
    hass: HomeAssistant,
    api: MagicMock,
    client: TestClient,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Keeping the stations ignores this suggestion, also after the next update."""
    entry, issue = await set_up_suggestion(hass, api, hass_storage)

    result = await start_fix(client, issue)
    result = await fix_step(client, result, {"next_step_id": "keep"})
    assert result["type"] == "abort"
    assert result["reason"] == "kept"
    assert entry.options[CONF_TEMPERATURE_SENSORS] == [SECOND_SENSOR]

    await entry.runtime_data.async_refresh()
    kept = issue_registry.async_get_issue(DOMAIN, issue)
    assert kept is not None
    assert kept.dismissed_version is not None, "the suggestion must stay ignored"
