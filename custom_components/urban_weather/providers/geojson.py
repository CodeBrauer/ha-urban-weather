"""
Networks published as a GeoJSON file with the latest values of each station.

The file is a FeatureCollection with one Point feature per station; the properties
hold the station's id and name, the time of its latest measurement and the values.
Both the station list and the measurements come from this one file, so a station is
its own sensor.

The request can carry query parameters (an ArcGIS FeatureServer `query` or a WFS
GetFeature URL), and a feed with times that are not ISO 8601 brings its own parser.

Not covered yet, to be added with the network that needs it:

- Dropping outdated stations: the station list keeps every station with a value, also
  one silent for longer than STATION_OFFLINE_AFTER. A feed that keeps stations that
  stopped sending, or flags them with a property, needs a filter.
- Values sent as strings (a value parser instead of `is_number`) and times without a
  UTC offset in local time (a time zone for `parse_timestamp`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from custom_components.urban_weather.const import LOGGER, Field
from custom_components.urban_weather.provider import (
    ApiError,
    ApiSensor,
    BulkProvider,
    Measurement,
)
from custom_components.urban_weather.stations import Station, pick_sensor

from .common import OLDEST, async_get_json, is_number, parse_timestamp

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping
    from datetime import datetime

    import aiohttp

    from custom_components.urban_weather.provider import Network

# GeoJSON positions are [longitude, latitude].
POSITION_LENGTH = 2


@dataclass(frozen=True, slots=True)
class GeoJsonFeed:
    """How to read a feed: its request, and the properties of a station and its time."""

    station_id: str
    station_name: str
    timestamp: str
    # Query parameters of the request.
    params: Mapping[str, str] | None = None
    # Turns the value of the timestamp property into an aware datetime, else None.
    parse_time: Callable[[Any], datetime | None] = parse_timestamp


def _features(features: Any) -> list[dict[str, Any]]:
    if not isinstance(features, list):
        msg = "Unexpected GeoJSON format"
        raise ApiError(msg)
    return [feature for feature in features if isinstance(feature, dict)]


def _collection_features(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        msg = "Unexpected GeoJSON format"
        raise ApiError(msg)
    return _features(payload.get("features"))


def _properties(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    properties = feature.get("properties")
    return properties if isinstance(properties, dict) else {}


def _position(feature: Mapping[str, Any]) -> tuple[float, float] | None:
    geometry = feature.get("geometry")
    if not isinstance(geometry, dict) or geometry.get("type") != "Point":
        return None
    coordinates = geometry.get("coordinates")
    if (
        not isinstance(coordinates, list)
        or len(coordinates) < POSITION_LENGTH
        or not all(is_number(value) for value in coordinates[:POSITION_LENGTH])
    ):
        return None
    longitude, latitude = coordinates[:POSITION_LENGTH]
    return float(latitude), float(longitude)


def _station_id(properties: Mapping[str, Any], feed: GeoJsonFeed) -> str:
    return str(properties.get(feed.station_id) or "").strip()


def build_stations(
    features: list[dict[str, Any]],
    feed: GeoJsonFeed,
    fields: Mapping[str, Field],
) -> list[Station]:
    """
    Return one station for each feature that has an id, a position and a value.

    The station is a sensor of its own providing the mapped fields that have a value.
    On a repeated id the feature with the newest measurement is used.
    """
    stations: dict[str, Station] = {}
    for feature in sorted(
        features,
        key=lambda item: (
            feed.parse_time(_properties(item).get(feed.timestamp)) or OLDEST
        ),
        reverse=True,
    ):
        properties = _properties(feature)
        station_id = _station_id(properties, feed)
        position = _position(feature)
        if not station_id or position is None:
            LOGGER.debug("Skipping feature without id or position: %s", feature)
            continue
        if station_id in stations:
            continue
        name = str(properties.get(feed.station_name) or "").strip()
        sensor = ApiSensor(
            id=station_id,
            name=name or station_id,
            latitude=position[0],
            longitude=position[1],
            parameters=frozenset(
                mapped
                for name, mapped in fields.items()
                if is_number(properties.get(name))
            ),
        )
        temperature = pick_sensor([sensor], Field.TEMPERATURE)
        wind = pick_sensor([sensor], Field.WIND_SPEED)
        if temperature is None and wind is None:
            continue
        stations[station_id] = Station(
            code=station_id,
            latitude=position[0],
            longitude=position[1],
            temperature_sensor=temperature,
            wind_sensor=wind,
            district=None,
            lcz=None,
            lcz_source=None,
            zone=None,
            height_above_ground=None,
            temperature_height=None,
            name=name if name not in ("", station_id) else None,
        )
    return list(stations.values())


def parse_measurements(
    features: list[dict[str, Any]],
    feed: GeoJsonFeed,
    fields: Mapping[str, Field],
) -> dict[str, list[Measurement]]:
    """
    Return the latest measurement by station id, skipping features without time.

    On a repeated id the feature with the newest time is used, as for the stations.
    """
    measurements: dict[str, list[Measurement]] = {}
    for feature in features:
        properties = _properties(feature)
        station_id = _station_id(properties, feed)
        timestamp = feed.parse_time(properties.get(feed.timestamp))
        if not station_id or timestamp is None:
            continue
        if (
            station_id in measurements
            and measurements[station_id][0].timestamp >= timestamp
        ):
            continue
        values = {
            mapped: float(properties[name])
            for name, mapped in fields.items()
            if is_number(properties.get(name))
        }
        measurements[station_id] = [Measurement(timestamp=timestamp, values=values)]
    return measurements


class GeoJsonProvider(BulkProvider):
    """
    One request for the measurements of all stations.

    The file holds every station, so the request is the same for the station list
    and the measurements; the hub keeps the stations the locations use.
    """

    def __init__(
        self,
        network: Network,
        feed: GeoJsonFeed,
        session: aiohttp.ClientSession,
    ) -> None:
        """Use the shared client session; `network.endpoint` is the file's URL."""
        super().__init__(network)
        self.feed = feed
        self._session = session

    async def async_get_station_payload(self) -> dict[str, Any]:
        """Return the features (the hub stores a dict)."""
        return {"features": await self._async_features()}

    def build_stations(self, payload: dict[str, Any]) -> list[Station]:
        """Turn the stored features into stations."""
        return build_stations(
            _features(payload.get("features")), self.feed, self.network.fields
        )

    async def async_get_all_measurements(
        self, sensors: Collection[ApiSensor]
    ) -> dict[str, list[Measurement]]:
        """Return the latest measurement of all stations (none without sensors)."""
        if not sensors:
            return {}
        return parse_measurements(
            await self._async_features(), self.feed, self.network.fields
        )

    async def _async_features(self) -> list[dict[str, Any]]:
        url = self.network.endpoint
        return _collection_features(
            await async_get_json(self._session, url, url, params=self.feed.params)
        )
