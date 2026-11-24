<!-- source: 7e831481af5295518d7fc5e9f787f8a2c5354f06 -->
# Felder

Ein Netz ordnet seine eigenen Feldnamen den `Field`-Werten der Integration (`const.py`) zu,
in den `fields` seines `Network`. Diese Seite listet Einheit, Entität und Kombinationsregel
jedes Werts, den die Integration nutzt oder plant, damit alle Netze einen Wert gleich
abbilden.

## Regeln

- Der Provider liefert die Einheit der Tabelle und rechnet um, wenn das Netz eine andere
  nutzt (z. B. kPa oder Pa in hPa).
- Ein Sensor wird nur angelegt, wenn eine der gewählten Stationen seinen Wert misst.
- Ein geplanter Wert bekommt sein `Field`-Mitglied, seinen Plausibilitätsbereich und seinen
  Sensor mit dem ersten Netz, das ihn liefert, nach dieser Seite.
- Werte ohne Home-Assistant-Geräteklasse für ihre Einheit (z. B. NOx, UV-Intensität) sind
  nicht geplant.

## Aktuelle Felder

| `Field` | Einheit | Entität (Geräteklasse) | Kombiniert |
|---|---|---|---|
| `TEMPERATURE` | °C | Temperatur (`temperature`) | Median |
| `MIN_TEMPERATURE`, `MAX_TEMPERATURE` | °C | Temperatur Minimum, Maximum (`temperature`) | Median |
| `HUMIDITY` | % | Luftfeuchtigkeit (`humidity`) | Über den Taupunkt |
| `DEW_POINT` | °C | Keine, der Taupunkt wird aus Temperatur und Luftfeuchtigkeit berechnet | Nicht genutzt |
| `PRESSURE` | hPa | Luftdruck (`atmospheric_pressure`) | Median |
| `IRRADIANCE` | W/m² | Globalstrahlung (`irradiance`) | Maximum |
| `WIND_SPEED` | m/s | Windgeschwindigkeit (`wind_speed`) | Windstation |
| `WIND_GUST`, `WIND_GUST_1S` | m/s | Windböe (`wind_speed`) | Windstation |
| `WIND_DIRECTION`, `WIND_GUST_DIRECTION` | ° | Windrichtung, Böenrichtung (`wind_direction`) | Windstation |

Wie die Stationen kombiniert werden, die Plausibilitätsbereiche und die berechneten Werte
(Taupunkt, absolute Luftfeuchtigkeit, gefühlte Temperatur) beschreibt
[Aggregation](aggregation.md).

## Geplante Felder

| `Field` | Einheit | Entität (Geräteklasse) | Kombiniert | Geplant mit |
|---|---|---|---|---|
| `PRECIPITATION` | mm/h | Niederschlagsintensität (`precipitation_intensity`) | Median | Basel, Dortmund ([#103](https://github.com/CodeBrauer/ha-urban-weather/issues/103)) |
| `ILLUMINANCE` | lx | Beleuchtungsstärke (`illuminance`) | Maximum | openSenseMap ([#66](https://github.com/CodeBrauer/ha-urban-weather/issues/66)) |
| `PM1` | µg/m³ | PM1 (`pm1`) | Median | sensor.community ([#65](https://github.com/CodeBrauer/ha-urban-weather/issues/65)) |
| `PM25` | µg/m³ | PM2.5 (`pm25`) | Median | openSenseMap, sensor.community, Wien ([#64](https://github.com/CodeBrauer/ha-urban-weather/issues/64)) |
| `PM10` | µg/m³ | PM10 (`pm10`) | Median | openSenseMap, sensor.community, Wien |
| `NITROGEN_DIOXIDE` | µg/m³ | Stickstoffdioxid (`nitrogen_dioxide`) | Median | Wien |
| `OZONE` | µg/m³ | Ozon (`ozone`), auch an der Wetter-Entität | Median | Wien |
| `SULPHUR_DIOXIDE` | µg/m³ | Schwefeldioxid (`sulphur_dioxide`) | Median | Wien |
| `CARBON_MONOXIDE` | mg/m³ | Kohlenmonoxid (`carbon_monoxide`) | Median | Wien |

- **Niederschlag** ist eine Intensität, keine Menge pro Intervall, weil Netze über
  verschiedene Intervalle melden: Der Niederschlag der letzten Stunde in mm ist die mittlere
  Intensität in mm/h, eine Menge pro 5 Minuten wird mit 12 multipliziert.
- **Beleuchtungsstärke** nutzt wie die Globalstrahlung das Maximum, weil Sensoren oft
  verschattet sind.
- **Luftschadstoffe** nutzen den Median der gewählten Stationen, die den Wert messen. Die
  Werte an Verkehrsstationen und im Hintergrund unterscheiden sich stark; die Stationen
  werden nicht nach Lage gefiltert, du wählst sie aus.
- **Günstige Feinstaubsensoren** messen bei hoher Luftfeuchtigkeit zu hoch. Eine Korrektur
  gibt es noch nicht.
- Ein Luftqualitätsindex wird nicht berechnet.
