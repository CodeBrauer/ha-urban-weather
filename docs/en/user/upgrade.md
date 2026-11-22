# Upgrade from 0.2.x

Up to 0.2.x the integration was called *Klimamessnetz Mannheim* with the domain
`mannheim_climate`. From 0.3.0 on it is *Urban Weather (Stadtklima)* with the domain
`urban_weather`. Home Assistant treats them as two different integrations: your locations are
not taken over, you set them up once more.

If you give the new entities the entity IDs of the old ones, their history, long-term
statistics, dashboards and automations keep working.

!!! warning "Updating in HACS does not work"
    HACS stops the update with *"changed its domain from mannheim_climate to urban_weather,
    uninstall it and install it again"*. Use the migration script or the steps below instead.

Make a backup first.

## Option A: migration script

The [migration script](https://gist.github.com/CodeBrauer/d2727767079a7a8c2d7d7af4d1ec223a) runs the steps of option B through the Home Assistant API.
You need a [long-lived access token](https://www.home-assistant.io/docs/authentication/#your-account-profile)
and [uv](https://docs.astral.sh/uv/) (or Python 3.11 with `aiohttp`):

```bash
HA_URL=http://homeassistant.local:8123 HA_TOKEN=<token> uv run migrate_to_urban_weather.py
```

The script

1. reads every location of *Klimamessnetz Mannheim* and saves it to
   `urban_weather_migration.json`. It asks for the coordinates of each location, because
   Home Assistant does not hand them out; Enter takes your home location.
2. deletes the old locations after you confirm,
3. waits while you remove *Klimamessnetz Mannheim* in HACS, install *Urban Weather
   (Stadtklima)* and restart Home Assistant,
4. sets up the locations again with the same stations and settings and gives the new entities
   the old entity IDs.

If it stops, finish with the steps of option B; the JSON file has everything you need.

## Option B: step by step

### 1. Write down your setup

*Settings → Devices & services → Klimamessnetz Mannheim*, for each location:

- the entity IDs you use (*Entities* tab), for example `sensor.ilvesheim_temperature`,
- the stations, update interval and dew point correction (*Configure*).

### 2. Delete the old locations

Delete every location of *Klimamessnetz Mannheim*. This frees the entity IDs for the new
entities. The recorded history stays in the database. HACS refuses to remove the integration
while locations exist.

### 3. Remove the old version

HACS → *Klimamessnetz Mannheim* → ⋮ → *Remove*, then restart Home Assistant.

With a manual installation, delete `config/custom_components/mannheim_climate` instead. You can
also delete the cached sensor list `.storage/mannheim_climate.sensors`.

### 4. Install Urban Weather

Install *Urban Weather (Stadtklima)* in HACS and restart Home Assistant, see
[Installation](installation.md). The repository is the same; HACS follows its new name.

### 5. Set up the locations again

[Add each location](setup.md) at the same place. To get the same stations as before, pick
*Choose from a list* in the stations step instead of the recommendation. Afterwards set the
update interval and the dew point correction under *Configure*.

### 6. Restore the entity IDs

The new entities get new entity IDs, named after the location and in the language of your
Home Assistant (for example `sensor.home_temperature`). For each entity: open it, ⚙ →
*Entity ID*, enter the old ID and save. The history continues as long as the ID is the same.

Entities that did not exist in 0.2.x (for example the minimum and maximum temperature) can
keep their new IDs.
