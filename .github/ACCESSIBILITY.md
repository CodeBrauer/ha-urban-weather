# Accessibility

Urban Weather should be usable by everyone who uses Home Assistant, including people who
navigate by keyboard, use a screen reader or need larger text. If something gets in your
way, please tell us; that is a bug like any other.

## What the integration shows

| Part | Provided by |
|---|---|
| Setup and options dialogs (including the location pin), sensors, weather entity | Home Assistant's own interface; this integration supplies the texts and values |
| Station map page (`www/map.html`) | This integration, built on [Leaflet](https://leafletjs.com/) |
| [Documentation site](https://codebrauer.github.io/ha-urban-weather/) | This repository, built with [Zensical](https://zensical.org) |

The accessibility of Home Assistant's interface itself is up to the
[Home Assistant project](https://github.com/home-assistant/frontend/issues).

## Priorities

- Choosing stations works without the station map: the recommendation can be accepted
  or the stations chosen from a list.
- Texts, labels and error messages are clear and available in English and German.
- Images and screenshots in the documentation have alt texts.
- We aim for [WCAG 2.2](https://www.w3.org/TR/WCAG22/) level AA where feasible. This is a
  goal, not a claim of tested conformance.

## Known limitations

- The station map is designed for mouse and touch. It has not been tested with a screen
  reader. Use **Choose from a list** in the stations step instead.
- Map tiles come from third parties (OpenStreetMap, osm.ch) and cannot be adapted,
  for example for higher contrast.

## Reporting a barrier

Open an [issue](https://github.com/CodeBrauer/ha-urban-weather/issues/new?template=bug.yml)
and describe:

- What you tried to do and where (setup dialog, map page, documentation page).
- What blocked you.
- The assistive technology, browser and operating system you use, if any.

You don't need to know the cause or a fix. Issues about accessibility get the
`accessibility` label and are treated like other bugs; barriers that block a task come
first.
