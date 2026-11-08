<img src="custom_components/mannheim_climate/brand/icon@2x.png" alt="" width="96" align="right">

# Klimamessnetz Mannheim for Home Assistant

[Deutsch](README.md) · **English** · [Documentation](https://codebrauer.github.io/ha-urban-weather/)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

Climate values for your location from the dense urban climate network of
[Smart City Mannheim](https://smartmannheim.de/) (400+ stations): temperature, humidity,
dew point, absolute humidity, apparent temperature, air pressure, global irradiance and wind.

The integration picks the station that represents your place best. If the nearest one does
not fit (too far away, different surroundings, mounted on a roof), it combines several
stations around you instead.

> Unofficial project. Not affiliated with Smart City Mannheim GmbH or the city of Mannheim.

<p align="center"><img src="docs/screenshots/en/04-map.jpg" alt="Interactive station map" width="800"></p>

## Why?

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
- **Interactive station map**: zoom, click stations, pick a wind station. The map only allows
  as many stations as fit the API budget and shows the resulting update interval live.
- **One station or a combination**: the median of several stations, outliers removed;
  humidity is derived from the median dew point.
- **Sensors**: temperature, humidity, dew point, absolute humidity, apparent temperature,
  air pressure*, global irradiance*, wind speed, gust and direction (*if the selected
  stations measure it), plus diagnostic sensors (stations used, temperature spread, last
  measurement). Disabled by default: minimum and maximum temperature of the last
  10-minute interval and the gust direction.
- **Weather entity** with all current values. The condition (sunny / partly cloudy /
  cloudy) is estimated from irradiance during the day when at least 3 stations deliver it;
  the network has no cloud or rain sensors, so it stays unknown at night.
- **Respects the API limits** (shared request budget and cache across all locations).
- **Several locations** (home, work, ...), each as its own device.
- **Repairs** when a selected station stops delivering data or disappears, with a
  replacement you can apply directly, and **suggestions** when new stations are added
  nearby.
- **Reconfigure** to move a location, **options** to change stations, update interval and
  a dew point correction.
- **Diagnostics** download (coordinates redacted).
- English and German.

## Related integration

[Smart City Mannheim](https://github.com/smartmannheim/smartmannheim) (domain
`smartmannheim_klima`, in HACS as "Smart City Mannheim") uses the same climate API. This
project is unofficial and independent of it.

| | Klimamessnetz Mannheim (this repository) | Smart City Mannheim |
|---|---|---|
| Approach | One location, values that represent it best: a fitting station or a combination | Pick individual sensors, values per station |
| Choosing stations | Recommendation by distance, surroundings and mounting height; interactive map | Search by sensor code or street, list sorted by distance |
| Additional values | Absolute humidity, apparent temperature, weather entity | Pollen, air quality, DWD station Mannheim |

Both can be installed side by side but share the API limit per internet connection
(30 requests per hour). If you use both, keep the number of stations small.

## Installation

### HACS (custom repository)

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=CodeBrauer&repository=ha-urban-weather&category=integration)

Or manually:

1. HACS → ⋮ → *Custom repositories* → add `https://github.com/CodeBrauer/ha-urban-weather`
   with type *Integration*.
2. Install *Klimamessnetz Mannheim* and restart Home Assistant.

### Manual

Copy `custom_components/mannheim_climate` into your `config/custom_components/` folder and
restart Home Assistant.

## Setup

*Settings → Devices & services → Add integration → Klimamessnetz Mannheim*

1. **Location**: move the pin, the circle is the search radius.
2. **Surroundings**: how the area around the location is built up. Pre-selected from the
   Local Climate Zone map.
3. **Stations**: the recommendation is shown with its reason. Accept it, choose on the
   interactive map (opens in a new window; after saving, setup continues automatically) or
   choose from a list.

| Location | Stations |
|---|---|
| ![Choose the location](docs/screenshots/en/01-location.jpg) | ![Recommendation and ways to choose](docs/screenshots/en/03-menu.png) |
| **Device with sensors** | **Dashboard** |
| ![Device with all sensors](docs/screenshots/en/06-device.png) | ![Values on a dashboard](docs/screenshots/en/07-dashboard.png) |

Later you change stations, update interval and dew point correction under *Configure*. The
interactive map is available via *Reconfigure* (Home Assistant does not reliably show
external windows in options dialogs).

### How the recommendation works

- Stations on roofs or high points are not recommended for temperature.
- If the nearest street-level station is at most 1 km away and has the same surroundings,
  it is used on its own.
- Otherwise up to 4 stations within the search radius are combined, stations with the same
  surroundings first.

Surroundings are grouped from Local Climate Zones: densely built (LCZ 1–3), open built-up
(4–6, 9), industrial (7, 8, 10) and green/open (11–17). The zone of a station comes from the
city's metadata catalogue where available, otherwise from the global LCZ map.

When new stations are added that are part of the recommendation for a configured location,
a repair issue suggests them for 30 days. The selection only changes if you apply it:
other stations change the values (jumps in long-term statistics) and the API budget. If you
keep your stations, it only comes back for a different suggestion.

## API limits

The [Klima API](https://api.smartmannheim.de/doc) is public and needs no key. Its documented
limit is **30 measurement requests per hour per internet connection** (and a few station
list requests). In practice the API also limits short bursts (about 5 requests per 2 minutes)
and answers `429` with a `Retry-After` header.

The integration therefore:

- refreshes the station list at most once a day and caches it on disk,
- caches measurements for 9 minutes and shares them between locations,
- sends at most 4 requests per 2 minutes and 30 per hour, and fetches skipped stations
  shortly afterwards,
- plans at most 24 requests per hour for all locations together and picks the update
  interval accordingly (default 15 minutes; values arrive every 10 minutes with
  10–20 minutes delay anyway),
- keeps the last values during a `429` or an API outage until the last measurement is
  60 minutes old (or three update intervals, if that is longer); only then do the entities
  become unavailable.

Other scripts or devices that use the API from the same internet connection share the limit.

## When data stops

- If a selected station delivers no data for 24 hours or the API no longer knows it, a
  repair issue appears. *Fix* lets you use the recommendation without this station or
  choose from a list.
- During an API outage the last values stay (see above), then the entities become
  unavailable. There is no repair issue for this, because there is nothing you can fix.

Automations that use the temperature can react to an outage, for example with a push
notification to your phone. Adjust the entity and the notification service to your
installation:

```yaml
alias: "Klimamessnetz: no temperature"
triggers:
  - trigger: state
    entity_id: sensor.seckenheim_temperature
    to: unavailable
    for:
      minutes: 30
actions:
  - action: notify.mobile_app_my_phone
    data:
      message: No temperature from Klimamessnetz Mannheim for 30 minutes.
```

## Data sources and licences

| Data | Source | Licence |
|---|---|---|
| Measurements, station list | [Smart City Mannheim Klima API](https://opendata.smartmannheim.de/dataset/klimadaten-echtzeit-api) | dl-de/by-2-0 |
| Station siting metadata | [Metadatenkatalog Stadtklimamessnetze Mannheim](https://opendata.smartmannheim.de/dataset/metadaten-stadtklimamessnetze-mannheim) | dl-de/by-2-0 |
| Local Climate Zones | Demuzere et al. (2022), [Global map of LCZ](https://doi.org/10.5281/zenodo.6364594) | CC BY 4.0 |
| District names | © OpenStreetMap contributors via Nominatim | ODbL 1.0 |
| Map tiles of the station map | [basemap.de](https://basemap.de/) / BKG | CC BY 4.0 |
| Map library (bundled) | [Leaflet 1.9.4](https://leafletjs.com/) | BSD-2-Clause |

The static reference files in `custom_components/mannheim_climate/data/` are generated by
`scripts/build_reference_data.py` (source and date in each file's `source` header).

## Development

```bash
scripts/setup      # creates .venv with Home Assistant (uv)
scripts/develop    # starts Home Assistant on http://localhost:8123 with this integration
scripts/lint       # ruff format + check
scripts/test       # pytest (arguments are passed on, e.g. -k recommend)
```

On macOS some Home Assistant core dependencies (`pymicro-vad`, `pyspeex-noise`) have no
wheels for Python 3.14 and fail to compile. Build them once with the SDK path:

```bash
SDK=$(xcrun --show-sdk-path) SDKROOT="$SDK" CXXFLAGS="-isysroot $SDK -I$SDK/usr/include/c++/v1" uv pip install --python .venv/bin/python pymicro-vad pyspeex-noise
```

Regenerate the reference data (rarely needed, e.g. after a new metadata catalogue):

```bash
uv run --no-project --with openpyxl --with rasterio python scripts/build_reference_data.py
```

## Support

If you like the integration, you can buy me a beer:

[![Buy me a beer](https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20beer&emoji=%F0%9F%8D%BA&slug=codebrauer&button_colour=ffe500&font_colour=000000&font_family=Poppins&outline_colour=000000&coffee_colour=FFDD00)](https://buymeacoffee.com/codebrauer)

## License

MIT, see [LICENSE](LICENSE).
