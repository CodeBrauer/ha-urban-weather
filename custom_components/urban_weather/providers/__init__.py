"""The climate networks the integration can read."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .dortmund import DATASET as DORTMUND_DATASET
from .dortmund import DORTMUND
from .geojson import GeoJsonProvider
from .mannheim import MANNHEIM, MannheimProvider
from .mannheim.reference import load_reference_data
from .opendatasoft import OpendatasoftProvider
from .zurich import FEED as ZURICH_FEED
from .zurich import ZURICH

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from homeassistant.core import HomeAssistant

    from custom_components.urban_weather.provider import Provider


async def _async_create_mannheim(hass: HomeAssistant) -> Provider:
    reference = await hass.async_add_executor_job(load_reference_data)
    return MannheimProvider(MANNHEIM, async_get_clientsession(hass), reference)


async def _async_create_dortmund(hass: HomeAssistant) -> Provider:
    return OpendatasoftProvider(
        DORTMUND, DORTMUND_DATASET, async_get_clientsession(hass)
    )


async def _async_create_zurich(hass: HomeAssistant) -> Provider:
    return GeoJsonProvider(ZURICH, ZURICH_FEED, async_get_clientsession(hass))


# Network id -> provider factory.
PROVIDERS: dict[str, Callable[[HomeAssistant], Awaitable[Provider]]] = {
    MANNHEIM.id: _async_create_mannheim,
    DORTMUND.id: _async_create_dortmund,
    ZURICH.id: _async_create_zurich,
}


async def async_create_provider(hass: HomeAssistant, network_id: str) -> Provider:
    """Return the provider of a network (KeyError for an unknown id)."""
    return await PROVIDERS[network_id](hass)
