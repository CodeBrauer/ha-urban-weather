"""Tests for the API client."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import aiohttp
import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.urban_weather.api import (
    ApiConnectionError,
    ApiError,
    ApiRateLimitError,
    MannheimClimateApi,
    SensorNotFoundError,
    parse_measurements,
    parse_sensors,
)
from custom_components.urban_weather.const import (
    API_BASE_URL,
    DEFAULT_RETRY_AFTER_S,
    Field,
)

from .common import sensors_payload

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.test_util.aiohttp import (
        AiohttpClientMocker,
    )

SENSORS_URL = f"{API_BASE_URL}/sensors"
MEASUREMENTS_URL = f"{API_BASE_URL}/measurements/s1"


@pytest.fixture
async def client(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,  # noqa: ARG001
) -> MannheimClimateApi:
    """Return a client using the mocked aiohttp session."""
    return MannheimClimateApi(async_get_clientsession(hass))


async def test_sensor_list_is_returned_unchanged(
    client: MannheimClimateApi, aioclient_mock: AiohttpClientMocker
) -> None:
    """The hub stores the raw payload, so it must not be altered."""
    aioclient_mock.get(SENSORS_URL, json=sensors_payload())
    assert await client.async_get_sensors_payload() == sensors_payload()


@pytest.mark.parametrize("payload", [[], {"sensors": None}, {"error": "maintenance"}])
async def test_unexpected_sensor_list_format(
    client: MannheimClimateApi, aioclient_mock: AiohttpClientMocker, payload: Any
) -> None:
    """A sensor list without a sensors array is rejected (and not stored)."""
    aioclient_mock.get(SENSORS_URL, json=payload)
    with pytest.raises(ApiError, match="Unexpected sensor list format"):
        await client.async_get_sensors_payload()


async def test_measurements_are_parsed(
    client: MannheimClimateApi, aioclient_mock: AiohttpClientMocker
) -> None:
    """A successful response is parsed into measurements."""
    aioclient_mock.get(
        MEASUREMENTS_URL,
        json={"data": [{"timestamp": "2026-10-26T12:00:00Z", "temperature": 12.3}]},
    )
    [measurement] = await client.async_get_measurements("s1")
    assert measurement.timestamp == datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
    assert measurement.values == {Field.TEMPERATURE: 12.3}


@pytest.mark.parametrize(
    ("response", "error", "message"),
    [
        ({"status": 404}, SensorNotFoundError, "/measurements/s1"),
        ({"status": 500, "json": {"error": "internal"}}, ApiError, "HTTP 500"),
        ({"text": "<html>Bad Gateway</html>"}, ApiError, "Invalid JSON"),
        ({"exc": TimeoutError()}, ApiConnectionError, "Error fetching"),
        (
            {"exc": aiohttp.ClientConnectionError()},
            ApiConnectionError,
            "Error fetching",
        ),
    ],
    ids=["not_found", "server_error", "invalid_json", "timeout", "connection_error"],
)
async def test_request_errors(
    client: MannheimClimateApi,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    error: type[ApiError],
    message: str,
) -> None:
    """HTTP and connection errors map to the integration's exceptions."""
    aioclient_mock.get(MEASUREMENTS_URL, **response)
    with pytest.raises(error, match=message) as raised:
        await client.async_get_measurements("s1")
    assert type(raised.value) is error, "no more specific error than expected"


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"Retry-After": "60"}, 60.0),
        ({"Retry-After": "0"}, 1.0),
        ({}, DEFAULT_RETRY_AFTER_S),
        ({"Retry-After": "soon"}, DEFAULT_RETRY_AFTER_S),
    ],
    ids=["seconds", "at_least_one_second", "missing", "unreadable"],
)
async def test_rate_limit_retry_after(
    client: MannheimClimateApi,
    aioclient_mock: AiohttpClientMocker,
    headers: dict[str, str],
    expected: float,
) -> None:
    """A 429 reports how long to wait, with a default for missing/odd headers."""
    aioclient_mock.get(MEASUREMENTS_URL, status=429, headers=headers)
    with pytest.raises(ApiRateLimitError) as rate_limited:
        await client.async_get_measurements("s1")
    assert rate_limited.value.retry_after == expected


# Parsing


def test_parse_real_sensor_list() -> None:
    """The recorded list: one sensor without position is skipped, swaps are fixed."""
    sensors = {sensor.name: sensor for sensor in parse_sensors(sensors_payload())}
    assert len(sensors) == 53
    assert "2303LH085" not in sensors
    swapped = sensors["2306LH126"]
    assert (swapped.latitude, swapped.longitude) == (49.498952, 8.467278)
    assert Field.TEMPERATURE in sensors["2507LH096"].parameters
    assert Field.WIND_SPEED in sensors["2507LW182"].parameters


@pytest.mark.parametrize(
    "raw",
    [
        {"id": "", "position": [8.5, 49.5]},
        {"id": "s1", "position": None},
        {"id": "s1", "position": [8.5]},
        {"id": "s1", "position": [8.5, "49.5"]},
        {"id": "s1", "position": [8.5, float("nan")]},
        {"id": "s1", "position": [True, 49.5]},
    ],
    ids=["no_id", "no_position", "one_value", "string", "nan", "bool"],
)
def test_parse_sensors_skips_unusable_entries(raw: dict[str, Any]) -> None:
    """Entries without id or a numeric position are left out."""
    assert parse_sensors({"paramSets": [], "sensors": [raw]}) == []


@pytest.mark.parametrize("param_set", [None, 5, -1, "0"])
def test_parse_sensors_unknown_param_set(param_set: Any) -> None:
    """An unknown parameter set gives a sensor without parameters."""
    [sensor] = parse_sensors(
        {
            "paramSets": [[Field.TEMPERATURE]],
            "sensors": [{"id": " s1 ", "position": [8.5, 49.5], "paramSet": param_set}],
        }
    )
    assert sensor.id == "s1"
    assert sensor.name == "s1", "falls back to the id"
    assert sensor.parameters == frozenset()


@pytest.mark.parametrize("parse", [parse_sensors, parse_measurements])
def test_parse_rejects_non_object_payload(parse: Any) -> None:
    """A list or error string instead of an object is an API error."""
    with pytest.raises(ApiError):
        parse(["unexpected"])


def test_parse_measurements() -> None:
    """Newest first; invalid timestamps and non-numeric values are dropped."""
    measurements = parse_measurements(
        {
            "data": [
                {"timestamp": "2026-10-26T11:50:00Z", "temperature": 12.1},
                {"timestamp": "2026-10-26T12:00:00Z", "temperature": 12.3, "x": None},
                {"timestamp": "yesterday", "temperature": 99},
                {"temperature": 99},
                {"timestamp": "2026-10-26T11:40:00Z", "airHumidity": "80", "ok": True},
            ]
        }
    )
    assert [m.timestamp.minute for m in measurements] == [0, 50, 40]
    assert [dict(m.values) for m in measurements] == [
        {Field.TEMPERATURE: 12.3},
        {Field.TEMPERATURE: 12.1},
        {},
    ]
