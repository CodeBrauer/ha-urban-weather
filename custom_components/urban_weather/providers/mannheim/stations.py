"""Group the sensors of the Mannheim API into stations with siting metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.urban_weather.const import Field
from custom_components.urban_weather.geo import cluster_points
from custom_components.urban_weather.stations import LczSource, Station

if TYPE_CHECKING:
    from collections.abc import Iterable

    from custom_components.urban_weather.provider import ApiSensor

    from .reference import ReferenceData

STATION_CLUSTER_RADIUS_M = 15
STATION_CODE_LENGTH = 8  # "0101-046" out of "0101-046-21"
CATALOG_CODE_LENGTH = 11


def _station_code(sensors: list[ApiSensor]) -> str:
    for sensor in sensors:
        if len(sensor.name) == CATALOG_CODE_LENGTH and sensor.name[4] == "-":
            return sensor.name[:STATION_CODE_LENGTH]
    primary = next((s for s in sensors if Field.TEMPERATURE in s.parameters), None)
    return (primary or sensors[0]).name


def _pick(sensors: list[ApiSensor], field: Field) -> ApiSensor | None:
    # More parameters = newer hardware generation (e.g. with pressure).
    candidates = [sensor for sensor in sensors if field in sensor.parameters]
    return max(candidates, key=lambda s: len(s.parameters), default=None)


def build_stations(
    sensors: Iterable[ApiSensor], reference: ReferenceData
) -> list[Station]:
    """Group sensors at the same spot and attach catalogue/LCZ/district data."""
    sensor_list = list(sensors)
    clusters = cluster_points(
        [(sensor.latitude, sensor.longitude) for sensor in sensor_list],
        STATION_CLUSTER_RADIUS_M,
    )
    stations = []
    for cluster in clusters:
        members = [sensor_list[index] for index in cluster]
        temperature = _pick(members, Field.TEMPERATURE)
        wind = _pick(members, Field.WIND_SPEED)
        if temperature is None and wind is None:
            continue
        anchor = temperature or wind
        names = [sensor.name for sensor in members if sensor is temperature] + [
            sensor.name for sensor in members if sensor is not temperature
        ]
        entry = reference.catalog_entry(names, anchor.latitude, anchor.longitude)
        if entry and entry.lcz:
            lcz, lcz_source = entry.lcz, LczSource.CATALOG
        else:
            lcz = reference.lcz(anchor.latitude, anchor.longitude)
            lcz_source = LczSource.MAP if lcz else None
        stations.append(
            Station(
                code=_station_code(members),
                latitude=anchor.latitude,
                longitude=anchor.longitude,
                temperature_sensor=temperature,
                wind_sensor=wind,
                district=reference.district(anchor.latitude, anchor.longitude),
                lcz=lcz,
                lcz_source=lcz_source,
                zone=entry.zone if entry else None,
                height_above_ground=entry.height_above_ground if entry else None,
                temperature_height=entry.temperature_height if entry else None,
            )
        )
    return stations
