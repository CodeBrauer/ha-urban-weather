# Installation

## Requirements

| | |
|---|---|
| Home Assistant | 2026.9 or newer |
| HACS | 2.0.5 or newer (only for installation via HACS) |
| Internet | Access to `api.smartmannheim.de` from Home Assistant |
| Browser | Access to `sgx.geodatenzentrum.de` for the map tiles (basemap.de) of the station map |

The API is public and needs no account or key.

## HACS (custom repository)

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=CodeBrauer&repository=ha-urban-weather&category=integration)

Or manually:

1. HACS → ⋮ → *Custom repositories* → add `https://github.com/CodeBrauer/ha-urban-weather`
   with type *Integration*.
2. Install *Urban Weather (Stadtklima)* and restart Home Assistant.

HACS installs the ZIP file attached to each GitHub release and shows new versions as updates.
The release notes list breaking changes and what you have to do after updating.

## Manual

Copy `custom_components/urban_weather` into your `config/custom_components/` folder and
restart Home Assistant. Updates work the same way: replace the folder and restart.

## Next step

[Add your first location](setup.md).

## Uninstall

1. *Settings → Devices & services → Urban Weather (Stadtklima)*: delete every location. Their
   repair issues are removed with them.
2. Remove the integration in HACS (or delete the folder) and restart Home Assistant.

The cached station list stays in `.storage/urban_weather.sensors`; you can delete the file.
