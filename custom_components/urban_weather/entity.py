"""Base entity for the Urban Weather integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, REPOSITORY_URL
from .coordinator import ClimateCoordinator


class MannheimClimateEntity(CoordinatorEntity[ClimateCoordinator]):
    """One virtual measuring point per config entry."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: ClimateCoordinator, key: str) -> None:
        """Attach the entity to the config entry's device."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Smart City Mannheim (Open Data)",
            model="Klimamessnetz Mannheim",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=REPOSITORY_URL,
        )
