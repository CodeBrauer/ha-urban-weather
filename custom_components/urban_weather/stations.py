"""Stations of a network and the station recommendation for a location."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from .const import (
    LCZ_ENVIRONMENT,
    MAX_COVERAGE_DISTANCE_M,
    RECOMMENDED_STATIONS,
    SINGLE_STATION_MAX_DISTANCE_M,
    Environment,
    Field,
    MountZone,
)
from .geo import distance_m

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from .provider import ApiSensor


class LczSource(StrEnum):
    """Where a station's Local Climate Zone comes from."""

    CATALOG = "catalog"
    MAP = "map"


class RecommendationReason(StrEnum):
    """Why a set of stations was recommended."""

    NEAREST_FITS = "nearest_fits"
    NEAREST_CLOSE = "nearest_close"
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


def pick_sensor(sensors: Iterable[ApiSensor], field: Field) -> ApiSensor | None:
    """
    Return the sensor of a station that provides a field.

    More parameters = newer hardware generation (e.g. with pressure); on a tie the
    first sensor wins.
    """
    candidates = [sensor for sensor in sensors if field in sensor.parameters]
    return max(candidates, key=lambda s: len(s.parameters), default=None)


def nearest(
    stations: Iterable[Station], latitude: float, longitude: float
) -> list[Station]:
    """Return stations sorted by distance to a coordinate."""
    return sorted(
        stations, key=lambda station: station.distance_to(latitude, longitude)
    )


def networks_in_range(
    stations_by_network: Mapping[str, Iterable[Station]],
    latitude: float,
    longitude: float,
) -> list[tuple[str, float]]:
    """
    Return the networks with a temperature station in range, nearest first.

    Each network comes with the distance to its nearest temperature station.
    """
    in_range = []
    for network_id, stations in stations_by_network.items():
        distance = min(
            (
                station.distance_to(latitude, longitude)
                for station in stations
                if station.temperature_sensor
            ),
            default=None,
        )
        if distance is not None and distance <= MAX_COVERAGE_DISTANCE_M:
            in_range.append((network_id, distance))
    return sorted(in_range, key=lambda network: network[1])


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
    if closest_distance <= SINGLE_STATION_MAX_DISTANCE_M:
        if closest.environment == environment:
            return Recommendation(
                [closest], wind_station, RecommendationReason.NEAREST_FITS, closest
            )
        # Without surroundings for any station of the network, distance decides.
        if not any(station.environment for station in candidates):
            return Recommendation(
                [closest], wind_station, RecommendationReason.NEAREST_CLOSE, closest
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
