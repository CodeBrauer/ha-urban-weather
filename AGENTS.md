# AGENTS.md

Instructions for AI coding agents (and humans) working on this repository.

Home Assistant custom integration `urban_weather` ("Urban Weather (Stadtklima)"). It combines stations of the Smart City Mannheim urban climate network into values for one location. The repository is public and installed by other people via HACS, so every release reaches real installations.

## Layout

| Path | Content |
|---|---|
| `custom_components/urban_weather/` | The integration |
| `api.py` | HTTP client and response parsing |
| `hub.py` | One per Home Assistant: rate limiter, measurement cache, station list (refreshed daily, stored copy as fallback) |
| `stations.py`, `reference.py`, `data/` | Sensors grouped into stations, siting metadata, station recommendation |
| `aggregation.py` | Combining readings (median, outliers, dew point, apparent temperature) |
| `selection.py` | Request budget and station presentation shared by the flows and the map |
| `config_flow.py`, `map_view.py`, `www/` | Config/options flow; the station map page is an external step |
| `coordinator.py` | Polling per location, catch-up of deferred requests, repair issues |
| `sensor.py`, `weather.py`, `diagnostics.py` | Entities and diagnostics |
| `tests/` | pytest with `pytest-homeassistant` |
| `docs/`, `mkdocs*.yml` | Documentation site (Zensical, GitHub Pages): `docs/en/` source, `docs/de/` German translation |
| `config/` | Local dev instance (gitignored) |

## Commands

```bash
scripts/setup      # .venv with Home Assistant (uv, Python 3.14)
scripts/develop    # dev instance on http://localhost:8123
scripts/lint       # ruff format + check (select = ALL), docs translation check
scripts/test       # pytest, arguments are passed through
scripts/docs       # docs on http://localhost:8000 (`de`: German, `build`: check + strict build)
uv run --no-project --with playwright python scripts/screenshots.py  # docs screenshots, needs scripts/develop
```

Run `scripts/lint` and `scripts/test` before every push. CI runs lint, pytest, hassfest, HACS validation, the PR title check and, for docs changes, the strict docs build; all must pass.

## Language

- Code, comments, commits, issues, PRs and release notes are written in English.
- `README.md` is English (shown by GitHub and HACS), `README.de.md` is its German version. Change both together.
- UI strings: `strings.json` is the source, `translations/en.json` an identical copy, `translations/de.json` the German translation. Change all three together with identical keys.
- Docs site: `docs/en/` is the source, `docs/de/` its German translation with the same files and outline. A PR that changes documented behaviour updates both, and the READMEs where they describe it; `scripts/check_docs.py` enforces the sync of the docs. Workflow (translate only the diff): [`.claude/skills/docs-site/SKILL.md`](.claude/skills/docs-site/SKILL.md).

## Versioning

[Semantic Versioning](https://semver.org). The version lives only in `manifest.json` (`version`); releases are tagged `vX.Y.Z` with a GitHub release. HACS installs the release asset `urban_weather.zip`, which `.github/workflows/release.yml` builds and attaches when a release is published.

For users of an integration, "breaking" means they have to act after updating:

| Bump | Examples |
|---|---|
| MAJOR | Entity removed or renamed, `unique_id` changed, value changes meaning or unit, config entry data/options changed without migration, option removed |
| MINOR | New entities, options or features; config entry change with migration (`async_migrate_entry`); higher minimum Home Assistant version (`hacs.json`) |
| PATCH | Bug fixes, translations, docs, dependency updates without behaviour change |

Before 1.0.0, breaking changes bump MINOR and are listed under "Breaking changes" in the release notes. From 1.0.0 on, entity ids, unique ids and the config entry format are stable.

Release steps: [`.claude/skills/release/SKILL.md`](.claude/skills/release/SKILL.md) (a Claude Code skill, readable as a runbook by any agent).

## Pull requests and tests

- Every PR that changes behaviour includes tests: new behaviour is covered, a bug fix comes with a test that fails without the fix. Docs- or CI-only PRs are exempt.
- Tests may follow manual testing of new logic, but a PR is not marked ready for review without them.
- Extend the existing `tests/test_<module>.py`; add a file only for a new module.
- Reuse `tests/common.py` (test location `HOME`, sensor ids from the fixture, `add_home_entry`, `add_location`, `respond`, `make_station`) and the `api` fixture in `tests/conftest.py`, which replaces `hub.MannheimClimateApi`.
- Gotchas:
  - Fixtures that need a running event loop (`hass`-bound objects) must be `async def`.
  - Fixtures that create an aiohttp client session must depend on `aioclient_mock`.
  - Use the `freezer` fixture for time; it also moves `time.monotonic` used by the rate limiter.
- Conventional Commits; branches `type/<issue>-short-description`; reference issues (`Refs #1`, `Fixes #1`). Open PRs as drafts first.
- PRs are squash-merged with their title as the commit message, so PR titles follow Conventional Commits too (checked by `.github/workflows/pr-title.yml`). `next` reaches `main` by fast-forward, not by a PR merge, so each squashed commit stays on its own.
- AI agents: never commit, push or open PRs without explicit approval of the person you work for. Commits substantially written by an agent get a `Co-authored-by:` trailer.

## The API is a shared, rate-limited resource

- The limits of `api.smartmannheim.de` apply per public IP, shared with the maintainer's production Home Assistant. Never poll the live API in loops or scripts; a few manual requests for debugging at most.
- Tests never call the live API (`pytest-socket` blocks it). Use `tests/fixtures/sensors.json`, a trimmed real response.
- The client-side limits and the planned budget are in `const.py`. Features that add requests must fit the planned budget, which `StationSelection` enforces. Discuss changes to the limits in an issue first.

## Home Assistant specifics

- Minimum Home Assistant version: `hacs.json`. Dev and test version: `requirements_dev.txt`, pinned exactly together with `pytest-homeassistant`; bump both together.
- Flow schemas use `probatio` (Home Assistant 2026.9+), not `voluptuous`.
- `manifest.json`: `domain` and `name` first, other keys alphabetical (hassfest).
- Config entry format changes need a migration (`VERSION`/`MINOR_VERSION` of the config flow).

## Generated and vendored files

Do not edit these by hand:

- `custom_components/urban_weather/data/*.json`: generated by `scripts/build_reference_data.py` (see its docstring).
- `www/leaflet/`: vendored Leaflet 1.9.4, verified against the npm sha512 (`SOURCE.txt`). Update only together with a new hash check and `SOURCE.txt`.
- `tests/fixtures/sensors.json`: trimmed `/sensors` response, source and filter in `tests/common.py`.

## Dev instance

- `scripts/develop` runs Home Assistant with `config/` as configuration directory. The login of the local instance is in `config/dev-credentials.txt`; never commit or print it.
- `homeassistant.restart` crashes the dev instance on macOS with Python 3.14. Stop and start the process instead.
- Build problems on macOS: see "Development environment" in `docs/en/developer/contributing.md`.
