"""Tests for the shared request budget and measurement cache."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from homeassistant.util import dt as dt_util

from custom_components.urban_weather.const import NEW_STATION_PERIOD, STORAGE_KEY
from custom_components.urban_weather.hub import (
    ClimateHub,
    RateLimiter,
    RequestDeferredError,
    StationListUnavailableError,
    async_get_hub,
    track_first_seen,
)
from custom_components.urban_weather.provider import (
    ApiConnectionError,
    ApiRateLimitError,
    Measurement,
)
from custom_components.urban_weather.providers.mannheim import MEASUREMENT_LIMITS

from .common import (
    MEASURED_AT,
    MEASUREMENTS,
    NEAREST_SENSOR,
    NEAREST_WIND_SENSOR,
    mannheim_provider,
    sensors_payload,
    store_sensor_list,
)

if TYPE_CHECKING:
    from typing import Any

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

RATE_LIMIT_WARNING = "rate limit was hit"
STATIONS_IN_FIXTURE = 27
NOW = MEASURED_AT


# RateLimiter (4 requests per 2 minutes, 30 per hour)


def test_rate_limiter_allows_four_requests_per_two_minutes(
    freezer: FrozenDateTimeFactory,
) -> None:
    """The 5th request has to wait until the oldest one leaves the window."""
    limiter = RateLimiter(MEASUREMENT_LIMITS)
    for _ in range(4):
        assert limiter.wait_time() == 0
        limiter.acquire()
        freezer.tick(10)
    # Requests at 0, 10, 20, 30 s; now 40 s: the first one expires at 120 s.
    assert limiter.wait_time() == pytest.approx(80)
    freezer.tick(80)
    assert limiter.wait_time() == 0


def test_rate_limiter_allows_thirty_requests_per_hour(
    freezer: FrozenDateTimeFactory,
) -> None:
    """Spread-out requests are limited by the hourly window."""
    limiter = RateLimiter(MEASUREMENT_LIMITS)
    for _ in range(30):
        assert limiter.wait_time() == 0, "40 s apart never hits the 2-minute limit"
        limiter.acquire()
        freezer.tick(40)
    # 30 requests from 0 to 1160 s; now 1200 s: the first one expires at 3600 s.
    assert limiter.wait_time() == pytest.approx(2400)
    freezer.tick(2400)
    assert limiter.wait_time() == 0


def test_rate_limiter_blocks_after_rate_limit(freezer: FrozenDateTimeFactory) -> None:
    """After a 429 the limiter waits for Retry-After, even with budget left."""
    limiter = RateLimiter(MEASUREMENT_LIMITS)
    limiter.block_for(60)
    assert limiter.blocked
    assert limiter.wait_time() == pytest.approx(60)
    freezer.tick(60)
    assert not limiter.blocked
    assert limiter.wait_time() == 0


# ClimateHub


@pytest.fixture
async def hub(api: MagicMock) -> ClimateHub:  # noqa: ARG001
    """Return a hub using the mocked API (reference data and store are unused)."""
    return ClimateHub(MagicMock(), mannheim_provider(), MagicMock())


async def test_measurements_are_cached_for_nine_minutes(
    hub: ClimateHub, api: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Locations sharing a station and repeated refreshes reuse the response."""
    assert await hub.async_get_measurements("s1") == MEASUREMENTS
    freezer.tick(timedelta(minutes=8, seconds=59))
    assert await hub.async_get_measurements("s1") == MEASUREMENTS
    assert api.async_get_measurements.await_count == 1
    freezer.tick(timedelta(seconds=1))
    await hub.async_get_measurements("s1")
    assert api.async_get_measurements.await_count == 2


