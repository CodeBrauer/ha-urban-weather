"""Weather entity with the current combined values (no forecast)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from astral import Observer
from astral.sun import elevation
from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_SUNNY,
    WeatherEntity,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.util import dt as dt_util

from .entity import MannheimClimateEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import ClimateCoordinator, MannheimClimateConfigEntry

PARALLEL_UPDATES = 0

# Clear-sky global irradiance after Haurwitz (1945), z = solar zenith angle.
HAURWITZ_SCALE_W_M2 = 1098
HAURWITZ_EXTINCTION = 0.057
# Below this sun elevation the clear-sky index is too noisy (low sun, buildings).
MIN_SUN_ELEVATION_DEG = 10
# Calibrated against DWD Mannheim sunshine duration (10 days in 2026, 10-min values)
# using the maximum of 4 street-level stations; single stations are often shaded.
SUNNY_MIN_CLEAR_SKY_INDEX = 0.55
PARTLY_CLOUDY_MIN_CLEAR_SKY_INDEX = 0.25
MIN_IRRADIANCE_STATIONS = 3


def clear_sky_irradiance(sun_elevation_deg: float) -> float:
    """Return the modelled clear-sky global irradiance in W/m²."""
    cos_zenith = math.sin(math.radians(sun_elevation_deg))
    if cos_zenith <= 0:
        return 0.0
    return (
        HAURWITZ_SCALE_W_M2 * cos_zenith * math.exp(-HAURWITZ_EXTINCTION / cos_zenith)
    )


def condition_from_irradiance(
    irradiance: float | None, stations: int, sun_elevation_deg: float
) -> str | None:
    """
    Estimate cloudiness from measured vs. clear-sky irradiance (daytime only).

    The network has no cloud or precipitation sensors, so at night, with fewer
    than MIN_IRRADIANCE_STATIONS stations or without irradiance the condition
    stays unknown.
    """
    if (
        irradiance is None
        or stations < MIN_IRRADIANCE_STATIONS
        or sun_elevation_deg < MIN_SUN_ELEVATION_DEG
    ):
        return None
    clear_sky_index = irradiance / clear_sky_irradiance(sun_elevation_deg)
    if clear_sky_index >= SUNNY_MIN_CLEAR_SKY_INDEX:
        return ATTR_CONDITION_SUNNY
    if clear_sky_index >= PARTLY_CLOUDY_MIN_CLEAR_SKY_INDEX:
        return ATTR_CONDITION_PARTLYCLOUDY
    return ATTR_CONDITION_CLOUDY


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: MannheimClimateConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the weather entity."""
    async_add_entities([ClimateWeather(entry.runtime_data)])


class ClimateWeather(MannheimClimateEntity, WeatherEntity):
    """Current conditions of the configured location."""

    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND

    def __init__(self, coordinator: ClimateCoordinator) -> None:
        """Set up the weather entity."""
        super().__init__(coordinator, "weather")
        data = coordinator.config_entry.data
        self._observer = Observer(data[CONF_LATITUDE], data[CONF_LONGITUDE])

    @property
    def condition(self) -> str | None:
        """Return the estimated cloudiness during the day."""
        sun = elevation(self._observer, dt_util.utcnow())
        data = self.coordinator.data
        return condition_from_irradiance(data.irradiance, data.irradiance_stations, sun)

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return self.coordinator.data.temperature

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the apparent temperature."""
        return self.coordinator.data.apparent_temperature

    @property
    def native_dew_point(self) -> float | None:
        """Return the dew point."""
        return self.coordinator.data.dew_point

    @property
    def humidity(self) -> float | None:
        """Return the relative humidity."""
        return self.coordinator.data.humidity

    @property
    def native_pressure(self) -> float | None:
        """Return the air pressure."""
        return self.coordinator.data.pressure

    @property
    def native_wind_speed(self) -> float | None:
        """Return the mean wind speed."""
        return self.coordinator.data.wind_speed

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Return the wind gust speed."""
        return self.coordinator.data.wind_gust

    @property
    def wind_bearing(self) -> float | None:
        """Return the wind direction."""
        return self.coordinator.data.wind_direction
