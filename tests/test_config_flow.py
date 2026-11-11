"""Tests for the config flow, the interactive map step and the options flow."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from unittest.mock import patch
from urllib.parse import urlparse

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_RADIUS,
)
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant.common import MockConfigEntry

from custom_components.urban_weather.const import (
    CONF_DEW_POINT_OFFSET,
    CONF_ENVIRONMENT,
    CONF_SCAN_INTERVAL,
    CONF_TEMPERATURE_SENSORS,
    CONF_WIND_SENSOR,
    DOMAIN,
    NO_WIND_SENSOR,
    Environment,
)
from custom_components.urban_weather.provider import ApiConnectionError

from .common import (
    CATALOG_SENSOR,
    HOME,
    HOME_DATA,
    HOME_UNIQUE_ID,
    NEAREST_SENSOR,
    NEAREST_WIND_SENSOR,
    SECOND_SENSOR,
    add_home_entry,
    add_location,
    configure,
    location,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    from unittest.mock import AsyncMock, MagicMock

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.config_entries import ConfigFlowResult
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.typing import ClientSessionGenerator

pytestmark = pytest.mark.usefixtures("enable_custom_integrations", "api")

MUNICH = (48.137, 11.575)
DENSE_PLACE = (49.498952, 8.467278)  # 2306LH126, LCZ 2
DENSE_SENSOR = "846c0b2b-4a6f-48ed-9383-d975cae2823f"  # 2306LH126


@pytest.fixture(autouse=True)
def setup_entry() -> Generator[AsyncMock]:
    """Do not set up created or reloaded entries (see test_init)."""
    with patch(
        "custom_components.urban_weather.async_setup_entry", return_value=True
    ) as setup:
        yield setup


async def start_at_stations_menu(
    hass: HomeAssistant, place: tuple[float, float] = HOME
) -> ConfigFlowResult:
    """Run the user flow up to the station menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await configure(hass, result, location(*place))
    result = await configure(hass, result, {CONF_ENVIRONMENT: Environment.OPEN_BUILT})
    assert result["type"] is FlowResultType.MENU
    return result


# User flow


async def test_user_flow_accepts_recommendation(hass: HomeAssistant) -> None:
    """Location, surroundings, recommendation: one station plus wind."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await configure(hass, result, location(*HOME))
    assert result["step_id"] == "environment"

    result = await configure(hass, result, {CONF_ENVIRONMENT: Environment.OPEN_BUILT})
    assert result["menu_options"] == ["accept", "map", "list"]
    assert "2507LH096" in result["description_placeholders"]["recommended_list"]

    result = await configure(hass, result, {"next_step_id": "accept"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Seckenheim"
    assert result["result"].unique_id == HOME_UNIQUE_ID
    assert result["data"] == HOME_DATA
    assert result["options"] == {
        CONF_TEMPERATURE_SENSORS: [NEAREST_SENSOR],
        CONF_WIND_SENSOR: NEAREST_WIND_SENSOR,
        CONF_SCAN_INTERVAL: 15,
        CONF_DEW_POINT_OFFSET: 0.0,
    }


async def test_title_is_home_name_at_home(hass: HomeAssistant) -> None:
    """A location at the Home Assistant home gets the home's name."""
    hass.config.latitude, hass.config.longitude = HOME
    result = await start_at_stations_menu(hass)
    result = await configure(hass, result, {"next_step_id": "accept"})
    assert result["title"] == hass.config.location_name


async def test_search_radius_is_capped(hass: HomeAssistant) -> None:
    """The radius of the location picker is limited to 10 km."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await configure(hass, result, location(*HOME, radius=50_000))
    result = await configure(hass, result, {CONF_ENVIRONMENT: Environment.OPEN_BUILT})
    result = await configure(hass, result, {"next_step_id": "accept"})
    assert result["data"][CONF_RADIUS] == 10_000


@pytest.mark.parametrize(
    ("place", "expected"),
    [(HOME, Environment.OPEN_BUILT), (DENSE_PLACE, Environment.DENSE)],
    ids=["open_built", "dense"],
)
async def test_environment_preselected_from_lcz_map(
    hass: HomeAssistant, place: tuple[float, float], expected: Environment
) -> None:
    """The surroundings step suggests the LCZ class of the location."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await configure(hass, result, location(*place))
    assert result["data_schema"]({})[CONF_ENVIRONMENT] == expected


