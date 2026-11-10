"""Geodesic helpers without Home Assistant imports (shared with the build script)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

EARTH_RADIUS_M = 6_371_000
TILE_SIZE_PX = 256
FULL_CIRCLE_DEG = 360
DIRECTION_ARROWS = ("↑", "↗", "→", "↘", "↓", "↙", "←", "↖")


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance between two points in metres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the initial bearing from point 1 to point 2 (0 = north, clockwise)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)
    x = math.sin(d_lambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(
        d_lambda
    )
    return math.degrees(math.atan2(x, y)) % FULL_CIRCLE_DEG


def direction_arrow(bearing: float) -> str:
    """Return a language-neutral arrow for a bearing."""
    sector = FULL_CIRCLE_DEG / len(DIRECTION_ARROWS)
    index = round(bearing / sector) % len(DIRECTION_ARROWS)
    return DIRECTION_ARROWS[index]


def to_pixel(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    """Project a coordinate to global Web Mercator pixel coordinates."""
    scale = TILE_SIZE_PX * 2**zoom
    x = (lon + 180) / 360 * scale
    sin_lat = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * scale
    return x, y


def cluster_points(
    points: Sequence[tuple[float, float]], radius_m: float
) -> list[list[int]]:
    """Group point indices lying within radius of a cluster's first point."""
    clusters: list[list[int]] = []
    for index, (lat, lon) in enumerate(points):
        for cluster in clusters:
            first_lat, first_lon = points[cluster[0]]
            if distance_m(lat, lon, first_lat, first_lon) <= radius_m:
                cluster.append(index)
                break
        else:
            clusters.append([index])
    return clusters
