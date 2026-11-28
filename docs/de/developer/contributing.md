<!-- source: f9c79e06da93d26d86d4d8959cf2ea2f1b4d84a7 -->
# Mitarbeit

Die Regeln für Code, Tests, Commits, Pull Requests und Versionierung stehen in
[`AGENTS.md`](https://github.com/CodeBrauer/ha-urban-weather/blob/main/AGENTS.md). Sie
gelten für Menschen und KI-Agenten gleichermaßen.

## Entwicklungsumgebung

| Befehl | Zweck |
|---|---|
| `scripts/setup` | Legt `.venv` mit Home Assistant an (uv, Python 3.14) |
| `scripts/develop` | Startet Home Assistant auf <http://localhost:8123> mit `config/` und dieser Integration |
| `scripts/lint` | `ruff format` und `ruff check` (`select = ALL`), die Typprüfung (`mypy`, strict), danach der Doku-Check |
| `scripts/test` | pytest; Argumente werden weitergegeben, z. B. `scripts/test -k recommend` |
| `scripts/docs` | Startet die Doku lokal; `scripts/docs de` für Deutsch, `scripts/docs build` für beide |
| `scripts/screenshots.py` | Erstellt die Screenshots der Doku in beiden Sprachen aus der laufenden Dev-Instanz: `uv run --no-project --with playwright python scripts/screenshots.py` |
| `scripts/social_preview.py` | Schreibt das Vorschaubild des Repositorys als SVG aus den unterstützten Messnetzen: `python3 scripts/social_preview.py preview.svg` |

Unter macOS gibt es für einige Abhängigkeiten von Home Assistant (`pymicro-vad`,
`pyspeex-noise`) keine Wheels für Python 3.14, und der Build scheitert. Einmal mit SDK-Pfad
bauen:

```bash
SDK=$(xcrun --show-sdk-path) SDKROOT="$SDK" CXXFLAGS="-isysroot $SDK -I$SDK/usr/include/c++/v1" uv pip install --python .venv/bin/python pymicro-vad pyspeex-noise
```

!!! warning "Die APIs sind geteilt"
    Die API-Limits gelten pro öffentlicher IP, geteilt mit deinem eigenen Home Assistant.
    Frag eine echte API nie in Schleifen oder Skripten ab. Tests rufen keine auf; sie nutzen
    die gekürzten Antworten in `tests/fixtures/`.

## Typische Änderungen

| Änderung | Betroffene Stellen |
|---|---|
| Neuer Sensor | `SENSORS` in `sensor.py`; sein Name in `strings.json` und `translations/`, wenn er einen `translation_key` hat; [Entitäten](../user/entities.md) und die READMEs |
| Neue Option oder neues Feld im Config Entry | `config_flow.py` mit Migration (`VERSION`/`MINOR_VERSION`); `strings.json` und `translations/`; [Einrichtung](../user/setup.md) und [Config Entry](architecture.md#config-entry) |
| Budget, Limits oder Intervalle | `RequestLimits` des Messnetzes in `providers/`, Intervalle in `const.py` (vorher in einem Issue besprechen); `selection.py` und `www/map.js` teilen sich die Budget-Regeln; [API-Limits](../user/api-limits.md) |
| Texte der Kartenseite | Der Selector `map_page` in `strings.json` und `translations/` |
| Neues Messnetz | Checkliste in [`.claude/skills/new-network/SKILL.md`](https://github.com/CodeBrauer/ha-urban-weather/blob/main/.claude/skills/new-network/SKILL.md) |

## Continuous Integration

| Workflow | Läuft bei | Prüft |
|---|---|---|
| Lint | Push, Pull Request | `ruff check`, `ruff format --check`, `mypy` |
| Test | Push, Pull Request | pytest; schlägt unter 95 % Coverage fehl. Die Coverage-Tabelle steht in der Zusammenfassung des Jobs und auf [Codacy](https://app.codacy.com/gh/CodeBrauer/ha-urban-weather/coverage) |
| Validate | Push, Pull Request, täglich | hassfest, HACS-Validierung |
| Docs | Änderungen an der Doku | Übersetzungs-Check, strikter Build beider Sprachen; Deploy auf GitHub Pages von `main` |
| Release | veröffentlichtes Release | Hängt `urban_weather.zip` an, das HACS installiert |
| Social preview | veröffentlichtes Release, manuell | Erzeugt das Vorschaubild (7 Tage aufbewahrt) und verlinkt es in den Messnetz-Issues, die die Release Notes nennen |

Releases folgen dem Runbook in
[`.claude/skills/release/SKILL.md`](https://github.com/CodeBrauer/ha-urban-weather/blob/main/.claude/skills/release/SKILL.md).

## Dokumentation

Diese Seite wird mit [Zensical](https://zensical.org) aus Markdown in `docs/` gebaut:

| Pfad | Inhalt |
|---|---|
| `docs/en/` | Englische Seiten, die Quelle |
| `docs/de/` | Deutsche Übersetzung, gleiche Dateien und Struktur |
| `docs/screenshots/` | Screenshots je Sprache (`de/`, `en/`) aus `scripts/screenshots.py`, auch für die READMEs |
| `docs/assets/` | Stylesheet, gemeinsam für beide Sprachen |
| `mkdocs.base.yml` | Gemeinsame Konfiguration der Seite |
| `mkdocs.yml`, `mkdocs.de.yml` | Navigation und Spracheinstellungen jeder Sprache |

Änderungen, die dokumentiertes Verhalten ändern, passen die Seiten in beiden Sprachen im
selben Pull Request an. `scripts/check_docs.py` sorgt dafür, dass nichts vergessen wird: Jede
englische Seite braucht eine deutsche Seite mit denselben Überschriften, Code-Blöcken,
Tabellen und Bildern, und jede deutsche Seite merkt sich die Version der englischen Seite,
aus der sie übersetzt wurde.

```bash
python3 scripts/check_docs.py                               # was fehlt oder veraltet ist
python3 scripts/check_docs.py --stamp docs/en/user/setup.md # nach dem Aktualisieren der Übersetzung
scripts/docs build                                          # Check und strikter Build beider Sprachen
```

Der Ablauf, eine Übersetzung mit möglichst wenig Aufwand zu aktualisieren, steht in
[`.claude/skills/docs-site/SKILL.md`](https://github.com/CodeBrauer/ha-urban-weather/blob/main/.claude/skills/docs-site/SKILL.md).
