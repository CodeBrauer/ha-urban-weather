<!-- source: 58aa671c1e367667f94b7ca1070334b68ae94fe3 -->
# Stationsempfehlung

Dichte Netze wie das Mannheimer mit über 400 Stationen haben viele davon in
Straßenschluchten, auf Dächern oder in Parks, oft nur wenige hundert Meter voneinander
entfernt. Ihre Werte unterscheiden sich, deshalb
ist die nächste Station nicht immer die beste für deinen Ort.

## Stationen

Eine Station ist ein Ort mit einem oder mehreren Sensormodulen: Temperatur und Luftfeuchte,
oft Luftdruck und Strahlung, an manchen Masten auch Wind. Module, die höchstens 15 m
auseinander liegen, gelten als eine Station. Jede Station hat:

| Eigenschaft | Quelle |
|---|---|
| Code, z. B. `0101-046` | Sensornamen der API |
| Stadtteil | OpenStreetMap |
| Umgebung | Lokale Klimazone aus dem Metadatenkatalog der Stadt, sonst aus der globalen LCZ-Karte |
| Dach oder Hochpunkt | Montagezone und Höhe über Grund aus dem Metadatenkatalog |

Details: [Stationen und Referenzdaten](../developer/reference-data.md).

## So entsteht die Empfehlung

```mermaid
flowchart TD
    All[Temperaturstationen<br>nach Entfernung sortiert] --> Street[Stationen auf Dächern<br>und Hochpunkten weglassen]
    Street --> Near{Nächste Station höchstens 1 km entfernt<br>und gleiche Umgebung?}
    Near -- ja --> Single[Allein verwenden]
    Near -- nein --> Radius[Stationen im Suchradius,<br>die 4 nächsten, wenn dort keine sind]
    Radius --> Order[Gleiche Umgebung zuerst,<br>dann die nächsten übrigen]
    Order --> Combine[Bis zu 4 Stationen kombinieren]
```

- Stationen auf Dächern oder Hochpunkten messen andere Temperaturen als im Straßenraum und
  werden für die Temperatur nicht empfohlen. Du kannst sie trotzdem selbst wählen; sie sind
  mit *Dach/Hochpunkt* gekennzeichnet.
- Die Windstation ist die nächste Station mit Windsensor, egal wo sie montiert ist.
- Die Begründung steht bei der Empfehlung: Die nächste Station passt, ist zu weit weg oder
  hat eine andere Umgebung.
- In einem [Messnetz ohne Standortdaten](#messnetze-ohne-standortdaten) entscheidet allein
  die Entfernung.
- *Empfehlung übernehmen* fehlt, wenn die Empfehlung nicht ins [API-Budget](api-limits.md)
  passt, zum Beispiel weil andere Standorte schon den Großteil davon nutzen. Wähle dann auf
  der Karte oder in der Liste weniger Stationen.

## Messnetze ohne Standortdaten

Das Dortmunder Messnetz veröffentlicht keine Daten zu Umgebung oder Montage. Seine Sensoren
werden nach der Stations-ID des Datensatzes gruppiert; der Code einer Station ist diese ID
(z. B. `DOBHAP`).

- Die nächste Station im Umkreis von 1 km wird allein verwendet; sonst werden bis zu
  4 Stationen im Suchradius kombiniert.
- Die Umgebung, die du bei der Einrichtung bestätigst, wird beim Standort gespeichert, ändert
  die Empfehlung aber nicht.
- Black-Globe-Sensoren bleiben außen vor: Sie messen eine Strahlungstemperatur, die bei
  Sonne mehrere Kelvin über der Lufttemperatur liegt.

## Selbst wählen

- **Eine Station** liefert genau ihre Werte, einschließlich kurzer lokaler Effekte.
- **Mehrere Stationen** liefern ihren Median, der ruhiger ist und näher am typischen Wert
  der Gegend liegt. Ab 4 Stationen werden Ausreißer verworfen.
- Höchstens 6 Stationen pro Standort; wie viele passen, hängt vom API-Budget ab.

## Neue Stationen

Die Stadt ergänzt immer wieder Stationen. Enthält die tägliche Stationsliste Stationen, die
in den letzten 30 Tagen neu hinzugekommen sind und zur aktuellen Empfehlung für einen
Standort gehören, schlägt ein Reparaturhinweis die neue Empfehlung vor.

- Die Auswahl ändert sich nur, wenn du den Vorschlag übernimmst, weil andere Stationen die
  Werte (Sprünge in Langzeitstatistiken) und das API-Budget verändern.
- Behältst du deine Stationen, wird der Vorschlag ignoriert. Er kommt erst bei einem anderen
  Vorschlag wieder.
- Passt die Empfehlung nicht ins API-Budget, erscheint kein Vorschlag.

Siehe [Reparaturen und Fehlersuche](troubleshooting.md#neue-stationen-in-der-nahe).
