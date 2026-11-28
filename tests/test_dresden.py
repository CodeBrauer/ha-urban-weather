"""Tests for the Dresden network: WFS in long format, a time window, CET times."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

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
    ApiSensor,
)
from custom_components.urban_weather.providers import PROVIDERS
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
from custom_components.urban_weather.providers.karlsruhe import KARLSRUHE
from custom_components.urban_weather.providers.zurich import ZURICH
from custom_components.urban_weather.stations import RecommendationReason, recommend

from .common import (
    DRESDEN_HOME,
    DRESDEN_NEAREST,
    DRESDEN_NOW,
    configure,
    dresden_geojson,
    location,
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
    [built] = build_stations(features, DRESDEN_FEED, DRESDEN.fields)
    assert built.temperature_sensor.parameters == {Field.TEMPERATURE}, (
        "a value that is never filled in does not create an entity"
    )


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
