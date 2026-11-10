<!-- source: 87c4520d586c7cfdf21232c7596c9fce9fcccff0 -->
# API-Limits

Die [Klima-API](https://api.smartmannheim.de/doc) ist öffentlich und braucht keinen
Schlüssel. Dokumentiert sind **30 Messwert-Abfragen pro Stunde und Internetanschluss**
(öffentliche IP-Adresse), dazu wenige Abfragen der Stationsliste. In der Praxis begrenzt die
API zusätzlich kurze Bursts (etwa 5 Abfragen pro 2 Minuten) und antwortet mit `429` und
einem `Retry-After`-Header.

Das Limit gilt für alles hinter deinem Internetanschluss: Andere Integrationen in Home
Assistant, Skripte oder Geräte, die `api.smartmannheim.de` nutzen, teilen es sich.

## Was die Integration tut

| Maßnahme | Wert |
|---|---|
| Stationsliste | Höchstens einmal am Tag geladen und lokal gespeichert; ist die API nicht erreichbar, wird die gespeicherte Kopie verwendet |
| Messwert-Cache | 9 Minuten, geteilt zwischen allen Standorten |
| Gesendete Abfragen | Höchstens 4 pro 2 Minuten und 30 pro Stunde; übersprungene Stationen werden kurz danach nachgeholt |
| Geplante Abfragen | Höchstens 24 pro Stunde für alle Standorte zusammen, 6 bleiben also für andere Clients frei |
| Nach einer `429` | Keine Abfragen, bis `Retry-After` abgelaufen ist |

## Wie viele Stationen passen

Jeder Standort braucht pro gewählter Station und Aktualisierung eine Abfrage, die
Windstation zählt als Station:

```text
Abfragen pro Stunde = (Stationen + Windstation) × 60 / Aktualisierungsintervall in Minuten
```

Die Summe über alle aktivierten Standorte darf höchstens 24 betragen.

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
