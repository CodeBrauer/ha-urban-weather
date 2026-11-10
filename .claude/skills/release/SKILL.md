---
name: release
description: >-
  Publish a new version of the urban_weather integration: pick the SemVer bump
  from the changes since the last release, bump manifest.json, then tag and create
  the GitHub release (which HACS installs) with user-facing release notes. Use when
  asked to release, publish or tag a version, to draft release notes, or to check
  whether a release is due.
---

# Release

Versioning rules: "Versioning" in `AGENTS.md`. A release is published to HACS users immediately, so nothing is committed, pushed, tagged or published before the person you work for approves the version and the notes (step 4).

## 1. Preconditions

```bash
git switch main && git pull --ff-only && git status --short
gh run list --branch main --limit 6          # latest lint, test and validate runs succeeded
LAST=$(gh release view --json tagName --jq .tagName)
```

Stop and report if the tree is dirty or CI on `main` is red.

## 2. Collect the changes

```bash
git log --no-merges --format='%h %s' "$LAST"..main
gh pr list --state merged --base main --limit 50 \
  --search "merged:>=$(gh release view "$LAST" --json publishedAt --jq '.publishedAt[:10]')"
```

If there are only `test`, `ci`, `docs`, `chore` or `refactor` changes without visible effect, no release is due. Say so and stop.

## 3. Pick the version

Commit types are a hint, not the decision. Also read the diff of everything users depend on:

```bash
git diff "$LAST"..main -- hacs.json custom_components/urban_weather/{__init__,const,config_flow,entity,sensor,weather}.py
```

| Look for | Bump |
|---|---|
| `type!:` or `BREAKING CHANGE:` footer; removed or renamed entity description `key` (part of the `unique_id`); changed unit, device class or meaning of a value; removed option; config entry change without migration | MAJOR (before 1.0.0: MINOR, listed as breaking) |
| `feat`; new entity or option; migration (`VERSION`/`MINOR_VERSION`, `async_migrate_entry`); higher `homeassistant` in `hacs.json` | MINOR |
| Only `fix`, `perf`, translations, dependency updates | PATCH |

If new code uses a Home Assistant API that is newer than the minimum in `hacs.json`, the minimum has to be raised in a separate PR before the release.

## 4. Draft the notes and ask for approval

Write the notes to a scratch file outside the repository. They are English and written for users, not developers (compare `gh release view v0.1.0`):

```markdown
## Breaking changes
- What changed and what users have to do after updating.

## Features
- One line per visible change (#7)

## Fixes
- ...

Requires Home Assistant 2026.9 or newer.
```

- Omit empty sections. The last line uses the `homeassistant` minimum from `hacs.json`.
- Leave out tests, CI and refactors. Mention docs only when users act on them (e.g. installation steps).

Show the version, the change that decides the bump, and the notes. Wait for an explicit go.

## 5. Bump the version

```bash
git switch -c chore/release-vX.Y.Z
# set "version": "X.Y.Z" in custom_components/urban_weather/manifest.json, nothing else
scripts/lint && scripts/test
git commit -am "chore(release): vX.Y.Z"
git push -u origin chore/release-vX.Y.Z
gh pr create --title "chore(release): vX.Y.Z" --body-file <notes>
```

Continue once the PR is merged and CI on `main` is green.

## 6. Tag and publish

```bash
git switch main && git pull --ff-only
jq -r .version custom_components/urban_weather/manifest.json   # must print X.Y.Z
gh release create vX.Y.Z --target "$(git rev-parse HEAD)" --title vX.Y.Z --notes-file <notes>
git fetch --tags
```

- `gh release create` creates the tag on GitHub, like v0.1.0.
- No `--prerelease`: HACS hides prereleases unless users enable beta versions.
- Publishing starts `.github/workflows/release.yml`, which attaches `urban_weather.zip`. HACS installs that asset (`zip_release` in `hacs.json`), so the release cannot be installed until the workflow has succeeded.

## 7. Verify and follow up

```bash
gh run watch "$(gh run list --workflow release.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
gh release view vX.Y.Z --json assets --jq '.assets[].name'   # must list urban_weather.zip
git show vX.Y.Z:custom_components/urban_weather/manifest.json | jq -r .version
gh api 'repos/{owner}/{repo}/milestones' --jq '.[] | "\(.number) \(.title) open=\(.open_issues)"'
```

- If the workflow failed, re-run it (`gh run rerun <id>`); it replaces an existing asset. A re-run uses the workflow file of the tag, so a broken workflow needs a fix on `main` and a new PATCH release.
- If a milestone with this version exists and has no open issues left, close it with `gh api -X PATCH 'repos/{owner}/{repo}/milestones/<number>' -f state=closed`. This is covered by the approval in step 4.
- Never delete, move or re-tag a published version; HACS installations may already use it. Fix mistakes with a new PATCH release.
