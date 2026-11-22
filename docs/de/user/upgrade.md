<!-- source: 6a2cedc9cd9bfa605b0d197c8a2cd32ece1b3028 -->
# Upgrade von 0.2.x

Bis 0.2.x hieß die Integration *Klimamessnetz Mannheim* mit der Domain `mannheim_climate`. Ab
0.3.0 heißt sie *Urban Weather (Stadtklima)* mit der Domain `urban_weather`. Home Assistant
sieht darin zwei verschiedene Integrationen: Deine Standorte werden nicht übernommen, du legst
sie einmal neu an.

Gibst du den neuen Entitäten die Entitäts-IDs der alten, laufen Verlauf, Langzeitstatistik,
Dashboards und Automationen weiter.

!!! warning "Das Update in HACS funktioniert nicht"
    HACS bricht das Update ab mit *"changed its domain from mannheim_climate to urban_weather,
    uninstall it and install it again"*. Geh stattdessen so vor wie unten beschrieben.

## 1. Einrichtung notieren

*Einstellungen → Geräte & Dienste → Klimamessnetz Mannheim*, für jeden Standort:

- die Entitäts-IDs, die du verwendest (Reiter *Entitäten*), zum Beispiel `sensor.ilvesheim_temperatur`,
- Stationen, Aktualisierungsintervall und Taupunkt-Korrektur (*Konfigurieren*).

## 2. Alte Standorte löschen

Lösche alle Standorte von *Klimamessnetz Mannheim*. Damit werden die Entitäts-IDs für die neuen
Entitäten frei. Der aufgezeichnete Verlauf bleibt in der Datenbank. Solange es Standorte gibt,
lässt HACS die Integration nicht entfernen.

## 3. Alte Version entfernen

HACS → *Klimamessnetz Mannheim* → ⋮ → *Entfernen*, dann Home Assistant neu starten.

Bei einer manuellen Installation löschst du stattdessen `config/custom_components/mannheim_climate`.
Die zwischengespeicherte Sensorliste `.storage/mannheim_climate.sensors` kannst du ebenfalls löschen.

## 4. Urban Weather installieren

*Urban Weather (Stadtklima)* in HACS installieren und Home Assistant neu starten, siehe
[Installation](installation.md). Das Repository ist dasselbe; HACS folgt dem neuen Namen.

## 5. Standorte neu anlegen

[Lege jeden Standort](setup.md) am selben Ort an. Für dieselben Stationen wie vorher wählst du im
Schritt Stationen *Aus einer Liste auswählen* statt der Empfehlung. Danach stellst du unter
*Konfigurieren* Aktualisierungsintervall und Taupunkt-Korrektur ein.

## 6. Entitäts-IDs wiederherstellen

Die neuen Entitäten bekommen neue Entitäts-IDs, benannt nach dem Standort und in der Sprache
deines Home Assistant (zum Beispiel `sensor.home_temperatur`). Für jede Entität: öffnen, ⚙ →
*Entitäts-ID*, alte ID eintragen und speichern. Der Verlauf läuft weiter, solange die ID gleich ist.

Entitäten, die es in 0.2.x nicht gab (zum Beispiel Minimal- und Maximaltemperatur), können ihre
neuen IDs behalten.
