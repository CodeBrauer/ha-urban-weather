# API limits

Each network has its own limits and its own request budget; locations in one network do not
take stations from locations in another. The documented limits and what the integration sends
are on the page of each network: [Smart City Mannheim](../networks/mannheim.md#limits),
[Klimamessnetz Dortmund](../networks/dortmund.md#limits). This page explains how the budget
limits the number of stations.

The limits apply to everything behind your internet connection (public IP address): other
Home Assistant integrations, scripts or devices that use the same API share them.

## How many stations fit

The sum of the requests of all enabled locations of a network must stay at or below its
planned requests per hour (24 in Mannheim, 60 in Dortmund). How many requests a location needs
depends on how the network delivers its values.

### One request per station (Mannheim)

Each location needs one request per selected station and update, the wind station counts as
a station:

```text
requests per hour = (stations + wind station) × 60 / update interval in minutes
```

| Stations + wind | 10 min | 15 min | 20 min | 30 min |
|---|---|---|---|---|
| 1 + 1 | 12 | **8** | 6 | 4 |
| 2 + 1 | 18 | **12** | 9 | 6 |
| 4 + 1 | 30 | **20** | 15 | 10 |
| 6 + 1 | 42 | 28 | **21** | 14 |

Bold: the interval chosen automatically for a single location (the shortest of 15, 20 and
30 minutes that fits). 10 minutes can be chosen in the options if the budget allows it.

- The setup, the map and the options only allow selections that fit. The map shows how many
  stations fit and the resulting interval.
- Disabled locations do not count.
- With several locations, each one leaves fewer stations or a longer interval for the
  others.

### One request for all stations (Dortmund)

One request returns the values of all stations the locations use, so the number of stations
costs no requests:

```text
requests per hour = 60 / update interval in minutes   (per location)
```
