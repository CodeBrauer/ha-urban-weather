"""
Urban climate network of the city of Zürich (stadtklima-zuerich.ch).

Run by Umwelt- und Gesundheitsschutz (UGZ). The open data file "measurements/latest"
holds the latest air temperature and relative humidity of each measuring point.
"""

from __future__ import annotations

from custom_components.urban_weather.const import Field
from custom_components.urban_weather.provider import Network, RequestLimits

from .common import OSM_CH
from .geojson import GeoJsonFeed

FIELDS: dict[str, Field] = {
    "temperature_c": Field.TEMPERATURE,
    "humidity_relative_percent": Field.HUMIDITY,
}

FEED = GeoJsonFeed(
    station_id="location_id", station_name="location_name", timestamp="timestamp"
)

# No limits are documented. The file is cached for 60 seconds and new values arrive
# every few minutes, and one request returns all stations, so a few requests per hour
# are enough. The cap is the integration's own, like for Dortmund.
MEASUREMENT_LIMITS = ((2, 60), (60, 3600))
STATION_LIST_LIMITS = ((2, 900), (4, 3600))
PER_HOUR = 60
PLANNED_BUDGET_PER_HOUR = 60

ZURICH = Network(
    id="zurich",
    name="Stadtklimamessnetz Zürich",
    operator="Stadt Zürich, Umwelt- und Gesundheitsschutz (UGZ)",
    area="Zürich",
    endpoint="https://stadtklima-zuerich.ch/ogd/v1/measurements/latest.geojson",
    fields=FIELDS,
    attribution="Stadt Zürich (UGZ), CC0 (stadtklima-zuerich.ch)",
    limits=RequestLimits(
        measurements=MEASUREMENT_LIMITS,
        station_list=STATION_LIST_LIMITS,
        per_hour=PER_HOUR,
        planned_per_hour=PLANNED_BUDGET_PER_HOUR,
    ),
    tiles=OSM_CH,
)
