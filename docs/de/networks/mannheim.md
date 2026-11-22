<!-- source: 4505478eb4db0d1d050e32e866f52954108cda59 -->
# Smart City Mannheim

| | |
|---|---|
| Betreiber | Smart City Mannheim GmbH |
| Messnetz | Stadtklima-Messnetz Mannheim |
| Plattform | Eigene REST-API, [Dokumentation](https://api.smartmannheim.de/doc) |
| Endpunkt | `https://api.smartmannheim.de/climate` |
| Zugriff | Öffentlich, kein Schlüssel |
| Lizenz | dl-de/by-2-0 |
| Quellenangabe | Smart City Mannheim GmbH, dl-de/by-2-0 (opendata.smartmannheim.de) |
| Kartenkacheln | basemap.de |
| Messnetz-ID | `mannheim` |

## Abdeckung

Über 400 Stationen in ganz Mannheim, viele davon in Straßenschluchten, auf Dächern oder in
Parks, nur wenige hundert Meter voneinander entfernt. Neben Temperatur und Luftfeuchte misst
das Messnetz:

- Luftdruck und Globalstrahlung (neuere Hardware-Generationen),
- Wind an einigen Masten,
- Taupunkt, minimale und maximale Temperatur sowie eine 1-Sekunden- und 3-Sekunden-Böe mit
  ihrer Richtung.

Welche Werte eine Station liefert, ist unterschiedlich; Entitäten gibt es nur für Werte, die
die gewählten Stationen messen (siehe [Entitäten](../user/entities.md)).

## Daten

- Die API listet Sensormodule, keine Stationen. Module im Abstand von höchstens 15 m bilden
  eine Station. Eine Station hat ein Temperaturmodul und, falls vorhanden, ein Windmodul.
- Pro Modul liefert die API die Messwerte der letzten 60 Minuten; die Integration nutzt den
  neuesten gültigen. Das kostet eine Abfrage pro Sensor.
- Standortdaten liegen der Integration bei: der Metadatenkatalog der Stadt (Montagezone,
  Höhe über Grund, Local Climate Zone), ein Raster der Local Climate Zones als Rückfall und
  ein Stadtteilname je Station. Die [Stationsempfehlung](../user/stations.md) nutzt sie.
  Details und Quellen: [Stationen und Referenzdaten](../developer/reference-data.md).
- Der Stationscode sind die ersten 8 Zeichen des Sensornamens (`0101-046` aus
  `0101-046-21`).

## Limits

Die [Klima-API](https://api.smartmannheim.de/doc) dokumentiert **30 Messwert-Abfragen pro
Stunde und Internetanschluss** (öffentliche IP-Adresse), dazu wenige Abfragen der
Stationsliste. In der Praxis begrenzt sie zusätzlich kurze Bursts (etwa 5 Abfragen pro
2 Minuten) und antwortet mit `429` und einem `Retry-After`-Header. Alles hinter deinem
Internetanschluss, das `api.smartmannheim.de` nutzt, teilt sich das Limit.

| Maßnahme | Wert |
|---|---|
| Stationsliste | Höchstens einmal am Tag geladen und lokal gespeichert; ist die API nicht erreichbar, wird die gespeicherte Kopie verwendet |
| Messwert-Cache | 9 Minuten, geteilt zwischen allen Standorten |
| Gesendete Abfragen | Höchstens 4 pro 2 Minuten und 30 pro Stunde; übersprungene Stationen werden kurz danach nachgeholt |
| Geplante Abfragen | Höchstens 24 pro Stunde für alle Standorte zusammen, 6 bleiben also für andere Clients frei |
| Nach einer `429` | Keine Abfragen, bis `Retry-After` abgelaufen ist |

Jede Station kostet bei jeder Aktualisierung eine Abfrage: [wie viele Stationen passen](../user/api-limits.md#eine-abfrage-pro-station-mannheim).

## Verwandte Integration

[Smart City Mannheim](https://github.com/smartmannheim/smartmannheim) (Domain
`smartmannheim_klima`) nutzt dieselbe API. Beide lassen sich parallel installieren, teilen
sich aber das Limit von 30 Abfragen pro Stunde. Diese Integration plant nur ihre eigenen
Abfragen, halte die Zahl der Stationen deshalb in beiden klein.

| | Urban Weather (Stadtklima) | Smart City Mannheim |
|---|---|---|
| Ansatz | Ein Standort, Werte, die ihn am besten abbilden: passende Station oder Kombination mehrerer | Einzelne Sensoren wählen, Werte pro Station |
| Stationswahl | Empfehlung nach Entfernung, Umgebung und Montagehöhe; interaktive Karte | Suche nach Sensorcode oder Straße, Liste nach Entfernung |
| Zusätzliche Werte | Absolute Feuchte, gefühlte Temperatur, Wetter-Entität | Pollenflug, Luftqualität, DWD-Station Mannheim |

## Besonderheiten

- Manche Sensoren melden vertauschte Koordinaten; die Integration tauscht sie zurück (in
  Deutschland ist der Breitengrad größer als der Längengrad).
- Sensoren ohne brauchbare Position werden übersprungen.
- Das Messnetz misst tendenziell zu feucht. Die
  [Taupunkt-Korrektur](../user/setup.md) gleicht das aus; −1,3 K passten in einem
  31-Tage-Vergleich zur DWD-Station Mannheim.
- Stationen auf Dächern oder Hochpunkten messen andere Temperaturen als auf Straßenhöhe und
  werden für die Temperatur nicht empfohlen.
