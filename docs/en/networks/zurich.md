# Stadtklimamessnetz Zürich

| | |
|---|---|
| Operator | Stadt Zürich, Umwelt- und Gesundheitsschutz (UGZ) |
| Network | Stadtklima Zürich, latest measurements |
| Platform | GeoJSON file, [stadtklima-zuerich.ch](https://stadtklima-zuerich.ch/) |
| Endpoint | `https://stadtklima-zuerich.ch/ogd/v1/measurements/latest.geojson` |
| Access | Public, no key |
| Licence | CC0 |
| Attribution | Stadt Zürich (UGZ), CC0 (stadtklima-zuerich.ch) |
| Map tiles | osm.ch (OpenStreetMap, Swiss style) |
| Network id | `zurich` |

## Coverage

107 stations across Zürich. All of them measure temperature and humidity; the network has
no air pressure, irradiance or wind values.

## Data

- The file is a GeoJSON FeatureCollection with one point per measuring point and its latest
  values.
- Each measuring point is a station on its own; its `location_id` is the station code.
- The station list and the measurements come from the same file, so each costs one request
  and the number of stations costs no requests.
- The file has no siting data. The station recommendation works by distance only, see
  [Networks without siting data](../user/stations.md#networks-without-siting-data).

## Limits

No limits are documented. The server caches the file for 60 seconds, so the integration
applies the same cap as for Dortmund.

| Measure | Value |
|---|---|
| Station list | Refreshed at most once a day and stored locally |
| Measurement cache | 9 minutes, shared between all locations |
| Requests sent | At most 2 per minute and 60 per hour |
| Requests planned | At most 60 per hour for all locations together |

One request returns all stations, so the number of stations costs nothing:
[how many stations fit](../user/api-limits.md#one-request-for-all-stations-dortmund-zurich).

## Quirks

- Stations without a temperature value are left out.
- The measuring point ids are numbers; the integration uses them as text.
