"""Sensors for the combined values of a location."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    EntityCategory,
    UnitOfDensity,
    UnitOfIrradiance,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)

from .const import Field
from .entity import MannheimClimateEntity

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .aggregation import Estimate
    from .coordinator import ClimateCoordinator, MannheimClimateConfigEntry

PARALLEL_UPDATES = 0
UNIT_KELVIN_DIFFERENCE = "K"


@dataclass(frozen=True, kw_only=True)
class ClimateSensorDescription(SensorEntityDescription):
    """Describes a combined value."""

    value_fn: Callable[[Estimate], float | int | datetime | None]
    available_fn: Callable[[ClimateCoordinator], bool] = lambda _: True


def _provides(*fields: Field) -> Callable[[ClimateCoordinator], bool]:
    return lambda coordinator: all(coordinator.provides(field) for field in fields)


SENSORS: tuple[ClimateSensorDescription, ...] = (
    ClimateSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda e: e.temperature,
    ),
    ClimateSensorDescription(
        key="min_temperature",
        translation_key="min_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda e: e.min_temperature,
        available_fn=_provides(Field.MIN_TEMPERATURE),
    ),
    ClimateSensorDescription(
        key="max_temperature",
        translation_key="max_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda e: e.max_temperature,
        available_fn=_provides(Field.MAX_TEMPERATURE),
    ),
    ClimateSensorDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda e: e.humidity,
        available_fn=_provides(Field.HUMIDITY),
    ),
    ClimateSensorDescription(
        key="dew_point",
        translation_key="dew_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda e: e.dew_point,
        available_fn=_provides(Field.HUMIDITY),
    ),
    ClimateSensorDescription(
        key="absolute_humidity",
        device_class=SensorDeviceClass.ABSOLUTE_HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDensity.GRAMS_PER_CUBIC_METER,
        suggested_display_precision=1,
        value_fn=lambda e: e.absolute_humidity,
        available_fn=_provides(Field.HUMIDITY),
    ),
    ClimateSensorDescription(
        key="apparent_temperature",
        translation_key="apparent_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda e: e.apparent_temperature,
        available_fn=_provides(Field.HUMIDITY, Field.WIND_SPEED),
    ),
    ClimateSensorDescription(
        key="pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.HPA,
        suggested_display_precision=0,
        value_fn=lambda e: e.pressure,
        available_fn=_provides(Field.PRESSURE),
    ),
    ClimateSensorDescription(
        key="irradiance",
        translation_key="irradiance",
        device_class=SensorDeviceClass.IRRADIANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        suggested_display_precision=0,
        value_fn=lambda e: e.irradiance,
        available_fn=_provides(Field.IRRADIANCE),
    ),
    ClimateSensorDescription(
        key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=1,
        value_fn=lambda e: e.wind_speed,
        available_fn=_provides(Field.WIND_SPEED),
    ),
    ClimateSensorDescription(
        key="wind_gust",
        translation_key="wind_gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=1,
        value_fn=lambda e: e.wind_gust,
        available_fn=_provides(Field.WIND_SPEED),
    ),
    ClimateSensorDescription(
        key="wind_direction",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=0,
        value_fn=lambda e: e.wind_direction,
        available_fn=_provides(Field.WIND_DIRECTION),
    ),
    ClimateSensorDescription(
        key="wind_gust_direction",
        translation_key="wind_gust_direction",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        value_fn=lambda e: e.wind_gust_direction,
        available_fn=_provides(Field.WIND_GUST_DIRECTION),
    ),
    ClimateSensorDescription(
        key="stations_used",
        translation_key="stations_used",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda e: len(e.used),
    ),
    ClimateSensorDescription(
        key="temperature_spread",
        translation_key="temperature_spread",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        # No temperature device class: a difference must not be converted like °C/°F.
        native_unit_of_measurement=UNIT_KELVIN_DIFFERENCE,
        suggested_display_precision=1,
        value_fn=lambda e: e.spread,
    ),
    ClimateSensorDescription(
        key="last_measurement",
        translation_key="last_measurement",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda e: e.last_measurement,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: MannheimClimateConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the sensors the selected stations can provide."""
    coordinator = entry.runtime_data
    async_add_entities(
        ClimateSensor(coordinator, description)
        for description in SENSORS
        if description.available_fn(coordinator)
    )


class ClimateSensor(MannheimClimateEntity, SensorEntity):
    """A combined value of the selected stations."""

    entity_description: ClimateSensorDescription

    def __init__(
        self, coordinator: ClimateCoordinator, description: ClimateSensorDescription
    ) -> None:
        """Set up the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | datetime | None:
        """Return the combined value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """List the per-station values on the temperature sensor."""
        if self.entity_description.key != "temperature":
            return None
        data = self.coordinator.data
        return {
            "stations": {
                reading.code: {
                    "temperature": reading.get(Field.TEMPERATURE),
                    "humidity": reading.get(Field.HUMIDITY),
                    "distance_km": round(reading.distance_m / 1000, 2),
                    "timestamp": reading.measurement.timestamp.isoformat(),
                }
                for reading in data.used
            },
            "dropped_outliers": [reading.code for reading in data.dropped],
            "humidity_uncorrected": data.humidity_uncorrected,
        }
