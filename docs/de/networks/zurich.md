<!-- source: 93b70d1dad45a132c11bf48a12cc7b9c55bc166b -->
# Stadtklimamessnetz Zürich

| | |
|---|---|
| Betreiber | Stadt Zürich, Umwelt- und Gesundheitsschutz (UGZ) |
| Messnetz | Stadtklima Zürich, aktuelle Messungen |
| Plattform | GeoJSON-Datei, [stadtklima-zuerich.ch](https://stadtklima-zuerich.ch/) |
| Endpunkt | `https://stadtklima-zuerich.ch/ogd/v1/measurements/latest.geojson` |
| Zugriff | Öffentlich, kein Schlüssel |
| Lizenz | CC0 |
| Quellenangabe | Stadt Zürich (UGZ), CC0 (stadtklima-zuerich.ch) |
| Kartenkacheln | osm.ch (OpenStreetMap, Swiss Style) |
| Messnetz-ID | `zurich` |

## Abdeckung

107 Stationen in ganz Zürich. Alle messen Temperatur und Luftfeuchte; Luftdruck,
Globalstrahlung und Wind liefert das Messnetz nicht.

## Daten

- Die Datei ist eine GeoJSON-FeatureCollection mit einem Punkt pro Messpunkt und dessen
  letzten Werten.
- Jeder Messpunkt ist eine eigene Station; seine `location_id` ist der Stationscode.
- Stationsliste und Messwerte kommen aus derselben Datei und kosten je eine Abfrage; die
  Zahl der Stationen kostet also keine Abfragen.
- Die Datei enthält keine Standortdaten. Die Stationsempfehlung arbeitet allein nach
  Entfernung, siehe
  [Messnetze ohne Standortdaten](../user/stations.md#messnetze-ohne-standortdaten).

## Limits

Es sind keine Limits dokumentiert. Der Server hält die Datei 60 Sekunden im Cache; die
Integration nutzt dieselbe Obergrenze wie für Dortmund.

| Maßnahme | Wert |
|---|---|
| Stationsliste | Höchstens einmal am Tag aktualisiert und lokal gespeichert |
| Messwert-Cache | 9 Minuten, geteilt zwischen allen Standorten |
| Gesendete Abfragen | Höchstens 2 pro Minute und 60 pro Stunde |
| Geplante Abfragen | Höchstens 60 pro Stunde für alle Standorte zusammen |

Eine Abfrage liefert alle Stationen, die Anzahl der Stationen kostet also nichts:
[wie viele Stationen passen](../user/api-limits.md#eine-abfrage-fur-alle-stationen-dortmund-zurich).

## Besonderheiten

- Stationen ohne Temperaturwert bleiben außen vor.
- Die IDs der Messpunkte sind Zahlen; die Integration nutzt sie als Text.
