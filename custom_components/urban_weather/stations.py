"""Stations of a network and the station recommendation for a location."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from .const import (
    LCZ_ENVIRONMENT,
    RECOMMENDED_STATIONS,
    SINGLE_STATION_MAX_DISTANCE_M,
    Environment,
    MountZone,
)
from .geo import distance_m

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .provider import ApiSensor


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
