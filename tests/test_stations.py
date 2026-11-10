"""Tests for the station recommendation."""

from __future__ import annotations

import pytest

from custom_components.urban_weather.api import ApiSensor, parse_sensors
from custom_components.urban_weather.const import Environment, Field, MountZone
from custom_components.urban_weather.reference import load_reference_data
from custom_components.urban_weather.stations import (
    LczSource,
    Recommendation,
    RecommendationReason,
    Station,
    build_stations,
    recommend,
)

from .common import HOME, LCZ_OPEN_BUILT, make_station, sensors_payload

LCZ_DENSE = 2
LCZ_GREEN = 14
RADIUS_M = 3000


def recommend_for(
    stations: list[Station], environment: Environment = Environment.OPEN_BUILT
) -> Recommendation | None:
    """Recommend stations for HOME within the default search radius."""
    return recommend(stations, *HOME, environment, RADIUS_M)


def codes(stations: list[Station]) -> list[str]:
    """Return the station codes in order."""
    return [station.code for station in stations]


def test_nearest_station_used_alone_when_it_fits() -> None:
    """A street station within 1 km with the same surroundings is used alone."""
    near = make_station("near", 400)
    result = recommend_for([make_station("other", 800), near])
    assert result is not None
    assert result.stations == [near]
    assert result.nearest == near
    assert result.reason is RecommendationReason.NEAREST_FITS


def test_combination_when_nearest_is_too_far() -> None:
    """Beyond 1 km, up to 4 stations within the radius are combined."""
    stations = [make_station(f"s{i}", 1200 + i * 300) for i in range(6)]
    result = recommend_for(stations)
    assert result is not None
    assert codes(result.stations) == ["s0", "s1", "s2", "s3"]
    assert result.reason is RecommendationReason.NEAREST_TOO_FAR


def test_combination_when_nearest_has_other_surroundings() -> None:
    """A close station in other surroundings is combined with others, not alone."""
    dense = make_station("dense", 500, lcz=LCZ_DENSE)
    result = recommend_for([dense, make_station("open", 1500)])
    assert result is not None
    assert codes(result.stations) == ["open", "dense"]
    assert result.nearest == dense
    assert result.reason is RecommendationReason.NEAREST_OTHER_ENVIRONMENT


def test_combination_prefers_same_surroundings() -> None:
    """Same surroundings first (by distance), filled up with the closest others."""
    stations = [
        make_station("dense1", 1200, lcz=LCZ_DENSE),
        make_station("open1", 1300),
        make_station("green", 1400, lcz=LCZ_GREEN),
        make_station("open2", 1500),
        make_station("dense2", 1600, lcz=LCZ_DENSE),
    ]
    result = recommend_for(stations)
    assert result is not None
    assert codes(result.stations) == ["open1", "open2", "dense1", "green"]


@pytest.mark.parametrize(
    ("zone", "height_above_ground"),
    [(MountZone.ROOF, 0), (MountZone.HIGH_POINT, 0), (MountZone.STREET, 5)],
)
def test_elevated_stations_are_not_recommended(
    zone: MountZone, height_above_ground: int
) -> None:
    """Roof and high-point stations measure other air than at street level."""
    elevated = make_station(
        "roof", 100, zone=zone, height_above_ground=height_above_ground
    )
    street = make_station("street", 600)
    result = recommend_for([elevated, street])
    assert result is not None
    assert result.stations == [street]
    assert result.nearest == street


def test_station_without_catalogue_metadata_counts_as_street_level() -> None:
    """LoRa stations have no zone/height; they are candidates like street stations."""
    lora = make_station("lora", 300, zone=None, height_above_ground=None)
    result = recommend_for([lora])
    assert result is not None
    assert result.stations == [lora]


def test_nearest_station_without_lcz_is_not_used_alone() -> None:
    """Unknown surroundings never count as a fit."""
    unknown = make_station("unknown", 300, lcz=None)
    result = recommend_for([unknown, make_station("open", 1500)])
    assert result is not None
    assert codes(result.stations) == ["open", "unknown"]
    assert result.reason is RecommendationReason.NEAREST_OTHER_ENVIRONMENT


