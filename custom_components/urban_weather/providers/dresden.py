"""
KLIPS temperature sensor network of the city of Dresden.

Run by the Landeshauptstadt Dresden (Umweltamt). The city's WFS holds hourly air
temperature and relative humidity of each sensor, one feature per sensor, value and
hour, since 2023. Without a time filter a request returns that whole history, oldest
first, so every request selects a window.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from custom_components.urban_weather.const import Field
from custom_components.urban_weather.provider import Network, RequestLimits

from .common import BASEMAP_DE
from .geojson import GeoJsonFeed, TimeWindow

# Values of the `bemerk` property -> Field.
FIELDS: dict[str, Field] = {
    "air_temperature": Field.TEMPERATURE,
    "rel_humidity": Field.HUMIDITY,
}

# Display names: some start with "$" or "#" (meaning undocumented).
NAME_MARKS = "$#"

# Times are Central European Time all year, without daylight saving time.
CET = timezone(timedelta(hours=1), "CET")
TIME_FORMAT = "%d.%m.%Y %H:%M:%S"

# Values arrive one to two hours after the full hour (some sensors later), so the
# newest value of a sensor is up to about three hours old.
MAX_AGE = timedelta(hours=4)


def parse_time(value: Any) -> datetime | None:
    """Return a time like `26.11.2026 21:00:00` (Central European Time), else None."""
    try:
        return datetime.strptime(str(value), TIME_FORMAT).replace(tzinfo=CET)
    except ValueError:
        return None


def clean_name(value: str) -> str:
    """Return a station name without the leading marks and the spaces after them."""
    return value.strip().lstrip(NAME_MARKS).strip()


def measured_after(time: datetime) -> dict[str, str]:
    """
    Return the WFS filter selecting the values measured after a time (FES 2.0).

    The service compares about an hour earlier than the literal, so the window is a
    little longer than asked for.
    """
    literal = time.astimezone(CET).replace(tzinfo=None).isoformat(timespec="seconds")
    return {
        "FILTER": (
            '<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0">'
            "<fes:PropertyIsGreaterThan>"
            "<fes:ValueReference>messzeit</fes:ValueReference>"
            f"<fes:Literal>{literal}</fes:Literal>"
            "</fes:PropertyIsGreaterThan>"
            "</fes:Filter>"
        )
    }


FEED = GeoJsonFeed(
    station_id="device",
    station_name="bezeichnung",
    timestamp="messzeit",
    params={
        "NodeId": "2093",
        "Service": "WFS",
        "Version": "2.0.0",
        "Request": "GetFeature",
        "TypeNames": "cls:L1625",
        "outputFormat": "application/geo+json",
        "SrsName": "urn:ogc:def:crs:EPSG::4326",
    },
    # With gzip or deflate the server never ends the chunked response, so the request
    # runs into the timeout although the whole body has arrived.
    headers={"Accept-Encoding": "identity"},
    parse_time=parse_time,
    parse_name=clean_name,
    parameter="bemerk",
    value="wert_n",
    window=TimeWindow(
        params=measured_after,
        station_list=timedelta(hours=24),
        measurements=MAX_AGE,
    ),
    # The 24 h station list also holds sensors that stopped sending.
    current_within=MAX_AGE,
    # The two values of an hour can arrive in different hours.
    fill_within=timedelta(hours=1),
)

# No limits are documented. Values are hourly and one request returns all stations,
# so a refresh every 15 minutes is enough; the budget plans for 3 locations at that
# interval. The cap is the integration's own.
MEASUREMENT_LIMITS = ((2, 60), (24, 3600))
STATION_LIST_LIMITS = ((2, 900), (4, 3600))
PER_HOUR = 24
PLANNED_BUDGET_PER_HOUR = 12

DRESDEN = Network(
    id="dresden",
    name="KLIPS Dresden",
    operator="Landeshauptstadt Dresden, Umweltamt",
    area="Dresden",
    endpoint="https://kommisdd.dresden.de/net3/public/ogc.ashx",
    fields=FIELDS,
    attribution="Landeshauptstadt Dresden (KLIPS sensor network), dl-de/by-2-0",
    limits=RequestLimits(
        measurements=MEASUREMENT_LIMITS,
        station_list=STATION_LIST_LIMITS,
        per_hour=PER_HOUR,
        planned_per_hour=PLANNED_BUDGET_PER_HOUR,
    ),
    tiles=BASEMAP_DE,
    max_age=MAX_AGE,
)
