# Sensor City Karlsruhe

| | |
|---|---|
| Operator | Stadt Karlsruhe (Sensor City / CityCLIM) |
| Network | Sensor City, air temperature sensors |
| Platform | ArcGIS FeatureServer `Sensordaten_NodeRED`, [geoportal.karlsruhe.de](https://geoportal.karlsruhe.de/sensorcity/Dashboard/) |
| Endpoint | `https://geoportal.karlsruhe.de/ags04/rest/services/Hosted/Sensordaten_NodeRED/FeatureServer/1/query` |
| Access | Public, no key |
| Licence | Not stated |
| Attribution | Stadt Karlsruhe (Sensor City) |
| Map tiles | basemap.de |
| Network id | `karlsruhe` |

## Coverage

About 90 stations across Karlsruhe. All of them measure temperature and humidity; the network
has no wind values. The layer also holds air pressure and irradiance, which the integration
does not read.

## Data

- Layer 1 of the service holds the latest values of each sensor, one feature per sensor. The
  integration queries it for the air temperature sensors and receives them as GeoJSON.
- Each sensor is a station on its own; its `device_id` is the station code, the name is the
  label of the city (for example `173 - Schlossplatz 3 (Kreuzung Kronenstraße)`).
- Sensors report every few minutes. The time of a measurement is given in milliseconds since
  the epoch (UTC).
- The station list and the measurements come from the same query, so each costs one request
  and the number of stations costs no requests.
- The layer has no siting data. The station recommendation works by distance only, see
  [Networks without siting data](../user/stations.md#networks-without-siting-data).

## Limits

No limits are documented. The integration applies a cap of its own, below the caps of the
other networks that deliver all stations in one request.

| Measure | Value |
|---|---|
| Station list | Refreshed at most once a day and stored locally |
| Measurement cache | 9 minutes, shared between all locations |
| Requests sent | At most 2 per minute and 30 per hour |
| Requests planned | At most 24 per hour for all locations together |

One request returns all stations, so the number of stations costs nothing:
[how many stations fit](../user/api-limits.md#one-request-for-all-stations-dortmund-basel-zurich-karlsruhe-dresden).

## Quirks

- The layer also holds soil, water level and rain sensors; the query selects the air
  temperature sensors (`beschreibung = 'Temperatur-Sensor'`).
- Stations without a temperature value are left out.
