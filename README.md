<img src="custom_components/urban_weather/brand/icon@2x.png" alt="" width="96" align="right">

# Urban Weather (Stadtklima) für Home Assistant

**Deutsch** · [English](README.en.md) · [Dokumentation](https://codebrauer.github.io/ha-urban-weather/de/)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

Klimawerte für deinen Standort aus dem dichten Stadtklima-Messnetz von
[Smart City Mannheim](https://smartmannheim.de/) (über 400 Stationen): Temperatur,
Luftfeuchte, Taupunkt, absolute Feuchte, gefühlte Temperatur, Luftdruck, Globalstrahlung
und Wind.

Die Integration wählt die Station, die deinen Ort am besten abbildet. Passt die nächste
nicht (zu weit weg, andere Umgebung, auf einem Dach montiert), kombiniert sie stattdessen
mehrere Stationen um dich herum.

> Inoffizielles Projekt, nicht verbunden mit der Smart City Mannheim GmbH oder der Stadt
> Mannheim.

<p align="center"><img src="docs/screenshots/de/04-map.jpg" alt="Interaktive Stationskarte" width="800"></p>

## Warum?

Die Idee entstand aus einem einfachen Wunsch: eine gute Außentemperatur in Home Assistant,
die vor Ort gemessen und nicht über die globale Anbindung eines Wetterdienstes aus
Wettermodellen geschätzt wird. Die üblichen Alternativen überzeugen dafür kaum:

- **Zigbee- und Tuya-Klimasensoren** taugen draußen meist wenig: keine aktive Belüftung,
  der Montagepunkt oder Untergrund heizt sich auf, die Sensoren sind teils ungenau, und
  die Batterien müssen oft gewechselt werden.
- **Eine eigene Wetterstation** ist vergleichsweise teuer und muss zusätzlich
  Smart-Home-fähig sein.

Immer mehr Städte betreiben eigene Stadtklima-Messnetze. Diese Integration macht das Netz
von Smart City Mannheim in Home Assistant nutzbar.

## Funktionen

- **Standort auf der Karte**, vorbelegt mit deinem Zuhause aus Home Assistant.
- **Stationsempfehlung** nach Entfernung, Umgebung (lokale Klimazonen) und Montagehöhe,
  mit einem Klick übernehmen oder selbst wählen.
- **Interaktive Stationskarte**: zoomen, Stationen anklicken, Windstation wählen. Die Karte
  lässt nur so viele Stationen zu, wie ins API-Budget passen, und zeigt das resultierende
  Aktualisierungsintervall live an.
- **Eine Station oder eine Kombination**: Median mehrerer Stationen ohne Ausreißer; die
  Luftfeuchte wird über den Median-Taupunkt berechnet.
- **Sensoren**: Temperatur, Luftfeuchte, Taupunkt, absolute Feuchte, gefühlte Temperatur,
  Luftdruck\*, Globalstrahlung\*, Windgeschwindigkeit, Böe und Windrichtung (\*wenn die
  gewählten Stationen sie messen), dazu Diagnose-Sensoren (verwendete Stationen,
  Temperatur-Spannweite, letzte Messung). Standardmäßig deaktiviert: Minimum und Maximum
  der Temperatur im letzten 10-Minuten-Intervall und die Böenrichtung.
- **Wetter-Entität** mit allen aktuellen Werten. Der Zustand (sonnig / teilweise bewölkt /
  bewölkt) wird tagsüber aus der Globalstrahlung geschätzt, wenn mindestens 3 Stationen sie
  liefern. Das Netz hat keine Wolken- oder Regensensoren, nachts bleibt der Zustand daher
  unbekannt.
- **Hält die API-Limits ein** (gemeinsames Abfrage-Budget und Cache für alle Standorte).
- **Mehrere Standorte** (Zuhause, Arbeit, …), jeder als eigenes Gerät.
- **Reparaturhinweise**, wenn eine gewählte Station keine Daten mehr liefert oder
  verschwindet, mit Ersatzvorschlag zum direkten Übernehmen, und **Vorschläge**, wenn neue
  Stationen in der Nähe hinzukommen.
- **Neu konfigurieren**, um einen Standort zu verschieben, **Optionen** für Stationen,
  Aktualisierungsintervall und eine Taupunkt-Korrektur.
- **Diagnose-Download** (Koordinaten geschwärzt).
- Deutsch und Englisch.

## Verwandte Integration

Für dieselbe Klima-API gibt es auch [Smart City Mannheim](https://github.com/smartmannheim/smartmannheim)
(Domain `smartmannheim_klima`, in HACS als „Smart City Mannheim“). Dieses Projekt ist
inoffiziell und unabhängig davon.

| | Urban Weather (Stadtklima) (dieses Repo) | Smart City Mannheim |
|---|---|---|
| Ansatz | Ein Standort, Werte, die ihn am besten abbilden: passende Station oder Kombination mehrerer | Einzelne Sensoren wählen, Werte pro Station |
| Stationswahl | Empfehlung nach Entfernung, Umgebung und Montagehöhe; interaktive Karte | Suche nach Sensorcode oder Straße, Liste nach Entfernung |
| Zusätzliche Werte | Absolute Feuchte, gefühlte Temperatur, Wetter-Entität | Pollenflug, Luftqualität, DWD-Station Mannheim |

Beide lassen sich parallel installieren, teilen sich aber das API-Limit pro
Internetanschluss (30 Abfragen pro Stunde). Wer beide nutzt, hält die Zahl der Stationen
entsprechend klein.

## Installation

### HACS (benutzerdefiniertes Repository)

[![In HACS öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=CodeBrauer&repository=ha-urban-weather&category=integration)

Oder von Hand:

1. HACS → ⋮ → *Benutzerdefinierte Repositories* →
   `https://github.com/CodeBrauer/ha-urban-weather` mit Typ *Integration* hinzufügen.
2. *Urban Weather (Stadtklima)* installieren und Home Assistant neu starten.

### Manuell

`custom_components/urban_weather` in deinen Ordner `config/custom_components/`
kopieren und Home Assistant neu starten.

## Einrichtung

*Einstellungen → Geräte & Dienste → Integration hinzufügen → Urban Weather (Stadtklima)*

1. **Standort**: Pin verschieben, der Kreis ist der Suchradius.
2. **Umgebung**: Wie ist die Gegend um den Standort bebaut? Vorausgewählt aus der Karte
   der lokalen Klimazonen.
3. **Stationen**: Die Empfehlung wird begründet angezeigt. Du kannst sie übernehmen, auf
   der interaktiven Karte selbst wählen (öffnet sich in einem neuen Fenster, nach dem
   Speichern geht die Einrichtung automatisch weiter) oder aus einer Liste wählen.

| Standort | Stationen |
|---|---|
| ![Standort wählen](docs/screenshots/de/01-location.jpg) | ![Empfehlung und Auswahlwege](docs/screenshots/de/03-menu.png) |
| **Gerät mit Sensoren** | **Dashboard** |
| ![Gerät mit allen Sensoren](docs/screenshots/de/06-device.png) | ![Werte im Dashboard](docs/screenshots/de/07-dashboard.png) |

Später änderst du Stationen, Intervall und Taupunkt-Korrektur unter *Konfigurieren*. Die
interaktive Karte erreichst du dort über *Neu konfigurieren* (Home Assistant zeigt externe
Fenster in Options-Dialogen nicht zuverlässig an).

### So entsteht die Empfehlung

- Stationen auf Dächern oder Hochpunkten werden für die Temperatur nicht empfohlen.
- Ist die nächste Station im Straßenraum höchstens 1 km entfernt und hat dieselbe
  Umgebung, wird sie allein verwendet.
- Sonst werden bis zu 4 Stationen im Suchradius kombiniert, Stationen mit gleicher
  Umgebung zuerst.

Die Umgebung wird aus lokalen Klimazonen (LCZ) gruppiert: dicht bebaut (LCZ 1–3), locker
bebaut (4–6, 9), Industrie/Gewerbe (7, 8, 10) und grün/offen (11–17). Die Zone einer
Station stammt, wo vorhanden, aus dem Metadatenkatalog der Stadt, sonst aus der globalen
LCZ-Karte.

Kommen neue Stationen hinzu, die zur Empfehlung für einen eingerichteten Standort gehören,
erscheint 30 Tage lang ein Reparaturhinweis mit dem Vorschlag. Die Auswahl ändert sich nur,
wenn du ihn übernimmst: Andere Stationen verändern die Werte (Sprünge in
Langzeitstatistiken) und das API-Budget. Behältst du deine Stationen, kommt der Hinweis
erst bei einem anderen Vorschlag wieder.

## API-Limits

Die [Klima-API](https://api.smartmannheim.de/doc) ist öffentlich und braucht keinen
Schlüssel. Dokumentiert sind **30 Messwert-Abfragen pro Stunde und Internetanschluss**
(plus wenige Abfragen der Stationsliste). In der Praxis begrenzt die API zusätzlich kurze
Bursts (etwa 5 Abfragen pro 2 Minuten) und antwortet mit `429` und `Retry-After`.

Die Integration

- lädt die Stationsliste höchstens einmal am Tag und speichert sie lokal,
- speichert Messwerte 9 Minuten zwischen und teilt sie zwischen Standorten,
- sendet höchstens 4 Abfragen pro 2 Minuten und 30 pro Stunde und holt übersprungene
  Stationen kurz danach nach,
- plant für alle Standorte zusammen höchstens 24 Abfragen pro Stunde und wählt das
  Aktualisierungsintervall entsprechend (Standard 15 Minuten; neue Werte kommen ohnehin
  nur alle 10 Minuten mit 10–20 Minuten Verzögerung),
- behält bei einem `429` oder API-Ausfall die letzten Werte, bis die letzte Messung
  60 Minuten (bzw. drei Aktualisierungsintervalle, wenn das länger ist) alt ist; erst dann
  werden die Entitäten nicht verfügbar.

Andere Skripte oder Geräte, die die API über denselben Internetanschluss nutzen, teilen
sich das Limit.

## Wenn keine Daten mehr kommen

- Liefert eine gewählte Station 24 Stunden lang keine Daten oder kennt die API sie nicht
  mehr, erscheint ein Reparaturhinweis. Über *Beheben* übernimmst du die Empfehlung ohne
  diese Station oder wählst selbst aus einer Liste.
- Fällt die API aus, bleiben die letzten Werte stehen (siehe oben), danach werden die
  Entitäten nicht verfügbar. Dafür gibt es keinen Reparaturhinweis, weil du nichts beheben
  kannst.

Automationen, die die Temperatur verwenden, können auf den Ausfall reagieren, zum Beispiel
mit einer Push-Nachricht aufs Handy. Entität und Benachrichtigungsdienst passt du an deine
Installation an:

```yaml
alias: "Klimamessnetz: keine Temperatur"
triggers:
  - trigger: state
    entity_id: sensor.seckenheim_temperatur
    to: unavailable
    for:
      minutes: 30
actions:
  - action: notify.mobile_app_mein_handy
    data:
      message: Seit 30 Minuten keine Temperatur vom Klimamessnetz Mannheim.
```

## Datenquellen und Lizenzen

| Daten | Quelle | Lizenz |
|---|---|---|
| Messwerte, Stationsliste | [Klima-API Smart City Mannheim](https://opendata.smartmannheim.de/dataset/klimadaten-echtzeit-api) | dl-de/by-2-0 |
| Standort-Metadaten der Stationen | [Metadatenkatalog Stadtklimamessnetze Mannheim](https://opendata.smartmannheim.de/dataset/metadaten-stadtklimamessnetze-mannheim) | dl-de/by-2-0 |
| Lokale Klimazonen | Demuzere et al. (2022), [Global map of LCZ](https://doi.org/10.5281/zenodo.6364594) | CC BY 4.0 |
| Stadtteilnamen | © OpenStreetMap-Mitwirkende über Nominatim | ODbL 1.0 |
| Kartenkacheln der Stationskarte | [basemap.de](https://basemap.de/) / BKG | CC BY 4.0 |
| Kartenbibliothek (mitgeliefert) | [Leaflet 1.9.4](https://leafletjs.com/) | BSD-2-Clause |

Die statischen Referenzdateien in `custom_components/urban_weather/providers/mannheim/data/`
erzeugt `scripts/build_reference_data.py` (Quelle und Datum stehen jeweils im Feld `source`).

## Entwicklung

```bash
scripts/setup      # legt .venv mit Home Assistant an (uv)
scripts/develop    # startet Home Assistant auf http://localhost:8123 mit dieser Integration
scripts/lint       # ruff format + check
scripts/test       # pytest (Argumente werden durchgereicht, z. B. -k recommend)
```

Auf macOS gibt es für einige Abhängigkeiten von Home Assistant (`pymicro-vad`,
`pyspeex-noise`) keine Wheels für Python 3.14, und der Build scheitert. Einmal mit
SDK-Pfad bauen:

```bash
SDK=$(xcrun --show-sdk-path) SDKROOT="$SDK" CXXFLAGS="-isysroot $SDK -I$SDK/usr/include/c++/v1" uv pip install --python .venv/bin/python pymicro-vad pyspeex-noise
```

Referenzdaten neu erzeugen (selten nötig, z. B. nach einem neuen Metadatenkatalog):

```bash
uv run --no-project --with openpyxl --with rasterio python scripts/build_reference_data.py
```

## Unterstützen

Wenn dir die Integration gefällt, kannst du mir ein Bier ausgeben:

[![Buy me a beer](https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20beer&emoji=%F0%9F%8D%BA&slug=codebrauer&button_colour=ffe500&font_colour=000000&font_family=Poppins&outline_colour=000000&coffee_colour=FFDD00)](https://buymeacoffee.com/codebrauer)

## Lizenz

MIT, siehe [LICENSE](LICENSE).
