<!-- source: da505ed0c78d3ae5594479395f8c227b5ddf1e6c -->
# Abfragen und API-Zugriff

Jeder API-Zugriff läuft über `ClimateHub` (`hub.py`). Die Limits des Messnetzes
(`RequestLimits`, für Mannheim in `providers/mannheim/`) bilden die Limits der API pro IP
nach; [API-Limits](../user/api-limits.md) erklärt sie für Nutzer.

## Aktualisierungszyklus

Jeder `ClimateCoordinator` läuft alle `scan_interval` Minuten:

```mermaid
sequenceDiagram
    participant Coord as ClimateCoordinator
    participant Hub as ClimateHub
    participant API as Klima-API
    Coord->>Hub: async_get_stations() (Prüfung auf neue Stationen)
    loop jeder gewählte Temperatursensor, dann der Windsensor
        Coord->>Hub: async_get_measurements(sensor)
        alt seit weniger als MEASUREMENT_CACHE_TTL im Cache
            Hub-->>Coord: Messwerte aus dem Cache
        else Budget frei
            Hub->>API: GET /measurements/{id}
            alt 200
                API-->>Hub: letzte 60 Minuten
                Hub-->>Coord: Messwerte (zwischengespeichert)
            else 429
                API-->>Hub: Retry-After
                Hub->>Hub: Limiter sperren
                Hub-->>Coord: RequestDeferredError
            else 404
                Hub-->>Coord: SensorNotFoundError
            end
        else kein Budget
            Hub-->>Coord: RequestDeferredError(wait)
        end
        Coord->>Coord: neueste gültige Messung, Hinweise offline/entfernt
    end
    opt eine Abfrage wurde verschoben
        Coord->>Coord: Nachhol-Refresh nach wait + CATCH_UP_MARGIN_S planen
    end
    Coord->>Coord: estimate() oder letzte Werte behalten
```

- Ein verschobener Sensor nutzt seine Messwerte aus dem Cache, auch wenn sie älter als die
  Cache-Dauer sind; der Nachhol-Refresh fragt ihn ab, sobald das Budget es zulässt. Es ist
  immer nur ein Nachholen gleichzeitig geplant.
- Ein Lock pro Sensor verhindert, dass zwei Standorte denselben Sensor gleichzeitig
  abfragen; der zweite bekommt das Ergebnis aus dem Cache.

## Rate-Limiter

`RateLimiter` merkt sich die Zeitpunkte der letzten Abfragen und prüft gleitende Fenster:

| Limiter | Fenster (Mannheim) |
|---|---|
| Messwerte | 4 pro 120 s, 30 pro 3600 s (`MEASUREMENT_LIMITS`) |
| Stationsliste | 2 pro 900 s, 4 pro 3600 s (`SENSOR_LIST_LIMITS`) |

Eine `429` sperrt den Limiter für `Retry-After` Sekunden (`DEFAULT_RETRY_AFTER_S`, wenn der
Header fehlt). Abgelehnte Abfragen zählen bei der API mit, deshalb versucht es die
Integration nie früher erneut. Die erste `429` einer Serie wird als Warnung protokolliert,
die folgenden auf Debug-Level.

Der Limiter setzt nur die harten Limits durch. Im normalen Betrieb darunter zu bleiben, ist
Aufgabe des geplanten Budgets (`PLANNED_BUDGET_PER_HOUR`), das `StationSelection` bei der
Stationswahl prüft.

## Stationsliste

```mermaid
flowchart TD
    Call[async_get_stations] --> Mem{Im Speicher und jünger<br>als SENSOR_LIST_MAX_AGE?}
    Mem -- ja --> Return([Stationen])
    Mem -- nein --> Load[Gespeicherte Kopie laden]
    Load --> Age{Gespeicherte Kopie jünger<br>als SENSOR_LIST_MAX_AGE?}
    Age -- ja --> Build
    Age -- nein --> Fetch{/sensors abrufen<br>im Rahmen des Limiters}
    Fetch -- ok --> Save[Erstes Auftauchen aktualisieren,<br>Payload speichern]
    Save --> Build
    Fetch -- fehlgeschlagen --> Stored{Gespeicherte Kopie<br>beliebigen Alters?}
    Stored -- ja --> Build
    Stored -- nein --> Error([StationListUnavailableError])
    Build[build_stations] --> Return
```

Die gespeicherte Kopie (`.storage/urban_weather.sensors`) enthält den rohen Payload, den
Abrufzeitpunkt und für jeden Sensor, wann er zum ersten Mal auftauchte. Beim ersten Abruf
ohne Historie gelten alle Sensoren als bekannt, neu sind also nur später hinzugekommene. Ein
Sensor gilt `NEW_STATION_PERIOD` lang als neu.

## Gehaltene Werte und Verfügbarkeit

```mermaid
stateDiagram-v2
    state "Aktuell" as Current
    state "Gehalten" as Kept
    state "Nicht verfügbar" as Unavailable
    [*] --> Current
    Current --> Current: Messungen
    Current --> Kept: keine Messungen, neueste gehaltene<br>Messung innerhalb der Haltezeit
    Kept --> Current: Messungen
    Kept --> Unavailable: Haltezeit überschritten
    Current --> Unavailable: keine Messungen und<br>nichts zu halten
    Unavailable --> Current: Messungen
```

- Eine Messung zählt, wenn sie die neueste einer Station innerhalb von
  `MAX_MEASUREMENT_AGE` mit plausiblen Werten ist.
- Die Haltezeit ist `max(KEEP_VALUES_MIN_AGE, KEEP_VALUES_INTERVALS × scan_interval)`,
  gerechnet ab der neuesten Messung der gehaltenen Schätzung.
- Nicht verfügbar heißt, die Aktualisierung hat `UpdateFailed` ausgelöst:
  `waiting_for_budget` (mit `retry_after`), wenn Abfragen verschoben wurden, sonst
  `no_recent_data`.

## Reparaturhinweise bei der Aktualisierung

Jede Aktualisierung

- prüft, ob die aktuelle Empfehlung neue Sensoren enthält, und legt den Hinweis
  `new_stations` an, ersetzt oder löscht ihn,
- setzt `station_offline`, wenn ein Sensor `STATION_OFFLINE_AFTER` lang keine Messung hatte
  (gezählt ab dem Start des Coordinators), und löscht ihn sonst,
- setzt `station_removed` bei einer 404 und löscht ihn, sobald wieder Messwerte des Sensors
  ankommen, abgerufen oder aus dem Cache.
