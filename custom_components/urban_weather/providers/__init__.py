"""The climate networks the integration can read."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .mannheim import MANNHEIM, MannheimProvider
from .mannheim.reference import load_reference_data

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.urban_weather.provider import Provider


async def async_create_provider(hass: HomeAssistant) -> Provider:
    """Return the provider of the network (Mannheim is the only one so far)."""
    reference = await hass.async_add_executor_job(load_reference_data)
    return MannheimProvider(MANNHEIM, async_get_clientsession(hass), reference)
