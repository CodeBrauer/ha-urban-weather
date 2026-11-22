<!-- source: 9d3ee9fa96431db13aa4f7697f3318ee548b9949 -->
# Upgrade von 0.2.x

Bis 0.2.x hieß die Integration *Klimamessnetz Mannheim* mit der Domain `mannheim_climate`. Ab
0.3.0 heißt sie *Urban Weather (Stadtklima)* mit der Domain `urban_weather`. Home Assistant
sieht darin zwei verschiedene Integrationen: Deine Standorte werden nicht übernommen, du legst
sie einmal neu an.

Gibst du den neuen Entitäten die Entitäts-IDs der alten, laufen Verlauf, Langzeitstatistik,
Dashboards und Automationen weiter.

!!! warning "Das Update in HACS funktioniert nicht"
    HACS bricht das Update ab mit *"changed its domain from mannheim_climate to urban_weather,
    uninstall it and install it again"*. Nimm stattdessen das Migrationsskript oder die Schritte unten.

Mach vorher ein Backup.

## Option A: Migrationsskript

Das [Migrationsskript](https://gist.github.com/CodeBrauer/d2727767079a7a8c2d7d7af4d1ec223a) führt die Schritte von Option B über die Home-Assistant-API aus.
Du brauchst einen [langlebigen Zugriffstoken](https://www.home-assistant.io/docs/authentication/#your-account-profile)
und [uv](https://docs.astral.sh/uv/) (oder Python 3.11 mit `aiohttp`):

```bash
HA_URL=http://homeassistant.local:8123 HA_TOKEN=<token> uv run migrate_to_urban_weather.py
```

Das Skript

1. liest alle Standorte von *Klimamessnetz Mannheim* und speichert sie in
   `urban_weather_migration.json`. Es fragt pro Standort nach den Koordinaten, weil Home
   Assistant sie nicht herausgibt; Enter nimmt deinen Zuhause-Standort.
2. löscht nach deiner Bestätigung die alten Standorte,
3. wartet, während du in HACS *Klimamessnetz Mannheim* entfernst, *Urban Weather
   (Stadtklima)* installierst und Home Assistant neu startest,
4. legt die Standorte mit denselben Stationen und Einstellungen neu an und gibt den neuen
   Entitäten die alten Entitäts-IDs.

Bricht es ab, machst du mit den Schritten von Option B weiter; die JSON-Datei enthält alles, was du dafür brauchst.

## Option B: Schritt für Schritt

### 1. Einrichtung notieren

*Einstellungen → Geräte & Dienste → Klimamessnetz Mannheim*, für jeden Standort:

- die Entitäts-IDs, die du verwendest (Reiter *Entitäten*), zum Beispiel `sensor.ilvesheim_temperatur`,
- Stationen, Aktualisierungsintervall und Taupunkt-Korrektur (*Konfigurieren*).

### 2. Alte Standorte löschen

Lösche alle Standorte von *Klimamessnetz Mannheim*. Damit werden die Entitäts-IDs für die neuen
Entitäten frei. Der aufgezeichnete Verlauf bleibt in der Datenbank. Solange es Standorte gibt,
lässt HACS die Integration nicht entfernen.

### 3. Alte Version entfernen

HACS → *Klimamessnetz Mannheim* → ⋮ → *Entfernen*, dann Home Assistant neu starten.

Bei einer manuellen Installation löschst du stattdessen `config/custom_components/mannheim_climate`.
Die zwischengespeicherte Sensorliste `.storage/mannheim_climate.sensors` kannst du ebenfalls löschen.

### 4. Urban Weather installieren

*Urban Weather (Stadtklima)* in HACS installieren und Home Assistant neu starten, siehe
[Installation](installation.md). Das Repository ist dasselbe; HACS folgt dem neuen Namen.

### 5. Standorte neu anlegen

[Lege jeden Standort](setup.md) am selben Ort an. Für dieselben Stationen wie vorher wählst du im
Schritt Stationen *Aus einer Liste auswählen* statt der Empfehlung. Danach stellst du unter
*Konfigurieren* Aktualisierungsintervall und Taupunkt-Korrektur ein.

### 6. Entitäts-IDs wiederherstellen

Die neuen Entitäten bekommen neue Entitäts-IDs, benannt nach dem Standort und in der Sprache
deines Home Assistant (zum Beispiel `sensor.home_temperatur`). Für jede Entität: öffnen, ⚙ →
*Entitäts-ID*, alte ID eintragen und speichern. Der Verlauf läuft weiter, solange die ID gleich ist.

Entitäten, die es in 0.2.x nicht gab (zum Beispiel Minimal- und Maximaltemperatur), können ihre
neuen IDs behalten.
