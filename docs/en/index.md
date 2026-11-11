# Urban Weather (Stadtklima)

Home Assistant integration for the dense urban climate network of
[Smart City Mannheim](https://smartmannheim.de/) (400+ stations). It provides climate values
for a location of your choice: temperature, humidity, dew point, absolute humidity, apparent
temperature, air pressure, global irradiance and wind.

The integration picks the station that represents your place best. If the nearest one does
not fit (too far away, different surroundings, mounted on a roof), it combines several
stations around you instead.

![Interactive station map](screenshots/04-map.jpg)

!!! note "Unofficial project"
    Not affiliated with Smart City Mannheim GmbH or the city of Mannheim.

## Why this integration

It started with a simple wish: a good outdoor temperature in Home Assistant that is
measured on site, not estimated from weather models by a global weather service. The usual
alternatives fall short:

- **Zigbee and Tuya climate sensors** are mostly a poor fit outdoors: no active
  ventilation, the mounting point or surface heats up, some sensors are imprecise, and the
  batteries need frequent changes.
- **A weather station of your own** is comparatively expensive and also has to work with
  your smart home.

More and more cities run their own urban climate networks. This integration makes the
network of Smart City Mannheim usable in Home Assistant.

## Features

- **Location on a map**, pre-filled with your Home Assistant home location.
- **Station recommendation** based on distance, surroundings (Local Climate Zones) and
  mounting height; accept it with one click or choose yourself.
- **Interactive station map** that only allows as many stations as fit the API budget and
  shows the resulting update interval live.
- **One station or a combination**: the median of several stations, outliers removed.
- **Sensors and a weather entity** with all current values, plus diagnostic sensors.
- **Respects the API limits** with a shared request budget and cache for all locations.
- **Several locations** (home, work, ...), each as its own device.
- **Repairs** when a selected station stops delivering data or disappears, and
  **suggestions** when new stations are added nearby.
- English and German.

## How it works

```mermaid
flowchart LR
    API[(Klima API<br>api.smartmannheim.de)]
    Hub[Hub<br>request budget, cache,<br>station list]
    C1[Location 1<br>stations + combination]
    C2[Location 2<br>stations + combination]
    E1[Sensors and<br>weather entity]
    E2[Sensors and<br>weather entity]
    API -->|station list, daily| Hub
    API -->|measurements| Hub
    Hub --> C1 --> E1
    Hub --> C2 --> E2
```

All locations share one hub that talks to the API, so a station used by two locations is
fetched once and the requests of all locations together stay within the API limit. Each
location polls its stations and combines their latest values into one set of entities.

## Where to go next

| I want to | Page |
|---|---|
| Install the integration | [Installation](user/installation.md) |
| Add a location and choose stations | [Setup](user/setup.md) |
| Know what each entity means | [Entities](user/entities.md) |
| Understand which stations are recommended | [Station recommendation](user/stations.md) |
| Know how many stations fit and why | [API limits](user/api-limits.md) |
| Fix missing values or a repair issue | [Repairs and troubleshooting](user/troubleshooting.md) |
| Work on the code | [Architecture](developer/architecture.md) |
