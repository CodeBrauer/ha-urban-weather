"""Diagnostics for the Urban Weather integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import MannheimClimateConfigEntry

TO_REDACT = {CONF_LATITUDE, CONF_LONGITUDE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001
    entry: MannheimClimateConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics without the configured coordinates."""
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": dict(entry.options),
        },
        "stations": [
            {
                "code": station.code,
                "district": station.district,
                "distance_m": round(coordinator.distance_to(station)),
                "lcz": station.lcz,
                "lcz_source": station.lcz_source,
                "zone": station.zone,
                "height_above_ground": station.height_above_ground,
                "temperature_sensor": station.temperature_sensor.name,
                "parameters": sorted(station.temperature_sensor.parameters),
            }
            for station in coordinator.stations
        ],
        "wind_station": coordinator.wind_station.code
        if coordinator.wind_station
        else None,
        "estimate": {
            key: value
            for key, value in asdict(data).items()
            if key not in ("used", "dropped")
        }
        if data
        else None,
        "readings": [
            {
                "code": reading.code,
                "timestamp": reading.measurement.timestamp,
                "values": dict(reading.measurement.values),
            }
            for reading in (data.used + data.dropped if data else [])
        ],
        "hub": coordinator.hub.diagnostics(),
    }
