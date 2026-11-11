"""Fix flows: replace a broken station, or apply a suggestion with new stations."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.helpers import issue_registry as ir

from .config_flow import Location, selected_options
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_TEMPERATURE_SENSORS,
    CONF_WIND_SENSOR,
    DEFAULT_SCAN_INTERVAL_MIN,
    DOMAIN,
    ISSUE_ENTRY_ID,
    ISSUE_SENSOR_ID,
    NO_WIND_SENSOR,
)
from .hub import StationListUnavailableError, async_get_hub
from .selection import StationSelection

if TYPE_CHECKING:
    from homeassistant.components.repairs import RepairsFlowResult
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .api import ApiSensor
    from .stations import Station


async def async_create_fix_flow(
    hass: HomeAssistant,  # noqa: ARG001
    issue_id: str,  # noqa: ARG001
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the flow for a station_offline, station_removed or new_stations issue."""
    sensor_id = data.get(ISSUE_SENSOR_ID)
    return StationRepairFlow(
        str(data[ISSUE_ENTRY_ID]), str(sensor_id) if sensor_id else None
    )


def without_sensor(stations: list[Station], sensor_id: str | None) -> list[Station]:
    """Return the stations as if the sensor did not exist."""

    def keep(sensor: ApiSensor | None) -> ApiSensor | None:
        return None if sensor and sensor.id == sensor_id else sensor

    return [
        replace(
            station,
            temperature_sensor=keep(station.temperature_sensor),
            wind_sensor=keep(station.wind_sensor),
        )
        for station in stations
    ]


class StationRepairFlow(RepairsFlow):
    """Replace a broken sensor of a location, or apply a suggested recommendation."""

    def __init__(self, entry_id: str, sensor_id: str | None) -> None:
        """Remember the location and the sensor to replace (None: suggestion)."""
        self._entry_id = entry_id
        self._sensor_id = sensor_id
        self._entry: ConfigEntry | None = None
        self._selection: StationSelection | None = None

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> RepairsFlowResult:
        """Show the recommendation without the sensor and the ways to fix."""
        self._entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if self._entry is None:
            return self.async_abort(reason="entry_not_found")
        hub = await async_get_hub(self.hass)
        try:
            stations = await hub.async_get_stations()
        except StationListUnavailableError:
            return self.async_abort(reason="cannot_connect")
        selection = self._selection = StationSelection(
            self.hass,
            hub,
            without_sensor(stations, self._sensor_id),
            Location.from_data(self._entry.data).as_tuple(),
            self._entry_id,
            self._entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN),
        )
        # A suggestion is applied or kept as a whole. Keeping some stations from a
        # list would bring the same suggestion back with the next update.
        options = ["list"] if self._sensor_id else ["keep"]
        if selection.recommendation_fits():
            options.insert(0, "accept")
        return self.async_show_menu(
            step_id="init",
            menu_options=options,
            description_placeholders={
                **self._issue_placeholders(),
                **await selection.async_placeholders(
                    selection.recommended_sensor_ids(),
                    selection.recommended_wind_sensor_id(),
                ),
            },
        )

    async def async_step_accept(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> RepairsFlowResult:
        """Use the recommendation without the sensor."""
        selection = self._selection
        return self._async_save(
            selection.recommended_sensor_ids(), selection.recommended_wind_sensor_id()
        )

    async def async_step_keep(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> RepairsFlowResult:
        """Keep the current stations and stop showing this suggestion."""
        # The repair dialog offers no "ignore" for fixable issues. Finishing the flow
        # would delete the issue and the next update would raise it again; an ignored
        # issue stays ignored when it is raised again with the same id.
        if ir.async_get(self.hass).async_get_issue(DOMAIN, self.issue_id):
            ir.async_ignore_issue(self.hass, DOMAIN, self.issue_id, ignore=True)
        return self.async_abort(reason="kept")

    async def async_step_list(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Select the stations from a list, the current ones without the sensor."""
        selection = self._selection
        options = self._entry.options
        selected = [
            sensor_id
            for sensor_id in options.get(CONF_TEMPERATURE_SENSORS, [])
            if sensor_id != self._sensor_id
        ] or selection.recommended_sensor_ids()
        wind = options.get(CONF_WIND_SENSOR) or NO_WIND_SENSOR
        if wind == self._sensor_id:
            wind = selection.recommended_wind_sensor_id()
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = list(user_input[CONF_TEMPERATURE_SENSORS])
            wind = user_input[CONF_WIND_SENSOR]
            errors = selection.validate(selected, wind)
            if not errors:
                return self._async_save(selected, wind)
        return self.async_show_form(
            step_id="list",
            data_schema=await selection.async_list_schema(selected, wind),
            errors=errors,
            description_placeholders=await selection.async_placeholders(selected, wind),
            last_step=True,
        )

    def _async_save(self, selected: list[str], wind: str) -> RepairsFlowResult:
        """Store the new stations and reload; finishing deletes the issue."""
        entry = self._entry
        self.hass.config_entries.async_update_entry(
            entry,
            options={
                **entry.options,
                **selected_options(self._selection, selected, wind),
            },
        )
        self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_create_entry(data={})

    def _issue_placeholders(self) -> dict[str, str]:
        issue = ir.async_get(self.hass).async_get_issue(DOMAIN, self.issue_id)
        return dict(issue.translation_placeholders or {}) if issue else {}
