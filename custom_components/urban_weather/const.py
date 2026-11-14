"""Constants for the Urban Weather integration."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "urban_weather"
REPOSITORY_URL = "https://github.com/CodeBrauer/ha-urban-weather"

REQUEST_TIMEOUT_S = 15
DEFAULT_RETRY_AFTER_S = 120
CATCH_UP_MARGIN_S = 2

SENSOR_LIST_MAX_AGE = timedelta(hours=24)
# How long a station added to the list is suggested for existing locations.
NEW_STATION_PERIOD = timedelta(days=30)
MEASUREMENT_CACHE_TTL = timedelta(minutes=9)
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.sensors"

# Config entry data
CONF_ENVIRONMENT = "environment"
# Config entry options
CONF_TEMPERATURE_SENSORS = "temperature_sensors"
CONF_WIND_SENSOR = "wind_sensor"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_DEW_POINT_OFFSET = "dew_point_offset"

NO_WIND_SENSOR = "none"
SCAN_INTERVAL_CHOICES_MIN = (10, 15, 20, 30)
DEFAULT_SCAN_INTERVAL_MIN = 15
DEFAULT_DEW_POINT_OFFSET_K = 0.0
DEW_POINT_OFFSET_LIMIT_K = 3.0
DEFAULT_SEARCH_RADIUS_M = 3000
MAX_SEARCH_RADIUS_M = 10_000

# Station selection
SINGLE_STATION_MAX_DISTANCE_M = 1000
MAX_SELECTED_STATIONS = 6
RECOMMENDED_STATIONS = 4
CANDIDATE_STATIONS = 15
MAP_CANDIDATE_STATIONS = 60
WIND_CANDIDATE_STATIONS = 8
MAX_COVERAGE_DISTANCE_M = 10_000

# Interactive station map (external step of the config flow)
MAP_SESSION_TTL = timedelta(minutes=30)
MAP_URL = f"/api/{DOMAIN}/map/{{token}}"
STATIC_URL = f"/{DOMAIN}_static"

# Aggregation
MAX_MEASUREMENT_AGE = timedelta(minutes=40)
# Without fresh data the last estimate stays until its newest measurement is
# max(KEEP_VALUES_MIN_AGE, KEEP_VALUES_INTERVALS x update interval) old.
KEEP_VALUES_MIN_AGE = timedelta(minutes=60)
KEEP_VALUES_INTERVALS = 3
OUTLIER_MIN_STATIONS = 4
OUTLIER_MAX_DEVIATION_K = 2.5
STATION_OFFLINE_AFTER = timedelta(hours=24)

# Data of the fixable repair issues
ISSUE_ENTRY_ID = "entry_id"
ISSUE_SENSOR_ID = "sensor_id"


class Environment(StrEnum):
    """Surroundings of a location, grouped from Local Climate Zones."""

    DENSE = "dense"
    OPEN_BUILT = "open_built"
    INDUSTRIAL = "industrial"
    GREEN = "green"


# Local Climate Zones (Stewart & Oke) 1-10 built types, 11-17 land cover types.
LCZ_ENVIRONMENT: dict[int, Environment] = {
    1: Environment.DENSE,
    2: Environment.DENSE,
    3: Environment.DENSE,
    4: Environment.OPEN_BUILT,
    5: Environment.OPEN_BUILT,
    6: Environment.OPEN_BUILT,
    7: Environment.INDUSTRIAL,
    8: Environment.INDUSTRIAL,
    9: Environment.OPEN_BUILT,
    10: Environment.INDUSTRIAL,
    **dict.fromkeys(range(11, 18), Environment.GREEN),
}


class MountZone(StrEnum):
    """Vertical zone of a station."""

    STREET = "street"
    ROOF = "roof"
    HIGH_POINT = "high_point"


class Field(StrEnum):
    """Measured values the integration uses; providers map their fields to these."""

    TEMPERATURE = "temperature"
    MIN_TEMPERATURE = "min_temperature"
    MAX_TEMPERATURE = "max_temperature"
    HUMIDITY = "humidity"
    DEW_POINT = "dew_point"
    PRESSURE = "pressure"
    IRRADIANCE = "irradiance"
    WIND_SPEED = "wind_speed"
    WIND_GUST = "wind_gust"
    WIND_GUST_1S = "wind_gust_1s"
    WIND_DIRECTION = "wind_direction"
    WIND_GUST_DIRECTION = "wind_gust_direction"
