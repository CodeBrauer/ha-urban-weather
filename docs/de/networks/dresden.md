<!-- source: 57eea22e233cdc5d8efa6c1dbd23549a1fe44fe9 -->
# KLIPS Dresden

| | |
|---|---|
| Betreiber | Landeshauptstadt Dresden, Umweltamt (Sensornetz des Forschungsprojekts KLIPS) |
| Messnetz | KLIPS-Temperatursensoren, „Lufttemperatur und Relative Feuchte - aktuelle Messwerte“ |
| Plattform | WFS des städtischen GIS (Ebene `cls:L1625`), [Themenstadtplan](https://stadtplan.dresden.de/?TH=UW_KLIPS_TEMPERATUR_MESS) |
| Endpunkt | `https://kommisdd.dresden.de/net3/public/ogc.ashx` |
| Zugriff | Öffentlich, kein Schlüssel |
| Lizenz | dl-de/by-2-0 |
| Quellenangabe | Landeshauptstadt Dresden (KLIPS sensor network), dl-de/by-2-0 |
| Kartenkacheln | basemap.de |
| Messnetz-ID | `dresden` |

## Abdeckung

Etwa 120 aktuelle Stationen in ganz Dresden, am dichtesten im Zentrum, in der Neustadt und in
Blasewitz; installiert sind etwa 260 Sensoren, viele davon inaktiv. Alle messen Temperatur und
Luftfeuchte; Luftdruck, Strahlung und Wind liefert das Messnetz nicht.

## Daten

- Der Dienst enthält Stundenwerte seit 2023, ein Feature pro Sensor, Wert und Stunde. Die
  Integration fasst sie pro Sensor zusammen und nutzt jeweils die neueste Stunde.
- Jede Abfrage hat ein Zeitfenster, weil die ganze Ebene mehrere Jahre enthält: Die
  Stationsliste blickt 24 Stunden zurück, die Messwerte 4 Stunden.
- Die Werte kommen ein bis zwei Stunden nach der vollen Stunde an, bei manchen Sensoren
  Stunden später. Ein Messwert gilt 4 Stunden statt der üblichen 40 Minuten, damit eine
  Station genutzt bleibt, bis ihr nächster Wert ankommt. Die letzten Werte bleiben 6 Stunden
  erhalten.
- Jeder Sensor ist eine eigene Station; seine `device`-Nummer ist der Stationscode, der Name
  ist seine Adresse (zum Beispiel `Postplatz (DVB)`).
- Stationsliste und Messwerte kommen aus derselben Ebene und kosten je eine Abfrage; die Zahl
  der Stationen kostet also keine Abfragen.
- Die Ebene enthält keine Standortdaten. Die Stationsempfehlung arbeitet allein nach
  Entfernung, siehe
  [Messnetze ohne Standortdaten](../user/stations.md#messnetze-ohne-standortdaten).

## Limits

Es sind keine Limits dokumentiert. Die Werte sind stündlich, deshalb nutzt die Integration eine
niedrige eigene Obergrenze: eine Aktualisierung alle 15 Minuten für bis zu 3 Standorte.

| Maßnahme | Wert |
|---|---|
| Stationsliste | Höchstens einmal am Tag aktualisiert und lokal gespeichert |
| Messwert-Cache | 9 Minuten, geteilt zwischen allen Standorten |
| Gesendete Abfragen | Höchstens 2 pro Minute und 24 pro Stunde |
| Geplante Abfragen | Höchstens 12 pro Stunde für alle Standorte zusammen |

Eine Abfrage liefert alle Stationen, die Anzahl der Stationen kostet also nichts:
[wie viele Stationen passen](../user/api-limits.md#eine-abfrage-fur-alle-stationen-dortmund-basel-zurich-karlsruhe-dresden).

## Besonderheiten

- Die Zeiten sind das ganze Jahr Mitteleuropäische Zeit (ohne Sommerzeit).
- Viele Sensoren hängen an Laternenmasten in mehr als 3 m Höhe. Die Werte sind
  strahlungskorrigiert.
- Manche Sensoren melden eine Luftfeuchte von 0 %; unplausible Werte bleiben außen vor.
- Manche Stationsnamen beginnen mit `$` oder `#`; die Integration lässt diese Zeichen weg.
- Stationen ohne Position bleiben außen vor, ebenso Stationen, deren neuester Wert mehr als
  4 Stunden älter ist als der neueste Wert des Messnetzes.
- Der Server beendet eine komprimierte Antwort nie, deshalb fragt die Integration eine
  unkomprimierte an (`Accept-Encoding: identity`).
