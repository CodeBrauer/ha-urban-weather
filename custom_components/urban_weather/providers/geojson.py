"""
Networks published as a GeoJSON file with the latest values of each station.

The file is a FeatureCollection with one Point feature per station; the properties
hold the station's id and name, the time of its latest measurement and the values.
Both the station list and the measurements come from this one file, so a station is
its own sensor.

The request can carry query parameters (an ArcGIS FeatureServer `query` or a WFS
GetFeature URL), and a feed with times that are not ISO 8601 brings its own parser.

A feed in long format has one feature per station, value and time: a property names
the value (a key of the network's fields), another holds it. A feed that holds a time
series selects a window for each request, as it returns its whole history otherwise.

A feed can leave out stations that fell silent: those whose newest value is older than
`current_within` before the newest value of the payload. The cut is relative to the
payload, not to now, as the hub also builds stations from a stored copy.

Not covered yet, to be added with the network that needs it:

- Values sent as strings (a value parser instead of `is_number`).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from homeassistant.util import dt as dt_util

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
    from datetime import datetime, timedelta

    import aiohttp

    from custom_components.urban_weather.provider import Network

# GeoJSON positions are [longitude, latitude].
POSITION_LENGTH = 2


@dataclass(frozen=True, slots=True)
class TimeWindow:
    """How far back the requests of a feed holding a time series look."""

    # Query parameters selecting the features measured after a time.
    params: Callable[[datetime], Mapping[str, str]]
    # The station list wants a long window (stations fall silent for hours), the
    # measurements a short one, as they are requested often.
    station_list: timedelta
    measurements: timedelta


@dataclass(frozen=True, slots=True)
class GeoJsonFeed:
    """How to read a feed: its request, and the properties of a station and its time."""

    station_id: str
    station_name: str
    timestamp: str
    # Query parameters and extra headers of the request.
    params: Mapping[str, str] | None = None
    headers: Mapping[str, str] | None = None
    # Turns the value of the timestamp property into an aware datetime, else None.
    parse_time: Callable[[Any], datetime | None] = parse_timestamp
    # Turns the value of the name property (as text) into the name shown.
    parse_name: Callable[[str], str] = str.strip
    # Long format only: the properties holding the name of a value (a key of the
    # network's fields) and the value itself.
    parameter: str | None = None
    value: str | None = None
    # Time series only: the window of each request.
    window: TimeWindow | None = None
    # Stations whose newest value is older than this before the newest value of the
    # payload are left out of the station list; None keeps every station.
    current_within: timedelta | None = None
    # Long format only: a value missing at a station's newest time is taken from an
    # older time up to this much earlier; None fills nothing.
    fill_within: timedelta | None = None


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


def _time(feature: Mapping[str, Any], feed: GeoJsonFeed) -> datetime:
    return feed.parse_time(_properties(feature).get(feed.timestamp)) or OLDEST


def _newest_first(
    features: list[dict[str, Any]], feed: GeoJsonFeed
) -> list[dict[str, Any]]:
    return sorted(features, key=lambda item: _time(item, feed), reverse=True)


def _merge_long_format(
    features: list[dict[str, Any]],
    feed: GeoJsonFeed,
    fields: Mapping[str, Field],
) -> list[dict[str, Any]]:
    """Return one feature per station and time with the values as properties."""
    if feed.parameter is None:
        return features
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for feature in features:
        properties = _properties(feature)
        name = properties.get(feed.parameter)
        value = properties.get(feed.value) if feed.value else None
        if not isinstance(name, str) or name not in fields or not is_number(value):
            continue
        key = (_station_id(properties, feed), str(properties.get(feed.timestamp)))
        if key not in merged:
            merged[key] = {
                **feature,
                "properties": {
                    feed.station_id: properties.get(feed.station_id),
                    feed.station_name: properties.get(feed.station_name),
                    feed.timestamp: properties.get(feed.timestamp),
                },
            }
        merged[key]["properties"][name] = value
    return list(merged.values())


def _newest_features(
    features: list[dict[str, Any]], feed: GeoJsonFeed
) -> list[dict[str, Any]]:
    """Return the newest feature of each station (and value in long format)."""
    newest: dict[tuple[str, str], dict[str, Any]] = {}
    for feature in _newest_first(features, feed):
        properties = _properties(feature)
        if feed.value and not is_number(properties.get(feed.value)):
            continue
        parameter = properties.get(feed.parameter) if feed.parameter else None
        newest.setdefault((_station_id(properties, feed), str(parameter)), feature)
    return list(newest.values())


def build_stations(
    features: list[dict[str, Any]],
    feed: GeoJsonFeed,
    fields: Mapping[str, Field],
) -> list[Station]:
    """
    Return one station for each feature that has an id, a position and a value.

    The station is a sensor of its own providing the mapped fields that have a value
    in any of its features (in long format its values can be of different times).
    On a repeated id the feature with the newest measurement is used.
    """
    stations: dict[str, Station] = {}
    ordered = _newest_first(_merge_long_format(features, feed, fields), feed)
    newest = _time(ordered[0], feed) if ordered else OLDEST
    measured: dict[str, set[Field]] = {}
    for feature in ordered:
        properties = _properties(feature)
        measured.setdefault(_station_id(properties, feed), set()).update(
            mapped for name, mapped in fields.items() if is_number(properties.get(name))
        )
    for feature in ordered:
        properties = _properties(feature)
        station_id = _station_id(properties, feed)
        position = _position(feature)
        if not station_id or position is None:
            LOGGER.debug("Skipping feature without id or position: %s", feature)
            continue
        if station_id in stations:
            continue
        if feed.current_within and newest - _time(feature, feed) > feed.current_within:
            # Newest first: the station's newest value is already too old.
            continue
        name = feed.parse_name(str(properties.get(feed.station_name) or ""))
        sensor = ApiSensor(
            id=station_id,
            name=name or station_id,
            latitude=position[0],
            longitude=position[1],
            parameters=frozenset(measured[station_id]),
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
    With `fill_within`, a value missing at the newest time comes from an older one
    within that span; the measurement keeps the newest time, so an old value never
    makes a fresh one look stale.
    """
    measurements: dict[str, Measurement] = {}
    for feature in _newest_first(_merge_long_format(features, feed, fields), feed):
        properties = _properties(feature)
        station_id = _station_id(properties, feed)
        timestamp = feed.parse_time(properties.get(feed.timestamp))
        if not station_id or timestamp is None:
            continue
        values = {
            mapped: float(properties[name])
            for name, mapped in fields.items()
            if is_number(properties.get(name))
        }
        newer = measurements.get(station_id)
        if newer is None:
            measurements[station_id] = Measurement(timestamp=timestamp, values=values)
            continue
        if feed.fill_within is None or newer.timestamp - timestamp > feed.fill_within:
            continue
        missing = {
            key: value for key, value in values.items() if key not in newer.values
        }
        if missing:
            measurements[station_id] = replace(
                newer, values={**newer.values, **missing}
            )
    return {station_id: [m] for station_id, m in measurements.items()}


class GeoJsonProvider(BulkProvider):
    """
    One request for the measurements of all stations.

    The file holds every station, so the request is the same for the station list
    and the measurements (apart from the window of a time series); the hub keeps the
    stations the locations use.
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
        window = self.feed.window
        if window is None:
            return {"features": await self._async_features(None)}
        # A time series is long; the stored list keeps what the stations need.
        features = await self._async_features(window.station_list)
        return {"features": _newest_features(features, self.feed)}

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
        window = self.feed.window
        return parse_measurements(
            await self._async_features(window.measurements if window else None),
            self.feed,
            self.network.fields,
        )

    async def _async_features(
        self, look_back: timedelta | None
    ) -> list[dict[str, Any]]:
        """Request the features, of the last `look_back` for a time series."""
        params = dict(self.feed.params or {})
        if self.feed.window and look_back:
            params.update(self.feed.window.params(dt_util.utcnow() - look_back))
        url = self.network.endpoint
        return _collection_features(
            await async_get_json(
                self._session,
                url,
                url,
                params=params or None,
                headers=self.feed.headers,
            )
        )
