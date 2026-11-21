"""The climate networks the integration can read."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .mannheim import MANNHEIM, MannheimProvider
from .mannheim.reference import load_reference_data

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from homeassistant.core import HomeAssistant

    from custom_components.urban_weather.provider import Provider


async def _async_create_mannheim(hass: HomeAssistant) -> Provider:
    reference = await hass.async_add_executor_job(load_reference_data)
    return MannheimProvider(MANNHEIM, async_get_clientsession(hass), reference)


# Network id -> provider factory.
PROVIDERS: dict[str, Callable[[HomeAssistant], Awaitable[Provider]]] = {
    MANNHEIM.id: _async_create_mannheim,
}


async def async_create_provider(hass: HomeAssistant, network_id: str) -> Provider:
    """Return the provider of a network (KeyError for an unknown id)."""
    return await PROVIDERS[network_id](hass)
