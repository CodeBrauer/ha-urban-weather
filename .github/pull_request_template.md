## Summary

<!-- What does this change and why? -->

Fixes #

## Checklist

- [ ] The title follows Conventional Commits (`fix: …`, `feat: …`); it becomes the commit message.
- [ ] Behaviour changes are covered by tests; a bug fix has a test that fails without it.
- [ ] `scripts/lint` and `scripts/test` pass.
- [ ] Documented behaviour is updated in `docs/en/` and `docs/de/`, and in both READMEs where they describe it.
- [ ] UI strings are changed in `strings.json`, `translations/en.json` and `translations/de.json`.
- [ ] No live network API is called in loops, scripts or tests.
