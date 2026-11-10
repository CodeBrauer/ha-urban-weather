"""Combine the latest readings of several stations into one estimate."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from .const import (
    OUTLIER_MAX_DEVIATION_K,
    OUTLIER_MIN_STATIONS,
    Field,
)

if TYPE_CHECKING:
    from datetime import datetime, timedelta

    from .api import Measurement

# Magnus formula coefficients over water (Sonntag 1990), as in the original gist.
MAGNUS_A = 17.62
MAGNUS_B = 243.12
MAGNUS_E0_HPA = 6.112
WATER_VAPOUR_GAS_CONSTANT = 216.7  # g K / m³ / hPa for absolute humidity
KELVIN_OFFSET = 273.15
MAX_HUMIDITY = 100.0

PLAUSIBLE_RANGES: dict[Field, tuple[float, float]] = {
    Field.TEMPERATURE: (-30.0, 45.0),
    Field.MIN_TEMPERATURE: (-30.0, 45.0),
    Field.MAX_TEMPERATURE: (-30.0, 45.0),
    Field.HUMIDITY: (1.0, 100.0),
    Field.PRESSURE: (850.0, 1100.0),
    Field.IRRADIANCE: (0.0, 1500.0),
    Field.WIND_SPEED: (0.0, 60.0),
    Field.WIND_GUST: (0.0, 80.0),
    Field.WIND_GUST_1S: (0.0, 80.0),
    Field.WIND_DIRECTION: (0.0, 360.0),
    Field.WIND_GUST_DIRECTION: (0.0, 360.0),
}


def dew_point(temperature: float, humidity: float) -> float:
    """Dew point in °C from air temperature (°C) and relative humidity (%)."""
    gamma = math.log(humidity / 100) + MAGNUS_A * temperature / (MAGNUS_B + temperature)
    return MAGNUS_B * gamma / (MAGNUS_A - gamma)


def relative_humidity(temperature: float, dew_point_value: float) -> float:
    """Relative humidity in % from air temperature and dew point (°C)."""
    return 100 * math.exp(
        MAGNUS_A * dew_point_value / (MAGNUS_B + dew_point_value)
        - MAGNUS_A * temperature / (MAGNUS_B + temperature)
    )


def vapour_pressure(temperature: float, humidity: float) -> float:
    """Water vapour pressure in hPa."""
    saturation = MAGNUS_E0_HPA * math.exp(
        MAGNUS_A * temperature / (MAGNUS_B + temperature)
    )
    return humidity / 100 * saturation


def absolute_humidity(temperature: float, humidity: float) -> float:
    """Absolute humidity in g/m³."""
    return (
        WATER_VAPOUR_GAS_CONSTANT
        * vapour_pressure(temperature, humidity)
        / (KELVIN_OFFSET + temperature)
    )


def apparent_temperature(temperature: float, humidity: float, wind: float) -> float:
    """Apparent temperature (Steadman 1994, as used by the Australian BoM) in °C."""
    return (
        temperature + 0.33 * vapour_pressure(temperature, humidity) - 0.70 * wind - 4.00
    )


def latest_valid(
    measurements: list[Measurement], now: datetime, max_age: timedelta
) -> Measurement | None:
    """Return the newest measurement within max_age with only plausible values."""
    for measurement in measurements:
        if now - measurement.timestamp > max_age:
            return None
        values = {
            key: value
            for key, value in measurement.values.items()
            if _is_plausible(key, value)
        }
        if values:
            return replace(measurement, values=values)
    return None


def _is_plausible(key: str, value: float) -> bool:
    if key not in PLAUSIBLE_RANGES:
        return True
    low, high = PLAUSIBLE_RANGES[key]
    return low <= value <= high


@dataclass(frozen=True, slots=True)
class StationReading:
    """Latest valid values of one temperature station."""

    code: str
    distance_m: float
    measurement: Measurement

    def get(self, key: Field) -> float | None:
        """Return a value of this reading."""
        return self.measurement.values.get(key)


@dataclass(slots=True)
class Estimate:
    """Combined values for the configured location."""

    temperature: float | None = None
    min_temperature: float | None = None
    max_temperature: float | None = None
    humidity: float | None = None
    dew_point: float | None = None
    humidity_uncorrected: float | None = None
    absolute_humidity: float | None = None
    apparent_temperature: float | None = None
    pressure: float | None = None
    irradiance: float | None = None
    irradiance_stations: int = 0
    wind_speed: float | None = None
    wind_gust: float | None = None
    wind_direction: float | None = None
    wind_gust_direction: float | None = None
    spread: float | None = None
    last_measurement: datetime | None = None
    used: list[StationReading] = field(default_factory=list)
    dropped: list[StationReading] = field(default_factory=list)


def _drop_outliers(
    readings: list[StationReading],
) -> tuple[list[StationReading], list[StationReading]]:
    if len(readings) < OUTLIER_MIN_STATIONS:
        return readings, []
    median = statistics.median(r.get(Field.TEMPERATURE) for r in readings)
    kept = [
        r
        for r in readings
        if abs(r.get(Field.TEMPERATURE) - median) <= OUTLIER_MAX_DEVIATION_K
    ]
    return kept, [r for r in readings if r not in kept]


def _median(readings: list[StationReading], key: Field) -> float | None:
    values = [value for r in readings if (value := r.get(key)) is not None]
    return statistics.median(values) if values else None


def estimate(
    readings: list[StationReading],
    wind: Measurement | None,
    dew_point_offset: float,
) -> Estimate:
    """
    Combine station readings.

    Temperature is the median of all stations. Humidity is derived from the median
    dew point (optionally corrected) because averaging relative humidity across
    stations with different temperatures is physically wrong. Irradiance uses the
    maximum because street-level sensors are often shaded.
    """
    result = Estimate()
    with_temperature = [r for r in readings if r.get(Field.TEMPERATURE) is not None]
    used, result.dropped = _drop_outliers(with_temperature)
    result.used = sorted(used, key=lambda r: r.distance_m)

    if used:
        temperatures = [r.get(Field.TEMPERATURE) for r in used]
        result.temperature = statistics.median(temperatures)
        result.spread = max(temperatures) - min(temperatures)
        result.min_temperature = _median(used, Field.MIN_TEMPERATURE)
        result.max_temperature = _median(used, Field.MAX_TEMPERATURE)
        result.last_measurement = max(r.measurement.timestamp for r in used)
        dew_points = [
            dew_point(r.get(Field.TEMPERATURE), humidity)
            for r in used
            if (humidity := r.get(Field.HUMIDITY)) is not None
        ]
        if dew_points:
            raw_dew_point = statistics.median(dew_points)
            corrected = min(raw_dew_point + dew_point_offset, result.temperature)
            result.dew_point = corrected
            result.humidity = min(
                relative_humidity(result.temperature, corrected), MAX_HUMIDITY
            )
            result.humidity_uncorrected = min(
                relative_humidity(result.temperature, raw_dew_point), MAX_HUMIDITY
            )
            result.absolute_humidity = absolute_humidity(
                result.temperature, result.humidity
            )
        result.pressure = _median(used, Field.PRESSURE)
        irradiances = [v for r in used if (v := r.get(Field.IRRADIANCE)) is not None]
        result.irradiance = max(irradiances) if irradiances else None
        result.irradiance_stations = len(irradiances)

    if wind:
        result.wind_speed = wind.values.get(Field.WIND_SPEED)
        result.wind_gust = wind.values.get(
            Field.WIND_GUST, wind.values.get(Field.WIND_GUST_1S)
        )
        result.wind_direction = wind.values.get(Field.WIND_DIRECTION)
        result.wind_gust_direction = wind.values.get(Field.WIND_GUST_DIRECTION)

    if (
        result.temperature is not None
        and result.humidity is not None
        and result.wind_speed is not None
    ):
        result.apparent_temperature = apparent_temperature(
            result.temperature, result.humidity, result.wind_speed
        )
    return result
