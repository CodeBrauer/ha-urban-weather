<!-- source: 63bbae45e7488d8c6741127762575b4de38f12ab -->
# Entitäten

Jeder Standort liefert Sensoren und eine Wetter-Entität. Gemessen wird alle 10 Minuten, die
Werte kommen mit 10–20 Minuten Verzögerung an; Messungen, die älter als 40 Minuten sind,
werden nicht verwendet.

## Sensoren

Ein Sensor wird nur angelegt, wenn eine der gewählten Stationen seinen Wert misst.

| Sensor | Einheit | Angelegt, wenn | Wert |
|---|---|---|---|
| Temperatur | °C | immer | Median der Stationen |
| Temperatur (Minimum) | °C | die Stationen sie messen | Median der Minima der Stationen im letzten 10-Minuten-Intervall. Standardmäßig deaktiviert. |
| Temperatur (Maximum) | °C | die Stationen sie messen | Median der Maxima der Stationen im letzten 10-Minuten-Intervall. Standardmäßig deaktiviert. |
| Luftfeuchtigkeit | % | die Stationen Luftfeuchte messen | Berechnet aus Taupunkt und Temperatur |
| Taupunkt | °C | die Stationen Luftfeuchte messen | Median-Taupunkt der Stationen plus Taupunkt-Korrektur |
| Absolute Luftfeuchtigkeit | g/m³ | die Stationen Luftfeuchte messen | Berechnet aus Temperatur und Luftfeuchte |
| Gefühlte Temperatur | °C | Luftfeuchte und eine Windstation | Temperatur, wie sie sich anfühlt, mit Luftfeuchte und Wind |
| Luftdruck | hPa | die Stationen ihn messen | Median der Stationen |
| Globalstrahlung | W/m² | die Stationen sie messen | Maximum der Stationen, weil Sensoren im Straßenraum oft verschattet sind |
| Windgeschwindigkeit | km/h | Windstation | Mittlere Windgeschwindigkeit (die API liefert m/s) |
| Windböe | km/h | die Windstation eine Böe misst | 3-Sekunden-Böe, sonst 1-Sekunden-Böe |
| Windrichtung | ° | die Windstation sie misst | Mittlere Windrichtung |
| Böenrichtung | ° | die Windstation sie misst | Richtung der Böe. Standardmäßig deaktiviert. |
| Verwendete Stationen | | immer | Diagnose: Stationen mit aktuellen Daten, ohne Ausreißer |
| Temperatur-Spannweite | K | immer | Diagnose: Unterschied zwischen der wärmsten und der kältesten verwendeten Station |
| Letzte Messung | | immer | Diagnose: Zeitpunkt der neuesten verwendeten Messung |

Wie die Stationen kombiniert werden, beschreibt [Aggregation](../developer/aggregation.md).

### Attribute des Temperatursensors

| Attribut | Inhalt |
|---|---|
| `stations` | Pro Stationscode: `temperature`, `humidity` (nur wenn die Stationen sie messen), `distance_km` und `timestamp` der verwendeten Messung |
| `dropped_outliers` | Codes der Stationen, die als Ausreißer verworfen wurden |
| `humidity_uncorrected` | Luftfeuchte ohne Taupunkt-Korrektur (nur wenn die Stationen Luftfeuchte messen) |

## Wetter-Entität

Die Wetter-Entität zeigt die aktuelle Temperatur, gefühlte Temperatur, Taupunkt,
Luftfeuchte, Luftdruck, Windgeschwindigkeit, Böe und Windrichtung, soweit die gewählten Stationen sie messen.
Eine Vorhersage hat sie nicht.

Der Zustand wird aus der Globalstrahlung geschätzt, weil das Netz keine Wolken- oder
Regensensoren hat:

| Zustand | Gemessene Strahlung im Vergleich zu wolkenlosem Himmel |
|---|---|
| Sonnig | mindestens 55 % |
| Teilweise bewölkt | mindestens 25 % |
| Bewölkt | weniger als 25 % |
| Unbekannt | nachts, bei Sonnenstand unter 10° oder wenn weniger als 3 Stationen Strahlung messen |

<div class="screenshots" markdown>

![Details der Wetter-Entität](../screenshots/09-weather.png)

</div>

![Werte im Dashboard](../screenshots/07-dashboard.png)

## Wenn Werte fehlen

Ist die API nicht erreichbar oder greift ihr Rate-Limit, behalten die Entitäten ihre letzten
Werte, bis die letzte Messung 60 Minuten alt ist (oder drei Aktualisierungsintervalle, wenn
das länger ist). Danach werden sie nicht verfügbar. Siehe
[Reparaturen und Fehlersuche](troubleshooting.md).
