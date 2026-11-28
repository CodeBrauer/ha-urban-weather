# Contributing

Thanks for helping with Urban Weather. Bug reports, ideas, new networks, translations and
code are all welcome.

By taking part you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Issues and questions

- **Bugs:** open a [bug report](https://github.com/CodeBrauer/ha-urban-weather/issues/new?template=bug.yml)
  with the System Health details and a debug log.
- **Ideas:** open a [feature request](https://github.com/CodeBrauer/ha-urban-weather/issues/new?template=feature_request.yml).
- **A network for your city:** use the [network template](https://github.com/CodeBrauer/ha-urban-weather/issues/new?template=new_network.yml);
  its checklist shows what a network needs before it can be added.
- **Questions:** ask in [Discussions](https://github.com/CodeBrauer/ha-urban-weather/discussions).
- **Security vulnerabilities:** never in a public issue, see the [security policy](SECURITY.md).
- **Accessibility barriers:** see the [accessibility statement](ACCESSIBILITY.md).

Search the existing issues first; a comment on an open issue helps more than a duplicate.

## Pull requests

1. For anything larger than a small fix, open or comment on an issue first, so we can agree
   on the approach before you spend time on it.
2. Set up the development environment as described in
   [Contributing](https://codebrauer.github.io/ha-urban-weather/developer/contributing/) on
   the documentation site.
3. Follow the rules in [`AGENTS.md`](../AGENTS.md). They apply to humans and AI agents
   alike. In short:
   - Behaviour changes come with tests; a bug fix with a test that fails without it.
   - English in code, commits and PRs; README, docs and UI strings change in English and
     German together.
   - Never poll the live network APIs in loops or scripts; they are rate-limited and
     shared.
4. Run `scripts/lint` and `scripts/test` before you push.
5. Open the pull request as a draft and fill in the template. Its title follows
   [Conventional Commits](https://www.conventionalcommits.org) (`fix: …`, `feat: …`),
   because it becomes the commit message when the PR is squash-merged.
