"""Constants for the Urban Weather integration."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "urban_weather"
ATTRIBUTION = "Smart City Mannheim GmbH, dl-de/by-2-0 (opendata.smartmannheim.de)"
REPOSITORY_URL = "https://github.com/CodeBrauer/ha-urban-weather"

API_BASE_URL = "https://api.smartmannheim.de/climate"
REQUEST_TIMEOUT_S = 15
DEFAULT_RETRY_AFTER_S = 120

# Client-side mirror of the API limits (per public IP, see docs/en/user/api-limits.md).
# Documented: 30 measurement requests per hour. Observed: short fixed windows (~5
# requests per 2 min per server instance, at least two instances) and rejected
# requests count too, so after a 429 we wait for Retry-After instead of retrying.
MEASUREMENT_BUDGET_PER_HOUR = 30
# (max requests, window in seconds); every window must have room for a request.
MEASUREMENT_LIMITS = ((4, 120), (MEASUREMENT_BUDGET_PER_HOUR, 3600))
SENSOR_LIST_LIMITS = ((2, 900), (4, 3600))
CATCH_UP_MARGIN_S = 2
# Keep part of the hourly budget free for other clients behind the same IP.
PLANNED_BUDGET_PER_HOUR = 24

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
STATION_CLUSTER_RADIUS_M = 15
SINGLE_STATION_MAX_DISTANCE_M = 1000
MAX_SELECTED_STATIONS = 6
RECOMMENDED_STATIONS = 4
CANDIDATE_STATIONS = 15
MAP_CANDIDATE_STATIONS = 60
WIND_CANDIDATE_STATIONS = 8
MAX_COVERAGE_DISTANCE_M = 10_000
CATALOG_MATCH_RADIUS_M = 30
DISTRICT_MATCH_RADIUS_M = 750

# Interactive station map (external step of the config flow)
MAP_SESSION_TTL = timedelta(minutes=30)
MAP_URL = f"/api/{DOMAIN}/map/{{token}}"
STATIC_URL = f"/{DOMAIN}_static"
# Official German basemap (BKG), open data under CC BY 4.0, no API key needed.
TILE_URL = (
    "https://sgx.geodatenzentrum.de/wmts_basemapde/tile/1.0.0/"
    "de_basemapde_web_raster_farbe/default/GLOBAL_WEBMERCATOR/{z}/{y}/{x}.png"
)
TILE_ATTRIBUTION = "© basemap.de / BKG (CC BY 4.0)"

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
    """Vertical zone of a station (metadata catalogue Tab. 43)."""

    STREET = "street"
    ROOF = "roof"
    HIGH_POINT = "high_point"


CATALOG_ZONES: dict[int, MountZone] = {
    1: MountZone.STREET,
    2: MountZone.ROOF,
    3: MountZone.HIGH_POINT,
}


class Field(StrEnum):
    """Measurement fields delivered by the API."""

    TEMPERATURE = "temperature"
    MIN_TEMPERATURE = "minTemperature"
    MAX_TEMPERATURE = "maxTemperature"
    HUMIDITY = "airHumidity"
    DEW_POINT = "dewPoint"
    PRESSURE = "atmosphericPressure"
    IRRADIANCE = "irradiation"
    WIND_SPEED = "averageWindSpeed"
    WIND_GUST = "windGust3s"
    WIND_GUST_1S = "windGust1s"
    WIND_DIRECTION = "averageWindDirection"
    WIND_GUST_DIRECTION = "windGustDirection"
