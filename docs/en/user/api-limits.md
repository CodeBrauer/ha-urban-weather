# API limits

The [Klima API](https://api.smartmannheim.de/doc) is public and needs no key. Its
documented limit is **30 measurement requests per hour per internet connection** (public IP
address), plus a few requests of the station list. In practice the API also limits short
bursts (about 5 requests per 2 minutes) and answers `429` with a `Retry-After` header.

The limit applies to everything behind your internet connection: other Home Assistant
integrations, scripts or devices that use `api.smartmannheim.de` share it.

## What the integration does

| Measure | Value |
|---|---|
| Station list | Refreshed at most once a day and stored locally; a stored copy is used if the API is unavailable |
| Measurement cache | 9 minutes, shared between all locations |
| Requests sent | At most 4 per 2 minutes and 30 per hour; skipped stations are fetched shortly afterwards |
| Requests planned | At most 24 per hour for all locations together, so 6 stay free for other clients |
| After a `429` | No requests until `Retry-After` has passed |

## How many stations fit

Each location needs one request per selected station and update, the wind station counts as
a station:

```text
requests per hour = (stations + wind station) × 60 / update interval in minutes
```

The sum over all enabled locations must stay at or below 24.

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