async def test_outside_coverage(hass: HomeAssistant) -> None:
    """Places without a station within 10 km are rejected; the form stays open."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await configure(hass, result, location(*MUNICH))
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "outside_coverage"}

    result = await configure(hass, result, location(*HOME))
    assert result["step_id"] == "environment"


async def test_location_already_configured(hass: HomeAssistant) -> None:
    """Locations within ~100 m of a configured one are rejected."""
    add_home_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await configure(hass, result, location(HOME[0] + 0.0002, HOME[1]))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_cannot_connect(hass: HomeAssistant, api: MagicMock) -> None:
    """Without station list the flow cannot start."""
    api.async_get_sensors_payload.side_effect = ApiConnectionError("timeout")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_menu_without_accept_when_recommendation_does_not_fit(
    hass: HomeAssistant,
) -> None:
    """Another location using 21 of 24 requests leaves no room for station + wind."""
    add_location(hass, 6, 20)
    result = await start_at_stations_menu(hass)
    assert result["menu_options"] == ["map", "list"]


async def test_list_step(hass: HomeAssistant) -> None:
    """The list starts with the recommendation; errors keep the form open."""
    result = await start_at_stations_menu(hass)
    result = await configure(hass, result, {"next_step_id": "list"})
    assert result["step_id"] == "list"
    defaults = result["data_schema"]({})
    assert defaults[CONF_TEMPERATURE_SENSORS] == [NEAREST_SENSOR]
    assert defaults[CONF_WIND_SENSOR] == NEAREST_WIND_SENSOR

    result = await configure(
        hass,
        result,
        {CONF_TEMPERATURE_SENSORS: [], CONF_WIND_SENSOR: NO_WIND_SENSOR},
    )
    assert result["errors"] == {CONF_TEMPERATURE_SENSORS: "no_station_selected"}

    result = await configure(
        hass,
        result,
        {
            CONF_TEMPERATURE_SENSORS: [NEAREST_SENSOR, SECOND_SENSOR],
            CONF_WIND_SENSOR: NO_WIND_SENSOR,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_TEMPERATURE_SENSORS] == [
        NEAREST_SENSOR,
        SECOND_SENSOR,
    ]
    assert result["options"][CONF_WIND_SENSOR] is None


# Interactive map (external step)


async def open_map(hass: HomeAssistant) -> tuple[ConfigFlowResult, str]:
    """Run the flow to the map step; return the result and the page path."""
    hass.config.internal_url = "http://homeassistant.local:8123"
    result = await start_at_stations_menu(hass)
    result = await configure(hass, result, {"next_step_id": "map"})
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    url = urlparse(result["url"])
    assert url.netloc == "homeassistant.local:8123"
    return result, url.path


async def test_map_selection_continues_flow(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """The map page shows the stations; saving there finishes the flow."""
    result, path = await open_map(hass)
    client = await hass_client_no_auth()

    page = await client.get(path)
    assert page.status == HTTPStatus.OK
    assert page.headers["Cache-Control"] == "no-store"
    assert NEAREST_SENSOR in await page.text()

    saved = await client.post(
        path,
        json={
            CONF_TEMPERATURE_SENSORS: [NEAREST_SENSOR, SECOND_SENSOR],
            CONF_WIND_SENSOR: NEAREST_WIND_SENSOR,
        },
    )
    assert saved.status == HTTPStatus.OK
    assert await saved.json() == {"ok": True}

    result = await configure(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_TEMPERATURE_SENSORS] == [
        NEAREST_SENSOR,
        SECOND_SENSOR,
    ]
    assert result["options"][CONF_WIND_SENSOR] == NEAREST_WIND_SENSOR
    assert (await client.get(path)).status == HTTPStatus.NOT_FOUND, "link used up"


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ("not json", "invalid"),
        ({CONF_TEMPERATURE_SENSORS: [NEAREST_SENSOR]}, "invalid"),
        (
            {CONF_TEMPERATURE_SENSORS: ["unknown"], CONF_WIND_SENSOR: NO_WIND_SENSOR},
            "unknown_station",
        ),
        (
            {CONF_TEMPERATURE_SENSORS: [], CONF_WIND_SENSOR: NO_WIND_SENSOR},
            "no_station_selected",
        ),
    ],
    ids=["no_json", "missing_wind", "unknown_station", "empty"],
)
async def test_map_rejects_invalid_selection(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    body: Any,
    error: str,
) -> None:
    """Invalid selections are reported to the page; the flow keeps waiting."""
    result, path = await open_map(hass)
    client = await hass_client_no_auth()
    if isinstance(body, str):
        response = await client.post(path, data=body)
    else:
        response = await client.post(path, json=body)
    assert response.status == HTTPStatus.BAD_REQUEST
    assert await response.json() == {"error": error}
    flow = hass.config_entries.flow.async_get(result["flow_id"])
    assert flow["step_id"] == "map"


async def test_map_link_expires(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A map link is valid for 30 minutes."""
    _, path = await open_map(hass)
    client = await hass_client_no_auth()
    freezer.tick(timedelta(minutes=29, seconds=59))
    assert (await client.get(path)).status == HTTPStatus.OK
    freezer.tick(timedelta(seconds=1))
    assert (await client.get(path)).status == HTTPStatus.NOT_FOUND
    response = await client.post(
        path,
        json={CONF_TEMPERATURE_SENSORS: [NEAREST_SENSOR], CONF_WIND_SENSOR: "none"},
    )
    assert response.status == HTTPStatus.NOT_FOUND
    assert await response.json() == {"error": "expired"}


