"""Group API sensors into stations and recommend stations for a location."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from .const import (
    LCZ_ENVIRONMENT,
    RECOMMENDED_STATIONS,
    SINGLE_STATION_MAX_DISTANCE_M,
    STATION_CLUSTER_RADIUS_M,
    Environment,
    Field,
    MountZone,
)
from .geo import cluster_points, distance_m

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .api import ApiSensor
    from .reference import ReferenceData

STATION_CODE_LENGTH = 8  # "0101-046" out of "0101-046-21"
CATALOG_CODE_LENGTH = 11


class LczSource(StrEnum):
    """Where a station's Local Climate Zone comes from."""

    CATALOG = "catalog"
    MAP = "map"


class RecommendationReason(StrEnum):
    """Why a set of stations was recommended."""

    NEAREST_FITS = "nearest_fits"
    NEAREST_TOO_FAR = "nearest_too_far"
    NEAREST_OTHER_ENVIRONMENT = "nearest_other_environment"


@dataclass(frozen=True, slots=True)
class Station:
    """Co-located sensors with their siting metadata."""

    code: str
    latitude: float
    longitude: float
    temperature_sensor: ApiSensor | None
    wind_sensor: ApiSensor | None
    district: str | None
    lcz: int | None
    lcz_source: LczSource | None
    zone: MountZone | None
    height_above_ground: int | None
    temperature_height: int | None

    @property
    def environment(self) -> Environment | None:
        """Surroundings derived from the station's LCZ."""
        return LCZ_ENVIRONMENT.get(self.lcz) if self.lcz else None

    @property
    def is_elevated(self) -> bool:
        """Return True for roof or high-point stations (not street level)."""
        return self.zone in (MountZone.ROOF, MountZone.HIGH_POINT) or bool(
            self.height_above_ground
        )

    @property
    def label(self) -> str:
        """Human-readable station name."""
        return f"{self.district} ({self.code})" if self.district else self.code

    def distance_to(self, latitude: float, longitude: float) -> float:
        """Return the distance to a coordinate in metres."""
        return distance_m(latitude, longitude, self.latitude, self.longitude)


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


def nearest(
    stations: Iterable[Station], latitude: float, longitude: float
) -> list[Station]:
    """Return stations sorted by distance to a coordinate."""
    return sorted(
        stations, key=lambda station: station.distance_to(latitude, longitude)
    )


@dataclass(frozen=True, slots=True)
class Recommendation:
    """Recommended temperature stations and wind station for a location."""

    stations: list[Station]
    wind_station: Station | None
    reason: RecommendationReason
    nearest: Station


def recommend(
    stations: Iterable[Station],
    latitude: float,
    longitude: float,
    environment: Environment,
    radius_m: float,
) -> Recommendation | None:
    """
    Pick the nearest station if it represents the location, else several to average.

    The nearest street-level station is used alone when it is close enough and has
    the same surroundings. Otherwise up to RECOMMENDED_STATIONS stations within the
    radius are averaged, same surroundings first, filled up with the closest others.
    """
    by_distance = nearest(stations, latitude, longitude)
    candidates = [
        station
        for station in by_distance
        if station.temperature_sensor and not station.is_elevated
    ]
    if not candidates:
        return None
    wind_station = next((s for s in by_distance if s.wind_sensor), None)
    closest = candidates[0]
    closest_distance = closest.distance_to(latitude, longitude)
    if closest.environment == environment and (
        closest_distance <= SINGLE_STATION_MAX_DISTANCE_M
    ):
        return Recommendation(
            [closest], wind_station, RecommendationReason.NEAREST_FITS, closest
        )

    within = [
        station
        for station in candidates
        if station.distance_to(latitude, longitude) <= radius_m
    ] or candidates[:RECOMMENDED_STATIONS]
    same = [station for station in within if station.environment == environment]
    others = [station for station in within if station.environment != environment]
    picked = (same + others)[:RECOMMENDED_STATIONS]
    reason = (
        RecommendationReason.NEAREST_TOO_FAR
        if closest_distance > SINGLE_STATION_MAX_DISTANCE_M
        else RecommendationReason.NEAREST_OTHER_ENVIRONMENT
    )
    return Recommendation(picked, wind_station, reason, closest)
