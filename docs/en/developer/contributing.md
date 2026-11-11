# Contributing

Rules for code, tests, commits, pull requests and versioning are in
[`AGENTS.md`](https://github.com/CodeBrauer/ha-urban-weather/blob/main/AGENTS.md). They
apply to humans and AI agents alike.

## Development environment

| Command | Purpose |
|---|---|
| `scripts/setup` | Creates `.venv` with Home Assistant (uv, Python 3.14) |
| `scripts/develop` | Starts Home Assistant on <http://localhost:8123> with `config/` and this integration |
| `scripts/lint` | `ruff format` and `ruff check` (`select = ALL`), then the documentation check |
| `scripts/test` | pytest; arguments are passed on, e.g. `scripts/test -k recommend` |
| `scripts/docs` | Serves the documentation locally; `scripts/docs de` for German, `scripts/docs build` for both |
| `scripts/screenshots.py` | Takes the documentation screenshots in both languages from the running dev instance: `uv run --no-project --with playwright python scripts/screenshots.py` |

On macOS some Home Assistant dependencies (`pymicro-vad`, `pyspeex-noise`) have no wheels
for Python 3.14 and fail to compile. Build them once with the SDK path:

```bash
SDK=$(xcrun --show-sdk-path) SDKROOT="$SDK" CXXFLAGS="-isysroot $SDK -I$SDK/usr/include/c++/v1" uv pip install --python .venv/bin/python pymicro-vad pyspeex-noise
```

!!! warning "The API is shared"
    The API limits apply per public IP, shared with your own Home Assistant. Never poll the
    live API in loops or scripts. Tests never call it; they use `tests/fixtures/sensors.json`.

## Typical changes

| Change | Places to touch |
|---|---|
| New sensor | `SENSORS` in `sensor.py`; its name in `strings.json` and `translations/` if it has a `translation_key`; [Entities](../user/entities.md) and the READMEs |
| New option or config entry field | `config_flow.py` with a migration (`VERSION`/`MINOR_VERSION`); `strings.json` and `translations/`; [Setup](../user/setup.md) and [Config entry](architecture.md#config-entry) |
| Budget, limits or intervals | `const.py` (discuss in an issue first); `selection.py` and `www/map.js` share the budget rules; [API limits](../user/api-limits.md) |
| Text of the map page | The `map_page` selector in `strings.json` and `translations/` |

## Continuous integration

| Workflow | Runs on | Checks |
|---|---|---|
| Lint | push, pull request | `ruff check`, `ruff format --check` |
| Test | push, pull request | pytest with coverage |
| Validate | push, pull request, daily | hassfest, HACS validation |
| Docs | changes to the documentation | translation check, strict build of both languages; deploys to GitHub Pages from `main` |
| Release | published release | Attaches `urban_weather.zip`, which HACS installs |

Releases follow the runbook in
[`.claude/skills/release/SKILL.md`](https://github.com/CodeBrauer/ha-urban-weather/blob/main/.claude/skills/release/SKILL.md).

## Documentation

This site is built with [Zensical](https://zensical.org) from Markdown in `docs/`:

| Path | Content |
|---|---|
| `docs/en/` | English pages, the source |
| `docs/de/` | German translation, same files and structure |
| `docs/screenshots/` | Screenshots per language (`de/`, `en/`) from `scripts/screenshots.py`, also used by the READMEs |
| `docs/assets/` | Stylesheet, shared by both languages |
| `mkdocs.base.yml` | Shared site configuration |
| `mkdocs.yml`, `mkdocs.de.yml` | Navigation and language settings of each language |

Changes that alter documented behaviour update the pages in both languages in the same pull
request. `scripts/check_docs.py` makes sure nothing is forgotten: every English page needs a
German page with the same headings, code blocks, tables and images, and each German page
records the version of the English page it was translated from.

```bash
python3 scripts/check_docs.py                               # what is missing or outdated
python3 scripts/check_docs.py --stamp docs/en/user/setup.md # after updating the translation
scripts/docs build                                          # check and strict build of both languages
```

The workflow for updating a translation with as little effort as possible is in
[`.claude/skills/docs-site/SKILL.md`](https://github.com/CodeBrauer/ha-urban-weather/blob/main/.claude/skills/docs-site/SKILL.md).
