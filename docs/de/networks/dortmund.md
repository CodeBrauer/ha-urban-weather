<!-- source: a521c61b911c60418d04a97b060b179ba60a2a18 -->
# Klimamessnetz Dortmund

| | |
|---|---|
| Betreiber | Stadt Dortmund; aufgebaut im Projekt Data2Resilience mit der Ruhr-Universität Bochum |
| Messnetz | Klimasensoren - Aktuelle Messung |
| Plattform | Opendatasoft, [Datensatz](https://open-data.dortmund.de/explore/dataset/klimasensoren-aktuelle-messungen/) |
| Endpunkt | `https://open-data.dortmund.de/api/explore/v2.1` |
| Zugriff | Öffentlich, kein Schlüssel |
| Lizenz | dl-de/zero-2-0 |
| Quellenangabe | Stadt Dortmund, dl-de/zero-2-0 (open-data.dortmund.de) |
| Kartenkacheln | basemap.de |
| Messnetz-ID | `dortmund` |

## Abdeckung

76 Stationen in ganz Dortmund. Alle messen Temperatur und Luftfeuchte; etwa ein Drittel
misst zusätzlich Luftdruck, Globalstrahlung und Wind (Geschwindigkeit, Böe und Richtung).

## Daten

- Der Datensatz enthält pro Sensor einen Eintrag mit der letzten Messung. Neue Werte kommen
  alle 5 Minuten.
- Sensoren werden über die Stations-ID des Datensatzes zu Stationen gruppiert; sie ist auch
  der Stationscode (z. B. `DOBHAP`). Innerhalb einer Station wird der Sensor mit den meisten
  Werten genutzt.
- Eine Abfrage liefert die Werte aller Stationen, die die Standorte nutzen; die Zahl der
  Stationen kostet also keine Abfragen.
- Der Datensatz enthält keine Standortdaten. Die Stationsempfehlung arbeitet allein nach
  Entfernung, siehe
  [Messnetze ohne Standortdaten](../user/stations.md#messnetze-ohne-standortdaten).

## Limits

Jede Antwort meldet ein Kontingent von 50.000 Abfragen pro Tag (etwa 2.083 pro Stunde);
weitere Limits sind nicht dokumentiert.

| Maßnahme | Wert |
|---|---|
| Stationsliste | Höchstens einmal am Tag aktualisiert und lokal gespeichert |
| Messwert-Cache | 9 Minuten, geteilt zwischen allen Standorten |
| Gesendete Abfragen | Höchstens 2 pro Minute und 60 pro Stunde |
| Geplante Abfragen | Höchstens 60 pro Stunde für alle Standorte zusammen |

Eine Abfrage liefert alle Stationen, die Anzahl der Stationen kostet also nichts:
[wie viele Stationen passen](../user/api-limits.md#eine-abfrage-fur-alle-stationen-dortmund-basel-zurich-karlsruhe-dresden).

## Besonderheiten

- Black-Globe-Sensoren bleiben außen vor: Sie melden eine Strahlungstemperatur als
  Lufttemperatur, die in der Sonne mehrere Kelvin über der Lufttemperatur liegt.
- Der Luftdruck kommt in kPa und wird in hPa umgerechnet.
- Ein Sensor, der 24 Stunden still war, wird aus seiner Station herausgenommen, wenn die
  Station einen aktuellen Sensor hat. So verdeckt ein Sensor, der nicht mehr sendet, nicht
  seinen Ersatz.
