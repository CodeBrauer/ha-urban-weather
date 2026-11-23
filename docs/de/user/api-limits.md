<!-- source: b0490bc717689fee9549a565f1f0511d43397e31 -->
# API-Limits

Jedes Messnetz hat eigene Limits und ein eigenes Abfrage-Budget; Standorte in einem Messnetz
nehmen Standorten in einem anderen keine Stationen weg. Die dokumentierten Limits und was die
Integration sendet, stehen auf der Seite des jeweiligen Messnetzes:
[Smart City Mannheim](../networks/mannheim.md#limits),
[Klimamessnetz Dortmund](../networks/dortmund.md#limits),
[Stadtklimamessnetz Zürich](../networks/zurich.md#limits) und
[Sensor City Karlsruhe](../networks/karlsruhe.md#limits). Diese Seite erklärt, wie das
Budget die Zahl der Stationen begrenzt.

Die Limits gelten für alles hinter deinem Internetanschluss (öffentliche IP-Adresse): Andere
Integrationen in Home Assistant, Skripte oder Geräte, die dieselbe API nutzen, teilen sie sich.

## Wie viele Stationen passen

Die Summe der Abfragen aller aktivierten Standorte eines Messnetzes darf höchstens die
geplanten Abfragen pro Stunde betragen (24 in Mannheim und Karlsruhe, 60 in Dortmund und Zürich). Wie viele Abfragen
ein Standort braucht, hängt davon ab, wie das Messnetz seine Werte liefert.

### Eine Abfrage pro Station (Mannheim)

Jeder Standort braucht pro gewählter Station und Aktualisierung eine Abfrage, die
Windstation zählt als Station:

```text
Abfragen pro Stunde = (Stationen + Windstation) × 60 / Aktualisierungsintervall in Minuten
```

| Stationen + Wind | 10 min | 15 min | 20 min | 30 min |
|---|---|---|---|---|
| 1 + 1 | 12 | **8** | 6 | 4 |
| 2 + 1 | 18 | **12** | 9 | 6 |
| 4 + 1 | 30 | **20** | 15 | 10 |
| 6 + 1 | 42 | 28 | **21** | 14 |

Fett: das Intervall, das für einen einzelnen Standort automatisch gewählt wird (das kürzeste
von 15, 20 und 30 Minuten, das passt). 10 Minuten lassen sich in den Optionen wählen, wenn
das Budget es zulässt.

- Einrichtung, Karte und Optionen lassen nur Auswahlen zu, die passen. Die Karte zeigt, wie
  viele Stationen passen und welches Intervall sich ergibt.
- Deaktivierte Standorte zählen nicht.
- Bei mehreren Standorten lässt jeder den anderen weniger Stationen oder ein längeres
  Intervall.

### Eine Abfrage für alle Stationen (Dortmund, Zürich)

Eine Abfrage liefert die Werte aller Stationen, die die Standorte nutzen. Die Anzahl der
Stationen kostet also keine Abfragen. [Karlsruhe](../networks/karlsruhe.md) funktioniert genauso:

```text
Abfragen pro Stunde = 60 / Aktualisierungsintervall in Minuten   (pro Standort)
```
