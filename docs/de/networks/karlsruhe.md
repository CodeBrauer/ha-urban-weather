<!-- source: 367a636bbf3c20fb9109b74ff0d391b1340ca95d -->
# Sensor City Karlsruhe

| | |
|---|---|
| Betreiber | Stadt Karlsruhe (Sensor City / CityCLIM) |
| Messnetz | Sensor City, Lufttemperatursensoren |
| Plattform | ArcGIS FeatureServer `Sensordaten_NodeRED`, [geoportal.karlsruhe.de](https://geoportal.karlsruhe.de/sensorcity/Dashboard/) |
| Endpunkt | `https://geoportal.karlsruhe.de/ags04/rest/services/Hosted/Sensordaten_NodeRED/FeatureServer/1/query` |
| Zugriff | Öffentlich, kein Schlüssel |
| Lizenz | Nicht angegeben |
| Quellenangabe | Stadt Karlsruhe (Sensor City) |
| Kartenkacheln | basemap.de |
| Messnetz-ID | `karlsruhe` |

## Abdeckung

Etwa 90 Stationen in ganz Karlsruhe. Alle messen Temperatur und Luftfeuchte; Wind liefert das
Messnetz nicht. Die Ebene enthält auch Luftdruck und Strahlung, die die Integration nicht
liest.

## Daten

- Ebene 1 des Dienstes enthält die letzten Werte jedes Sensors, ein Feature pro Sensor. Die
  Integration fragt sie für die Lufttemperatursensoren ab und erhält sie als GeoJSON.
- Jeder Sensor ist eine eigene Station; seine `device_id` ist der Stationscode, der Name ist
  die Bezeichnung der Stadt (zum Beispiel `173 - Schlossplatz 3 (Kreuzung Kronenstraße)`).
- Die Sensoren melden alle paar Minuten. Der Zeitpunkt einer Messung ist in Millisekunden seit
  der Epoche (UTC) angegeben.
- Stationsliste und Messwerte kommen aus derselben Abfrage und kosten je eine Abfrage; die
  Zahl der Stationen kostet also keine Abfragen.
- Die Ebene enthält keine Standortdaten. Die Stationsempfehlung arbeitet allein nach
  Entfernung, siehe
  [Messnetze ohne Standortdaten](../user/stations.md#messnetze-ohne-standortdaten).

## Limits

Es sind keine Limits dokumentiert. Die Integration nutzt eine eigene Obergrenze, die unter
denen der anderen Messnetze liegt, die alle Stationen in einer Abfrage liefern.

| Maßnahme | Wert |
|---|---|
| Stationsliste | Höchstens einmal am Tag aktualisiert und lokal gespeichert |
| Messwert-Cache | 9 Minuten, geteilt zwischen allen Standorten |
| Gesendete Abfragen | Höchstens 2 pro Minute und 30 pro Stunde |
| Geplante Abfragen | Höchstens 24 pro Stunde für alle Standorte zusammen |

Eine Abfrage liefert alle Stationen, die Anzahl der Stationen kostet also nichts:
[wie viele Stationen passen](../user/api-limits.md#eine-abfrage-fur-alle-stationen-dortmund-basel-zurich-karlsruhe).

## Besonderheiten

- Die Ebene enthält auch Boden-, Pegel- und Regensensoren; die Abfrage wählt die
  Lufttemperatursensoren (`beschreibung = 'Temperatur-Sensor'`).
- Stationen ohne Temperaturwert bleiben außen vor.
