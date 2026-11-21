"""Tests for the provider interface, with a fake network next to Mannheim."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import MockConfigEntry

from custom_components.urban_weather.const import (
    CONF_ENVIRONMENT,
    CONF_TEMPERATURE_SENSORS,
    DOMAIN,
    MAX_SELECTED_STATIONS,
    MEASUREMENT_CACHE_TTL,
    NO_WIND_SENSOR,
    SCAN_INTERVAL_CHOICES_MIN,
    STORAGE_KEY,
    Environment,
    Field,
)
from custom_components.urban_weather.hub import RequestDeferredError, async_get_hub
from custom_components.urban_weather.provider import (
    ApiConnectionError,
    ApiRateLimitError,
    ApiSensor,
    BulkProvider,
    Measurement,
    Network,
    RequestLimits,
    TileLayer,
)
from custom_components.urban_weather.providers.mannheim import MANNHEIM
from custom_components.urban_weather.selection import StationSelection

from .common import (
    HOME,
    MEASUREMENT_AGE,
    add_home_entry,
    configure,
    location,
    make_station,
)

if TYPE_CHECKING:
    from collections.abc import Collection, Generator

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    from custom_components.urban_weather.stations import Station

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

FAKE_NETWORK = Network(
    name="Fake network",
    operator="Fake operator",
    area="Fakeville",
    endpoint="https://fake.example/api",
    fields={"t": Field.TEMPERATURE, "rh": Field.HUMIDITY},
    attribution="Fake data (CC0)",
    limits=RequestLimits(
        measurements=((1, 60),),
        station_list=((1, 3600),),
        per_hour=60,
        planned_per_hour=48,
    ),
    tiles=TileLayer(url="https://tiles.example/{z}/{x}/{y}.png", attribution="Fake"),
)
PAYLOAD = {"stations": ["fake1", "fake2"]}
FAKE_SENSOR = "fake1-t"


class FakeProvider(BulkProvider):
    """Stations near HOME without siting data; all sensors in one request."""

    def __init__(self) -> None:
        """Record the sensors of each measurement request."""
        super().__init__(FAKE_NETWORK)
        self.requests: list[set[str]] = []

    async def async_get_station_payload(self) -> dict[str, Any]:
        """Return a payload only this provider understands."""
        return PAYLOAD

    def build_stations(self, payload: dict[str, Any]) -> list[Station]:
        """Return one station per payload entry, without LCZ and mount zone."""
        return [
            make_station(
                code,
                400 + index * 200,
                lcz=None,
                zone=None,
                height_above_ground=None,
            )
            for index, code in enumerate(payload["stations"])
        ]

    async def async_get_all_measurements(
        self, sensors: Collection[ApiSensor]
    ) -> dict[str, list[Measurement]]:
        """Return one recent measurement for each requested sensor."""
        self.requests.append({sensor.id for sensor in sensors})
        measurement = Measurement(
            dt_util.utcnow() - MEASUREMENT_AGE,
            {Field.TEMPERATURE: 21.0, Field.HUMIDITY: 50.0},
        )
        return {sensor.id: [measurement] for sensor in sensors}


@pytest.fixture
def provider() -> Generator[FakeProvider]:
    """Let the hub use the fake provider instead of Mannheim."""
    fake = FakeProvider()
    with patch(
        "custom_components.urban_weather.hub.async_create_provider", return_value=fake
    ):
        yield fake


def test_network_measurements_come_from_the_field_mapping() -> None:
    """A network measures what its field mapping names."""
    assert FAKE_NETWORK.measurements == {Field.TEMPERATURE, Field.HUMIDITY}
    assert MANNHEIM.measurements == set(Field)


def test_provider_defaults_without_reference_data() -> None:
    """Without reference data there is no LCZ and no district."""
    provider = FakeProvider()
    assert provider.lcz(*HOME) is None
    assert provider.district(*HOME) is None


async def test_hub_stores_the_raw_station_list(
    hass: HomeAssistant, hass_storage: dict[str, Any], provider: FakeProvider
) -> None:
    """The hub stores the provider's payload as is and indexes its stations."""
    hub = await async_get_hub(hass)
    stations = await hub.async_get_stations()
    assert [station.code for station in stations] == PAYLOAD["stations"]
    assert hub.station_for_sensor(FAKE_SENSOR).code == "fake1"
    assert hass_storage[STORAGE_KEY]["data"]["payload"] == PAYLOAD
    assert hub.provider is provider


