# Klimamessnetz Dortmund

| | |
|---|---|
| Operator | Stadt Dortmund; built in the project Data2Resilience with Ruhr University Bochum |
| Network | Klimasensoren - Aktuelle Messung |
| Platform | Opendatasoft, [dataset](https://open-data.dortmund.de/explore/dataset/klimasensoren-aktuelle-messungen/) |
| Endpoint | `https://open-data.dortmund.de/api/explore/v2.1` |
| Access | Public, no key |
| Licence | dl-de/zero-2-0 |
| Attribution | Stadt Dortmund, dl-de/zero-2-0 (open-data.dortmund.de) |
| Map tiles | basemap.de |
| Network id | `dortmund` |

## Coverage

76 stations across Dortmund. All of them measure temperature and humidity; about a third
also measure air pressure, global irradiance and wind (speed, gust and direction).

## Data

- The dataset holds one record per sensor with its latest measurement. New values arrive
  every 5 minutes.
- Sensors are grouped into stations by the station id of the dataset, which is also the
  station code (e.g. `DOBHAP`). Within a station the sensor with the most values is used.
- One request returns the values of all stations the locations use, so the number of
  stations costs no requests.
- The dataset has no siting data. The station recommendation works by distance only, see
  [Networks without siting data](../user/stations.md#networks-without-siting-data).

## Limits

Every response reports a quota of 50,000 requests per day (about 2,083 per hour); no other
limits are documented.

| Measure | Value |
|---|---|
| Station list | Refreshed at most once a day and stored locally |
| Measurement cache | 9 minutes, shared between all locations |
| Requests sent | At most 2 per minute and 60 per hour |
| Requests planned | At most 60 per hour for all locations together |

One request returns all stations, so the number of stations costs nothing:
[how many stations fit](../user/api-limits.md#one-request-for-all-stations-dortmund).

## Quirks

- Black globe sensors are left out: they report a radiant temperature as air temperature,
  which reads several kelvin above the air temperature in sunshine.
- Air pressure is delivered in kPa and converted to hPa.
- A sensor that has been silent for 24 hours is left out of its station if the station has a
  current sensor, so a sensor that stopped sending does not shadow its replacement.
