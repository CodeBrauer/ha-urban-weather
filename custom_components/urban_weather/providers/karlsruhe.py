"""
Sensor City network of the city of Karlsruhe (CityCLIM).

Run by the Stadt Karlsruhe. The ArcGIS FeatureServer "Sensordaten_NodeRED" holds the
latest values of each sensor in layer 1; a query returns them as GeoJSON. The layer
also holds soil, water level and rain sensors, so the query selects the air
temperature sensors.
"""

from __future__ import annotations

from custom_components.urban_weather.const import Field
from custom_components.urban_weather.provider import Network, RequestLimits

from .common import BASEMAP_DE, parse_epoch_ms
from .geojson import GeoJsonFeed

FIELDS: dict[str, Field] = {
    "temp": Field.TEMPERATURE,
    "luftfeuchte": Field.HUMIDITY,
}

AIR_TEMPERATURE_SENSORS = "beschreibung = 'Temperatur-Sensor'"

FEED = GeoJsonFeed(
    station_id="device_id",
    station_name="name",
    timestamp="measured_at",
    params={
        "where": AIR_TEMPERATURE_SENSORS,
        "outFields": "device_id,name,measured_at," + ",".join(FIELDS),
        "f": "geojson",
    },
    parse_time=parse_epoch_ms,
)

# No limits are documented. The sensors report every few minutes and one request
# returns all stations, so a few requests per hour are enough. The cap is the
# integration's own, below the 60 per hour of the other bulk networks.
MEASUREMENT_LIMITS = ((2, 60), (30, 3600))
STATION_LIST_LIMITS = ((2, 900), (4, 3600))
PER_HOUR = 30
PLANNED_BUDGET_PER_HOUR = 24

KARLSRUHE = Network(
    id="karlsruhe",
    name="Sensor City Karlsruhe",
    operator="Stadt Karlsruhe",
    area="Karlsruhe",
    endpoint=(
        "https://geoportal.karlsruhe.de/ags04/rest/services/Hosted/"
        "Sensordaten_NodeRED/FeatureServer/1/query"
    ),
    fields=FIELDS,
    attribution="Stadt Karlsruhe (Sensor City)",
    limits=RequestLimits(
        measurements=MEASUREMENT_LIMITS,
        station_list=STATION_LIST_LIMITS,
        per_hour=PER_HOUR,
        planned_per_hour=PLANNED_BUDGET_PER_HOUR,
    ),
    tiles=BASEMAP_DE,
)