async def test_request_deferred_when_budget_is_used(
    hub: ClimateHub, api: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """The 5th sensor within 2 minutes is deferred without calling the API."""
    for sensor in ("s1", "s2", "s3", "s4"):
        await hub.async_get_measurements(sensor)
    with pytest.raises(RequestDeferredError) as deferred:
        await hub.async_get_measurements("s5")
    assert deferred.value.wait == pytest.approx(120)
    assert api.async_get_measurements.await_count == 4
    freezer.tick(120)
    assert await hub.async_get_measurements("s5") == MEASUREMENTS


async def test_rate_limit_defers_and_blocks_requests(
    hub: ClimateHub, api: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """A 429 defers the request and pauses all requests for Retry-After."""
    api.async_get_measurements.side_effect = ApiRateLimitError(60)
    with pytest.raises(RequestDeferredError) as deferred:
        await hub.async_get_measurements("s1")
    assert deferred.value.wait == 60
    assert hub.diagnostics()["rate_limited"]

    with pytest.raises(RequestDeferredError):
        await hub.async_get_measurements("s2")
    assert api.async_get_measurements.await_count == 1, "blocked: no request sent"

    freezer.tick(60)
    assert not hub.diagnostics()["rate_limited"]


async def test_rate_limit_warning_once_per_streak(
    hub: ClimateHub,
    api: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Repeated 429s warn once; a success in between starts a new streak."""
    api.async_get_measurements.side_effect = [
        ApiRateLimitError(60),
        ApiRateLimitError(60),
        MEASUREMENTS,
        ApiRateLimitError(60),
    ]

    def warnings() -> int:
        return sum(
            record.levelno == logging.WARNING
            and RATE_LIMIT_WARNING in record.getMessage()
            for record in caplog.records
        )

    for sensor in ("s1", "s2"):
        with pytest.raises(RequestDeferredError):
            await hub.async_get_measurements(sensor)
        freezer.tick(60)
    assert warnings() == 1

    await hub.async_get_measurements("s3")
    freezer.tick(60)
    with pytest.raises(RequestDeferredError):
        await hub.async_get_measurements("s4")
    assert warnings() == 2


async def test_concurrent_requests_for_one_sensor_share_the_response(
    hub: ClimateHub, api: MagicMock
) -> None:
    """Two locations refreshing at once cause only one API request."""

    async def slow_response(_sensor_id: str) -> list[Measurement]:
        await asyncio.sleep(0)
        return MEASUREMENTS

    api.async_get_measurements.side_effect = slow_response
    results = await asyncio.gather(
        hub.async_get_measurements("s1"), hub.async_get_measurements("s1")
    )
    assert results == [MEASUREMENTS, MEASUREMENTS]
    assert api.async_get_measurements.await_count == 1


# Station list (refreshed once a day, stored copy as fallback)


async def test_station_list_fetched_once_a_day(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The list is fetched, stored and kept for 24 hours."""
    hub = await async_get_hub(hass)
    stations = await hub.async_get_stations()
    assert len(stations) == STATIONS_IN_FIXTURE
    assert hub.station_for_sensor(NEAREST_WIND_SENSOR).code == "2507LH096"
    assert hass_storage[STORAGE_KEY]["data"]["payload"] == sensors_payload()

    freezer.tick(timedelta(hours=23, minutes=59))
    assert await hub.async_get_stations() is stations
    assert api.async_get_sensors_payload.await_count == 1
    freezer.tick(timedelta(minutes=1))
    await hub.async_get_stations()
    assert api.async_get_sensors_payload.await_count == 2


async def test_fresh_stored_station_list_used_without_request(
    hass: HomeAssistant, hass_storage: dict[str, Any], api: MagicMock
) -> None:
    """After a restart, a list stored less than a day ago is used as is."""
    store_sensor_list(hass_storage, timedelta(hours=23))
    hub = await async_get_hub(hass)
    assert len(await hub.async_get_stations()) == STATIONS_IN_FIXTURE
    api.async_get_sensors_payload.assert_not_awaited()


async def test_old_stored_station_list_used_when_api_fails(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    api: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An outdated stored list is better than none."""
    store_sensor_list(hass_storage, timedelta(days=3))
    api.async_get_sensors_payload.side_effect = ApiConnectionError("timeout")
    hub = await async_get_hub(hass)
    assert len(await hub.async_get_stations()) == STATIONS_IN_FIXTURE
    assert "Could not refresh the station list" in caplog.text


async def test_station_list_unavailable_without_api_and_store(
    hass: HomeAssistant, api: MagicMock
) -> None:
    """Without a stored copy an API failure makes the list unavailable."""
    api.async_get_sensors_payload.side_effect = ApiConnectionError("timeout")
    hub = await async_get_hub(hass)
    with pytest.raises(StationListUnavailableError):
        await hub.async_get_stations()


async def test_station_list_rate_limit_blocks_further_requests(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """After a 429 the stored copy is used until Retry-After has passed."""
    store_sensor_list(hass_storage, timedelta(days=3))
    api.async_get_sensors_payload.side_effect = ApiRateLimitError(900)
    hub = await async_get_hub(hass)
    await hub.async_get_stations()
    freezer.tick(timedelta(minutes=14))
    await hub.async_get_stations()
    assert api.async_get_sensors_payload.await_count == 1, "blocked: no request sent"

    api.async_get_sensors_payload.side_effect = None
    freezer.tick(timedelta(minutes=1))
    await hub.async_get_stations()
    assert api.async_get_sensors_payload.await_count == 2
    assert hass_storage[STORAGE_KEY]["data"]["fetched_at"] == (
        dt_util.utcnow().isoformat()
    )


# New sensors (first seen in the station list)


@pytest.mark.parametrize(
    ("history", "expected"),
    [
        (None, {"a": None, "b": None, "c": None}),
        (
            {"a": None, "b": "2026-10-01T00:00:00+00:00", "gone": None},
            {"a": None, "b": "2026-10-01T00:00:00+00:00", "c": NOW.isoformat()},
        ),
    ],
    ids=["no_history", "history"],
)
def test_track_first_seen(
    history: dict[str, str | None] | None, expected: dict[str, str | None]
) -> None:
    """Without history all sensors are known; later only added ones get a time."""
    assert track_first_seen(history, ["a", "b", "c"], NOW) == expected


async def test_added_sensor_is_new_for_thirty_days(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    api: MagicMock,  # noqa: ARG001
    freezer: FrozenDateTimeFactory,
) -> None:
    """A sensor missing from the stored history is new from the next refresh on."""
    store_sensor_list(hass_storage, timedelta(days=3), new=NEAREST_WIND_SENSOR)
    hub = await async_get_hub(hass)
    await hub.async_get_stations()
    assert hub.is_new(NEAREST_WIND_SENSOR)
    assert not hub.is_new(NEAREST_SENSOR)
    first_seen = hass_storage[STORAGE_KEY]["data"]["first_seen"]
    assert first_seen[NEAREST_WIND_SENSOR] == dt_util.utcnow().isoformat()

    freezer.tick(NEW_STATION_PERIOD - timedelta(seconds=1))
    assert hub.is_new(NEAREST_WIND_SENSOR)
    freezer.tick(timedelta(seconds=1))
    assert not hub.is_new(NEAREST_WIND_SENSOR)


async def test_first_refresh_after_update_knows_all_sensors(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    api: MagicMock,  # noqa: ARG001
) -> None:
    """A stored list without history must not make every sensor new."""
    store_sensor_list(hass_storage, timedelta(days=3))
    hub = await async_get_hub(hass)
    await hub.async_get_stations()
    assert not hub.is_new(NEAREST_WIND_SENSOR)
    assert set(hass_storage[STORAGE_KEY]["data"]["first_seen"].values()) == {None}