async def test_map_link_invalid_after_flow_is_closed(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Closing the dialog invalidates the link."""
    result, path = await open_map(hass)
    client = await hass_client_no_auth()
    hass.config_entries.flow.async_abort(result["flow_id"])
    assert (await client.get(path)).status == HTTPStatus.NOT_FOUND


async def test_map_unknown_link(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Guessed tokens get no page."""
    _, path = await open_map(hass)
    client = await hass_client_no_auth()
    response = await client.get(path.rsplit("/", 1)[0] + "/guessed")
    assert response.status == HTTPStatus.NOT_FOUND


# Reconfigure


async def test_reconfigure_moves_location(hass: HomeAssistant) -> None:
    """A moved location gets new stations; interval and humidity offset stay."""
    entry = add_home_entry(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    assert result["data_schema"]({})[CONF_LOCATION][CONF_LATITUDE] == HOME[0]

    result = await configure(hass, result, location(*DENSE_PLACE))
    result = await configure(hass, result, {CONF_ENVIRONMENT: Environment.DENSE})
    result = await configure(hass, result, {"next_step_id": "accept"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "49.499_8.467"
    assert entry.data[CONF_ENVIRONMENT] == Environment.DENSE
    assert entry.options[CONF_TEMPERATURE_SENSORS] == [DENSE_SENSOR]
    assert entry.options[CONF_SCAN_INTERVAL] == 30
    assert entry.options[CONF_DEW_POINT_OFFSET] == -1.3


async def test_reconfigure_to_other_location_aborts(hass: HomeAssistant) -> None:
    """A location cannot be moved onto another configured one."""
    add_home_entry(hass)
    other = MockConfigEntry(
        domain=DOMAIN,
        unique_id="49.499_8.467",
        data={**HOME_DATA, CONF_LATITUDE: DENSE_PLACE[0]},
    )
    other.add_to_hass(hass)
    result = await other.start_reconfigure_flow(hass)
    result = await configure(hass, result, location(*HOME))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# Options


async def test_options_change_stations_and_offset(
    hass: HomeAssistant, setup_entry: AsyncMock
) -> None:
    """Stations, interval and offset are saved; the entry is reloaded."""
    entry = add_home_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    defaults = result["data_schema"]({})
    assert defaults[CONF_TEMPERATURE_SENSORS] == [CATALOG_SENSOR]
    assert defaults[CONF_WIND_SENSOR] == NO_WIND_SENSOR

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_TEMPERATURE_SENSORS: [NEAREST_SENSOR, SECOND_SENSOR],
            CONF_WIND_SENSOR: NEAREST_WIND_SENSOR,
            CONF_SCAN_INTERVAL: "10",
            CONF_DEW_POINT_OFFSET: -1.26,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_TEMPERATURE_SENSORS: [NEAREST_SENSOR, SECOND_SENSOR],
        CONF_WIND_SENSOR: NEAREST_WIND_SENSOR,
        CONF_SCAN_INTERVAL: 10,
        CONF_DEW_POINT_OFFSET: -1.3,
    }
    assert setup_entry.await_count == 1, "reloaded"


async def test_options_over_budget(hass: HomeAssistant) -> None:
    """Another location's requests count: 2 stations + wind every 10 min is too much."""
    entry = add_home_entry(hass)
    add_location(hass, 4, 15)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_TEMPERATURE_SENSORS: [NEAREST_SENSOR, SECOND_SENSOR],
            CONF_WIND_SENSOR: NEAREST_WIND_SENSOR,
            CONF_SCAN_INTERVAL: "10",
            CONF_DEW_POINT_OFFSET: 0,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "over_budget"}


async def test_options_cannot_connect(hass: HomeAssistant, api: MagicMock) -> None:
    """Without station list the options cannot be changed."""
    api.async_get_sensors_payload.side_effect = ApiConnectionError("timeout")
    entry = add_home_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
