# Smart City Mannheim

| | |
|---|---|
| Operator | Smart City Mannheim GmbH |
| Network | Urban climate network of Mannheim |
| Platform | Own REST API, [documentation](https://api.smartmannheim.de/doc) |
| Endpoint | `https://api.smartmannheim.de/climate` |
| Access | Public, no key |
| Licence | dl-de/by-2-0 |
| Attribution | Smart City Mannheim GmbH, dl-de/by-2-0 (opendata.smartmannheim.de) |
| Map tiles | basemap.de |
| Network id | `mannheim` |

## Coverage

More than 400 stations across Mannheim, many of them in street canyons, on roofs or in
parks only a few hundred metres apart. Besides temperature and humidity the network
measures:

- air pressure and global irradiance (newer hardware generations),
- wind on some masts,
- dew point, minimum and maximum temperature, and a 1-second and 3-second wind gust with
  its direction.

Which values a station delivers varies; entities only exist for values the selected stations
measure (see [Entities](../user/entities.md)).

## Data

- The API lists sensor modules, not stations. Modules within 15 m of each other form one
  station. A station has a temperature module and, if present, a wind module.
- Per module the API returns the measurements of the last 60 minutes; the integration uses
  the newest valid one. This costs one request per sensor.
- Siting data is bundled with the integration: the city's metadata catalogue (mounting zone,
  height above ground, Local Climate Zone), a Local Climate Zone raster as a fallback and a
  district name per station. The [station recommendation](../user/stations.md) uses it.
  Details and sources: [Stations and reference data](../developer/reference-data.md).
- The station code is the first 8 characters of the sensor name (`0101-046` from
  `0101-046-21`).

## Limits

The [Klima API](https://api.smartmannheim.de/doc) documents **30 measurement requests per
hour per internet connection** (public IP address), plus a few requests of the station list.
In practice it also limits short bursts (about 5 requests per 2 minutes) and answers `429`
with a `Retry-After` header. Everything behind your internet connection that uses
`api.smartmannheim.de` shares the limit.

| Measure | Value |
|---|---|
| Station list | Refreshed at most once a day and stored locally; a stored copy is used if the API is unavailable |
| Measurement cache | 9 minutes, shared between all locations |
| Requests sent | At most 4 per 2 minutes and 30 per hour; skipped stations are fetched shortly afterwards |
| Requests planned | At most 24 per hour for all locations together, so 6 stay free for other clients |
| After a `429` | No requests until `Retry-After` has passed |

Each station costs a request per update: [how many stations fit](../user/api-limits.md#one-request-per-station-mannheim).

## Related integration

[Smart City Mannheim](https://github.com/smartmannheim/smartmannheim) (domain
`smartmannheim_klima`) uses the same API. Both can be installed side by side but share the
limit of 30 requests per hour. This integration only plans its own requests, so keep the
number of stations small in both.

| | Urban Weather (Stadtklima) | Smart City Mannheim |
|---|---|---|
| Approach | One location, values that represent it best: a fitting station or a combination | Pick individual sensors, values per station |
| Choosing stations | Recommendation by distance, surroundings and mounting height; interactive map | Search by sensor code or street, list sorted by distance |
| Additional values | Absolute humidity, apparent temperature, weather entity | Pollen, air quality, DWD station Mannheim |

## Quirks

- Some sensors report swapped coordinates; the integration swaps them back (in Germany the
  latitude is larger than the longitude).
- Sensors without a usable position are skipped.
- The network tends to read too humid. The
  [dew point correction](../user/setup.md) corrects this; −1.3 K matched the DWD station
  Mannheim in a 31-day comparison.
- Stations on roofs or high points read other temperatures than at street level and are not
  recommended for temperature.
