# Smart Climate Luftklima Basel

| | |
|---|---|
| Operator | Canton of Basel-Stadt, with meteoblue |
| Network | Smart Climate Luftklima |
| Platform | Opendatasoft, [dataset 100009](https://data.bs.ch/explore/dataset/100009/) |
| Endpoint | `https://data.bs.ch/api/explore/v2.1` |
| Access | Public, no key |
| Licence | CC BY 4.0 |
| Attribution | Kanton Basel-Stadt, CC BY 4.0 (data.bs.ch) |
| Map tiles | osm.ch |
| Network id | `basel` |

## Coverage

About 70 active stations in Basel and its surroundings; a few are across the border in
Germany and France. Many are mounted on street lamps. All of them measure temperature. The
network has no humidity, so there is no dew point or apparent temperature. Precipitation
is published too, but not used yet.

## Data

- The dataset is a time series, not one record per sensor: each sensor reports about once an
  hour, with gaps. The integration uses the newest record of each sensor.
- Every request has a time window, because the whole dataset holds millions of records: the
  station list looks back 24 hours, the measurements 3 hours.
- A measurement counts for 90 minutes instead of the usual 40, so the hourly values do not
  drop out for much of each hour.
- The station id, the sensor id and the sensor name are the ones of the dataset, one sensor
  per station.
- One request returns the values of all stations the locations use, so the number of
  stations costs no requests.
- The dataset has no siting data. The station recommendation works by distance only, see
  [Networks without siting data](../user/stations.md#networks-without-siting-data).

## Limits

Every response reports a quota of 500,000 requests per day (about 20,800 per hour); no other
limits are documented.

| Measure | Value |
|---|---|
| Station list | Refreshed at most once a day and stored locally |
| Measurement cache | 9 minutes, shared between all locations |
| Requests sent | At most 2 per minute and 60 per hour |
| Requests planned | At most 60 per hour for all locations together |

One request returns all stations, so the number of stations costs nothing:
[how many stations fit](../user/api-limits.md#one-request-for-all-stations-dortmund-basel-zurich-karlsruhe).

## Quirks

- The values are raw data that the operator does not check for plausibility.
