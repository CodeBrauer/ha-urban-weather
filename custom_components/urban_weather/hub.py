"""Shared API access: request budget, measurement cache and station list."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .api import ApiError, ApiRateLimitError, MannheimClimateApi, parse_sensors
from .const import (
    DOMAIN,
    LOGGER,
    MEASUREMENT_CACHE_TTL,
    MEASUREMENT_LIMITS,
    NEW_STATION_PERIOD,
    SENSOR_LIST_LIMITS,
    SENSOR_LIST_MAX_AGE,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .reference import ReferenceData, load_reference_data
from .stations import Station, build_stations

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    from homeassistant.core import HomeAssistant

    from .api import Measurement

DATA_HUB: HassKey[ClimateHub] = HassKey(DOMAIN)
MINUTES_PER_HOUR = 60


class StationListUnavailableError(ApiError):
    """Neither the API nor the local cache can provide the station list."""


class RequestDeferredError(ApiError):
    """No request budget left right now; try again after `wait` seconds."""

    def __init__(self, wait: float) -> None:
        """Store how long to wait."""
        super().__init__(f"Request deferred for {wait:.0f} s")
        self.wait = wait


class RateLimiter:
    """Sliding-window limits mirroring the API's per-IP limits."""

    def __init__(self, windows: tuple[tuple[int, float], ...]) -> None:
        """Take (max requests, window seconds) pairs."""
        self._windows = windows
        self._longest = max(seconds for _, seconds in windows)
        self._history: deque[float] = deque()
        self._blocked_until = 0.0

    def wait_time(self) -> float:
        """Return seconds until the next request is allowed (0 = now)."""
        now = time.monotonic()
        while self._history and self._history[0] <= now - self._longest:
            self._history.popleft()
        wait = max(0.0, self._blocked_until - now)
        for limit, seconds in self._windows:
            recent = [t for t in self._history if t > now - seconds]
            if len(recent) >= limit:
                wait = max(wait, recent[-limit] + seconds - now)
        return wait

    def acquire(self) -> None:
        """Record a request (call only when wait_time() is 0)."""
        self._history.append(time.monotonic())

    def block_for(self, seconds: float) -> None:
        """Pause after the API answered 429 (other clients share our IP)."""
        self._blocked_until = time.monotonic() + seconds

    @property
    def blocked(self) -> bool:
        """Return True while the API told us to back off."""
        return time.monotonic() < self._blocked_until


@dataclass(slots=True)
class _CachedMeasurements:
    fetched_at: datetime
    measurements: list[Measurement]


def requests_per_hour(sensor_count: int, interval_minutes: int) -> int:
    """Return the planned measurement requests per hour of one config entry."""
    return round(sensor_count * MINUTES_PER_HOUR / interval_minutes)


def track_first_seen(
    first_seen: dict[str, str | None] | None,
    sensor_ids: Iterable[str],
    now: datetime,
) -> dict[str, str | None]:
    """
    Remember when each sensor of the station list first appeared (ISO time).

    Without a history (first refresh after install or update) all sensors count as
    known (None), so only sensors added later are new.
    """
    if first_seen is None:
        return dict.fromkeys(sensor_ids)
    return {
        sensor_id: first_seen[sensor_id] if sensor_id in first_seen else now.isoformat()
        for sensor_id in sensor_ids
    }


