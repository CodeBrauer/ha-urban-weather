"""Tests for combining station readings into one estimate."""

from __future__ import annotations

import statistics
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.urban_weather.aggregation import (
    Estimate,
    StationReading,
    absolute_humidity,
    apparent_temperature,
    dew_point,
    estimate,
    latest_valid,
    relative_humidity,
)
from custom_components.urban_weather.const import MAX_MEASUREMENT_AGE, Field
from custom_components.urban_weather.provider import Measurement

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


def make_reading(  # noqa: PLR0913
    code: str,
    temperature: float | None,
    humidity: float | None = None,
    *,
    distance_m: float = 0.0,
    timestamp: datetime = NOW,
    extra: dict[str, float] | None = None,
) -> StationReading:
    """Return a station reading; None values are left out like missing API fields."""
    values = {Field.TEMPERATURE: temperature, Field.HUMIDITY: humidity, **(extra or {})}
    return StationReading(
        code,
        distance_m,
        Measurement(timestamp, {k: v for k, v in values.items() if v is not None}),
    )


def measurement(minutes_ago: int, values: dict[str, float]) -> Measurement:
    """Return a measurement taken minutes_ago before NOW."""
    return Measurement(NOW - timedelta(minutes=minutes_ago), values)


# Formulas


def test_dew_point_matches_reference_table() -> None:
    """20 °C at 50 % has a dew point of about 9.3 °C."""
    assert dew_point(20.0, 50.0) == pytest.approx(9.3, abs=0.1)


@pytest.mark.parametrize(("temperature", "humidity"), [(-10, 85), (0, 100), (35, 20)])
def test_relative_humidity_inverts_dew_point(
    temperature: float, humidity: float
) -> None:
    """Humidity -> dew point -> humidity returns the original humidity."""
    assert relative_humidity(
        temperature, dew_point(temperature, humidity)
    ) == pytest.approx(humidity)


def test_absolute_humidity_matches_reference_table() -> None:
    """20 °C at 50 % holds about 8.65 g/m³ water vapour."""
    assert absolute_humidity(20.0, 50.0) == pytest.approx(8.65, abs=0.1)


def test_apparent_temperature_decreases_with_wind() -> None:
    """Steadman: 20 °C at 50 % feels like ~19.8 °C in calm air, 0.7 K less per m/s."""
    calm = apparent_temperature(20.0, 50.0, 0.0)
    assert calm == pytest.approx(19.85, abs=0.05)
    assert apparent_temperature(20.0, 50.0, 2.0) == pytest.approx(calm - 1.4)


# latest_valid


def test_latest_valid_returns_newest_measurement() -> None:
    """Measurements are newest first; the first one within max age wins."""
    newest = measurement(5, {Field.TEMPERATURE: 12.0})
    result = latest_valid(
        [newest, measurement(15, {Field.TEMPERATURE: 11.0})],
        NOW,
        MAX_MEASUREMENT_AGE,
    )
    assert result == newest


def test_latest_valid_rejects_measurements_older_than_max_age() -> None:
    """A station whose newest value is too old provides nothing."""
    too_old = measurement(41, {Field.TEMPERATURE: 12.0})
    assert latest_valid([too_old], NOW, MAX_MEASUREMENT_AGE) is None


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        # -999 is the "no value" marker of the network's daily archives.
        (
            {Field.TEMPERATURE: -999.0, Field.HUMIDITY: 80.0},
            {Field.HUMIDITY: 80.0},
        ),
        # Humidity 0 would make the dew point formula fail (log(0)).
        ({Field.TEMPERATURE: 12.0, Field.HUMIDITY: 0.0}, {Field.TEMPERATURE: 12.0}),
        (
            {Field.TEMPERATURE: 45.0, Field.WIND_DIRECTION: 360.0},
            {Field.TEMPERATURE: 45.0, Field.WIND_DIRECTION: 360.0},
        ),
        ({Field.TEMPERATURE: -30.1, Field.PRESSURE: 1013.0}, {Field.PRESSURE: 1013.0}),
        (
            {
                Field.TEMPERATURE: 12.0,
                Field.MIN_TEMPERATURE: -999.0,
                Field.MAX_TEMPERATURE: 45.1,
            },
            {Field.TEMPERATURE: 12.0},
        ),
        (
            {Field.WIND_DIRECTION: 0.0, Field.WIND_GUST_DIRECTION: 360.1},
            {Field.WIND_DIRECTION: 0.0},
        ),
        # Fields without a known range are kept as delivered.
        ({"precipitationTick": 3.0}, {"precipitationTick": 3.0}),
    ],
)
def test_latest_valid_drops_implausible_values(
    values: dict[str, float], expected: dict[str, float]
) -> None:
    """Values outside the plausible range are removed, range limits are valid."""
    result = latest_valid([measurement(0, values)], NOW, MAX_MEASUREMENT_AGE)
    assert result is not None
    assert result.values == expected


