"""Tests for the Opendatasoft provider with the Dortmund network."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch
from urllib.parse import parse_qs

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
from custom_components.urban_weather.providers.dortmund import DATASET, DORTMUND
from custom_components.urban_weather.providers.opendatasoft import (
    OpendatasoftProvider,
    build_stations,
    parse_measurements,
)
from custom_components.urban_weather.stations import RecommendationReason, recommend

from .common import (
    DORTMUND_HOME,
    DORTMUND_NEAREST,
    DORTMUND_NOW,
    configure,
    dortmund_records,
    location,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

EXPORT_URL = (
    f"{DORTMUND.endpoint}/catalog/datasets/klimasensoren-aktuelle-messungen"
    "/exports/json"
)
FIELDS = DORTMUND.fields
ALL_FIELDS = frozenset(FIELDS.values())
STALE_SENSOR = "fc70122c-3c93-478a-96a6-9fdff796d16f"  # DOBDKP, last value in May
CURRENT_SENSOR = "cbdfeec3-ca72-4141-ac07-7f0ec93edc84"  # DOBDKP, its successor
SHT35_SENSOR = "3f7964d9-a03c-4756-942a-a65093951555"  # DOTKLS
# Taken before the autouse fixture `only_mannheim` removes it for each test.
CREATE_DORTMUND = PROVIDERS[DORTMUND.id]


@pytest.fixture
def dortmund(
    aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> Generator[AiohttpClientMocker]:
    """Offer Dortmund (export answered from the fixture) at the time of the export."""
    freezer.move_to(DORTMUND_NOW)
    aioclient_mock.get(EXPORT_URL, json=dortmund_records())
    with patch.dict(PROVIDERS, {DORTMUND.id: CREATE_DORTMUND}):
        yield aioclient_mock


@pytest.fixture
async def provider(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,  # noqa: ARG001
) -> OpendatasoftProvider:
    """Return the Dortmund provider using the mocked aiohttp session."""
    return OpendatasoftProvider(DORTMUND, DATASET, async_get_clientsession(hass))


def query(aioclient_mock: AiohttpClientMocker, call: int = -1) -> dict[str, str]:
    """Return the query parameters of a recorded request."""
    url = aioclient_mock.mock_calls[call][1]
    return {key: value for key, [value] in parse_qs(url.query_string).items()}


def sensor(sensor_id: str) -> ApiSensor:
    """Return a sensor as the hub passes it to the provider."""
    return ApiSensor(sensor_id, "ATM41", *DORTMUND_HOME, ALL_FIELDS)


# Requests


async def test_station_list_is_one_export_without_black_globes(
    provider: OpendatasoftProvider, aioclient_mock: AiohttpClientMocker
) -> None:
    """The station list selects ids, position, time and the mapped fields."""
    aioclient_mock.get(EXPORT_URL, json=dortmund_records())
    assert await provider.async_get_station_payload() == {"records": dortmund_records()}
    assert aioclient_mock.call_count == 1
    assert query(aioclient_mock) == {
        "select": "device_id,data_station_id,sensormodell,standort,measured_at,"
        + ",".join(FIELDS),
        "where": 'sensormodell != "Blackglobe"',
    }


async def test_measurements_are_one_export_of_the_sensors_in_use(
    provider: OpendatasoftProvider, aioclient_mock: AiohttpClientMocker
) -> None:
    """All sensors in one request, selected by id; pressure is converted to hPa."""
    aioclient_mock.get(EXPORT_URL, json=dortmund_records())
    measurements = await provider.async_get_all_measurements(
        [sensor(DORTMUND_NEAREST), sensor(SHT35_SENSOR)]
    )
    assert aioclient_mock.call_count == 1
    assert query(aioclient_mock) == {
        "select": "device_id,measured_at," + ",".join(FIELDS),
        "where": f'(device_id="{DORTMUND_NEAREST}" OR device_id="{SHT35_SENSOR}") '
        'AND (sensormodell != "Blackglobe")',
    }
    [nearest] = measurements[DORTMUND_NEAREST]
    assert nearest.timestamp.isoformat() == "2026-11-21T11:07:33+00:00"
    assert nearest.values[Field.PRESSURE] == 1008.4, "100.84 kPa"
    assert nearest.values[Field.TEMPERATURE] == 6.7


async def test_no_request_without_sensors(
    provider: OpendatasoftProvider, aioclient_mock: AiohttpClientMocker
) -> None:
    """Without sensors in use there is nothing to ask for."""
    assert await provider.async_get_all_measurements([]) == {}
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    ("response", "error", "message"),
    [
        ({"status": 404}, ApiError, "HTTP 404"),
        ({"status": 500}, ApiError, "HTTP 500"),
        ({"json": {"error_code": "ODSQLError"}}, ApiError, "Unexpected export"),
        ({"text": "<html>Bad Gateway</html>"}, ApiError, "Invalid JSON"),
        ({"exc": aiohttp.ClientConnectionError()}, ApiConnectionError, "Error"),
        ({"status": 429}, ApiRateLimitError, "Rate limited"),
    ],
    ids=[
        "not_found",
        "server_error",
        "error_object",
        "invalid_json",
        "connection",
        "429",
    ],
)
async def test_request_errors(
    provider: OpendatasoftProvider,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    error: type[ApiError],
    message: str,
) -> None:
    """Errors map to the integration's exceptions; a 404 is no missing sensor."""
    aioclient_mock.get(EXPORT_URL, **response)
    with pytest.raises(error, match=message) as raised:
        await provider.async_get_all_measurements([sensor(DORTMUND_NEAREST)])
    assert type(raised.value) is error, "no more specific error than expected"


