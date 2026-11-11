"""Tests for the provider interface, with a fake network next to Mannheim."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util

from custom_components.urban_weather.const import (
    CONF_ENVIRONMENT,
    CONF_TEMPERATURE_SENSORS,
    DOMAIN,
    NO_WIND_SENSOR,
    STORAGE_KEY,
    Environment,
    Field,
)
from custom_components.urban_weather.hub import RequestDeferredError, async_get_hub
from custom_components.urban_weather.provider import (
    Measurement,
    Network,
    Provider,
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
    from collections.abc import Generator

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


class FakeProvider(Provider):
    """Stations near HOME without siting data; one request per refresh (bulk)."""

    def __init__(self) -> None:
        """Count the measurement requests."""
        super().__init__(FAKE_NETWORK)
        self.requests = 0

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

    async def async_get_measurements(self, sensor_id: str) -> list[Measurement]:  # noqa: ARG002
        """Return one recent measurement."""
        self.requests += 1
        return [
            Measurement(
                dt_util.utcnow() - MEASUREMENT_AGE,
                {Field.TEMPERATURE: 21.0, Field.HUMIDITY: 50.0},
            )
        ]

    def requests_per_refresh(self, sensors: int) -> int:
        """Return one request for all sensors."""
        return min(sensors, 1)


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


async def test_hub_uses_the_network_limits(
    hass: HomeAssistant, provider: FakeProvider, freezer: FrozenDateTimeFactory
) -> None:
    """With one request per minute the second sensor waits a minute."""
    hub = await async_get_hub(hass)
    await hub.async_get_measurements("fake1-t")
    with pytest.raises(RequestDeferredError) as deferred:
        await hub.async_get_measurements("fake2-t")
    assert deferred.value.wait == pytest.approx(60)
    assert provider.requests == 1
    freezer.tick(60)
    await hub.async_get_measurements("fake2-t")
    assert provider.requests == 2


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
