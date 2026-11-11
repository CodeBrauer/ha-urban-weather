"""Config flow: location, surroundings and station selection (menu, map or list)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import probatio
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_DEW_POINT_OFFSET,
    CONF_ENVIRONMENT,
    CONF_SCAN_INTERVAL,
    CONF_TEMPERATURE_SENSORS,
    CONF_WIND_SENSOR,
    DEFAULT_DEW_POINT_OFFSET_K,
    DEFAULT_SCAN_INTERVAL_MIN,
    DEFAULT_SEARCH_RADIUS_M,
    DEW_POINT_OFFSET_LIMIT_K,
    DOMAIN,
    LCZ_ENVIRONMENT,
    MAX_COVERAGE_DISTANCE_M,
    MAX_SEARCH_RADIUS_M,
    NO_WIND_SENSOR,
    SCAN_INTERVAL_CHOICES_MIN,
    Environment,
)
from .geo import distance_m
from .hub import ClimateHub, StationListUnavailableError, async_get_hub
from .map_view import (
    DATA_MAP,
    MAP_SELECTION,
    MapSessions,
    async_get_map_sessions,
    map_url,
)
from .selection import StationSelection
from .stations import Station, nearest

if TYPE_CHECKING:
    from collections.abc import Mapping

HOME_MATCH_RADIUS_M = 100
FALLBACK_TITLE = "Mannheim"
DEFAULT_ENVIRONMENT = Environment.OPEN_BUILT
SOURCE_RECONFIGURE = "reconfigure"


@dataclass(slots=True)
class Location:
    """The point to estimate values for."""

    latitude: float
    longitude: float
    radius: float
    environment: Environment = DEFAULT_ENVIRONMENT

    def as_data(self) -> dict[str, Any]:
        """Return config entry data."""
        return {
            CONF_LATITUDE: self.latitude,
            CONF_LONGITUDE: self.longitude,
            CONF_RADIUS: self.radius,
            CONF_ENVIRONMENT: self.environment.value,
        }

    def as_tuple(self) -> tuple[float, float, float, Environment]:
        """Return the values StationSelection needs."""
        return (self.latitude, self.longitude, self.radius, self.environment)

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> Location:
        """Read config entry data."""
        return cls(
            data[CONF_LATITUDE],
            data[CONF_LONGITUDE],
            data.get(CONF_RADIUS, DEFAULT_SEARCH_RADIUS_M),
            Environment(data.get(CONF_ENVIRONMENT, DEFAULT_ENVIRONMENT)),
        )

    @property
    def unique_id(self) -> str:
        """Locations closer than ~100 m count as the same."""
        return f"{self.latitude:.3f}_{self.longitude:.3f}"


def _location_schema(default: Mapping[str, float]) -> probatio.Schema:
    return probatio.Schema(
        {
            probatio.Required(CONF_LOCATION, default=dict(default)): LocationSelector(
                LocationSelectorConfig(radius=True)
            ),
        }
    )


def _parse_location(user_input: Mapping[str, Any]) -> Location:
    location = user_input[CONF_LOCATION]
    radius = min(
        float(location.get(CONF_RADIUS) or DEFAULT_SEARCH_RADIUS_M), MAX_SEARCH_RADIUS_M
    )
    return Location(location[CONF_LATITUDE], location[CONF_LONGITUDE], radius)


def _is_covered(stations: list[Station], location: Location) -> bool:
    return any(
        station.temperature_sensor
        and station.distance_to(location.latitude, location.longitude)
        <= MAX_COVERAGE_DISTANCE_M
        for station in stations
    )


def _environment_schema(default: Environment) -> probatio.Schema:
    return probatio.Schema(
        {
            probatio.Required(CONF_ENVIRONMENT, default=default.value): SelectSelector(
                SelectSelectorConfig(
                    options=[environment.value for environment in Environment],
                    translation_key=CONF_ENVIRONMENT,
                    mode=SelectSelectorMode.LIST,
                )
            )
        }
    )


def detected_environment(hub: ClimateHub, location: Location) -> Environment:
    """Return the surroundings at a location according to the LCZ map."""
    lcz = hub.reference.lcz(location.latitude, location.longitude)
    return LCZ_ENVIRONMENT.get(lcz, DEFAULT_ENVIRONMENT) if lcz else DEFAULT_ENVIRONMENT


def _station_options(selected: list[str], wind: str) -> dict[str, Any]:
    return {
        CONF_TEMPERATURE_SENSORS: list(selected),
        CONF_WIND_SENSOR: None if wind == NO_WIND_SENSOR else wind,
    }


def selected_options(
    selection: StationSelection, selected: list[str], wind: str
) -> dict[str, Any]:
    """Return the options for a station choice with the shortest fitting interval."""
    interval = selection.fitting_interval(len(selected), wind)
    return {
        **_station_options(selected, wind),
        CONF_SCAN_INTERVAL: interval or SCAN_INTERVAL_CHOICES_MIN[-1],
    }


class MannheimClimateConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up or move a location."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow state."""
        self._hub: ClimateHub | None = None
        self._stations: list[Station] = []
        self._location: Location | None = None
        self._selection: StationSelection | None = None
        self._map_choice: dict[str, Any] | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,  # noqa: ARG004
    ) -> MannheimClimateOptionsFlow:
        """Return the options flow."""
        return MannheimClimateOptionsFlow()

    @callback
    def async_remove(self) -> None:
        """Invalidate an open map link when the flow ends."""
        # The singleton holds a placeholder while it is still being created.
        if isinstance(sessions := self.hass.data.get(DATA_MAP), MapSessions):
            sessions.remove_flow(self.flow_id)

    async def _async_load(self) -> bool:
        self._hub = await async_get_hub(self.hass)
        try:
            self._stations = await self._hub.async_get_stations()
        except StationListUnavailableError:
            return False
        return True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the location on a map."""
        if not await self._async_load():
            return self.async_abort(reason="cannot_connect")
        errors: dict[str, str] = {}
        if user_input is not None:
            location = _parse_location(user_input)
            if not _is_covered(self._stations, location):
                errors["base"] = "outside_coverage"
            else:
                await self.async_set_unique_id(location.unique_id)
                self._abort_if_unique_id_configured()
                self._location = location
                return await self.async_step_environment()
        return self.async_show_form(
            step_id="user",
            data_schema=_location_schema(
                {
                    CONF_LATITUDE: self.hass.config.latitude,
                    CONF_LONGITUDE: self.hass.config.longitude,
                    CONF_RADIUS: DEFAULT_SEARCH_RADIUS_M,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Move an existing location."""
        if not await self._async_load():
            return self.async_abort(reason="cannot_connect")
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            location = _parse_location(user_input)
            taken = any(
                other.unique_id == location.unique_id
                for other in self.hass.config_entries.async_entries(DOMAIN)
                if other.entry_id != entry.entry_id
            )
            if taken:
                return self.async_abort(reason="already_configured")
            if not _is_covered(self._stations, location):
                errors["base"] = "outside_coverage"
            else:
                self._location = location
                return await self.async_step_environment()
        current = Location.from_data(entry.data)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_location_schema(
                {
                    CONF_LATITUDE: current.latitude,
                    CONF_LONGITUDE: current.longitude,
                    CONF_RADIUS: current.radius,
                }
            ),
            errors=errors,
        )

    async def async_step_environment(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the surroundings (pre-selected from the LCZ map)."""
        if user_input is not None:
            self._location.environment = Environment(user_input[CONF_ENVIRONMENT])
            entry_id, min_interval = None, DEFAULT_SCAN_INTERVAL_MIN
            if self.source == SOURCE_RECONFIGURE:
                entry = self._get_reconfigure_entry()
                entry_id = entry.entry_id
                min_interval = entry.options.get(CONF_SCAN_INTERVAL, min_interval)
            self._selection = StationSelection(
                self.hass,
                self._hub,
                self._stations,
                self._location.as_tuple(),
                entry_id,
                min_interval,
            )
            return await self.async_step_stations()
        return self.async_show_form(
            step_id="environment",
            data_schema=_environment_schema(
                detected_environment(self._hub, self._location)
            ),
        )

    async def async_step_stations(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Offer the recommendation, the interactive map or the list."""
        selection = self._selection
        options = ["map", "list"]
        if selection.recommendation_fits():
            options.insert(0, "accept")
        return self.async_show_menu(
            step_id="stations",
            menu_options=options,
            description_placeholders=await selection.async_placeholders(
                selection.recommended_sensor_ids(),
                selection.recommended_wind_sensor_id(),
            ),
        )

    async def async_step_accept(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Use the recommendation as is."""
        selection = self._selection
        return self._async_finish(
            selection.recommended_sensor_ids(), selection.recommended_wind_sensor_id()
        )

    async def async_step_map(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Open the interactive map; the map page continues the flow when saved."""
        if user_input is not None:
            self._map_choice = user_input[MAP_SELECTION]
            return self.async_external_step_done(next_step_id="map_done")
        selection = self._selection
        payload = await selection.async_map_payload(
            selection.recommended_sensor_ids(), selection.recommended_wind_sensor_id()
        )
        sessions = await async_get_map_sessions(self.hass)
        url = map_url(self.hass, sessions.create(self.flow_id, selection, payload))
        return self.async_external_step(
            step_id="map", url=url, description_placeholders={"url": url}
        )

    async def async_step_map_done(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Create or update the entry with the stations chosen on the map."""
        choice = self._map_choice
        return self._async_finish(
            choice[CONF_TEMPERATURE_SENSORS], choice[CONF_WIND_SENSOR]
        )

    async def async_step_list(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the stations from a list, recommendation pre-selected."""
        selection = self._selection
        selected = selection.recommended_sensor_ids()
        wind = selection.recommended_wind_sensor_id()
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = list(user_input[CONF_TEMPERATURE_SENSORS])
            wind = user_input[CONF_WIND_SENSOR]
            errors = selection.validate(selected, wind)
            if not errors:
                return self._async_finish(selected, wind)
        return self.async_show_form(
            step_id="list",
            data_schema=await selection.async_list_schema(selected, wind),
            errors=errors,
            description_placeholders=await selection.async_placeholders(selected, wind),
            last_step=True,
        )

    def _async_finish(self, selected: list[str], wind: str) -> ConfigFlowResult:
        options = selected_options(self._selection, selected, wind)
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            return self.async_update_reload_and_abort(
                entry,
                unique_id=self._location.unique_id,
                data=self._location.as_data(),
                options={**entry.options, **options},
            )
        return self.async_create_entry(
            title=self._title(),
            data=self._location.as_data(),
            options={**options, CONF_DEW_POINT_OFFSET: DEFAULT_DEW_POINT_OFFSET_K},
        )

    def _title(self) -> str:
        location = self._location
        if (
            distance_m(
                location.latitude,
                location.longitude,
                self.hass.config.latitude,
                self.hass.config.longitude,
            )
            <= HOME_MATCH_RADIUS_M
        ):
            return self.hass.config.location_name
        district = self._hub.reference.district(location.latitude, location.longitude)
        if district:
            return district
        closest = nearest(self._stations, location.latitude, location.longitude)
        return next((s.district for s in closest if s.district), FALLBACK_TITLE)


class MannheimClimateOptionsFlow(OptionsFlowWithReload):
    """Change stations (list), polling interval and humidity correction."""

    def __init__(self) -> None:
        """Initialize the flow state."""
        self._selection: StationSelection | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the current choice; the map is available via reconfigure."""
        entry = self.config_entry
        if self._selection is None:
            hub = await async_get_hub(self.hass)
            try:
                stations = await hub.async_get_stations()
            except StationListUnavailableError:
                return self.async_abort(reason="cannot_connect")
            self._selection = StationSelection(
                self.hass,
                hub,
                stations,
                Location.from_data(entry.data).as_tuple(),
                entry.entry_id,
                min_interval=min(SCAN_INTERVAL_CHOICES_MIN),
            )
        selection = self._selection
        options = entry.options
        selected = list(options.get(CONF_TEMPERATURE_SENSORS, []))
        wind = options.get(CONF_WIND_SENSOR) or NO_WIND_SENSOR
        interval = int(options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN))
        offset = float(options.get(CONF_DEW_POINT_OFFSET, DEFAULT_DEW_POINT_OFFSET_K))
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = list(user_input[CONF_TEMPERATURE_SENSORS])
            wind = user_input[CONF_WIND_SENSOR]
            interval = int(user_input[CONF_SCAN_INTERVAL])
            offset = float(user_input[CONF_DEW_POINT_OFFSET])
            errors = selection.validate(selected, wind, interval)
            if not errors:
                return self.async_create_entry(
                    data={
                        **_station_options(selected, wind),
                        CONF_SCAN_INTERVAL: interval,
                        CONF_DEW_POINT_OFFSET: round(offset, 1),
                    }
                )
        extra = {
            probatio.Required(
                CONF_SCAN_INTERVAL, default=str(interval)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=str(minutes), label=f"{minutes} min")
                        for minutes in SCAN_INTERVAL_CHOICES_MIN
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            probatio.Required(CONF_DEW_POINT_OFFSET, default=offset): NumberSelector(
                NumberSelectorConfig(
                    min=-DEW_POINT_OFFSET_LIMIT_K,
                    max=DEW_POINT_OFFSET_LIMIT_K,
                    step=0.1,
                    unit_of_measurement="K",
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=await selection.async_list_schema(selected, wind, extra),
            errors=errors,
            description_placeholders=await selection.async_placeholders(
                selected, wind, interval
            ),
        )
