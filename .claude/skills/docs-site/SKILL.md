---
name: docs-site
description: >-
  Update the documentation site (docs/en/, docs/de/, built with Zensical) and keep the
  German translation complete and in sync with the English source. Use whenever a change
  touches docs/, when behaviour described there changes, or when scripts/check_docs.py
  reports a missing or outdated translation.
---

# Docs site

`docs/en/` is the source, `docs/de/` has the same files with the same outline (headings, code blocks, table rows, images, admonitions in the same order). `scripts/check_docs.py` enforces it; `scripts/lint` and the Docs workflow run it.

Every sentence exists twice, so keep the token cost low: translate only what changed, never re-read or rewrite whole pages.

## Update a page

1. Edit `docs/en/<page>.md`. With several edits in one PR, translate after the last one.
2. `python3 scripts/check_docs.py` prints a `git show <blob> | diff -u - docs/en/<page>.md` command per outdated page. Run it: the diff is exactly what to translate. If git reports a bad object (that English version was never staged or committed), use `git diff HEAD -- docs/en/<page>.md`.
3. Apply only those changes to `docs/de/<page>.md`: locate the passage with `grep -n`, change it with Edit.
4. `python3 scripts/check_docs.py --stamp docs/en/<page>.md` records the translated version and runs the check again. Structure differences name the lines in both languages.
5. Before pushing: `scripts/docs build` (check plus strict build of both languages; broken links and anchors fail).

## Add, move or remove a page

- Both languages at the same path; update `nav` in `mkdocs.yml` and `mkdocs.de.yml`. Section names are translated there, page titles come from the first heading. Shared settings go to `mkdocs.base.yml`; lists set there must not be repeated in a language file, because `INHERIT` appends lists.
- Stamp a new translation once it is complete.

## Translation rules

- German like the UI and `README.md`: informal "du", short sentences.
- UI labels as in `custom_components/urban_weather/translations/de.json` (grep the English text in `strings.json` to find the key).
- Keep: code, identifiers, constant names, file paths, URLs, image paths, Mermaid syntax and node ids. Example entity ids use the German name (`sensor.seckenheim_temperatur`).
- Translate: prose, table cells, alt texts, admonition titles, Mermaid labels (state names via the `state "Label" as Id` lines), strings in YAML examples.
- Links to headings use the German anchor (`#neue-stationen-in-der-nahe`).

| English | German |
|---|---|
| location | Standort |
| surroundings | Umgebung |
| search radius | Suchradius |
| recommendation | Empfehlung |
| update interval | Aktualisierungsintervall |
| dew point correction | Taupunkt-Korrektur |
| repair issue / Repairs | Reparaturhinweis / Reparaturen |
| Configure / Reconfigure | Konfigurieren / Neu konfigurieren |
| API request, request budget | API-Abfrage, Abfrage-Budget |
| internet connection | Internetanschluss |
| roof/high point | Dach/Hochpunkt |
| densely built, open built-up, industrial, green/open | dicht bebaut, locker bebaut, Industrie/Gewerbe, grün/offen |
| apparent temperature, global irradiance | gefühlte Temperatur, Globalstrahlung |
| weather entity, unavailable | Wetter-Entität, nicht verfügbar |

## Writing rules

- Describe behaviour for the reader and name the constant from `const.py` instead of copying code. Current state only, no history.
- Keep pages short; facts that change often (numbers, limits) belong in one place, other pages link there.
- Screenshots live in `docs/screenshots/de/` and `docs/screenshots/en/` (also used by the READMEs). Each language folder links its own as `screenshots/`, so both languages use the same image paths. Regenerate them with `scripts/screenshots.py` (both languages at once, needs the running dev instance) instead of editing images by hand; a new motif goes into that script.
- Dialog screenshots go into a `<div class="screenshots" markdown>` gallery (thumbnails, the lightbox shows the full image); page-wide screenshots stand alone.
