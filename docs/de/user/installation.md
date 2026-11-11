<!-- source: 4f0e4f0d797368c55bac2de8da2adf5047e710af -->
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
2. *Urban Weather (Stadtklima)* installieren und Home Assistant neu starten.

HACS installiert die ZIP-Datei, die an jedem GitHub-Release hängt, und zeigt neue Versionen
als Updates an. Die Release Notes nennen Breaking Changes und was du nach dem Update tun
musst.

## Manuell

`custom_components/urban_weather` in deinen Ordner `config/custom_components/` kopieren
und Home Assistant neu starten. Updates funktionieren genauso: Ordner ersetzen und neu
starten.

## Nächster Schritt

[Richte deinen ersten Standort ein](setup.md).

## Deinstallieren

1. *Einstellungen → Geräte & Dienste → Urban Weather (Stadtklima)*: alle Standorte löschen.
   Ihre Reparaturhinweise werden mit entfernt.
2. Die Integration in HACS entfernen (oder den Ordner löschen) und Home Assistant neu
   starten.

Die zwischengespeicherte Stationsliste bleibt in `.storage/urban_weather.sensors`; die
Datei kannst du löschen.
