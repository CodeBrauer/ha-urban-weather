<!-- source: 7e84b8af03af9afe0eb38cfed95988f6e853037f -->
# Architektur

Die Integration liegt in `custom_components/urban_weather/`. Die Konventionen für die
Arbeit daran (Befehle, Tests, Commits, Versionierung) stehen in
[`AGENTS.md`](https://github.com/CodeBrauer/ha-urban-weather/blob/main/AGENTS.md).

## Komponenten

```mermaid
flowchart TB
    subgraph External[Extern]
        API[(Klima-API<br>api.smartmannheim.de)]
        Tiles[(basemap.de-Kacheln)]
    end
    subgraph HA[Home Assistant]
        subgraph HubBox[ClimateHub, einer pro Home Assistant]
            Limiter[RateLimiter<br>Messwerte + Stationsliste]
            Cache[Messwert-Cache]
            List[Stationsliste<br>Store + erstes Auftauchen]
            Ref[ReferenceData<br>Katalog, LCZ, Stadtteile]
        end
        Store[(.storage/<br>urban_weather.sensors)]
        subgraph Entry[Pro Config Entry]
            Coord[ClimateCoordinator]
            Sensors[Sensor-Entitäten]
            Weather[Wetter-Entität]
        end
        Flows[Config-, Options- und Repair-Flows]
        Selection[StationSelection<br>Empfehlung + Budget]
        MapView[MapView<br>HTTP-Seite ohne Login]
    end
    Browser[Browser]
    API <--> Limiter
    List <--> Store
    Coord --> HubBox
    Coord --> Sensors
    Coord --> Weather
    Flows --> Selection --> HubBox
    Flows --> MapView
    Browser <--> MapView
    Browser --> Tiles
```

| Modul | Aufgabe |
|---|---|
| `api.py` | HTTP-Client für `/sensors` und `/measurements/{id}`, Parsen der Antworten, Fehlertypen (`ApiRateLimitError`, `SensorNotFoundError`, …) |
| `hub.py` | Singleton `ClimateHub`: Rate-Limiter, Messwert-Cache, Stationsliste mit gespeicherter Kopie und Zeitpunkt des ersten Auftauchens |
| `stations.py` | Gruppieren der Sensoren zu `Station`s, `recommend()` |
| `reference.py`, `data/` | Mitgelieferter Metadatenkatalog, LCZ-Raster und Stadtteilnamen |
| `selection.py` | `StationSelection`: Empfehlung, Abfrage-Budget und Beschriftungen, gemeinsam für alle Flows und die Karte |
| `config_flow.py` | Config Flow (Standort, Umgebung, Stationen), Reconfigure, Options Flow |
| `map_view.py`, `www/` | Kartenseite als externer Schritt des Config Flows |
| `coordinator.py` | `ClimateCoordinator`: Abfragen, Nachholen, gehaltene Werte, Reparaturhinweise |
| `aggregation.py` | Plausibilität, Ausreißer, Mediane und abgeleitete Werte |
| `sensor.py`, `weather.py` | Entitäten; Schätzung des Wetterzustands |
| `repairs.py` | Fix-Flows für die Reparaturhinweise |
| `diagnostics.py` | Diagnose mit entfernten Koordinaten |
| `geo.py` | Entfernung, Richtung und Clustering ohne Home-Assistant-Imports (auch vom Build-Skript genutzt) |
| `const.py` | Alle Limits, Intervalle und Schwellen, die diese Doku nennt |

## Einrichten eines Standorts

```mermaid
sequenceDiagram
    participant HA as Home Assistant
    participant Init as async_setup_entry
    participant Hub as ClimateHub
    participant Coord as ClimateCoordinator
    HA->>Init: Config Entry
    Init->>Hub: async_get_hub (beim ersten Aufruf angelegt)
    Init->>Hub: async_get_stations()
    alt keine Liste von der API und keine gespeichert
        Hub-->>Init: StationListUnavailableError
        Init-->>HA: ConfigEntryNotReady (wird wiederholt)
    end
    Init->>Init: gewählte Sensor-IDs den Stationen zuordnen
    alt keine davon existiert
        Init-->>HA: ConfigEntryError
    end
    Init->>Coord: anlegen, erster Refresh
    Coord->>Coord: _async_setup: Reparaturhinweise mit der Auswahl abgleichen
    Coord->>Hub: Messwerte aller gewählten Sensoren
    Init->>HA: Sensor- und Wetter-Plattform laden
```

Sensoren werden nur für Werte angelegt, die ein gewählter Sensor misst (`parameters` des
API-Sensors). Änderungen an den Optionen laden den Eintrag neu (`OptionsFlowWithReload`).

## Kartenseite

Die Karte ist ein externer Schritt des Config Flows, ausgeliefert von Home Assistant selbst:

```mermaid
sequenceDiagram
    participant Flow as Config Flow
    participant Map as MapView
    participant Browser
    Flow->>Map: MapSessions.create(flow, selection, payload)
    Flow-->>Browser: externer Schritt mit /api/urban_weather/map/{token}
    Browser->>Map: GET Seite (Payload eingebettet)
    Browser->>Browser: Leaflet-Karte, Kacheln von basemap.de
    Browser->>Map: POST Stationen und Windstation
    Map->>Map: StationSelection.validate()
    Map->>Flow: async_configure(map_selection)
    Flow->>Flow: externer Schritt fertig, Eintrag anlegen oder aktualisieren
```

- Die Seite braucht kein Home-Assistant-Login, deshalb ist der Link ein nicht erratbares
  Token, das an den Flow gebunden ist und nach `MAP_SESSION_TTL` abläuft. Antworten werden
  nicht gecacht.
- Der Server prüft die Auswahl erneut; die Seite hilft nur, im Budget zu bleiben.
- `www/map.js` wiederholt die Budget-Regeln von `StationSelection`, um das Intervall live
  anzuzeigen. Ändere beide zusammen.
- Die Texte kommen aus dem Selector `map_page` in `strings.json`, in der Systemsprache.
- Leaflet liegt mitgeliefert in `www/leaflet/`; die statischen Dateien werden unter
  `STATIC_URL` mit einem Inhalts-Hash als Cache-Buster ausgeliefert.

## Config Entry

`VERSION = 1`, bisher ohne Migrationen. Änderungen an diesem Format brauchen eine Migration
(siehe [`AGENTS.md`](https://github.com/CodeBrauer/ha-urban-weather/blob/main/AGENTS.md#home-assistant-specifics)).

| Teil | Schlüssel | Inhalt |
|---|---|---|
| `unique_id` | | `"{latitude:.3f}_{longitude:.3f}"`, Standorte unter etwa 100 m Abstand sind also Duplikate |
| `data` | `latitude`, `longitude` | Standort |
| | `radius` | Suchradius in Metern (`DEFAULT_SEARCH_RADIUS_M`, höchstens `MAX_SEARCH_RADIUS_M`) |
| | `environment` | `dense`, `open_built`, `industrial` oder `green` (`Environment`) |
| `options` | `temperature_sensors` | API-Sensor-IDs der Temperaturstationen |
| | `wind_sensor` | API-Sensor-ID der Windstation oder `null` |
| | `scan_interval` | Aktualisierungsintervall in Minuten (`SCAN_INTERVAL_CHOICES_MIN`) |
| | `dew_point_offset` | Taupunkt-Korrektur in K |

Entitäten haben die Unique ID `{entry_id}_{key}` (`key` der Entity Description, `weather`
für die Wetter-Entität) und gehören zu einem Dienst-Gerät pro Eintrag. Ab 1.0.0 sind
Entitäts-IDs, Unique IDs und dieses Format stabil.

## Reparaturhinweise

| Issue-ID | Daten | Angelegt von |
|---|---|---|
| `station_offline_{entry_id}_{sensor_id}` | `entry_id`, `sensor_id` | Coordinator, keine gültigen Daten für `STATION_OFFLINE_AFTER` |
| `station_removed_{entry_id}_{sensor_id}` | `entry_id`, `sensor_id` | Coordinator, 404 von der API oder Sensor fehlt in der Stationsliste |
| `new_stations_{entry_id}_{Sensor-IDs mit - verbunden}` | `entry_id` | Coordinator, neue Sensoren in einer Empfehlung, die ins Budget passt |

Alle Hinweise sind behebbar und laufen über `StationRepairFlow`. Die ID eines Vorschlags
enthält seine Sensoren, ein ignorierter Vorschlag bleibt deshalb ignoriert, während ein
anderer neu erscheint. Hinweise zu Sensoren, die nicht mehr gewählt sind, werden beim Setup
gelöscht, alle Hinweise eines Eintrags, wenn er entfernt wird.
