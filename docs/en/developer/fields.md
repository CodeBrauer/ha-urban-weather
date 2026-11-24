# Fields

A network maps its own field names to the `Field` values of the integration (`const.py`),
in the `fields` of its `Network`. This page lists the units, entities and combination rules
of every value the integration uses or plans to use, so all networks map a value the same
way.

## Rules

- The provider delivers the unit of the table and converts if the network uses another one
  (e.g. kPa or Pa to hPa).
- A sensor is only created if one of the selected stations measures its value.
- A planned value gets its `Field` member, plausible range and sensor with the first network
  that delivers it, following this page.
- Values without a Home Assistant device class for their unit (e.g. NOx, UV intensity) are
  not planned.

## Current fields

| `Field` | Unit | Entity (device class) | Combined |
|---|---|---|---|
| `TEMPERATURE` | °C | Temperature (`temperature`) | Median |
| `MIN_TEMPERATURE`, `MAX_TEMPERATURE` | °C | Temperature minimum, maximum (`temperature`) | Median |
| `HUMIDITY` | % | Humidity (`humidity`) | Via the dew point |
| `DEW_POINT` | °C | None, the dew point is calculated from temperature and humidity | Not used |
| `PRESSURE` | hPa | Atmospheric pressure (`atmospheric_pressure`) | Median |
| `IRRADIANCE` | W/m² | Global irradiance (`irradiance`) | Maximum |
| `WIND_SPEED` | m/s | Wind speed (`wind_speed`) | Wind station |
| `WIND_GUST`, `WIND_GUST_1S` | m/s | Wind gust (`wind_speed`) | Wind station |
| `WIND_DIRECTION`, `WIND_GUST_DIRECTION` | ° | Wind direction, gust direction (`wind_direction`) | Wind station |

How the stations are combined, the plausible ranges and the calculated values (dew point,
absolute humidity, apparent temperature) are described in [Aggregation](aggregation.md).

## Planned fields

| `Field` | Unit | Entity (device class) | Combined | Planned with |
|---|---|---|---|---|
| `PRECIPITATION` | mm/h | Precipitation intensity (`precipitation_intensity`) | Median | Basel, Dortmund ([#103](https://github.com/CodeBrauer/ha-urban-weather/issues/103)) |
| `ILLUMINANCE` | lx | Illuminance (`illuminance`) | Maximum | openSenseMap ([#66](https://github.com/CodeBrauer/ha-urban-weather/issues/66)) |
| `PM1` | µg/m³ | PM1 (`pm1`) | Median | sensor.community ([#65](https://github.com/CodeBrauer/ha-urban-weather/issues/65)) |
| `PM25` | µg/m³ | PM2.5 (`pm25`) | Median | openSenseMap, sensor.community, Wien ([#64](https://github.com/CodeBrauer/ha-urban-weather/issues/64)) |
| `PM10` | µg/m³ | PM10 (`pm10`) | Median | openSenseMap, sensor.community, Wien |
| `NITROGEN_DIOXIDE` | µg/m³ | Nitrogen dioxide (`nitrogen_dioxide`) | Median | Wien |
| `OZONE` | µg/m³ | Ozone (`ozone`), also on the weather entity | Median | Wien |
| `SULPHUR_DIOXIDE` | µg/m³ | Sulphur dioxide (`sulphur_dioxide`) | Median | Wien |
| `CARBON_MONOXIDE` | mg/m³ | Carbon monoxide (`carbon_monoxide`) | Median | Wien |

- **Precipitation** is an intensity, not an amount per interval, because networks report
  over different intervals: the precipitation of the last hour in mm is the mean intensity
  in mm/h, an amount per 5 minutes is multiplied by 12.
- **Illuminance** uses the maximum like the irradiance, because sensors are often shaded.
- **Air pollutants** use the median of the selected stations that measure the value. Levels
  at traffic sites and in the background differ strongly; the stations are not filtered by
  siting, the user chooses them.
- **Low-cost particle sensors** read too high at high humidity. There is no correction yet.
- An air quality index is not calculated.
