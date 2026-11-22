# Supported networks

The integration reads urban climate networks of cities. A network is a set of stations
across a city that measure temperature and more, published with an open licence and no
login. When you add a location, the integration uses the network with a station nearby.

| Network | Stations | Values | Siting data | Platform | Endpoint |
|---|---|---|---|---|---|
| [Smart City Mannheim](mannheim.md) | 400+ | All values; wind on some masts | Surroundings, roof and high point | Own API | `api.smartmannheim.de` |
| [Klimamessnetz Dortmund](dortmund.md) | 76 | Temperature and humidity; about a third also air pressure, global irradiance and wind | None | Opendatasoft | `open-data.dortmund.de` |

Each network has its own [API limits](../user/api-limits.md) and request budget. Data
sources and licences: [Data sources](../data-sources.md).

## What a network page covers

| Section | Content |
|---|---|
| Overview | Operator, platform, endpoint, licence and attribution |
| Coverage | Where the stations are and what they measure |
| Data | How often new values arrive, how stations are formed, units |
| Limits | Request limits and budget |
| Quirks | Unusual data the integration handles |

## Request a network

Cities and networks that are planned or researched are tracked as
[issues titled "Network: ..."](https://github.com/CodeBrauer/ha-urban-weather/issues?q=is%3Aissue%20%22Network%3A%22%20in%3Atitle).
A network can be supported when it has live values (updated at least hourly), a licence that
allows reuse, stations across the city and access without a login. To propose one, use the
[network proposal form](https://github.com/CodeBrauer/ha-urban-weather/issues/new?template=new_network.yml).
