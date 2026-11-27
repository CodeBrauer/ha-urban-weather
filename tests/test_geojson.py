"""Tests for the GeoJSON provider with the Zürich, Karlsruhe and Dresden networks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import aiohttp
import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.urban_weather.aggregation import latest_valid
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
from custom_components.urban_weather.providers.common import parse_epoch_ms
from custom_components.urban_weather.providers.dresden import (
    DRESDEN,
    clean_name,
    parse_time,
)
from custom_components.urban_weather.providers.dresden import FEED as DRESDEN_FEED
from custom_components.urban_weather.providers.geojson import (
    GeoJsonProvider,
    build_stations,
    parse_measurements,
)
from custom_components.urban_weather.providers.karlsruhe import (
    FEED as KARLSRUHE_FEED,
)
from custom_components.urban_weather.providers.karlsruhe import KARLSRUHE
from custom_components.urban_weather.providers.zurich import FEED, ZURICH
from custom_components.urban_weather.stations import RecommendationReason, recommend

from .common import (
    DRESDEN_HOME,
    DRESDEN_NEAREST,
    DRESDEN_NOW,
    KARLSRUHE_HOME,
    KARLSRUHE_NEAREST,
    KARLSRUHE_NOW,
    ZURICH_HOME,
    ZURICH_NEAREST,
    ZURICH_NOW,
    configure,
    dresden_geojson,
    karlsruhe_geojson,
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
CREATE_KARLSRUHE = PROVIDERS[KARLSRUHE.id]
CREATE_DRESDEN = PROVIDERS[DRESDEN.id]


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
    assert nearest.label == f"Bootsanleger Bürkliplatz ({ZURICH_NEAREST})"
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
    assert station.name is None
    assert station.label == ZURICH_NEAREST, "no name, no repeated id"


def test_name_equal_to_the_id_is_no_name() -> None:
    """A name that only repeats the id is not shown twice."""
    [station] = build_stations(
        [feature(location_name=f" {ZURICH_NEAREST} ")], FEED, FIELDS
    )
    assert station.label == ZURICH_NEAREST


def test_newest_feature_wins_on_a_repeated_id() -> None:
    """A repeated id is one station, described and measured by its newest feature."""
    old = feature(
        timestamp="2026-11-22T10:00:00Z", location_name="Old", temperature_c=1
    )
    new = feature(
        timestamp="2026-11-22T11:00:00Z", location_name="New", temperature_c=2
    )
    for ordered in ([old, new], [new, old]):
        [station] = build_stations(ordered, FEED, FIELDS)
        assert station.temperature_sensor.name == "New"
        [measurement] = parse_measurements(ordered, FEED, FIELDS)[ZURICH_NEAREST]
        assert measurement.values[Field.TEMPERATURE] == 2.0, "not the older value"


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


# Karlsruhe: ArcGIS query with parameters, times in milliseconds since the epoch


@pytest.fixture
def karlsruhe(
    aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> Generator[AiohttpClientMocker]:
    """Offer Karlsruhe (query answered from the fixture) shortly after the export."""
    freezer.move_to(KARLSRUHE_NOW)
    aioclient_mock.get(KARLSRUHE.endpoint, json=karlsruhe_geojson())
    with patch.dict(PROVIDERS, {KARLSRUHE.id: CREATE_KARLSRUHE}):
        yield aioclient_mock


@pytest.fixture
async def karlsruhe_provider(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,  # noqa: ARG001
) -> GeoJsonProvider:
    """Return the Karlsruhe provider using the mocked aiohttp session."""
    return GeoJsonProvider(KARLSRUHE, KARLSRUHE_FEED, async_get_clientsession(hass))


def karlsruhe_features() -> list[dict[str, Any]]:
    """Return the features of the Karlsruhe fixture."""
    return karlsruhe_geojson()["features"]


async def test_karlsruhe_query_selects_air_temperature(
    karlsruhe_provider: GeoJsonProvider, aioclient_mock: AiohttpClientMocker
) -> None:
    """The request carries the query: air temperature sensors only, as GeoJSON."""
    aioclient_mock.get(KARLSRUHE.endpoint, json=karlsruhe_geojson())
    await karlsruhe_provider.async_get_station_payload()
    [(_, url, _, _)] = aioclient_mock.mock_calls
    assert url.query["where"] == "beschreibung = 'Temperatur-Sensor'"
    assert url.query["f"] == "geojson"
    assert set(url.query["outFields"].split(",")) == {
        "device_id",
        "name",
        "measured_at",
        "temp",
        "luftfeuchte",
    }, "only the properties the integration reads"


async def test_karlsruhe_measurements(
    karlsruhe_provider: GeoJsonProvider, aioclient_mock: AiohttpClientMocker
) -> None:
    """The time in milliseconds is read as UTC; temperature and humidity map."""
    aioclient_mock.get(KARLSRUHE.endpoint, json=karlsruhe_geojson())
    sensors = [ApiSensor(KARLSRUHE_NEAREST, "Station", *KARLSRUHE_HOME, frozenset())]
    measurements = await karlsruhe_provider.async_get_all_measurements(sensors)
    assert len(measurements) == len(karlsruhe_features())
    [nearest] = measurements[KARLSRUHE_NEAREST]
    assert nearest.timestamp.isoformat() == "2026-11-23T16:19:08.012000+00:00"
    assert nearest.values == {Field.TEMPERATURE: 1.3, Field.HUMIDITY: 74.0}
    assert karlsruhe_provider.requests_per_refresh(7) == 1


def test_karlsruhe_stations() -> None:
    """Each sensor is a station of its own, named by the label of the city."""
    stations = build_stations(karlsruhe_features(), KARLSRUHE_FEED, KARLSRUHE.fields)
    assert len(stations) == 7
    nearest = next(s for s in stations if s.code == KARLSRUHE_NEAREST)
    assert (nearest.latitude, nearest.longitude) == pytest.approx(
        (49.011285, 8.406802)
    ), "lat, lon"
    assert (
        nearest.temperature_sensor.name
        == "173 - Schlossplatz 3 (Kreuzung Kronenstraße)"
    )
    assert nearest.temperature_sensor.parameters == frozenset(KARLSRUHE.fields.values())
    assert nearest.wind_sensor is None
    assert nearest.label == (
        f"173 - Schlossplatz 3 (Kreuzung Kronenstraße) ({KARLSRUHE_NEAREST})"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1795450748012, "2026-11-23T16:19:08.012000+00:00"),
        (0, "1970-01-01T00:00:00+00:00"),
        (1795450748012.0, "2026-11-23T16:19:08.012000+00:00"),
        (None, None),
        ("1795450748012", None),
        (True, None),
        (float("nan"), None),
        (10**30, None),
    ],
    ids=["ms", "epoch", "float", "none", "text", "bool", "nan", "out_of_range"],
)
def test_parse_epoch_ms(value: Any, expected: str | None) -> None:
    """A number is a time in milliseconds; anything else gives no time."""
    parsed = parse_epoch_ms(value)
    assert (parsed.isoformat() if parsed else None) == expected


def test_karlsruhe_iso_time_is_no_time() -> None:
    """A feed with epoch times gives no measurement for a text time."""
    feature = karlsruhe_features()[0]
    feature["properties"]["measured_at"] = "2026-11-23T16:19:08Z"
    assert parse_measurements([feature], KARLSRUHE_FEED, KARLSRUHE.fields) == {}


def test_karlsruhe_recommendation_by_distance() -> None:
    """Without siting data, the nearest station within 1 km is used alone."""
    recommendation = recommend(
        build_stations(karlsruhe_features(), KARLSRUHE_FEED, KARLSRUHE.fields),
        *KARLSRUHE_HOME,
        Environment.OPEN_BUILT,
        3000,
    )
    assert recommendation.reason is RecommendationReason.NEAREST_CLOSE
    assert [s.code for s in recommendation.stations] == [KARLSRUHE_NEAREST]
    assert recommendation.wind_station is None


async def test_location_in_karlsruhe(
    hass: HomeAssistant,
    karlsruhe: AiohttpClientMocker,
    api: Any,  # noqa: ARG001
    entity_registry: er.EntityRegistry,
) -> None:
    """Set up a location: nearest station, one request per refresh, its entities."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await configure(hass, result, location(*KARLSRUHE_HOME))
    result = await configure(hass, result, {CONF_ENVIRONMENT: Environment.OPEN_BUILT})
    result = await configure(hass, result, {"next_step_id": "accept"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Karlsruhe"
    entry = result["result"]
    assert entry.data[CONF_NETWORK] == KARLSRUHE.id
    assert entry.options[CONF_TEMPERATURE_SENSORS] == [KARLSRUHE_NEAREST]
    assert entry.options[CONF_WIND_SENSOR] is None, "Karlsruhe measures no wind"
    await hass.async_block_till_done()
    assert karlsruhe.call_count == 2, "station list and one measurement request"

    states = {
        registry_entry.unique_id.removeprefix(f"{entry.entry_id}_"): hass.states.get(
            registry_entry.entity_id
        )
        for registry_entry in entity_registry.entities.get_entries_for_config_entry_id(
            entry.entry_id
        )
    }
    assert states["temperature"].state == "1.3"
    assert states["humidity"].state == "74.0"
    assert states["temperature"].attributes[ATTR_ATTRIBUTION] == KARLSRUHE.attribution
    assert "pressure" not in states, "pressure is not read"


# Dresden: WFS in long format with a time window, times in CET without offset


@pytest.fixture
def dresden(
    aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> Generator[AiohttpClientMocker]:
    """Offer Dresden (every request answered from the fixture) after the export."""
    freezer.move_to(DRESDEN_NOW)
    aioclient_mock.get(DRESDEN.endpoint, json=dresden_geojson())
    with patch.dict(PROVIDERS, {DRESDEN.id: CREATE_DRESDEN}):
        yield aioclient_mock


@pytest.fixture
async def dresden_provider(
    hass: HomeAssistant,
    dresden: AiohttpClientMocker,  # noqa: ARG001
) -> GeoJsonProvider:
    """Return the Dresden provider using the mocked aiohttp session."""
    return GeoJsonProvider(DRESDEN, DRESDEN_FEED, async_get_clientsession(hass))


def dresden_features() -> list[dict[str, Any]]:
    """Return the features of the Dresden fixture."""
    return dresden_geojson()["features"]


def dresden_feature(**changes: Any) -> dict[str, Any]:
    """Return the first feature of the Dresden fixture with changed properties."""
    first = dresden_features()[0]
    return {**first, "properties": {**first["properties"], **changes}}


def dresden_measurements() -> dict[str, Any]:
    """Return the measurements of the whole fixture by station."""
    return parse_measurements(dresden_features(), DRESDEN_FEED, DRESDEN.fields)


async def test_dresden_requests_select_a_window(
    dresden_provider: GeoJsonProvider, dresden: AiohttpClientMocker
) -> None:
    """Every request filters by time: 24 h for the station list, 4 h for values."""
    await dresden_provider.async_get_station_payload()
    await dresden_provider.async_get_all_measurements(
        [ApiSensor(DRESDEN_NEAREST, "Station", *DRESDEN_HOME, frozenset())]
    )
    [(_, station_url, _, station_headers), (_, measurement_url, _, headers)] = (
        dresden.mock_calls
    )
    for sent in (station_headers, headers):
        assert sent["Accept-Encoding"] == "identity", "compressed responses never end"
    for url in (station_url, measurement_url):
        assert url.query["TypeNames"] == "cls:L1625"
        assert url.query["outputFormat"] == "application/geo+json"
        assert url.query["SrsName"] == "urn:ogc:def:crs:EPSG::4326", "lon, lat"
        assert "PropertyIsGreaterThan" in url.query["FILTER"]
        assert "<fes:ValueReference>messzeit<" in url.query["FILTER"]
    # 22:35 UTC is 23:35 CET.
    assert "<fes:Literal>2026-11-25T23:35:00<" in station_url.query["FILTER"]
    assert "<fes:Literal>2026-11-26T19:35:00<" in measurement_url.query["FILTER"]
    assert dresden_provider.requests_per_refresh(7) == 1


async def test_dresden_station_payload_keeps_the_newest_values(
    dresden_provider: GeoJsonProvider,
) -> None:
    """The stored station list keeps the newest feature per station and value."""
    payload = await dresden_provider.async_get_station_payload()
    kept = {
        (f["properties"]["device"], f["properties"]["bemerk"]): f["properties"]
        for f in payload["features"]
    }
    assert len(kept) == len(payload["features"]) == 18, "9 stations x 2 values"
    assert kept[("223", "air_temperature")]["messzeit"] == "26.11.2026 19:00:00"
    assert kept[("224", "rel_humidity")]["messzeit"] == "26.11.2026 21:00:00"
    assert sorted(s.code for s in dresden_provider.build_stations(payload)) == sorted(
        s.code for s in build_stations(dresden_features(), DRESDEN_FEED, DRESDEN.fields)
    ), "the same stations as from the whole response"


def test_dresden_stations_group_values_by_device() -> None:
    """One station per device with both values; a device without geometry is out."""
    stations = {
        s.code: s
        for s in build_stations(dresden_features(), DRESDEN_FEED, DRESDEN.fields)
    }
    assert sorted(stations) == sorted(["200", "222", "223", "224", "491", "492"]), (
        "550 has no geometry, 167 and 280 fell silent"
    )
    nearest = stations[DRESDEN_NEAREST]
    assert (nearest.latitude, nearest.longitude) == pytest.approx(
        (51.050777, 13.734053), abs=1e-6
    ), "lat, lon"
    assert nearest.temperature_sensor.id == DRESDEN_NEAREST
    assert nearest.temperature_sensor.name == "Postplatz (DVB)"
    assert nearest.temperature_sensor.parameters == frozenset(DRESDEN.fields.values())
    assert nearest.wind_sensor is None
    assert nearest.label == f"Postplatz (DVB) ({DRESDEN_NEAREST})"
    [marked] = build_stations(
        [f for f in dresden_features() if f["properties"]["device"] == "280"],
        DRESDEN_FEED,
        DRESDEN.fields,
    )
    assert marked.name == "Fiedlerstraße 19", "without the leading mark"


def test_dresden_silent_stations_are_not_listed() -> None:
    """A station silent for longer than max_age before the newest value is left out."""
    codes = {
        s.code for s in build_stations(dresden_features(), DRESDEN_FEED, DRESDEN.fields)
    }
    assert "167" not in codes, "silent since 06:00, newest value 21:00"
    assert "280" not in codes, "silent since 09:00"
    assert "223" in codes, "two hours behind is still current"
    silent = next(f for f in dresden_features() if f["properties"]["device"] == "167")
    latitude, longitude = reversed(silent["geometry"]["coordinates"])
    recommendation = recommend(
        build_stations(dresden_features(), DRESDEN_FEED, DRESDEN.fields),
        latitude,
        longitude,
        Environment.OPEN_BUILT,
        3000,
    )
    assert "167" not in [s.code for s in recommendation.stations]


@pytest.mark.parametrize(
    ("time", "listed"),
    [("26.11.2026 17:00:00", True), ("26.11.2026 16:00:00", False)],
    ids=["max_age_before", "older"],
)
def test_dresden_silence_counts_from_the_newest_value(
    time: str,
    listed: bool,  # noqa: FBT001
) -> None:
    """The cut is relative to the newest value of the payload, not to now."""
    newest = dresden_feature()  # 21:00
    other = dresden_feature(device="999", messzeit=time)
    stations = build_stations([newest, other], DRESDEN_FEED, DRESDEN.fields)
    assert ("999" in {s.code for s in stations}) is listed


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("$Vogesenweg 9", "Vogesenweg 9"),
        ("#  Kohlenstraße", "Kohlenstraße"),
        (" $ Goldener Reiter ", "Goldener Reiter"),
        ("Postplatz (DVB)", "Postplatz (DVB)"),
        ("Hohlergasse 2d - Tilo_Garten- Nr_2", "Hohlergasse 2d - Tilo_Garten- Nr_2"),
        ("$", ""),
    ],
    ids=["dollar", "hash_spaces", "spaces_around", "plain", "inner_marks", "mark_only"],
)
def test_dresden_clean_name(value: str, expected: str) -> None:
    """Leading `$` or `#` marks and the spaces after them are left out."""
    assert clean_name(value) == expected


def test_dresden_budget_fits_three_locations() -> None:
    """Three locations at 15 minutes fit the planned budget and the sent limits."""
    requests = 3 * 60 // 15
    assert DRESDEN.limits.planned_per_hour >= requests
    assert DRESDEN.limits.per_hour >= DRESDEN.limits.planned_per_hour
    assert all(
        count >= requests * window / 3600
        for count, window in DRESDEN.limits.measurements
        if window >= 3600
    ), "the hourly limit lets the planned requests through"


def test_dresden_measurements_are_the_newest_hour() -> None:
    """Values of the newest hour per station, the time read as CET."""
    measurements = dresden_measurements()
    assert len(measurements) == 9, "a station without geometry still has values"
    [nearest] = measurements[DRESDEN_NEAREST]
    assert nearest.timestamp.isoformat() == "2026-11-26T20:00:00+01:00"
    assert nearest.values == {Field.TEMPERATURE: 1.2, Field.HUMIDITY: 62.0}
    [fresh] = measurements["224"]
    assert fresh.timestamp == DRESDEN_NOW.replace(hour=20, minute=0)
    assert fresh.values == {Field.TEMPERATURE: 0.6, Field.HUMIDITY: 64.0}


@pytest.mark.parametrize(
    ("station", "current"),
    [
        ("224", True),
        (DRESDEN_NEAREST, True),
        ("491", True),
        ("223", False),
        ("167", False),
    ],
    ids=["newest_hour", "hour_before", "status_u", "late", "silent"],
)
def test_dresden_late_stations_are_stale(station: str, current: bool) -> None:  # noqa: FBT001
    """Values up to about 3 h old are used; late and silent stations drop out."""
    latest = latest_valid(dresden_measurements()[station], DRESDEN_NOW, DRESDEN.max_age)
    assert (latest is not None) is current


def test_dresden_value_missing_in_the_newest_hour_comes_from_an_older_one() -> None:
    """A station's newest hour with humidity only keeps the temperature before it."""
    features = [
        dresden_feature(messzeit="26.11.2026 20:00:00", wert_n=1.0),
        dresden_feature(
            messzeit="26.11.2026 20:00:00", bemerk="rel_humidity", wert_n=60.0
        ),
        dresden_feature(
            messzeit="26.11.2026 21:00:00", bemerk="rel_humidity", wert_n=65.0
        ),
    ]
    station = features[0]["properties"]["device"]
    [measurement] = parse_measurements(features, DRESDEN_FEED, DRESDEN.fields)[station]
    assert measurement.values == {Field.TEMPERATURE: 1.0, Field.HUMIDITY: 65.0}
    assert measurement.timestamp.isoformat() == "2026-11-26T21:00:00+01:00", (
        "the time of the newest value"
    )


def test_dresden_station_measures_values_of_different_hours() -> None:
    """A station's values in different hours still count as what it measures."""
    features = [
        dresden_feature(
            messzeit="26.11.2026 20:00:00", bemerk="rel_humidity", wert_n=60.0
        ),
        dresden_feature(messzeit="26.11.2026 21:00:00", wert_n=1.0),
    ]
    [station] = build_stations(features, DRESDEN_FEED, DRESDEN.fields)
    assert station.temperature_sensor is not None
    assert station.temperature_sensor.parameters == {
        Field.TEMPERATURE,
        Field.HUMIDITY,
    }


def test_dresden_old_value_does_not_make_a_fresh_one_stale() -> None:
    """A value older than an hour is not filled in, so the fresh one stays current."""
    features = [
        dresden_feature(
            messzeit="26.11.2026 17:00:00", bemerk="rel_humidity", wert_n=60.0
        ),
        dresden_feature(messzeit="26.11.2026 21:00:00", wert_n=1.0),
    ]
    station = features[0]["properties"]["device"]
    [measurement] = parse_measurements(features, DRESDEN_FEED, DRESDEN.fields)[station]
    assert measurement.values == {Field.TEMPERATURE: 1.0}
    assert measurement.timestamp.isoformat() == "2026-11-26T21:00:00+01:00"
    latest = latest_valid([measurement], DRESDEN_NOW, DRESDEN.max_age)
    assert latest is not None, "the fresh temperature is used"


async def test_dresden_station_payload_skips_newer_unusable_values(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A newer feature without a value does not hide the last valid one."""
    valid = dresden_feature(messzeit="26.11.2026 20:00:00", wert_n=1.0)
    empty = dresden_feature(messzeit="26.11.2026 21:00:00", wert_n=None)
    aioclient_mock.get(
        DRESDEN.endpoint,
        json={"type": "FeatureCollection", "features": [valid, empty]},
    )
    provider = GeoJsonProvider(DRESDEN, DRESDEN_FEED, async_get_clientsession(hass))
    payload = await provider.async_get_station_payload()
    assert [f["properties"]["wert_n"] for f in payload["features"]] == [1.0]
    assert [s.code for s in provider.build_stations(payload)] == [
        valid["properties"]["device"]
    ]


def test_dresden_humidity_of_zero_is_dropped() -> None:
    """A humidity of 0 % is implausible; the temperature of that hour is used."""
    [measurement] = dresden_measurements()["280"]
    assert measurement.values == {Field.TEMPERATURE: 0.4, Field.HUMIDITY: 0.0}
    latest = latest_valid([measurement], measurement.timestamp, DRESDEN.max_age)
    assert latest is not None
    assert latest.values == {Field.TEMPERATURE: 0.4}


@pytest.mark.parametrize(
    "changes",
    [
        {"bemerk": "wind_speed"},
        {"bemerk": None},
        {"bemerk": ["air_temperature"]},
        {"wert_n": None},
        {"wert_n": "0.6"},
        {"messzeit": "2026-11-26T21:00:00"},
        {"device": None},
    ],
    ids=[
        "unknown_value",
        "no_value_name",
        "list_value_name",
        "no_value",
        "text_value",
        "iso_time",
        "no_device",
    ],
)
def test_dresden_unusable_features_are_skipped(changes: dict[str, Any]) -> None:
    """Unknown or missing values, other time formats and missing ids are left out."""
    assert (
        parse_measurements([dresden_feature(**changes)], DRESDEN_FEED, DRESDEN.fields)
        == {}
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("26.11.2026 21:00:00", "2026-11-26T20:00:00+00:00"),
        ("26.07.2026 21:00:00", "2026-07-26T20:00:00+00:00"),
        ("2026-11-26T21:00:00", None),
        ("26.11.2026", None),
        (None, None),
    ],
    ids=["winter", "summer_is_cet_too", "iso", "date_only", "none"],
)
def test_dresden_parse_time(value: Any, expected: str | None) -> None:
    """Times are CET all year, without daylight saving time."""
    parsed = parse_time(value)
    assert (parsed.astimezone(DRESDEN_NOW.tzinfo).isoformat() if parsed else None) == (
        expected
    )


def test_dresden_recommendation_by_distance() -> None:
    """Without siting data, the nearest station within 1 km is used alone."""
    recommendation = recommend(
        build_stations(dresden_features(), DRESDEN_FEED, DRESDEN.fields),
        *DRESDEN_HOME,
        Environment.OPEN_BUILT,
        3000,
    )
    assert recommendation.reason is RecommendationReason.NEAREST_CLOSE
    assert [s.code for s in recommendation.stations] == [DRESDEN_NEAREST]
    assert recommendation.wind_station is None


async def test_location_in_dresden(
    hass: HomeAssistant,
    dresden: AiohttpClientMocker,
    api: Any,  # noqa: ARG001
    entity_registry: er.EntityRegistry,
) -> None:
    """Set up a location: nearest station, one request per refresh, its entities."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await configure(hass, result, location(*DRESDEN_HOME))
    result = await configure(hass, result, {CONF_ENVIRONMENT: Environment.OPEN_BUILT})
    result = await configure(hass, result, {"next_step_id": "accept"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Dresden"
    entry = result["result"]
    assert entry.data[CONF_NETWORK] == DRESDEN.id
    assert entry.options[CONF_TEMPERATURE_SENSORS] == [DRESDEN_NEAREST]
    assert entry.options[CONF_WIND_SENSOR] is None, "Dresden measures no wind"
    assert entry.options[CONF_SCAN_INTERVAL] == 15, "4 requests per hour"
    await hass.async_block_till_done()
    assert dresden.call_count == 2, "station list and one measurement request"

    states = {
        registry_entry.unique_id.removeprefix(f"{entry.entry_id}_"): hass.states.get(
            registry_entry.entity_id
        )
        for registry_entry in entity_registry.entities.get_entries_for_config_entry_id(
            entry.entry_id
        )
    }
    assert states["temperature"].state == "1.2"
    assert states["humidity"].state == "62.0"
    assert states["temperature"].attributes[ATTR_ATTRIBUTION] == DRESDEN.attribution
