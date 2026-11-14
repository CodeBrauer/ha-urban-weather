"""Interface between the integration and the climate networks it reads."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping
    from datetime import datetime

    from .const import Field
    from .stations import Station


class ApiError(Exception):
    """Unexpected API response."""


class ApiConnectionError(ApiError):
    """The API could not be reached."""


class ApiRateLimitError(ApiError):
    """The API rejected the request because of its rate limit."""

    def __init__(self, retry_after: float) -> None:
        """Store how long the API asks us to wait."""
        super().__init__(f"Rate limited, retry after {retry_after:.0f} s")
        self.retry_after = retry_after


class SensorNotFoundError(ApiError):
    """The sensor does not exist (any more)."""


@dataclass(frozen=True, slots=True)
class ApiSensor:
    """A sensor as listed by the API."""

    id: str
    name: str
    latitude: float
    longitude: float
    parameters: frozenset[str]


@dataclass(frozen=True, slots=True)
class Measurement:
    """One timestamped set of values of a sensor."""

    timestamp: datetime
    values: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class RequestLimits:
    """Client-side mirror of a network's request limits."""

    # (max requests, window in seconds); every window must have room for a request.
    measurements: tuple[tuple[int, float], ...]
    station_list: tuple[tuple[int, float], ...]
    # Documented measurement requests per hour, shown to the user.
    per_hour: int
    # What the station selection plans with, below the documented limit.
    planned_per_hour: int


@dataclass(frozen=True, slots=True)
class TileLayer:
    """Background map of the station map page."""

    url: str
    attribution: str


@dataclass(frozen=True, slots=True)
class Network:
    """Everything about a network that is configuration, not code."""

    # Device model and manufacturer of the entities.
    name: str
    operator: str
    # Title of a location without a known district.
    area: str
    endpoint: str
    # Field name of the network -> Field.
    fields: Mapping[str, Field]
    attribution: str
    limits: RequestLimits
    tiles: TileLayer

    @property
    def measurements(self) -> frozenset[Field]:
        """Return the values the network can measure."""
        return frozenset(self.fields.values())

    @property
    def host(self) -> str:
        """Return the host of the endpoint, as named in messages to the user."""
        return urlsplit(self.endpoint).hostname or self.endpoint


class Provider(ABC):
    """
    Access to one network; one subclass per platform (type of API).

    A provider declares its request model by its base class: SensorProvider (one
    request per sensor) or BulkProvider (one request for all sensors).
    """

    def __init__(self, network: Network) -> None:
        """Keep the network configuration."""
        self.network = network

    @abstractmethod
    async def async_get_station_payload(self) -> dict[str, Any]:
        """Return the raw station list, which the hub stores as is."""

    @abstractmethod
    def build_stations(self, payload: dict[str, Any]) -> list[Station]:
        """Return the stations of a raw station list (fresh or stored)."""

    @abstractmethod
    def requests_per_refresh(self, sensors: int) -> int:
        """Return the measurement requests one refresh of these sensors costs."""

    def lcz(self, latitude: float, longitude: float) -> int | None:  # noqa: ARG002
        """Return the Local Climate Zone at a coordinate, if the network has a map."""
        return None

    def district(self, latitude: float, longitude: float) -> str | None:  # noqa: ARG002
        """Return the district name at a coordinate, if the network knows it."""
        return None


class SensorProvider(Provider):
    """A network that returns the measurements of one sensor per request."""

    @abstractmethod
    async def async_get_measurements(self, sensor_id: str) -> list[Measurement]:
        """
        Return the recent measurements of a sensor, newest first.

        Raises ApiRateLimitError, SensorNotFoundError, ApiConnectionError or
        ApiError.
        """

    def requests_per_refresh(self, sensors: int) -> int:
        """Return one request per sensor."""
        return sensors


class BulkProvider(Provider):
    """A network that returns the measurements of all sensors in one request."""

    @abstractmethod
    async def async_get_all_measurements(
        self, sensors: Collection[ApiSensor]
    ) -> dict[str, list[Measurement]]:
        """
        Return recent measurements by sensor id, newest first.

        `sensors` are the sensors the locations use; the provider may restrict its
        request to them (e.g. a geo filter around them) or return more. Raises
        ApiRateLimitError, ApiConnectionError or ApiError.
        """

    def requests_per_refresh(self, sensors: int) -> int:
        """Return one request for any number of sensors."""
        return min(sensors, 1)
