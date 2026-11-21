# Entities

Every location provides sensors and a weather entity. Values are measured every 10 minutes
and arrive with 10–20 minutes delay; measurements older than 40 minutes are not used.

## Sensors

A sensor is only created if one of the selected stations measures its value.

| Sensor | Unit | Created when | Value |
|---|---|---|---|
| Temperature | °C | always | Median of the stations |
| Temperature (minimum) | °C | stations measure it | Median of the stations' minimum in the last 10-minute interval. Disabled by default. |
| Temperature (maximum) | °C | stations measure it | Median of the stations' maximum in the last 10-minute interval. Disabled by default. |
| Humidity | % | stations measure humidity | Calculated from the dew point and the temperature |
| Dew point | °C | stations measure humidity | Median dew point of the stations, plus the dew point correction |
| Absolute humidity | g/m³ | stations measure humidity | Calculated from temperature and humidity |
| Apparent temperature | °C | humidity and a wind station | Temperature as felt, including humidity and wind |
| Atmospheric pressure | hPa | stations measure it | Median of the stations |
| Global irradiance | W/m² | stations measure it | Maximum of the stations, because street-level sensors are often shaded |
| Wind speed | km/h | wind station | Mean wind speed (the API delivers m/s) |
| Wind gust | km/h | wind station measures a gust | 3-second gust, else 1-second gust |
| Wind direction | ° | wind station measures it | Mean wind direction |
| Wind gust direction | ° | wind station measures it | Direction of the gust. Disabled by default. |
| Stations used | | always | Diagnostic: stations that delivered current data, without outliers |
| Temperature spread | K | always | Diagnostic: difference between the warmest and the coldest station used |
| Last measurement | | always | Diagnostic: time of the newest measurement used |

How the stations are combined is described in [Aggregation](../developer/aggregation.md).

### Attributes of the temperature sensor

| Attribute | Content |
|---|---|
| `stations` | Per station code: `temperature`, `humidity` (only if stations measure it), `distance_km` and `timestamp` of the reading used |
| `dropped_outliers` | Codes of stations left out as outliers |
| `humidity_uncorrected` | Humidity without the dew point correction (only if stations measure humidity) |

## Weather entity

The weather entity shows the current temperature, apparent temperature, dew point, humidity,
pressure, wind speed, gust and direction, as far as the selected stations measure them.
It has no forecast.

The condition is estimated from the global irradiance, because the network has no cloud or
rain sensors:

| Condition | Measured irradiance compared to a clear sky |
|---|---|
| Sunny | at least 55 % |
| Partly cloudy | at least 25 % |
| Cloudy | less than 25 % |
| Unknown | at night, with the sun lower than 10° or with fewer than 3 stations measuring irradiance |

<div class="screenshots" markdown>

![Weather entity details](../screenshots/09-weather.png)

</div>

![Values on a dashboard](../screenshots/07-dashboard.png)

## When values are missing

If the API is unreachable or rate limited, the entities keep their last values until the last
measurement is 60 minutes old (or three update intervals, if that is longer). Then they
become unavailable. See [Repairs and troubleshooting](troubleshooting.md).
