"""
Networks published as a dataset on an Opendatasoft portal (Explore API v2.1).

The dataset holds one record per sensor with its latest measurement. Both the station
list and the measurements come from the export endpoint, which returns all matching
records in one response (the records endpoint pages by 100).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from custom_components.urban_weather.const import LOGGER, STATION_OFFLINE_AFTER, Field
from custom_components.urban_weather.provider import (
    ApiError,
    ApiSensor,
    BulkProvider,
    Measurement,
)
from custom_components.urban_weather.stations import Station, pick_sensor

from .common import async_get_json, is_number

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    import aiohttp

    from custom_components.urban_weather.provider import Network

# Drops float artifacts of unit conversions (100.59 kPa x 10 = 1005.9000000000001).
CONVERTED_DIGITS = 6
OLDEST = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class OpendatasoftDataset:
    """Where the sensors of a network are in an Opendatasoft dataset."""

    id: str
    # Field names of the sensor id, its station, a readable sensor name, the
    # position (geo_point_2d) and the time of the latest measurement.
    sensor_id: str
    station_id: str
    sensor_name: str
    position: str
    timestamp: str
    # ODSQL condition selecting the records that are sensors the integration uses.
    where: str | None = None
    # Field name -> factor to the unit of the integration.
    factors: Mapping[str, float] = field(default_factory=dict)


def _timestamp(record: Mapping[str, Any], name: str) -> datetime | None:
    try:
        timestamp = datetime.fromisoformat(str(record[name]))
    except KeyError, TypeError, ValueError:
        return None
    return timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=UTC)


def _records(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        msg = "Unexpected export format"
        raise ApiError(msg)
    return [record for record in payload if isinstance(record, dict)]


def _position(record: Mapping[str, Any], name: str) -> tuple[float, float] | None:
    position = record.get(name)
    if not isinstance(position, dict):
        return None
    latitude, longitude = position.get("lat"), position.get("lon")
    if not (is_number(latitude) and is_number(longitude)):
        return None
    return float(latitude), float(longitude)


def build_stations(
    records: list[dict[str, Any]],
    dataset: OpendatasoftDataset,
    fields: Mapping[str, Field],
) -> list[Station]:
    """
    Group the sensor records of the station list by their station id.

    A sensor provides the mapped fields that have a value. Within a station the
    sensor with the most fields is used, on a tie the most recent one. Sensors
    silent for STATION_OFFLINE_AFTER are left out if their station has a current
    one, so a sensor that stopped sending does not shadow its replacement.
    """
    by_station: dict[str, list[tuple[ApiSensor, datetime]]] = {}
    dated = [
        (_timestamp(record, dataset.timestamp) or OLDEST, record) for record in records
    ]
    # The newest measurement stands for the time of the list (fresh or stored).
    listed_at = max((timestamp for timestamp, _ in dated), default=OLDEST)
    for timestamp, record in sorted(dated, key=lambda item: item[0], reverse=True):
        sensor_id = str(record.get(dataset.sensor_id) or "").strip()
        station_id = str(record.get(dataset.station_id) or "").strip()
        position = _position(record, dataset.position)
        if not sensor_id or not station_id or position is None:
            LOGGER.debug("Skipping record without id or position: %s", record)
            continue
        sensor = ApiSensor(
            id=sensor_id,
            name=str(record.get(dataset.sensor_name) or sensor_id).strip(),
            latitude=position[0],
            longitude=position[1],
            parameters=frozenset(
                mapped for name, mapped in fields.items() if is_number(record.get(name))
            ),
        )
        by_station.setdefault(station_id, []).append((sensor, timestamp))
    stations = []
    for code, members in by_station.items():
        sensors = _current(members, listed_at)
        temperature = pick_sensor(sensors, Field.TEMPERATURE)
        wind = pick_sensor(sensors, Field.WIND_SPEED)
        anchor = temperature or wind
        if anchor is None:
            continue
        stations.append(
            Station(
                code=code,
                latitude=anchor.latitude,
                longitude=anchor.longitude,
                temperature_sensor=temperature,
                wind_sensor=wind,
                district=None,
                lcz=None,
                lcz_source=None,
                zone=None,
                height_above_ground=None,
                temperature_height=None,
            )
        )
    return stations


def _current(
    members: list[tuple[ApiSensor, datetime]], listed_at: datetime
) -> list[ApiSensor]:
    current = [
        sensor
        for sensor, timestamp in members
        if listed_at - timestamp < STATION_OFFLINE_AFTER
    ]
    return current or [sensor for sensor, _ in members]


def _convert(value: float, factor: float | None) -> float:
    return round(value * factor, CONVERTED_DIGITS) if factor else value


def parse_measurements(
    records: list[dict[str, Any]],
    dataset: OpendatasoftDataset,
    fields: Mapping[str, Field],
) -> dict[str, list[Measurement]]:
    """Return the latest measurement by sensor id, skipping records without time."""
    measurements: dict[str, list[Measurement]] = {}
    for record in records:
        sensor_id = str(record.get(dataset.sensor_id) or "").strip()
        timestamp = _timestamp(record, dataset.timestamp)
        if not sensor_id or timestamp is None:
            continue
        values = {
            mapped: _convert(float(record[name]), dataset.factors.get(name))
            for name, mapped in fields.items()
            if is_number(record.get(name))
        }
        measurements[sensor_id] = [Measurement(timestamp=timestamp, values=values)]
    return measurements


def _all_of(*conditions: str | None) -> str:
    return " AND ".join(f"({condition})" for condition in conditions if condition)


class OpendatasoftProvider(BulkProvider):
    """
    One request for the measurements of all sensors the locations use.

    The request selects these sensors by id, so the response stays small however
    large the dataset is.
    """

    def __init__(
        self,
        network: Network,
        dataset: OpendatasoftDataset,
        session: aiohttp.ClientSession,
    ) -> None:
        """Use the shared client session; `network.endpoint` is the portal's API."""
        super().__init__(network)
        self.dataset = dataset
        self._session = session

    async def async_get_station_payload(self) -> dict[str, Any]:
        """Return the sensor records (the hub stores a dict)."""
        dataset = self.dataset
        select = [
            dataset.sensor_id,
            dataset.station_id,
            dataset.sensor_name,
            dataset.position,
            dataset.timestamp,
            *self.network.fields,
        ]
        records = await self._async_export(select, dataset.where)
        return {"records": records}

    def build_stations(self, payload: dict[str, Any]) -> list[Station]:
        """Group the stored sensor records into stations."""
        return build_stations(
            _records(payload.get("records")), self.dataset, self.network.fields
        )

    async def async_get_all_measurements(
        self, sensors: Collection[ApiSensor]
    ) -> dict[str, list[Measurement]]:
        """Return the latest measurement of each of these sensors."""
        if not sensors:
            return {}
        dataset = self.dataset
        by_id = " OR ".join(
            f"{dataset.sensor_id}={json.dumps(sensor.id)}" for sensor in sensors
        )
        records = await self._async_export(
            [dataset.sensor_id, dataset.timestamp, *self.network.fields],
            _all_of(by_id, dataset.where),
        )
        return parse_measurements(records, dataset, self.network.fields)

    async def _async_export(
        self, select: list[str], where: str | None
    ) -> list[dict[str, Any]]:
        path = f"/catalog/datasets/{self.dataset.id}/exports/json"
        params = {"select": ",".join(select)}
        if where:
            params["where"] = where
        return _records(
            await async_get_json(
                self._session, f"{self.network.endpoint}{path}", path, params=params
            )
        )