def test_latest_valid_falls_back_when_newest_has_only_implausible_values() -> None:
    """A measurement without any plausible value is skipped."""
    older = measurement(10, {Field.TEMPERATURE: 12.0})
    result = latest_valid(
        [measurement(0, {Field.TEMPERATURE: -999.0}), older], NOW, MAX_MEASUREMENT_AGE
    )
    assert result == older


def test_latest_valid_returns_none_without_plausible_values() -> None:
    """Only implausible values means no measurement at all."""
    result = latest_valid(
        [measurement(0, {Field.TEMPERATURE: -999.0})], NOW, MAX_MEASUREMENT_AGE
    )
    assert result is None


# estimate


def test_estimate_single_station() -> None:
    """One station is used as is, humidity survives the dew point round trip."""
    reading = make_reading("a", 20.0, 50.0)
    result = estimate([reading], None, 0.0)
    assert result.temperature == 20.0
    assert result.spread == 0.0
    assert result.humidity == pytest.approx(50.0)
    assert result.dew_point == pytest.approx(dew_point(20.0, 50.0))
    assert result.absolute_humidity == pytest.approx(absolute_humidity(20.0, 50.0))
    assert result.last_measurement == NOW
    assert result.used == [reading]
    assert result.dropped == []


@pytest.mark.parametrize(
    ("temperatures", "expected"), [([10.0, 12.0, 14.0], 12.0), ([10.0, 12.0], 11.0)]
)
def test_estimate_uses_median_temperature(
    temperatures: list[float], expected: float
) -> None:
    """Temperature is the median, for odd and even station counts."""
    readings = [make_reading(str(i), t) for i, t in enumerate(temperatures)]
    assert estimate(readings, None, 0.0).temperature == expected


def test_estimate_drops_outlier_from_four_stations() -> None:
    """With 4+ stations, a station more than 2.5 K from the median is dropped."""
    readings = [
        make_reading("a", 10.0),
        make_reading("b", 10.5),
        make_reading("c", 11.0),
        make_reading("d", 20.0),
    ]
    result = estimate(readings, None, 0.0)
    assert [r.code for r in result.dropped] == ["d"]
    assert result.temperature == 10.5
    assert result.spread == 1.0


def test_estimate_keeps_station_exactly_at_outlier_limit() -> None:
    """A deviation of exactly 2.5 K is not an outlier."""
    readings = [make_reading(code, 10.0) for code in "abc"] + [make_reading("d", 12.5)]
    result = estimate(readings, None, 0.0)
    assert result.dropped == []
    assert len(result.used) == 4


def test_estimate_keeps_outliers_below_four_stations() -> None:
    """With fewer than 4 stations there is no reliable median to judge outliers."""
    readings = [
        make_reading("a", 10.0),
        make_reading("b", 10.0),
        make_reading("c", 20.0),
    ]
    result = estimate(readings, None, 0.0)
    assert result.dropped == []
    assert result.temperature == 10.0
    assert result.spread == 10.0


def test_estimate_derives_humidity_from_median_dew_point() -> None:
    """Humidity comes from the median dew point, not from the median humidity."""
    readings = [make_reading("cool", 10.0, 90.0), make_reading("warm", 20.0, 40.0)]
    result = estimate(readings, None, 0.0)
    median_dew_point = statistics.median([dew_point(10.0, 90.0), dew_point(20.0, 40.0)])
    assert result.dew_point == pytest.approx(median_dew_point)
    assert result.humidity == pytest.approx(relative_humidity(15.0, median_dew_point))
    assert result.humidity != pytest.approx(65.0, abs=1.0), (
        "humidity must not be the plain median of 90 % and 40 %"
    )


def test_estimate_applies_negative_dew_point_offset() -> None:
    """A negative offset lowers dew point and humidity, the raw value stays."""
    result = estimate([make_reading("a", 20.0, 50.0)], None, -1.3)
    assert result.dew_point == pytest.approx(dew_point(20.0, 50.0) - 1.3)
    assert result.humidity < 50.0
    assert result.humidity_uncorrected == pytest.approx(50.0)


def test_estimate_caps_positive_dew_point_offset_at_saturation() -> None:
    """The corrected dew point never exceeds the temperature (max. 100 %)."""
    result = estimate([make_reading("a", 20.0, 95.0)], None, 3.0)
    assert result.dew_point == 20.0
    assert result.humidity == 100.0


