"""
Climate network of the canton of Basel-Stadt (data.bs.ch, Opendatasoft).

Smart Climate Luftklima, operated with meteoblue. Dataset 100009 is a time series of
the sensors (about one value per hour), so every request has a time window.
"""

from __future__ import annotations

from datetime import timedelta

from custom_components.urban_weather.const import Field
from custom_components.urban_weather.provider import Network, RequestLimits

from .common import OSM_CH
from .opendatasoft import OpendatasoftDataset

# Precipitation is published too, but not used yet.
FIELDS: dict[str, Field] = {"meta_airtemp": Field.TEMPERATURE}

# The sensors report about hourly, with gaps; the station list also keeps sensors that
# skipped a few hours.
DATASET = OpendatasoftDataset(
    id="100009",
    sensor_id="name_original",
    station_id="name_original",
    sensor_name="name_custom",
    position="coords",
    timestamp="dates_max_date",
    station_window=timedelta(hours=24),
    measurement_window=timedelta(hours=3),
)

# Every response reports a quota of 500,000 requests per day (X-RateLimit-Limit); no
# other limits are documented. One request returns all sensors in use and the data
# changes hourly, so a few requests per hour are enough.
DAILY_QUOTA = 500_000
HOURS_PER_DAY = 24
MEASUREMENT_LIMITS = ((2, 60), (60, 3600))
STATION_LIST_LIMITS = ((2, 900), (4, 3600))
PLANNED_BUDGET_PER_HOUR = 60

BASEL = Network(
    id="basel",
    name="Smart Climate Luftklima Basel",
    operator="Kanton Basel-Stadt (Open Data)",
    area="Basel",
    endpoint="https://data.bs.ch/api/explore/v2.1",
    fields=FIELDS,
    attribution="Kanton Basel-Stadt, CC BY 4.0 (data.bs.ch)",
    limits=RequestLimits(
        measurements=MEASUREMENT_LIMITS,
        station_list=STATION_LIST_LIMITS,
        per_hour=DAILY_QUOTA // HOURS_PER_DAY,
        planned_per_hour=PLANNED_BUDGET_PER_HOUR,
    ),
    tiles=OSM_CH,
    # About one value per sensor per hour, with gaps.
    max_age=timedelta(minutes=90),
)
