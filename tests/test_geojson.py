"""Tests for the GeoJSON provider with the Zürich network."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import aiohttp
import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.urban_weather.const import (
    CONF_ENVIRONMENT,
    CONF_NETWORK,
    CONF_SCAN_INTERVAL,
    CONF_TEMPERATURE_SENSORS,
    CONF_WIND_SENSOR,
    DOMAIN,
    Environment,
    Field,
)
from custom_components.urban_weather.provider import (
    ApiConnectionError,
    ApiError,
    ApiRateLimitError,
    ApiSensor,
)
from custom_components.urban_weather.providers import PROVIDERS, async_create_provider
from custom_components.urban_weather.providers.geojson import (
    GeoJsonProvider,
    build_stations,
    parse_measurements,
)
from custom_components.urban_weather.providers.zurich import FEED, ZURICH
from custom_components.urban_weather.stations import RecommendationReason, recommend

from .common import (
    ZURICH_HOME,
    ZURICH_NEAREST,
    ZURICH_NOW,
    configure,
    location,
    zurich_geojson,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

FIELDS = ZURICH.fields
ALL_FIELDS = frozenset(FIELDS.values())
# Taken before the autouse fixture `only_mannheim` removes it for each test.
CREATE_ZURICH = PROVIDERS[ZURICH.id]


@pytest.fixture
def zurich(
    aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> Generator[AiohttpClientMocker]:
    """Offer Zürich (file answered from the fixture) at the time of the export."""
    freezer.move_to(ZURICH_NOW)
    aioclient_mock.get(ZURICH.endpoint, json=zurich_geojson())
    with patch.dict(PROVIDERS, {ZURICH.id: CREATE_ZURICH}):
        yield aioclient_mock


@pytest.fixture
async def provider(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,  # noqa: ARG001
) -> GeoJsonProvider:
    """Return the Zürich provider using the mocked aiohttp session."""
    return GeoJsonProvider(ZURICH, FEED, async_get_clientsession(hass))


def features() -> list[dict[str, Any]]:
    """Return the features of the fixture."""
    return zurich_geojson()["features"]


def feature(**changes: Any) -> dict[str, Any]:
    """Return the nearest feature with changed properties or `geometry`."""
    nearest = features()[0]
    geometry = changes.pop("geometry", nearest["geometry"])
    properties = {**nearest["properties"], **changes}
    return {**nearest, "geometry": geometry, "properties": properties}


def sensor(sensor_id: str) -> ApiSensor:
    """Return a sensor as the hub passes it to the provider."""
    return ApiSensor(sensor_id, "Station", *ZURICH_HOME, ALL_FIELDS)


# Requests


async def test_station_list_is_the_file(
    provider: GeoJsonProvider, aioclient_mock: AiohttpClientMocker
) -> None:
    """The station list is one request of the file; the features are stored."""
    aioclient_mock.get(ZURICH.endpoint, json=zurich_geojson())
    assert await provider.async_get_station_payload() == {"features": features()}
    assert aioclient_mock.call_count == 1


async def test_measurements_are_one_request_of_the_file(
    provider: GeoJsonProvider, aioclient_mock: AiohttpClientMocker
) -> None:
    """All stations in one request, whichever sensors are in use."""
    aioclient_mock.get(ZURICH.endpoint, json=zurich_geojson())
    measurements = await provider.async_get_all_measurements([sensor(ZURICH_NEAREST)])
    assert aioclient_mock.call_count == 1
    assert len(measurements) == len(features())
    [nearest] = measurements[ZURICH_NEAREST]
    assert nearest.timestamp.isoformat() == "2026-11-22T23:37:04+00:00"
    assert nearest.values == {Field.TEMPERATURE: 4.3, Field.HUMIDITY: 91.4}


async def test_no_request_without_sensors(
    provider: GeoJsonProvider, aioclient_mock: AiohttpClientMocker
) -> None:
    """Without sensors in use there is nothing to ask for."""
    assert await provider.async_get_all_measurements([]) == {}
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    ("response", "error", "message"),
    [
        ({"status": 404}, ApiError, "HTTP 404"),
        ({"status": 500}, ApiError, "HTTP 500"),
        ({"json": {"type": "Error"}}, ApiError, "Unexpected GeoJSON"),
        ({"json": {"type": "FeatureCollection"}}, ApiError, "Unexpected GeoJSON"),
        ({"json": []}, ApiError, "Unexpected GeoJSON"),
        ({"text": "<html>Bad Gateway</html>"}, ApiError, "Invalid JSON"),
        ({"exc": aiohttp.ClientConnectionError()}, ApiConnectionError, "Error"),
        ({"status": 429}, ApiRateLimitError, "Rate limited"),
    ],
    ids=[
        "not_found",
        "server_error",
        "error_object",
        "no_features",
        "list",
        "invalid_json",
        "connection",
        "429",
    ],
)
async def test_request_errors(
    provider: GeoJsonProvider,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    error: type[ApiError],
    message: str,
) -> None:
    """Errors map to the integration's exceptions; a 404 is no missing sensor."""
    aioclient_mock.get(ZURICH.endpoint, **response)
    with pytest.raises(error, match=message) as raised:
        await provider.async_get_all_measurements([sensor(ZURICH_NEAREST)])
    assert type(raised.value) is error, "no more specific error than expected"


# Parsing


def test_one_station_per_feature() -> None:
    """The station is its own sensor; id and name from the properties, no wind."""
    stations = {s.code: s for s in build_stations(features(), FEED, FIELDS)}
    assert sorted(stations) == ["117", "133", "163", "167", "172", "206", "96"]
    nearest = stations[ZURICH_NEAREST]
    assert (nearest.latitude, nearest.longitude) == (47.36565, 8.54193), "lat, lon"
    assert nearest.temperature_sensor.id == ZURICH_NEAREST
    assert nearest.temperature_sensor.name == "Bootsanleger Bürkliplatz"
    assert nearest.temperature_sensor.parameters == ALL_FIELDS
    assert nearest.wind_sensor is None
    assert all(
        s.lcz is None and s.district is None and s.zone is None
        for s in stations.values()
    ), "no siting data"


