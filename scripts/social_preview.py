"""
Write the social preview image of the repository (1280 x 640) as SVG.

    python3 scripts/social_preview.py social-preview.svg
    rsvg-convert -w 1280 social-preview.svg -o social-preview.png

The image shows the outline of Germany, Austria and Switzerland with a marker per
supported city, the logo in the middle connected to the cities, and the counts of
networks and stations. A new network needs an entry in CITIES;
tests/test_social_preview.py checks it against PROVIDERS. Upload the PNG under
Settings -> Social preview (GitHub has no API for it). The workflow
social-preview.yml renders it on each release.
"""

from __future__ import annotations

import base64
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
OUTLINE = ROOT / "scripts" / "data" / "dach_outline.json"
LOGO = ROOT / "custom_components" / "urban_weather" / "brand" / "icon@2x.png"


@dataclass(frozen=True, slots=True)
class City:
    """A supported network as the image shows it."""

    name: str
    # City centre, as <CITY>_HOME in tests/common.py.
    latitude: float
    longitude: float
    # Rounded station count, as in the READMEs.
    stations: int
    # Side of the marker the name is written on, and its vertical offset.
    label: Literal["left", "right"] = "left"
    label_dy: int = 5


# Network id -> city, in the order of the subtitle.
CITIES: dict[str, City] = {
    "mannheim": City("Mannheim", 49.4875, 8.4660, 400, label_dy=1),
    "dortmund": City("Dortmund", 51.5136, 7.4653, 76),
    "karlsruhe": City("Karlsruhe", 49.0093, 8.4037, 90, label_dy=9),
    "dresden": City("Dresden", 51.0505, 13.7383, 120, label="right"),
    "zurich": City("Zürich", 47.3662, 8.5410, 100, label="right", label_dy=18),
    "basel": City("Basel", 47.5584, 7.5886, 70, label_dy=6),
}

WIDTH, HEIGHT = 1280, 640
FONT = "'Helvetica Neue', Helvetica, Arial, 'Liberation Sans', sans-serif"
FEATURES = ("Temperatur", "Luftfeuchte", "Wetter")

# Map: bounding box of the outline, centre and height on the image.
LON_WEST, LON_EAST, LAT_SOUTH, LAT_NORTH = 5.85, 17.2, 45.8, 55.1
LONGITUDE_FACTOR = math.cos(math.radians(50))
MAP_CENTRE = (1012, 315)
MAP_HEIGHT = 480
# The logo sits in the middle of the map.
HUB = (10.6, 50.0)
LOGO_SIZE = 88
LABEL_GAP = 13
# Curvature of the connections, as a share of their length.
BEND = 0.15

# Text on the left.
TEXT_X = 96
TITLE_Y = 250
LINE_START_Y = 306
LINE_HEIGHT = 36
LINE_CHARACTERS = 38
PILL_HEIGHT = 42
PILL_ROW = 52
PILL_GAP = 10
PILL_CHARACTER = 9.8
PILL_PADDING = 40
PILLS_FIRST_ROW = 2


def project(longitude: float, latitude: float) -> tuple[float, float]:
    """Return the image position of a coordinate (equirectangular around 50° N)."""
    scale = MAP_HEIGHT / (LAT_NORTH - LAT_SOUTH)
    width = (LON_EAST - LON_WEST) * LONGITUDE_FACTOR * scale
    return (
        MAP_CENTRE[0] - width / 2 + (longitude - LON_WEST) * LONGITUDE_FACTOR * scale,
        MAP_CENTRE[1] - MAP_HEIGHT / 2 + (LAT_NORTH - latitude) * scale,
    )


def outline_paths() -> list[str]:
    """Return one SVG path per country of the outline."""
    countries = json.loads(OUTLINE.read_text("utf-8"))["countries"]
    paths = []
    for code, rings in countries.items():
        parts = []
        for ring in rings:
            points = [project(longitude, latitude) for longitude, latitude in ring]
            parts.append("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in points) + "Z")
        paths.append(f'<path id="{code}" d="{"".join(parts)}"/>')
    return paths


def check_cities() -> None:
    """Fail for a city outside the outline, which would be drawn off the map."""
    for city in CITIES.values():
        if not (
            LON_WEST <= city.longitude <= LON_EAST
            and LAT_SOUTH <= city.latitude <= LAT_NORTH
        ):
            msg = f"{city.name} is outside the outline of DE, AT and CH"
            raise ValueError(msg)


def city_list() -> str:
    """Return the city names as a German list ("A, B und C")."""
    names = [city.name for city in CITIES.values()]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " und " + names[-1]


def wrap(text: str) -> list[str]:
    """Break a text into lines of at most LINE_CHARACTERS (at spaces)."""
    lines: list[str] = []
    for word in text.split():
        if lines and len(lines[-1]) + 1 + len(word) <= LINE_CHARACTERS:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return lines


def station_count() -> str:
    """Return the total of stations, rounded down to hundreds ("800+")."""
    total = sum(city.stations for city in CITIES.values())
    return f"{total // 100 * 100}+"


def pills(labels: list[str], y: float) -> list[str]:
    """Return a row of rounded labels starting at TEXT_X."""
    shapes, texts = [], []
    x = TEXT_X
    for label in labels:
        width = round(len(label) * PILL_CHARACTER + PILL_PADDING)
        shapes.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="{PILL_HEIGHT}" rx="21"/>'
        )
        texts.append(
            f'<text x="{x + width / 2:.1f}" y="{y + 28}" text-anchor="middle">'
            f"{escape(label)}</text>"
        )
        x += width + PILL_GAP
    return [
        '<g fill="#FFFFFF" fill-opacity="0.12" stroke="#8CC8FA" stroke-opacity="0.45">',
        *shapes,
        "</g>",
        '<g fill="#E6F2FD">',
        *texts,
        "</g>",
    ]


