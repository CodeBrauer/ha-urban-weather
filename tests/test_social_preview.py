"""Tests for scripts/social_preview.py, which draws the supported networks."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from custom_components.urban_weather.providers import PROVIDERS

if TYPE_CHECKING:
    from types import ModuleType

SCRIPT = Path(__file__).parent.parent / "scripts" / "social_preview.py"
# Taken before the autouse fixture `only_mannheim` removes the other networks.
NETWORK_IDS = set(PROVIDERS)


def load_script() -> ModuleType:
    """Import the script (scripts/ is no package)."""
    spec = importlib.util.spec_from_file_location("social_preview", SCRIPT)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look up their module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script() -> ModuleType:
    """Return the script as module."""
    return load_script()


def test_every_network_has_a_city(script: ModuleType) -> None:
    """A new network fails here until it is drawn on the image."""
    assert set(script.CITIES) == NETWORK_IDS, (
        "add the network to CITIES in scripts/social_preview.py"
    )


def test_image_names_every_city_and_the_counts(script: ModuleType) -> None:
    """Subtitle and pills follow from the table."""
    svg = script.build_svg()
    for city in script.CITIES.values():
        assert f">{city.name}</text>" in svg, f"marker label of {city.name}"
    assert f">{len(NETWORK_IDS)} Messnetze<" in svg
    assert ">800+ Stationen<" in svg, "856 stations rounded down to hundreds"
    assert "Karlsruhe, Dresden, Zürich und Basel" in svg
    assert svg.count('<path id="') == 4, "DE, AT, CH and LI"


def test_city_outside_the_outline_fails(script: ModuleType) -> None:
    """A city off the map is an error, not a marker outside the outline."""
    paris = replace(script.CITIES["basel"], name="Paris", longitude=2.35)
    with (
        patch.dict(script.CITIES, {"paris": paris}),
        pytest.raises(ValueError, match="Paris is outside"),
    ):
        script.build_svg()


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        (["Basel"], "Basel"),
        (["Basel", "Zürich"], "Basel und Zürich"),
        (["Basel", "Zürich", "Dresden"], "Basel, Zürich und Dresden"),
    ],
    ids=["one", "two", "three"],
)
def test_city_list(script: ModuleType, names: list[str], expected: str) -> None:
    """The cities are listed the German way."""
    cities = {name: replace(script.CITIES["basel"], name=name) for name in names}
    with patch.object(script, "CITIES", cities):
        assert script.city_list() == expected


def test_wrap_keeps_lines_short(script: ModuleType) -> None:
    """Lines break at spaces before LINE_CHARACTERS."""
    lines = script.wrap("Klimamessnetze in " + ", ".join(["Mannheim"] * 8))
    assert all(len(line) <= script.LINE_CHARACTERS for line in lines)
    assert " ".join(lines) == "Klimamessnetze in " + ", ".join(["Mannheim"] * 8)


def test_main_writes_the_file(script: ModuleType, tmp_path: Path) -> None:
    """The CLI writes the SVG to the given path; without one it exits."""
    output = tmp_path / "preview.svg"
    with patch.object(sys, "argv", ["social_preview.py", str(output)]):
        script.main()
    assert output.read_text("utf-8").startswith("<svg ")
    with (
        patch.object(sys, "argv", ["social_preview.py"]),
        pytest.raises(SystemExit, match="Usage"),
    ):
        script.main()
