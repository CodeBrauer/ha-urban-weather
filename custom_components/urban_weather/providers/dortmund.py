"""
Climate network of the city of Dortmund (open-data.dortmund.de, Opendatasoft).

Built in the research project Data2Resilience with Ruhr University Bochum. Dataset
"Klimasensoren - Aktuelle Messung": the latest values of each sensor, every 5 minutes.
"""

from __future__ import annotations

from custom_components.urban_weather.const import Field
from custom_components.urban_weather.provider import Network, RequestLimits

from .common import BASEMAP_DE
from .opendatasoft import OpendatasoftDataset

FIELDS: dict[str, Field] = {
    "air_temperature": Field.TEMPERATURE,
    "data_relative_humidity": Field.HUMIDITY,
    "data_atmospheric_pressure": Field.PRESSURE,
    "data_solar_radiation": Field.IRRADIANCE,
    "data_wind_speed": Field.WIND_SPEED,
    "data_maximum_wind_speed": Field.WIND_GUST,
    "data_wind_direction": Field.WIND_DIRECTION,
}

DATASET = OpendatasoftDataset(
    id="klimasensoren-aktuelle-messungen",
    sensor_id="device_id",
    station_id="data_station_id",
    sensor_name="sensormodell",
    position="standort",
    timestamp="measured_at",
    # Black globe sensors report a radiant temperature as air_temperature; it reads
    # several kelvin above the air temperature in sunshine.
    where='sensormodell != "Blackglobe"',
    factors={"data_atmospheric_pressure": 10.0},  # kPa -> hPa
)

# Every response reports a quota of 50,000 requests per day (X-RateLimit-Limit); no
# other limits are documented. New values arrive every 5 minutes, and one request
# returns all sensors in use, so a few requests per hour are enough.
DAILY_QUOTA = 50_000
HOURS_PER_DAY = 24
MEASUREMENT_LIMITS = ((2, 60), (60, 3600))
STATION_LIST_LIMITS = ((2, 900), (4, 3600))
PLANNED_BUDGET_PER_HOUR = 60

DORTMUND = Network(
    id="dortmund",
    name="Klimamessnetz Dortmund",
    operator="Stadt Dortmund (Open Data)",
    area="Dortmund",
    endpoint="https://open-data.dortmund.de/api/explore/v2.1",
    fields=FIELDS,
    attribution="Stadt Dortmund, dl-de/zero-2-0 (open-data.dortmund.de)",
    limits=RequestLimits(
        measurements=MEASUREMENT_LIMITS,
        station_list=STATION_LIST_LIMITS,
        per_hour=DAILY_QUOTA // HOURS_PER_DAY,
        planned_per_hour=PLANNED_BUDGET_PER_HOUR,
    ),
    tiles=BASEMAP_DE,
)
