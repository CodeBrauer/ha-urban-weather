"""Shared fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from custom_components.urban_weather.providers import PROVIDERS
from custom_components.urban_weather.providers.mannheim import MANNHEIM

from .common import MEASUREMENTS, sensors_payload

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def only_mannheim() -> Generator[None]:
    """Offer only the Mannheim network; tests of other networks add theirs."""
    with patch.dict(PROVIDERS, {MANNHEIM.id: PROVIDERS[MANNHEIM.id]}, clear=True):
        yield


@pytest.fixture
def api() -> Generator[MagicMock]:
    """Replace the API client created by the Mannheim provider."""
    with patch(
        "custom_components.urban_weather.providers.mannheim.MannheimClimateApi",
        autospec=True,
    ) as api_class:
        client = api_class.return_value
        client.async_get_sensors_payload.return_value = sensors_payload()
        client.async_get_measurements.return_value = MEASUREMENTS
        yield client
