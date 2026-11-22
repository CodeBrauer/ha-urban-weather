<!-- source: 0cc35d7872b30c02bff25d7e2002055b118b6d24 -->
# Stationen und Referenzdaten

Die Mannheimer API listet Sensoren (Module), keine Stationen, und hat keine Metadaten zum
Standort der Messung. Der Mannheim-Provider gruppiert die Sensoren
(`providers/mannheim/stations.py`) und ergänzt Daten, die in
`custom_components/urban_weather/providers/mannheim/data/` mitgeliefert werden.

## Von Sensoren zu Stationen

```mermaid
flowchart TD
    S[API-Sensoren mit Position<br>und Parametern] --> Fix[Koordinaten tauschen, wo<br>Breite < Länge]
    Fix --> Cluster[Sensoren im Umkreis von<br>STATION_CLUSTER_RADIUS_M bündeln]
    Cluster --> Pick[Pro Bündel: Temperatur- und Windsensor,<br>jeweils der mit den meisten Parametern]
    Pick --> Cat{Katalogeintrag per Sensorname,<br>sonst im Umkreis von CATALOG_MATCH_RADIUS_M}
    Cat --> LCZ[LCZ aus dem Katalog,<br>sonst aus dem LCZ-Raster]
    Cat --> Zone[Montagezone und<br>Höhe über Grund]
    Pick --> District[Stadtteil im Umkreis von<br>DISTRICT_MATCH_RADIUS_M]
    LCZ --> Station[Station]
    Zone --> Station
    District --> Station
```

- Sensoren ohne brauchbare Position werden übersprungen. Manche Sensoren haben vertauschte
  Koordinaten; in Deutschland ist die Breite immer größer als die Länge.
- Mehr Parameter bedeuten eine neuere Hardware-Generation, zum Beispiel mit Luftdruck.
- Der Stationscode sind die ersten 8 Zeichen eines Sensornamens im Katalogformat
  (`0101-046` aus `0101-046-21`), sonst der Name des Temperatursensors.
- Bei der Zuordnung über die Position hat das Temperaturmodul Vorrang vor einem Windmodul am
  selben Ort.
- Eine Station ist erhöht (`is_elevated`), wenn ihre Zone Dach oder Hochpunkt ist oder sie
  über Grund montiert ist. Erhöhte Stationen werden für die Temperatur nicht empfohlen.

## Mitgelieferte Dateien

| Datei | Inhalt | Quelle | Lizenz |
|---|---|---|---|
| `catalog.json` | Metadaten pro Sensormodul: Code, Hardware-ID, Position, Höhen, Zone, LCZ | [Metadatenkatalog Stadtklimamessnetze Mannheim](https://opendata.smartmannheim.de/dataset/metadaten-stadtklimamessnetze-mannheim) | dl-de/by-2-0 |
| `lcz_grid.json` | Raster der lokalen Klimazonen um Mannheim, zlib-komprimiert | Demuzere et al. (2022), [Global map of LCZ](https://doi.org/10.5281/zenodo.6364594) | CC BY 4.0 |
| `districts.json` | Stadtteilname pro Stationsstandort | © OpenStreetMap-Mitwirkende über Nominatim | ODbL 1.0 |

Jede Datei hat einen `source`-Header mit Titel, URL, Lizenz und Erstellungsdatum. Die
Dateien werden einmal im Executor geladen, wenn der Hub angelegt wird.

## Neu erzeugen

Die Dateien erzeugt `scripts/build_reference_data.py`; bearbeite sie nicht von Hand. Neu
erzeugen musst du sie selten, etwa nach einem neuen Metadatenkatalog oder wenn viele neue
Stationen keinen Stadtteil haben:

```bash
uv run --no-project --with openpyxl --with rasterio python scripts/build_reference_data.py
```

Das Skript ruft die Stationsliste einmal ab (oder nutzt mit `--sensors-file` eine
gespeicherte Antwort) und fragt Nominatim einmal pro Stationsstandort, der noch nicht in
`.cache/reference-build/` liegt, mit einer Pause zwischen den Abfragen.
`--only catalog|lcz|districts` erzeugt eine einzelne Datei.