def text_block() -> list[str]:
    """Return title, subtitle and the two rows of pills."""
    lines = [
        "Urban Weather für Home Assistant \N{EN DASH}",
        *wrap(f"Klimamessnetze in {city_list()}"),
    ]
    out = [
        f'<g font-family="{FONT}" fill="#FFFFFF">',
        (
            f'<text x="{TEXT_X - 4}" y="{TITLE_Y}" font-size="88" font-weight="700" '
            'letter-spacing="-1">Stadtklima</text>'
        ),
    ]
    y = LINE_START_Y
    for line in lines:
        out.append(
            f'<text x="{TEXT_X}" y="{y}" font-size="28" fill-opacity="0.85">'
            f"{escape(line)}</text>"
        )
        y += LINE_HEIGHT
    out.append("</g>")
    labels = [f"{len(CITIES)} Messnetze", f"{station_count()} Stationen", *FEATURES]
    pill_y = y - LINE_HEIGHT + PILL_ROW - 16
    out.append(f'<g font-family="{FONT}" font-size="19" font-weight="500">')
    out += pills(labels[:PILLS_FIRST_ROW], pill_y)
    out += pills(labels[PILLS_FIRST_ROW:], pill_y + PILL_ROW)
    out.append("</g>")
    return out


def map_block() -> list[str]:
    """Return the outline, the connections, the city markers and the logo."""
    hub_x, hub_y = project(*HUB)
    out = [
        (
            '<g fill="#0B7DDA" fill-opacity="0.10" stroke="#8CC8FA" '
            'stroke-opacity="0.55" stroke-width="1.6" stroke-linejoin="round">'
        ),
        *outline_paths(),
        "</g>",
        (
            '<g fill="none" stroke="#8CC8FA" stroke-opacity="0.55" stroke-width="1.6" '
            'stroke-dasharray="2 5" stroke-linecap="round">'
        ),
    ]
    for city in CITIES.values():
        x, y = project(city.longitude, city.latitude)
        dx, dy = x - hub_x, y - hub_y
        control_x = (hub_x + x) / 2 - dy * BEND
        control_y = (hub_y + y) / 2 + dx * BEND
        out.append(
            f'<path d="M{hub_x:.1f} {hub_y:.1f}Q{control_x:.1f} {control_y:.1f} '
            f'{x:.1f} {y:.1f}"/>'
        )
    out += [
        "</g>",
        f'<g font-family="{FONT}" font-size="17" font-weight="500" fill="#E6F2FD">',
    ]
    for city in CITIES.values():
        x, y = project(city.longitude, city.latitude)
        right = city.label == "right"
        label_x = x + LABEL_GAP if right else x - LABEL_GAP
        out += [
            (
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="12" fill="#8CC8FA" '
                'fill-opacity="0.18"/>'
            ),
            (
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.5" fill="#8CC8FA" '
                'stroke="#071C33" stroke-width="1.5"/>'
            ),
            (
                f'<text x="{label_x:.1f}" y="{y + city.label_dy:.1f}" '
                f'text-anchor="{"start" if right else "end"}">'
                f"{escape(city.name)}</text>"
            ),
        ]
    logo = base64.b64encode(LOGO.read_bytes()).decode("ascii")
    out += [
        "</g>",
        (
            f'<circle cx="{hub_x:.1f}" cy="{hub_y:.1f}" r="{LOGO_SIZE * 0.78:.0f}" '
            'fill="url(#hubglow)"/>'
        ),
        (
            f'<image x="{hub_x - LOGO_SIZE / 2:.1f}" y="{hub_y - LOGO_SIZE / 2:.1f}" '
            f'width="{LOGO_SIZE}" height="{LOGO_SIZE}" '
            f'xlink:href="data:image/png;base64,{logo}"/>'
        ),
    ]
    return out


def build_svg() -> str:
    """Return the image as SVG."""
    check_cities()
    glow_x, glow_y = MAP_CENTRE
    return "\n".join(
        [
            (
                '<svg xmlns="http://www.w3.org/2000/svg" '
                'xmlns:xlink="http://www.w3.org/1999/xlink" '
                f'width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">'
            ),
            "<defs>",
            (
                '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
                '<stop offset="0" stop-color="#071C33"/>'
                '<stop offset="1" stop-color="#0A3561"/></linearGradient>'
            ),
            (
                f'<radialGradient id="glow" cx="{glow_x}" cy="{glow_y}" r="420" '
                'gradientUnits="userSpaceOnUse">'
                '<stop offset="0" stop-color="#0B7DDA" stop-opacity="0.35"/>'
                '<stop offset="1" stop-color="#0B7DDA" stop-opacity="0"/>'
                "</radialGradient>"
            ),
            (
                '<radialGradient id="hubglow">'
                '<stop offset="0.55" stop-color="#0B7DDA" stop-opacity="0.45"/>'
                '<stop offset="1" stop-color="#0B7DDA" stop-opacity="0"/>'
                "</radialGradient>"
            ),
            "</defs>",
            f'<rect width="{WIDTH}" height="{HEIGHT}" fill="url(#bg)"/>',
            f'<rect width="{WIDTH}" height="{HEIGHT}" fill="url(#glow)"/>',
            *map_block(),
            *text_block(),
            "</svg>",
            "",
        ]
    )


def main() -> None:
    """Write the SVG to the path given as argument."""
    if len(sys.argv) != 2:  # noqa: PLR2004
        sys.exit(f"Usage: {sys.argv[0]} <output.svg>")
    Path(sys.argv[1]).write_text(build_svg(), "utf-8")
    print(f"Wrote {sys.argv[1]}")


if __name__ == "__main__":
    main()
