# Security policy

## Supported versions

Only the [latest release](https://github.com/CodeBrauer/ha-urban-weather/releases/latest)
receives fixes. Update to it before you report a problem.

## Reporting a vulnerability

Please do not open a public issue. Report it privately through
[Report a vulnerability](https://github.com/CodeBrauer/ha-urban-weather/security/advisories/new)
in the Security tab of this repository.

Include what you found, how to reproduce it, the version of the integration and of Home
Assistant, and what an attacker could do with it.

This is a project maintained in spare time. You can expect a first reply within a week.
Once a fix is released, the advisory is published and credits you, unless you prefer
not to be named.

## Scope

In scope is the code in this repository, for example:

- The station map page that the integration serves through Home Assistant.
- Data the integration exposes, such as diagnostics revealing a configured location.
- Handling of responses from the network APIs.

Out of scope, please report these to the respective project:

- Home Assistant itself: [Home Assistant security](https://www.home-assistant.io/security/).
- The network APIs and their data: the operators listed under
  [Data sources](https://codebrauer.github.io/ha-urban-weather/data-sources/).