def add_entry(
    hass: HomeAssistant, sensors: list[str], **kwargs: Any
) -> MockConfigEntry:
    """Add a location of the fake network polling these sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN, options={CONF_TEMPERATURE_SENSORS: sensors}, **kwargs
    )
    entry.add_to_hass(hass)
    return entry


async def test_locations_share_one_bulk_request(
    hass: HomeAssistant, provider: FakeProvider, freezer: FrozenDateTimeFactory
) -> None:
    """One request fetches the sensors of all enabled locations for the cache."""
    add_entry(hass, [FAKE_SENSOR])
    add_entry(hass, ["fake2-t", "gone-t"])
    add_entry(hass, ["fake2-w"], disabled_by=ConfigEntryDisabler.USER)
    hub = await async_get_hub(hass)
    await hub.async_get_stations()
    assert await hub.async_get_measurements(FAKE_SENSOR)
    assert await hub.async_get_measurements("fake2-t")
    assert provider.requests == [{FAKE_SENSOR, "fake2-t"}], "known sensors in use"
    assert await hub.async_get_measurements("gone-t") == [], "missing in the response"
    assert len(provider.requests) == 1
    freezer.tick(MEASUREMENT_CACHE_TTL)
    await hub.async_get_measurements("fake2-t")
    assert len(provider.requests) == 2


async def test_bulk_request_uses_the_network_limits(
    hass: HomeAssistant, provider: FakeProvider, freezer: FrozenDateTimeFactory
) -> None:
    """A rate-limited bulk request defers all sensors without a second request."""
    fetch = AsyncMock(side_effect=ApiRateLimitError(60))
    provider.async_get_all_measurements = fetch
    hub = await async_get_hub(hass)
    await hub.async_get_stations()
    for sensor_id in (FAKE_SENSOR, "fake2-t"):
        with pytest.raises(RequestDeferredError) as deferred:
            await hub.async_get_measurements(sensor_id)
        assert deferred.value.wait == pytest.approx(60)
    assert fetch.await_count == 1
    fetch.side_effect = None
    fetch.return_value = {}
    freezer.tick(60)
    assert await hub.async_get_measurements(FAKE_SENSOR) == []
    assert fetch.await_count == 2


@pytest.mark.parametrize("interval", SCAN_INTERVAL_CHOICES_MIN)
async def test_bulk_network_allows_the_most_stations_at_every_interval(
    hass: HomeAssistant,
    provider: FakeProvider,  # noqa: ARG001
    interval: int,
) -> None:
    """The station count costs no requests: one per refresh and location."""
    hub = await async_get_hub(hass)
    selection = StationSelection(
        hass,
        hub,
        await hub.async_get_stations(),
        (*HOME, 3000.0, Environment.OPEN_BUILT),
        min_interval=interval,
    )
    assert selection.max_stations("fake1-w", interval) == MAX_SELECTED_STATIONS
    assert selection.fitting_interval(MAX_SELECTED_STATIONS, "fake1-w") == interval
    assert selection.planned_requests(MAX_SELECTED_STATIONS, "fake1-w", interval) == (
        60 // interval
    )


async def test_selection_uses_the_network_budget_cost_and_tiles(
    hass: HomeAssistant, provider: FakeProvider
) -> None:
    """Budget, cost per refresh and map tiles come from the provider."""
    hub = await async_get_hub(hass)
    selection = StationSelection(
        hass,
        hub,
        await hub.async_get_stations(),
        (*HOME, 3000.0, Environment.OPEN_BUILT),
    )
    assert selection.planned_requests(2, NO_WIND_SENSOR, 15) == 4, "one per refresh"
    placeholders = await selection.async_placeholders(["fake1-t"], NO_WIND_SENSOR)
    assert placeholders["budget"] == "48"
    assert placeholders["api_limit"] == "60"
    payload = await selection.async_map_payload(["fake1-t"], NO_WIND_SENSOR)
    assert payload["budget"]["per_hour"] == 48
    assert payload["budget"]["requests"] == [0, 1, 1, 1, 1, 1, 1, 1]
    assert payload["tiles"] == {
        "url": provider.network.tiles.url,
        "attribution": "Fake",
    }


async def test_flow_without_reference_data_uses_defaults(
    hass: HomeAssistant,
    provider: FakeProvider,  # noqa: ARG001
) -> None:
    """Without LCZ map and districts: default surroundings, network area as title."""
    with patch("custom_components.urban_weather.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await configure(hass, result, location(*HOME))
        assert result["data_schema"]({})[CONF_ENVIRONMENT] == Environment.OPEN_BUILT
        result = await configure(
            hass, result, {CONF_ENVIRONMENT: Environment.OPEN_BUILT}
        )
        result = await configure(hass, result, {"next_step_id": "accept"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Fakeville"


async def test_entities_name_the_network(
    hass: HomeAssistant,
    provider: FakeProvider,  # noqa: ARG001
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Attribution and device info come from the network of the location."""
    entry = add_home_entry(hass, **{CONF_TEMPERATURE_SENSORS: [FAKE_SENSOR]})
    assert await hass.config_entries.async_setup(entry.entry_id)
    temperature = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_temperature"
    )
    state = hass.states.get(temperature)
    assert state.state == "21.0"
    assert state.attributes[ATTR_ATTRIBUTION] == "Fake data (CC0)"
    device = device_registry.async_get(entity_registry.async_get(temperature).device_id)
    assert (device.manufacturer, device.model) == ("Fake operator", "Fake network")


async def test_errors_name_the_host_of_the_network(
    hass: HomeAssistant, provider: FakeProvider
) -> None:
    """Without a station list, flow and setup name the host of the network."""
    provider.async_get_station_payload = AsyncMock(
        side_effect=ApiConnectionError("down")
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["description_placeholders"] == {"host": "fake.example"}
    entry = add_home_entry(hass, **{CONF_TEMPERATURE_SENSORS: [FAKE_SENSOR]})
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.reason == "The station list could not be loaded from fake.example"
