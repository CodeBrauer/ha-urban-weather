<!-- source: 9762fb56584b7c74a6a5fe652c06b4982dbd0b92 -->
# Installation

## Voraussetzungen

| | |
|---|---|
| Home Assistant | 2026.9 oder neuer |
| HACS | 2.0.5 oder neuer (nur für die Installation über HACS) |
| Internet | Zugriff auf `api.smartmannheim.de` aus Home Assistant |
| Browser | Zugriff auf `sgx.geodatenzentrum.de` für die Kartenkacheln (basemap.de) der Stationskarte |

Die API ist öffentlich und braucht weder Konto noch Schlüssel.

## HACS (benutzerdefiniertes Repository)

[![In HACS öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=CodeBrauer&repository=ha-urban-weather&category=integration)

Oder von Hand:

1. HACS → ⋮ → *Benutzerdefinierte Repositories* →
   `https://github.com/CodeBrauer/ha-urban-weather` mit Typ *Integration* hinzufügen.
2. *Klimamessnetz Mannheim* installieren und Home Assistant neu starten.

HACS installiert die ZIP-Datei, die an jedem GitHub-Release hängt, und zeigt neue Versionen
als Updates an. Die Release Notes nennen Breaking Changes und was du nach dem Update tun
musst.

## Manuell

`custom_components/mannheim_climate` in deinen Ordner `config/custom_components/` kopieren
und Home Assistant neu starten. Updates funktionieren genauso: Ordner ersetzen und neu
starten.

## Nächster Schritt

[Richte deinen ersten Standort ein](setup.md).

## Deinstallieren

1. *Einstellungen → Geräte & Dienste → Klimamessnetz Mannheim*: alle Standorte löschen.
   Ihre Reparaturhinweise werden mit entfernt.
2. Die Integration in HACS entfernen (oder den Ordner löschen) und Home Assistant neu
   starten.

Die zwischengespeicherte Stationsliste bleibt in `.storage/mannheim_climate.sensors`; die
Datei kannst du löschen.