@pytest.mark.parametrize(
    "change",
    [
        {"location_id": None},
        {"location_id": ""},
        {"geometry": None},
        {"geometry": {"type": "Polygon", "coordinates": [[8.5, 47.3]]}},
        {"geometry": {"type": "Point", "coordinates": ["8.5", "47.3"]}},
        {"geometry": {"type": "Point", "coordinates": [8.5]}},
        {"temperature_c": None, "humidity_relative_percent": None},
    ],
    ids=[
        "no_id",
        "empty_id",
        "no_geometry",
        "not_a_point",
        "string_position",
        "short_position",
        "no_values",
    ],
)
def test_unusable_features_give_no_station(change: dict[str, Any]) -> None:
    """Features without id, Point position or temperature are left out."""
    assert build_stations([feature(**change)], FEED, FIELDS) == []


def test_station_without_a_name_uses_its_id() -> None:
    """The id stands in for a missing name."""
    [station] = build_stations([feature(location_name=None)], FEED, FIELDS)
    assert station.temperature_sensor.name == ZURICH_NEAREST


def test_newest_feature_wins_on_a_repeated_id() -> None:
    """A repeated id is one station, described by its newest feature."""
    old = feature(timestamp="2026-11-22T10:00:00Z", location_name="Old")
    new = feature(timestamp="2026-11-22T11:00:00Z", location_name="New")
    for ordered in ([old, new], [new, old]):
        [station] = build_stations(ordered, FEED, FIELDS)
        assert station.temperature_sensor.name == "New"


def test_parse_measurements_skips_missing_values_and_times() -> None:
    """Null values are left out; features without a time give no measurement."""
    collection = [
        feature(location_id=1, timestamp="2026-11-22T11:00:00", temperature_c=5),
        feature(location_id=2, timestamp=None, temperature_c=6.0),
        feature(location_id=3, timestamp="now", temperature_c=7.0),
        feature(
            location_id=4,
            timestamp="2026-11-22T12:00:00+01:00",
            temperature_c=None,
            humidity_relative_percent=None,
        ),
        feature(location_id=5, humidity_relative_percent="wet"),
        feature(location_id=None),
    ]
    measurements = parse_measurements(collection, FEED, FIELDS)
    assert set(measurements) == {"1", "4", "5"}
    [first] = measurements["1"]
    assert first.timestamp == ZURICH_NOW.replace(hour=11, minute=0), "naive time is UTC"
    assert first.values == {Field.TEMPERATURE: 5.0, Field.HUMIDITY: 91.4}
    [offset] = measurements["4"]
    assert offset.timestamp.isoformat() == "2026-11-22T12:00:00+01:00"
    assert offset.values == {}
    assert measurements["5"][0].values == {Field.TEMPERATURE: 4.3}, "text is no value"


def test_recommendation_by_distance() -> None:
    """Without siting data, the nearest station within 1 km is used alone."""
    recommendation = recommend(
        build_stations(features(), FEED, FIELDS),
        *ZURICH_HOME,
        Environment.OPEN_BUILT,
        3000,
    )
    assert recommendation.reason is RecommendationReason.NEAREST_CLOSE
    assert [s.code for s in recommendation.stations] == [ZURICH_NEAREST]
    assert recommendation.wind_station is None


# Integration


async def test_registered_as_network(hass: HomeAssistant) -> None:
    """Zürich is a network of its own with a GeoJSON provider."""
    with patch.dict(PROVIDERS, {ZURICH.id: CREATE_ZURICH}):
        provider = await async_create_provider(hass, ZURICH.id)
    assert isinstance(provider, GeoJsonProvider)
    assert provider.network is ZURICH
    assert provider.requests_per_refresh(7) == 1


async def test_location_in_zurich(
    hass: HomeAssistant,
    zurich: AiohttpClientMocker,
    api: Any,  # noqa: ARG001
    entity_registry: er.EntityRegistry,
) -> None:
    """Set up a location: nearest station, one request per refresh, its entities."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await configure(hass, result, location(*ZURICH_HOME))
    assert result["step_id"] == "environment", "Mannheim is out of range"
    result = await configure(hass, result, {CONF_ENVIRONMENT: Environment.OPEN_BUILT})
    assert "accept" in result["menu_options"]
    result = await configure(hass, result, {"next_step_id": "accept"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Zürich"
    entry = result["result"]
    assert entry.data[CONF_NETWORK] == ZURICH.id
    assert entry.options[CONF_TEMPERATURE_SENSORS] == [ZURICH_NEAREST]
    assert entry.options[CONF_WIND_SENSOR] is None, "Zürich measures no wind"
    assert entry.options[CONF_SCAN_INTERVAL] == 15
    await hass.async_block_till_done()
    assert zurich.call_count == 2, "station list and one measurement request"

    states = {
        registry_entry.unique_id.removeprefix(f"{entry.entry_id}_"): hass.states.get(
            registry_entry.entity_id
        )
        for registry_entry in entity_registry.entities.get_entries_for_config_entry_id(
            entry.entry_id
        )
    }
    assert states["temperature"].state == "4.3"
    assert states["humidity"].state == "91.4"
    assert states["temperature"].attributes[ATTR_ATTRIBUTION] == ZURICH.attribution
    assert "wind_speed" not in states, "Zürich has no wind"
    assert "pressure" not in states, "Zürich has no pressure"
