# KLIPS Dresden

| | |
|---|---|
| Operator | Landeshauptstadt Dresden, Umweltamt (sensor network of the research project KLIPS) |
| Network | KLIPS temperature sensors, "Lufttemperatur und Relative Feuchte - aktuelle Messwerte" |
| Platform | WFS of the city's GIS (layer `cls:L1625`), [Themenstadtplan](https://stadtplan.dresden.de/?TH=UW_KLIPS_TEMPERATUR_MESS) |
| Endpoint | `https://kommisdd.dresden.de/net3/public/ogc.ashx` |
| Access | Public, no key |
| Licence | dl-de/by-2-0 |
| Attribution | Landeshauptstadt Dresden (KLIPS sensor network), dl-de/by-2-0 |
| Map tiles | basemap.de |
| Network id | `dresden` |

## Coverage

About 120 current stations across Dresden, densest in the centre, Neustadt and Blasewitz;
about 260 sensors are installed, many of them inactive. All of them measure temperature and
humidity; the network has no air pressure, irradiance or wind values.

## Data

- The service holds hourly values, one feature per sensor, value and hour, since 2023. The
  integration groups them by sensor and uses the newest hour of each.
- Every request has a time window, because the whole layer holds several years: the station
  list looks back 24 hours, the measurements 4 hours.
- Values arrive one to two hours after the full hour, some sensors hours later. A measurement
  counts for 4 hours instead of the usual 40 minutes, so a station stays in use until its
  next value arrives. The last values are kept for 6 hours.
- Each sensor is a station on its own; its `device` number is the station code, the name is
  its address (for example `Postplatz (DVB)`).
- The station list and the measurements come from the same layer, so each costs one request
  and the number of stations costs no requests.
- The layer has no siting data. The station recommendation works by distance only, see
  [Networks without siting data](../user/stations.md#networks-without-siting-data).

## Limits

No limits are documented. The values are hourly, so the integration applies a low cap of its
own: one refresh every 15 minutes for up to 3 locations.

| Measure | Value |
|---|---|
| Station list | Refreshed at most once a day and stored locally |
| Measurement cache | 9 minutes, shared between all locations |
| Requests sent | At most 2 per minute and 24 per hour |
| Requests planned | At most 12 per hour for all locations together |

One request returns all stations, so the number of stations costs nothing:
[how many stations fit](../user/api-limits.md#one-request-for-all-stations-dortmund-basel-zurich-karlsruhe-dresden).

## Quirks

- Times are Central European Time all year (no daylight saving time).
- Many sensors are mounted on lamp posts at more than 3 m. The values are radiation corrected.
- Some sensors report a humidity of 0 %; implausible values are left out.
- Some station names start with `$` or `#`; the integration leaves these marks out.
- Stations without a position are left out, and so are stations whose newest value is more
  than 4 hours older than the newest value of the network.
- The server never ends a compressed response, so the integration asks for an uncompressed
  one (`Accept-Encoding: identity`).
