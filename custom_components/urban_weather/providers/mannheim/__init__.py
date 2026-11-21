"""Climate network of Smart City Mannheim (https://api.smartmannheim.de/doc)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.urban_weather.const import Field
from custom_components.urban_weather.provider import (
    Network,
    RequestLimits,
    SensorProvider,
    TileLayer,
)

from . import stations
from .api import MannheimClimateApi, parse_sensors

if TYPE_CHECKING:
    import aiohttp

    from custom_components.urban_weather.provider import Measurement
    from custom_components.urban_weather.stations import Station

    from .reference import ReferenceData

FIELDS: dict[str, Field] = {
    "temperature": Field.TEMPERATURE,
    "minTemperature": Field.MIN_TEMPERATURE,
    "maxTemperature": Field.MAX_TEMPERATURE,
    "airHumidity": Field.HUMIDITY,
    "dewPoint": Field.DEW_POINT,
    "atmosphericPressure": Field.PRESSURE,
    "irradiation": Field.IRRADIANCE,
    "averageWindSpeed": Field.WIND_SPEED,
    "windGust3s": Field.WIND_GUST,
    "windGust1s": Field.WIND_GUST_1S,
    "averageWindDirection": Field.WIND_DIRECTION,
    "windGustDirection": Field.WIND_GUST_DIRECTION,
}

# Limits per public IP, see docs/en/user/api-limits.md. Documented: 30 measurement
# requests per hour. Observed: short fixed windows (~5 requests per 2 min per server
# instance, at least two instances) and rejected requests count too, so after a 429
# we wait for Retry-After instead of retrying.
MEASUREMENT_BUDGET_PER_HOUR = 30
MEASUREMENT_LIMITS = ((4, 120), (MEASUREMENT_BUDGET_PER_HOUR, 3600))
SENSOR_LIST_LIMITS = ((2, 900), (4, 3600))
# Keep part of the hourly budget free for other clients behind the same IP.
PLANNED_BUDGET_PER_HOUR = 24

MANNHEIM = Network(
    name="Klimamessnetz Mannheim",
    operator="Smart City Mannheim (Open Data)",
    area="Mannheim",
    endpoint="https://api.smartmannheim.de/climate",
    fields=FIELDS,
    attribution="Smart City Mannheim GmbH, dl-de/by-2-0 (opendata.smartmannheim.de)",
    limits=RequestLimits(
        measurements=MEASUREMENT_LIMITS,
        station_list=SENSOR_LIST_LIMITS,
        per_hour=MEASUREMENT_BUDGET_PER_HOUR,
        planned_per_hour=PLANNED_BUDGET_PER_HOUR,
    ),
    # Official German basemap (BKG), open data under CC BY 4.0, no API key needed.
    tiles=TileLayer(
        url=(
            "https://sgx.geodatenzentrum.de/wmts_basemapde/tile/1.0.0/"
            "de_basemapde_web_raster_farbe/default/GLOBAL_WEBMERCATOR/{z}/{y}/{x}.png"
        ),
        attribution="© basemap.de / BKG (CC BY 4.0)",
    ),
)


class MannheimProvider(SensorProvider):
    """The Mannheim API lists sensors (modules); co-located ones form a station."""

    def __init__(
        self,
        network: Network,
        session: aiohttp.ClientSession,
        reference: ReferenceData,
    ) -> None:
        """Use the shared client session and the bundled reference data."""
        super().__init__(network)
        self._api = MannheimClimateApi(session, network)
        self._reference = reference

    async def async_get_station_payload(self) -> dict[str, Any]:
        """Return the raw /sensors response."""
        return await self._api.async_get_sensors_payload()

    def build_stations(self, payload: dict[str, Any]) -> list[Station]:
        """Group the listed sensors into stations with siting metadata."""
        return stations.build_stations(
            parse_sensors(payload, self.network.fields), self._reference
        )

    async def async_get_measurements(self, sensor_id: str) -> list[Measurement]:
        """Return the measurements of the last 60 minutes, newest first."""
        return await self._api.async_get_measurements(sensor_id)

    def lcz(self, latitude: float, longitude: float) -> int | None:
        """Return the mapped LCZ class around Mannheim."""
        return self._reference.lcz(latitude, longitude)

    def district(self, latitude: float, longitude: float) -> str | None:
        """Return the district name of the nearest known station location."""
        return self._reference.district(latitude, longitude)
