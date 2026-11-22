<!-- source: 200224189104626d93aaaf6ff0e521dc15af4fdf -->
# Unterstützte Messnetze

Die Integration liest Stadtklima-Messnetze von Städten. Ein Messnetz ist eine Reihe von
Stationen in einer Stadt, die Temperatur und mehr messen, mit offener Lizenz und ohne Login
veröffentlicht. Beim Hinzufügen eines Standorts nutzt die Integration das Messnetz mit einer
Station in der Nähe.

| Messnetz | Stationen | Werte | Standortdaten | Plattform | Endpunkt |
|---|---|---|---|---|---|
| [Smart City Mannheim](mannheim.md) | über 400 | Alle Werte; Wind an einigen Masten | Umgebung, Dach und Hochpunkt | Eigene API | `api.smartmannheim.de` |
| [Klimamessnetz Dortmund](dortmund.md) | 76 | Temperatur und Luftfeuchte; etwa ein Drittel auch Luftdruck, Globalstrahlung und Wind | Keine | Opendatasoft | `open-data.dortmund.de` |

Jedes Messnetz hat eigene [API-Limits](../user/api-limits.md) und ein eigenes Abfrage-Budget.
Datenquellen und Lizenzen: [Datenquellen](../data-sources.md).

## Was eine Messnetz-Seite enthält

| Abschnitt | Inhalt |
|---|---|
| Überblick | Betreiber, Plattform, Endpunkt, Lizenz und Quellenangabe |
| Abdeckung | Wo die Stationen stehen und was sie messen |
| Daten | Wie oft neue Werte kommen, wie Stationen gebildet werden, Einheiten |
| Limits | Abfrage-Limits und Budget |
| Besonderheiten | Ungewöhnliche Daten, mit denen die Integration umgeht |

## Ein Messnetz vorschlagen

Geplante und untersuchte Städte und Messnetze stehen als
[Issues mit dem Titel „Network: ..."](https://github.com/CodeBrauer/ha-urban-weather/issues?q=is%3Aissue%20%22Network%3A%22%20in%3Atitle).
Ein Messnetz lässt sich unterstützen, wenn es Livewerte (mindestens stündlich aktualisiert),
eine Lizenz für die Weiterverwendung, Stationen in der ganzen Stadt und Zugriff ohne Login
bietet. Für einen Vorschlag gibt es das
[Formular für Messnetz-Vorschläge](https://github.com/CodeBrauer/ha-urban-weather/issues/new?template=new_network.yml).