# Parsing


def test_stations_are_grouped_by_station_id() -> None:
    """Six stations; the sensor with the most fields measures, the newest on a tie."""
    stations = {s.code: s for s in build_stations(dortmund_records(), DATASET, FIELDS)}
    assert sorted(stations) == [
        "DOBBRS",
        "DOBDKP",
        "DOBHAP",
        "DOBHBF",
        "DODFRP",
        "DOTKLS",
    ]
    frp = stations["DODFRP"]
    assert frp.temperature_sensor.name == "ATM41", "ATM41 over SHT35"
    assert frp.wind_sensor is frp.temperature_sensor
    assert frp.temperature_sensor.parameters == ALL_FIELDS
    kls = stations["DOTKLS"]
    assert kls.temperature_sensor.parameters == {Field.TEMPERATURE, Field.HUMIDITY}
    assert kls.wind_sensor is None
    assert stations["DOBDKP"].temperature_sensor.id == CURRENT_SENSOR, "not the stale"
    assert all(
        s.lcz is None and s.district is None and s.zone is None
        for s in stations.values()
    ), "no siting data"


@pytest.mark.parametrize(
    "change",
    [
        {"device_id": None},
        {"data_station_id": ""},
        {"standort": None},
        {"standort": {"lat": "51.5", "lon": 7.4}},
        {"air_temperature": None, "data_wind_speed": None},
    ],
    ids=["no_id", "no_station", "no_position", "string_position", "no_values"],
)
def test_unusable_records_give_no_station(change: dict[str, Any]) -> None:
    """Records without ids, numeric position or temperature/wind are left out."""
    record = {**dortmund_records()[0], **change}
    assert build_stations([record], DATASET, FIELDS) == []


def test_parse_measurements_skips_missing_values_and_times() -> None:
    """Null values are left out; records without a time give no measurement."""
    records = [
        {"device_id": "a", "measured_at": "2026-11-21T11:00:00", "air_temperature": 5},
        {"device_id": "b", "measured_at": None, "air_temperature": 6.0},
        {"device_id": "c", "measured_at": "now", "air_temperature": 7.0},
        {"device_id": "d", "measured_at": "2026-11-21T11:00:00+00:00"},
    ]
    measurements = parse_measurements(records, DATASET, FIELDS)
    assert set(measurements) == {"a", "d"}
    [first] = measurements["a"]
    assert first.timestamp == DORTMUND_NOW.replace(minute=0), "naive time is UTC"
    assert first.values == {Field.TEMPERATURE: 5.0}
    assert measurements["d"][0].values == {}


def test_recommendation_by_distance() -> None:
    """Without siting data, the nearest station within 1 km is used alone."""
    recommendation = recommend(
        build_stations(dortmund_records(), DATASET, FIELDS),
        *DORTMUND_HOME,
        Environment.OPEN_BUILT,
        3000,
    )
    assert recommendation.reason is RecommendationReason.NEAREST_CLOSE
    assert [s.code for s in recommendation.stations] == ["DOBHAP"]
    assert recommendation.wind_station.code == "DOBHAP"


# Integration


async def test_registered_as_network(hass: HomeAssistant) -> None:
    """Dortmund is a network of its own with an Opendatasoft provider."""
    with patch.dict(PROVIDERS, {DORTMUND.id: CREATE_DORTMUND}):
        provider = await async_create_provider(hass, DORTMUND.id)
    assert isinstance(provider, OpendatasoftProvider)
    assert provider.network is DORTMUND
    assert provider.requests_per_refresh(7) == 1


async def test_location_in_dortmund(
    hass: HomeAssistant,
    dortmund: AiohttpClientMocker,
    api: Any,  # noqa: ARG001
    entity_registry: er.EntityRegistry,
) -> None:
    """Set up a location: nearest station, one request per refresh, its entities."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await configure(hass, result, location(*DORTMUND_HOME))
    assert result["step_id"] == "environment", "Mannheim is out of range"
    result = await configure(hass, result, {CONF_ENVIRONMENT: Environment.OPEN_BUILT})
    assert "accept" in result["menu_options"]
    result = await configure(hass, result, {"next_step_id": "accept"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Dortmund"
    entry = result["result"]
    assert entry.data[CONF_NETWORK] == DORTMUND.id
    assert entry.options[CONF_TEMPERATURE_SENSORS] == [DORTMUND_NEAREST]
    assert entry.options[CONF_WIND_SENSOR] == DORTMUND_NEAREST, "ATM41 measures wind"
    assert entry.options[CONF_SCAN_INTERVAL] == 15
    await hass.async_block_till_done()
    assert dortmund.call_count == 2, "station list and one measurement request"

    states = {
        registry_entry.unique_id.removeprefix(f"{entry.entry_id}_"): hass.states.get(
            registry_entry.entity_id
        )
        for registry_entry in entity_registry.entities.get_entries_for_config_entry_id(
            entry.entry_id
        )
    }
    assert states["temperature"].state == "6.7"
    assert states["pressure"].state == "1008.4"
    assert states["wind_speed"].state == "3.78", "1.05 m/s in km/h"
    assert states["temperature"].attributes[ATTR_ATTRIBUTION] == DORTMUND.attribution
    assert "min_temperature" not in states, "Dortmund has no min/max values"
