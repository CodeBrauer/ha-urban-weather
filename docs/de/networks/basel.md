<!-- source: 25711af1905875fdfda970d20a0c68243d2462c1 -->
# Smart Climate Luftklima Basel

| | |
|---|---|
| Betreiber | Kanton Basel-Stadt, mit meteoblue |
| Messnetz | Smart Climate Luftklima |
| Plattform | Opendatasoft, [Datensatz 100009](https://data.bs.ch/explore/dataset/100009/) |
| Endpunkt | `https://data.bs.ch/api/explore/v2.1` |
| Zugriff | Öffentlich, kein Schlüssel |
| Lizenz | CC BY 4.0 |
| Quellenangabe | Kanton Basel-Stadt, CC BY 4.0 (data.bs.ch) |
| Kartenkacheln | osm.ch |
| Messnetz-ID | `basel` |

## Abdeckung

Etwa 70 aktive Stationen in Basel und Umgebung; einige liegen jenseits der Grenze in
Deutschland und Frankreich. Viele hängen an Straßenlaternen. Alle messen Temperatur. Das
Messnetz hat keine Luftfeuchte, also gibt es keinen Taupunkt und keine gefühlte Temperatur.
Niederschlag wird ebenfalls veröffentlicht, aber noch nicht genutzt.

## Daten

- Der Datensatz ist eine Zeitreihe, kein Eintrag pro Sensor: Jeder Sensor meldet etwa einmal
  pro Stunde, mit Lücken. Die Integration nutzt den neuesten Eintrag jedes Sensors.
- Jede Abfrage hat ein Zeitfenster, weil der ganze Datensatz Millionen Einträge enthält: Die
  Stationsliste blickt 24 Stunden zurück, die Messwerte 3 Stunden.
- Ein Messwert gilt 120 statt der üblichen 40 Minuten, damit die stündlichen Werte nicht in
  einem großen Teil jeder Stunde wegfallen.
- Stations-ID, Sensor-ID und Sensorname sind die des Datensatzes, ein Sensor pro Station.
- Eine Abfrage liefert die Werte aller Stationen, die die Standorte nutzen; die Zahl der
  Stationen kostet also keine Abfragen.
- Der Datensatz enthält keine Standortdaten. Die Stationsempfehlung arbeitet allein nach
  Entfernung, siehe
  [Messnetze ohne Standortdaten](../user/stations.md#messnetze-ohne-standortdaten).

## Limits

Jede Antwort meldet ein Kontingent von 500.000 Abfragen pro Tag (etwa 20.800 pro Stunde);
weitere Limits sind nicht dokumentiert.

| Maßnahme | Wert |
|---|---|
| Stationsliste | Höchstens einmal am Tag aktualisiert und lokal gespeichert |
| Messwert-Cache | 9 Minuten, geteilt zwischen allen Standorten |
| Gesendete Abfragen | Höchstens 2 pro Minute und 60 pro Stunde |
| Geplante Abfragen | Höchstens 60 pro Stunde für alle Standorte zusammen |

Eine Abfrage liefert alle Stationen, die Anzahl der Stationen kostet also nichts:
[wie viele Stationen passen](../user/api-limits.md#eine-abfrage-fur-alle-stationen-dortmund-basel-zurich-karlsruhe).

## Besonderheiten

- Die Werte sind Rohdaten, die der Betreiber nicht auf Plausibilität prüft.