def test_estimate_uses_humidity_of_stations_that_have_it() -> None:
    """Stations without humidity still count for the temperature."""
    readings = [make_reading("a", 20.0, 50.0), make_reading("b", 22.0)]
    result = estimate(readings, None, 0.0)
    assert result.temperature == 21.0
    assert result.dew_point == pytest.approx(dew_point(20.0, 50.0))


def test_estimate_without_any_humidity() -> None:
    """Without humidity there is no dew point and no apparent temperature."""
    wind = Measurement(NOW, {Field.WIND_SPEED: 3.0})
    result = estimate([make_reading("a", 20.0)], wind, 0.0)
    assert result.temperature == 20.0
    assert result.humidity is None
    assert result.dew_point is None
    assert result.absolute_humidity is None
    assert result.apparent_temperature is None


def test_estimate_irradiance_maximum_and_pressure_median() -> None:
    """Irradiance is the maximum (shading), pressure the median of its stations."""
    readings = [
        make_reading(
            "a", 20.0, extra={Field.IRRADIANCE: 100.0, Field.PRESSURE: 1010.0}
        ),
        make_reading("b", 20.0, extra={Field.IRRADIANCE: 300.0}),
        make_reading("c", 20.0),
    ]
    result = estimate(readings, None, 0.0)
    assert result.irradiance == 300.0
    assert result.irradiance_stations == 2
    assert result.pressure == 1010.0


def test_estimate_min_max_temperature_median_without_outliers() -> None:
    """Minimum and maximum are medians of the used stations, outliers don't count."""

    def reading(code: str, temperature: float) -> StationReading:
        return make_reading(
            code,
            temperature,
            extra={
                Field.MIN_TEMPERATURE: temperature - 1,
                Field.MAX_TEMPERATURE: temperature + 1,
            },
        )

    readings = [reading("a", 10.0), reading("b", 10.5), reading("c", 11.0)]
    readings += [reading("outlier", 20.0), make_reading("no_min_max", 10.5)]
    result = estimate(readings, None, 0.0)
    assert [r.code for r in result.dropped] == ["outlier"]
    assert result.min_temperature == 9.5
    assert result.max_temperature == 11.5


def test_estimate_without_min_max_temperature() -> None:
    """Stations that don't measure minimum and maximum leave them empty."""
    result = estimate([make_reading("a", 20.0)], None, 0.0)
    assert result.min_temperature is None
    assert result.max_temperature is None


def test_estimate_wind_values() -> None:
    """Wind comes from the wind station and enables the apparent temperature."""
    wind = Measurement(
        NOW,
        {
            Field.WIND_SPEED: 3.0,
            Field.WIND_GUST: 7.0,
            Field.WIND_DIRECTION: 270.0,
            Field.WIND_GUST_DIRECTION: 250.0,
        },
    )
    result = estimate([make_reading("a", 20.0, 50.0)], wind, 0.0)
    assert result.wind_speed == 3.0
    assert result.wind_gust == 7.0
    assert result.wind_direction == 270.0
    assert result.wind_gust_direction == 250.0
    assert result.apparent_temperature == pytest.approx(
        apparent_temperature(20.0, result.humidity, 3.0)
    )


def test_estimate_falls_back_to_one_second_gust() -> None:
    """Older wind sensors only deliver the 1 s gust."""
    wind = Measurement(NOW, {Field.WIND_SPEED: 3.0, Field.WIND_GUST_1S: 9.0})
    assert estimate([], wind, 0.0).wind_gust == 9.0


def test_estimate_without_wind_has_no_apparent_temperature() -> None:
    """Apparent temperature needs wind."""
    result = estimate([make_reading("a", 20.0, 50.0)], None, 0.0)
    assert result.wind_speed is None
    assert result.apparent_temperature is None


@pytest.mark.parametrize(
    "readings", [[], [make_reading("a", None, 50.0)]], ids=["none", "no_temperature"]
)
def test_estimate_without_temperature_is_empty(readings: list[StationReading]) -> None:
    """Readings without temperature give an empty estimate."""
    assert estimate(readings, None, 0.0) == Estimate()


def test_estimate_sorts_used_stations_by_distance() -> None:
    """Used stations are listed nearest first; the newest timestamp is reported."""
    newest = NOW + timedelta(minutes=10)
    readings = [
        make_reading("far", 20.0, distance_m=300.0),
        make_reading("near", 20.0, distance_m=100.0, timestamp=newest),
        make_reading("middle", 20.0, distance_m=200.0),
    ]
    result = estimate(readings, None, 0.0)
    assert [r.code for r in result.used] == ["near", "middle", "far"]
    assert result.last_measurement == newest
