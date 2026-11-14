"""The Urban Weather integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir

from .const import CONF_TEMPERATURE_SENSORS, CONF_WIND_SENSOR, DOMAIN
from .coordinator import ClimateCoordinator, MannheimClimateConfigEntry
from .hub import StationListUnavailableError, async_get_hub

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.WEATHER]


async def async_setup_entry(
    hass: HomeAssistant, entry: MannheimClimateConfigEntry
) -> bool:
    """Set up a location from a config entry."""
    hub = await async_get_hub(hass)
    try:
        await hub.async_get_stations()
    except StationListUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="station_list_unavailable",
            translation_placeholders={"host": hub.provider.network.host},
        ) from err

    stations = [
        station
        for sensor_id in entry.options.get(CONF_TEMPERATURE_SENSORS, [])
        if (station := hub.station_for_sensor(sensor_id)) and station.temperature_sensor
    ]
    if not stations:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="no_stations_available"
        )
    wind_sensor_id = entry.options.get(CONF_WIND_SENSOR)
    wind_station = hub.station_for_sensor(wind_sensor_id) if wind_sensor_id else None

    coordinator = ClimateCoordinator(hass, entry, hub, stations, wind_station)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MannheimClimateConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant, entry: MannheimClimateConfigEntry
) -> None:
    """Remove the repair issues of a deleted config entry."""
    registry = ir.async_get(hass)
    for domain, issue in list(registry.issues):
        if domain == DOMAIN and entry.entry_id in issue:
            ir.async_delete_issue(hass, DOMAIN, issue)
