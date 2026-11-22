"""Tests for the provider interface, with a fake network next to Mannheim."""

from __future__ import annotations

import asyncio
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
    CONF_NETWORK,
    CONF_TEMPERATURE_SENSORS,
    DOMAIN,
    MAX_SELECTED_STATIONS,
    MEASUREMENT_CACHE_TTL,
    NO_WIND_SENSOR,
    SCAN_INTERVAL_CHOICES_MIN,
    Environment,
    Field,
)
from custom_components.urban_weather.hub import (
    RequestDeferredError,
    UnknownNetworkError,
    async_get_hub,
)
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
from custom_components.urban_weather.providers import PROVIDERS
from custom_components.urban_weather.providers.mannheim import MANNHEIM
from custom_components.urban_weather.selection import StationSelection

from .common import (
    CATALOG_SENSOR,
    HOME,
    HOME_DATA,
    MEASUREMENT_AGE,
    NEAREST_SENSOR,
    add_home_entry,
    add_location,
    configure,
    location,
    make_station,
    respond,
)

if TYPE_CHECKING:
    from collections.abc import Collection, Generator
    from unittest.mock import MagicMock

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    from custom_components.urban_weather.stations import Station

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

FAKE_NETWORK = Network(
    id="fake",
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
CREATE_MANNHEIM = PROVIDERS[MANNHEIM.id]
FAKE_SENSOR = "fake1-t"


class FakeProvider(BulkProvider):
    """Stations north of HOME without siting data; all sensors in one request."""

    def __init__(self, distance_m: float = 400) -> None:
        """Place the nearest station distance_m from HOME; record the requests."""
        super().__init__(FAKE_NETWORK)
        self.distance_m = distance_m
        self.requests: list[set[str]] = []

    async def async_get_station_payload(self) -> dict[str, Any]:
        """Return a payload only this provider understands."""
        return PAYLOAD

    def build_stations(self, payload: dict[str, Any]) -> list[Station]:
        """Return one station per payload entry, without LCZ and mount zone."""
        return [
            make_station(
                code,
                self.distance_m + index * 200,
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
    """Make the fake network the only one."""
    fake = FakeProvider()
    with patch.dict(
        PROVIDERS, {FAKE_NETWORK.id: AsyncMock(return_value=fake)}, clear=True
    ):
        yield fake


@pytest.fixture
def two_networks(
    api: MagicMock,  # noqa: ARG001
    provider: FakeProvider,
) -> Generator[FakeProvider]:
    """Offer the fake network next to Mannheim (API client per `api`)."""
    with patch.dict(PROVIDERS, {MANNHEIM.id: CREATE_MANNHEIM}):
        yield provider


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
    hub = await async_get_hub(hass, FAKE_NETWORK.id)
    stations = await hub.async_get_stations()
    assert [station.code for station in stations] == PAYLOAD["stations"]
    assert hub.station_for_sensor(FAKE_SENSOR).code == "fake1"
    assert hass_storage["urban_weather.fake.stations"]["data"]["payload"] == PAYLOAD
    assert hub.provider is provider


def add_entry(
    hass: HomeAssistant,
    sensors: list[str],
    network: str = FAKE_NETWORK.id,
    **kwargs: Any,
) -> MockConfigEntry:
    """Add a location of a network (default: fake) polling these sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NETWORK: network},
        options={CONF_TEMPERATURE_SENSORS: sensors},
        **kwargs,
    )
    entry.add_to_hass(hass)
    return entry


async def test_locations_share_one_bulk_request(
    hass: HomeAssistant, provider: FakeProvider, freezer: FrozenDateTimeFactory
) -> None:
    """One request fetches the sensors of the network's enabled locations."""
    add_entry(hass, [FAKE_SENSOR])
    add_entry(hass, ["fake2-t", "gone-t"])
    add_entry(hass, ["fake2-w"], disabled_by=ConfigEntryDisabler.USER)
    add_entry(hass, ["fake1-w"], network=MANNHEIM.id)
    hub = await async_get_hub(hass, FAKE_NETWORK.id)
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
    hub = await async_get_hub(hass, FAKE_NETWORK.id)
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
    hub = await async_get_hub(hass, FAKE_NETWORK.id)
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
    hub = await async_get_hub(hass, FAKE_NETWORK.id)
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
    entry = add_home_entry(
        hass, network=FAKE_NETWORK.id, **{CONF_TEMPERATURE_SENSORS: [FAKE_SENSOR]}
    )
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
    entry = add_home_entry(
        hass, network=FAKE_NETWORK.id, **{CONF_TEMPERATURE_SENSORS: [FAKE_SENSOR]}
    )
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.reason == "The station list could not be loaded from fake.example"


# Several networks


async def test_flow_suggests_the_network_with_the_nearest_station(
    hass: HomeAssistant,
    two_networks: FakeProvider,  # noqa: ARG001
) -> None:
    """Both networks are in range: the nearest is pre-selected, both can be chosen."""
    with patch("custom_components.urban_weather.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await configure(hass, result, location(*HOME))
        assert result["step_id"] == "network"
        schema = result["data_schema"]
        assert schema({})[CONF_NETWORK] == FAKE_NETWORK.id, "fake station at 400 m"
        labels = [
            option["label"] for option in schema.schema[CONF_NETWORK].config["options"]
        ]
        assert labels == ["Fake network · 400 m", "Klimamessnetz Mannheim · 444 m"]

        result = await configure(hass, result, {CONF_NETWORK: MANNHEIM.id})
        result = await configure(
            hass, result, {CONF_ENVIRONMENT: Environment.OPEN_BUILT}
        )
        result = await configure(hass, result, {"next_step_id": "accept"})
    assert result["data"][CONF_NETWORK] == MANNHEIM.id
    assert result["options"][CONF_TEMPERATURE_SENSORS] == [NEAREST_SENSOR]


@pytest.mark.parametrize("unavailable", [False, True], ids=["far", "unavailable"])
async def test_flow_skips_the_choice_with_one_network_in_range(
    hass: HomeAssistant, two_networks: FakeProvider, *, unavailable: bool
) -> None:
    """A network out of range or without station list is not offered."""
    two_networks.distance_m = 20_000
    if unavailable:
        two_networks.distance_m = 400
        two_networks.async_get_station_payload = AsyncMock(
            side_effect=ApiConnectionError("down")
        )
    with patch("custom_components.urban_weather.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await configure(hass, result, location(*HOME))
        assert result["step_id"] == "environment"
        result = await configure(
            hass, result, {CONF_ENVIRONMENT: Environment.OPEN_BUILT}
        )
        result = await configure(hass, result, {"next_step_id": "accept"})
    assert result["data"][CONF_NETWORK] == MANNHEIM.id


async def test_two_locations_in_different_networks(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    api: MagicMock,
    two_networks: FakeProvider,
    entity_registry: er.EntityRegistry,
) -> None:
    """Each location uses the hub, station list and attribution of its network."""
    api.async_get_measurements.side_effect = respond(
        {CATALOG_SENSOR: {Field.TEMPERATURE: 12.3}}
    )
    mannheim = add_home_entry(hass)
    fake = MockConfigEntry(
        domain=DOMAIN,
        data={**HOME_DATA, CONF_NETWORK: FAKE_NETWORK.id},
        options={CONF_TEMPERATURE_SENSORS: [FAKE_SENSOR]},
    )
    fake.add_to_hass(hass)
    # Setting up the integration sets up all its locations.
    assert await hass.config_entries.async_setup(mannheim.entry_id)
    await hass.async_block_till_done()
    assert fake.state is ConfigEntryState.LOADED

    assert mannheim.runtime_data.hub is await async_get_hub(hass, MANNHEIM.id)
    assert fake.runtime_data.hub is await async_get_hub(hass, FAKE_NETWORK.id)
    assert mannheim.runtime_data.hub is not fake.runtime_data.hub
    assert {"urban_weather.mannheim.stations", "urban_weather.fake.stations"} <= set(
        hass_storage
    )
    assert two_networks.requests == [{FAKE_SENSOR}]
    attributions = {
        entry.entry_id: hass.states.get(
            entity_registry.async_get_entity_id(
                "sensor", DOMAIN, f"{entry.entry_id}_temperature"
            )
        ).attributes[ATTR_ATTRIBUTION]
        for entry in (mannheim, fake)
    }
    assert attributions == {
        mannheim.entry_id: MANNHEIM.attribution,
        fake.entry_id: FAKE_NETWORK.attribution,
    }


async def test_budget_counts_only_locations_of_the_network(
    hass: HomeAssistant,
    two_networks: FakeProvider,  # noqa: ARG001
) -> None:
    """Each network has its own budget, used by its own locations only."""
    add_location(hass, 2, 10)
    add_location(hass, 6, 15, network=FAKE_NETWORK.id)
    location_tuple = (*HOME, 3000.0, Environment.OPEN_BUILT)
    selections = {}
    for network_id in (MANNHEIM.id, FAKE_NETWORK.id):
        hub = await async_get_hub(hass, network_id)
        selections[network_id] = StationSelection(
            hass, hub, await hub.async_get_stations(), location_tuple
        )
    assert selections[MANNHEIM.id].others == 18, "3 sensors every 10 min"
    assert selections[FAKE_NETWORK.id].others == 4, "1 bulk request every 15 min"


async def test_hub_is_created_once_per_network(
    hass: HomeAssistant,
    provider: FakeProvider,  # noqa: ARG001
) -> None:
    """Concurrent first calls share one hub; an unknown network has none."""
    first, second = await asyncio.gather(
        async_get_hub(hass, FAKE_NETWORK.id), async_get_hub(hass, FAKE_NETWORK.id)
    )
    assert first is second
    PROVIDERS[FAKE_NETWORK.id].assert_awaited_once()
    with pytest.raises(UnknownNetworkError):
        await async_get_hub(hass, MANNHEIM.id)


async def test_location_of_an_unknown_network_fails(
    hass: HomeAssistant,
    provider: FakeProvider,  # noqa: ARG001
) -> None:
    """A location naming a network this version does not know is not set up."""
    entry = add_home_entry(hass, network="unknown")
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == (
        'This location uses the network "unknown", which this version of the '
        "integration does not know. Update the integration or add the location again"
    )