class ClimateHub:
    """One instance per Home Assistant, shared by all config entries."""

    def __init__(
        self,
        hass: HomeAssistant,
        reference: ReferenceData,
        store: Store[dict[str, Any]],
    ) -> None:
        """Set up limiter and caches."""
        self._api = MannheimClimateApi(async_get_clientsession(hass))
        self.reference = reference
        self._store = store
        self._measurement_limiter = RateLimiter(MEASUREMENT_LIMITS)
        self._sensor_limiter = RateLimiter(SENSOR_LIST_LIMITS)
        self._measurements: dict[str, _CachedMeasurements] = {}
        self._sensor_locks: dict[str, asyncio.Lock] = {}
        self._stations: list[Station] | None = None
        self._stations_fetched_at: datetime | None = None
        self._stations_lock = asyncio.Lock()
        self._sensor_index: dict[str, Station] = {}
        self._first_seen: dict[str, str | None] = {}
        self._rate_limit_logged = False

    async def async_get_stations(self) -> list[Station]:
        """Return all stations, refreshing the sensor list at most once a day."""
        async with self._stations_lock:
            now = dt_util.utcnow()
            if (
                self._stations is not None
                and self._stations_fetched_at
                and now - self._stations_fetched_at < SENSOR_LIST_MAX_AGE
            ):
                return self._stations
            stored = await self._store.async_load()
            fetched_at = (
                dt_util.parse_datetime(stored["fetched_at"]) if stored else None
            )
            payload = stored["payload"] if stored else None
            first_seen = stored.get("first_seen") if stored else None
            fresh = None
            if fetched_at is None or now - fetched_at >= SENSOR_LIST_MAX_AGE:
                fresh = await self._async_fetch_sensor_list()
                if fresh is not None:
                    payload, fetched_at = fresh, now
            if payload is None:
                msg = "Station list not available"
                raise StationListUnavailableError(msg)
            self._set_stations(payload, fetched_at)
            if fresh is not None:
                first_seen = track_first_seen(first_seen, self._sensor_index, now)
                await self._store.async_save(
                    {
                        "fetched_at": now.isoformat(),
                        "payload": payload,
                        "first_seen": first_seen,
                    }
                )
            self._first_seen = first_seen or {}
            return self._stations

    async def _async_fetch_sensor_list(self) -> dict[str, Any] | None:
        if self._sensor_limiter.wait_time():
            LOGGER.debug("Sensor list budget exhausted, using stored copy")
            return None
        self._sensor_limiter.acquire()
        try:
            return await self._api.async_get_sensors_payload()
        except ApiRateLimitError as err:
            self._sensor_limiter.block_for(err.retry_after)
            LOGGER.debug("Sensor list rate limited, using stored copy")
        except ApiError as err:
            LOGGER.warning("Could not refresh the station list: %s", err)
        return None

    def _set_stations(self, payload: dict[str, Any], fetched_at: datetime) -> None:
        self._stations = build_stations(parse_sensors(payload), self.reference)
        self._stations_fetched_at = fetched_at
        self._sensor_index = {}
        for station in self._stations:
            for sensor in (station.temperature_sensor, station.wind_sensor):
                if sensor:
                    self._sensor_index[sensor.id] = station

    def station_for_sensor(self, sensor_id: str) -> Station | None:
        """Return the station a sensor belongs to (after async_get_stations)."""
        return self._sensor_index.get(sensor_id)

    def is_new(self, sensor_id: str) -> bool:
        """Return True if the sensor was added to the station list recently."""
        first_seen = self._first_seen.get(sensor_id)
        seen = dt_util.parse_datetime(first_seen) if first_seen else None
        return seen is not None and dt_util.utcnow() - seen < NEW_STATION_PERIOD

    def cached_measurements(self, sensor_id: str) -> list[Measurement]:
        """Return the last fetched measurements of a sensor (possibly stale)."""
        cached = self._measurements.get(sensor_id)
        return cached.measurements if cached else []

    async def async_get_measurements(self, sensor_id: str) -> list[Measurement]:
        """
        Return recent measurements of a sensor, from cache if fresh enough.

        Raises RequestDeferredError when the request budget is used up or the API
        asked us to back off, SensorNotFoundError and ApiConnectionError otherwise.
        """
        lock = self._sensor_locks.setdefault(sensor_id, asyncio.Lock())
        async with lock:
            cached = self._measurements.get(sensor_id)
            now = dt_util.utcnow()
            if cached and now - cached.fetched_at < MEASUREMENT_CACHE_TTL:
                return cached.measurements
            if wait := self._measurement_limiter.wait_time():
                raise RequestDeferredError(wait)
            self._measurement_limiter.acquire()
            try:
                measurements = await self._api.async_get_measurements(sensor_id)
            except ApiRateLimitError as err:
                self._measurement_limiter.block_for(err.retry_after)
                self._log_rate_limit(err.retry_after)
                raise RequestDeferredError(err.retry_after) from err
            self._rate_limit_logged = False
            self._measurements[sensor_id] = _CachedMeasurements(now, measurements)
            return measurements

    def _log_rate_limit(self, retry_after: float) -> None:
        # Warn once per streak; other clients on the same IP may cause this.
        if self._rate_limit_logged:
            LOGGER.debug("Still rate limited, retry after %.0f s", retry_after)
            return
        self._rate_limit_logged = True
        LOGGER.warning(
            "The climate API rate limit was hit (retry after %.0f s). Missing "
            "values are fetched afterwards. Other devices or scripts using "
            "api.smartmannheim.de from the same internet connection share the limit",
            retry_after,
        )

    def diagnostics(self) -> dict[str, Any]:
        """Return hub state for diagnostics."""
        return {
            "stations": len(self._stations or []),
            "stations_fetched_at": self._stations_fetched_at,
            "new_sensors": sorted(s for s in self._first_seen if self.is_new(s)),
            "cached_sensors": len(self._measurements),
            "rate_limited": self._measurement_limiter.blocked,
            "seconds_until_next_request": round(self._measurement_limiter.wait_time()),
        }


@singleton(DATA_HUB, async_=True)
async def async_get_hub(hass: HomeAssistant) -> ClimateHub:
    """Create the shared hub on first use."""
    reference = await hass.async_add_executor_job(load_reference_data)
    return ClimateHub(hass, reference, Store(hass, STORAGE_VERSION, STORAGE_KEY))