def test_nearest_stations_used_when_none_within_radius() -> None:
    """Outside the network a recommendation still uses the 4 nearest stations."""
    stations = [make_station(f"s{i}", 4000 + i * 1000) for i in range(6)]
    result = recommend_for(stations)
    assert result is not None
    assert codes(result.stations) == ["s0", "s1", "s2", "s3"]
    assert result.reason is RecommendationReason.NEAREST_TOO_FAR


@pytest.mark.parametrize(
    "stations",
    [
        [],
        [
            make_station("roof", 100, zone=MountZone.ROOF),
            make_station("wind", 200, temperature=False, wind=True),
        ],
    ],
    ids=["no_stations", "no_street_temperature_station"],
)
def test_no_recommendation_without_candidates(stations: list[Station]) -> None:
    """Without a street-level temperature station there is nothing to recommend."""
    assert recommend_for(stations) is None


def test_wind_station_is_nearest_with_wind_sensor() -> None:
    """Wind may come from any station, including elevated ones."""
    roof = make_station("roof", 800, zone=MountZone.ROOF, wind=True)
    result = recommend_for(
        [
            make_station("street", 300),
            roof,
            make_station("wind_only", 1500, temperature=False, wind=True),
        ]
    )
    assert result is not None
    assert codes(result.stations) == ["street"]
    assert result.wind_station == roof


def test_no_wind_station_without_wind_sensors() -> None:
    """Without wind sensors the recommendation has no wind station."""
    result = recommend_for([make_station("street", 300)])
    assert result is not None
    assert result.wind_station is None


# build_stations with the recorded sensor list and the bundled reference data


@pytest.fixture(scope="module")
def stations() -> dict[str, Station]:
    """Stations around HOME by the name of their temperature (else wind) sensor."""
    built = build_stations(parse_sensors(sensors_payload()), load_reference_data())
    return {
        (station.temperature_sensor or station.wind_sensor).name: station
        for station in built
    }


def test_sensors_at_one_mast_form_one_station(stations: dict[str, Station]) -> None:
    """53 sensors: temperature and wind sensors at the same spot are combined."""
    assert len(stations) == 27
    station = stations["2507LH096"]
    assert station.code == "2507LH096"
    assert station.wind_sensor is not None
    assert station.wind_sensor.name == "2507LW182"


def test_catalogued_station(stations: dict[str, Station]) -> None:
    """Catalogue stations get their code, LCZ and siting from the catalogue."""
    station = stations["0101-046-21"]
    assert station.code == "0101-046"
    assert (station.lcz, station.lcz_source) == (LCZ_OPEN_BUILT, LczSource.CATALOG)
    assert (station.zone, station.height_above_ground) == (MountZone.STREET, 0)
    assert station.district == "Seckenheim"


def test_lora_station_uses_lcz_map(stations: dict[str, Station]) -> None:
    """Stations missing in the catalogue get the LCZ from the map, no siting data."""
    station = stations["2507LH051"]
    assert (station.lcz, station.lcz_source) == (LCZ_OPEN_BUILT, LczSource.MAP)
    assert station.zone is None
    assert not station.is_elevated


def test_newer_temperature_sensor_preferred(stations: dict[str, Station]) -> None:
    """Two temperature sensors at one mast: the one with more parameters is used."""
    station = stations["2507LH076"]
    assert station.wind_sensor is not None
    assert station.wind_sensor.name == "2306LW049"
    assert Field.PRESSURE in station.temperature_sensor.parameters


def test_wind_only_station(stations: dict[str, Station]) -> None:
    """A wind sensor without temperature sensor nearby is a station of its own."""
    station = stations["2304LW088"]
    assert station.temperature_sensor is None
    assert station.code == "2304LW088"


def test_sensors_without_temperature_or_wind_are_ignored() -> None:
    """Sensors measuring neither temperature nor wind do not form a station."""
    pressure = ApiSensor("p1", "p1", *HOME, frozenset({Field.PRESSURE}))
    assert build_stations([pressure], load_reference_data()) == []
