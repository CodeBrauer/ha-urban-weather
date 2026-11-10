"""Station selection shared by the config flow, the options flow and the map page."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import probatio
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.translation import async_get_translations

from .const import (
    CANDIDATE_STATIONS,
    CONF_SCAN_INTERVAL,
    CONF_TEMPERATURE_SENSORS,
    CONF_WIND_SENSOR,
    DEFAULT_SCAN_INTERVAL_MIN,
    DOMAIN,
    MAP_CANDIDATE_STATIONS,
    MAX_SELECTED_STATIONS,
    MEASUREMENT_BUDGET_PER_HOUR,
    NO_WIND_SENSOR,
    PLANNED_BUDGET_PER_HOUR,
    SCAN_INTERVAL_CHOICES_MIN,
    TILE_ATTRIBUTION,
    TILE_URL,
    WIND_CANDIDATE_STATIONS,
    Environment,
)
from .geo import bearing_deg, direction_arrow
from .hub import requests_per_hour
from .stations import Recommendation, Station, nearest, recommend

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .hub import ClimateHub

METRES_PER_KM = 1000


def planned_requests_of_others(
    hass: HomeAssistant, exclude_entry_id: str | None
) -> int:
    """Return planned requests per hour of all other enabled config entries."""
    total = 0
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == exclude_entry_id or entry.disabled_by:
            continue
        sensors = len(entry.options.get(CONF_TEMPERATURE_SENSORS, []))
        if entry.options.get(CONF_WIND_SENSOR):
            sensors += 1
        total += requests_per_hour(
            sensors, entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN)
        )
    return total


class StationSelection:
    """Recommendation, budget and presentation of the stations around a location."""

    def __init__(  # noqa: PLR0913
        self,
        hass: HomeAssistant,
        hub: ClimateHub,
        stations: list[Station],
        location: tuple[float, float, float, Environment],
        entry_id: str | None = None,
        min_interval: int = DEFAULT_SCAN_INTERVAL_MIN,
    ) -> None:
        """Compute the recommendation and the budget used by other entries once."""
        self._hass = hass
        self._hub = hub
        self._stations = stations
        self.latitude, self.longitude, self.radius, environment = location
        self.min_interval = min_interval
        self.others = planned_requests_of_others(hass, entry_id)
        self.recommendation: Recommendation | None = recommend(
            stations, self.latitude, self.longitude, environment, self.radius
        )
        self._translations: dict[str, str] | None = None

    # Budget

    def planned_requests(self, count: int, wind: str, interval: int) -> int:
        """Return planned requests per hour of all entries with this selection."""
        sensors = count + (wind != NO_WIND_SENSOR)
        return requests_per_hour(sensors, interval) + self.others

    def fitting_interval(self, count: int, wind: str) -> int | None:
        """Return the shortest allowed interval that keeps all entries in budget."""
        for interval in SCAN_INTERVAL_CHOICES_MIN:
            if interval < self.min_interval:
                continue
            if self.planned_requests(count, wind, interval) <= PLANNED_BUDGET_PER_HOUR:
                return interval
        return None

    def max_stations(self, wind: str, interval: int | None = None) -> int:
        """Return how many stations fit the budget (at a fixed or any interval)."""
        best = 0
        for count in range(1, MAX_SELECTED_STATIONS + 1):
            fits = (
                self.fitting_interval(count, wind) is not None
                if interval is None
                else self.planned_requests(count, wind, interval)
                <= PLANNED_BUDGET_PER_HOUR
            )
            if fits:
                best = count
        return best

    def validate(
        self, selected: list[str], wind: str, interval: int | None = None
    ) -> dict[str, str]:
        """Return form errors for a selection (interval None = pick automatically)."""
        if not selected:
            return {CONF_TEMPERATURE_SENSORS: "no_station_selected"}
        known = {
            s.temperature_sensor.id for s in self._stations if s.temperature_sensor
        }
        wind_known = {s.wind_sensor.id for s in self._stations if s.wind_sensor}
        if not set(selected) <= known or wind not in (wind_known | {NO_WIND_SENSOR}):
            return {"base": "unknown_station"}
        if len(selected) > MAX_SELECTED_STATIONS:
            return {CONF_TEMPERATURE_SENSORS: "too_many_stations"}
        fits = (
            self.fitting_interval(len(selected), wind) is not None
            if interval is None
            else self.planned_requests(len(selected), wind, interval)
            <= PLANNED_BUDGET_PER_HOUR
        )
        return {} if fits else {"base": "over_budget"}

    # Recommendation

    def recommended_sensor_ids(self) -> list[str]:
        """Return the temperature sensors of the recommended stations."""
        if not self.recommendation:
            return []
        return [s.temperature_sensor.id for s in self.recommendation.stations]

    def recommended_wind_sensor_id(self) -> str:
        """Return the recommended wind sensor or the 'none' option."""
        station = self.recommendation.wind_station if self.recommendation else None
        return station.wind_sensor.id if station else NO_WIND_SENSOR

    def recommendation_fits(self) -> bool:
        """Return True if the recommendation can be used within the budget."""
        return bool(self.recommendation) and not self.validate(
            self.recommended_sensor_ids(), self.recommended_wind_sensor_id()
        )

    # Presentation

    async def async_translations(self) -> dict[str, str]:
        """Return the integration's selector translations in the system language."""
        if self._translations is None:
            self._translations = await async_get_translations(
                self._hass, self._hass.config.language, "selector", {DOMAIN}
            )
        return self._translations

    def translate(self, selector: str, option: str) -> str:
        """Translate a selector option (call async_translations first)."""
        key = f"component.{DOMAIN}.selector.{selector}.options.{option}"
        return (self._translations or {}).get(key, str(option))

    def distance_text(self, station: Station) -> str:
        """Return e.g. '1,2 km ↗' (direction seen from the location)."""
        distance = station.distance_to(self.latitude, self.longitude)
        arrow = direction_arrow(
            bearing_deg(
                self.latitude, self.longitude, station.latitude, station.longitude
            )
        )
        if distance < METRES_PER_KM:
            text = f"{distance:.0f} m"
        else:
            text = f"{distance / METRES_PER_KM:.1f} km"
            if self._hass.config.language.startswith("de"):
                text = text.replace(".", ",")
        return f"{text} {arrow}"

    def station_label(self, station: Station, *, recommended: bool) -> str:
        """Return e.g. '444 m ↙ · Seckenheim (2507LH096) · open built-up'."""
        parts = [self.distance_text(station), station.label]
        if station.environment:
            parts.append(self.translate("environment_short", station.environment))
        if station.is_elevated:
            parts.append(self.translate("station_flag", "elevated"))
        if recommended:
            parts.append(self.translate("station_flag", "recommended"))
        return " · ".join(parts)

    def recommendation_text(self) -> str:
        """Explain the recommendation in one sentence."""
        if not self.recommendation:
            return ""
        closest = self.recommendation.nearest
        environment = (
            self.translate("environment_short", closest.environment)
            if closest.environment
            else "?"
        )
        return self.translate("recommendation", self.recommendation.reason).format(
            station=closest.label,
            distance=self.distance_text(closest),
            environment=environment,
            count=len(self.recommendation.stations),
        )

    def recommendation_list(self) -> str:
        """Return the recommended stations as markdown list."""
        if not self.recommendation:
            return ""
        lines = [
            f"- {self.station_label(station, recommended=False)}"
            for station in self.recommendation.stations
        ]
        if wind := self.recommendation.wind_station:
            label = self.translate("station_flag", "wind")
            lines.append(f"- {label}: {self.distance_text(wind)} · {wind.label}")
        return "\n".join(lines)

    def _temperature_stations(self, selected: list[str], count: int) -> list[Station]:
        by_distance = nearest(
            [s for s in self._stations if s.temperature_sensor],
            self.latitude,
            self.longitude,
        )
        return by_distance[:count] + [
            s for s in by_distance[count:] if s.temperature_sensor.id in selected
        ]

    def _wind_stations(self, wind: str) -> list[Station]:
        stations = nearest(
            [s for s in self._stations if s.wind_sensor], self.latitude, self.longitude
        )[:WIND_CANDIDATE_STATIONS]
        if wind != NO_WIND_SENSOR and wind not in (s.wind_sensor.id for s in stations):
            current = self._hub.station_for_sensor(wind)
            if current and current.wind_sensor:
                stations.append(current)
        return stations

    def wind_options(self, wind: str) -> list[SelectOptionDict]:
        """Return the wind station choices, 'none' first."""
        options = [
            SelectOptionDict(
                value=NO_WIND_SENSOR, label=self.translate("station_flag", "no_wind")
            )
        ]
        options += [
            SelectOptionDict(
                value=station.wind_sensor.id,
                label=f"{self.distance_text(station)} · {station.label}",
            )
            for station in self._wind_stations(wind)
        ]
        return options

    async def async_list_schema(
        self, selected: list[str], wind: str, extra: dict[Any, Any] | None = None
    ) -> probatio.Schema:
        """Return the list form schema (stations, wind, optional extra fields)."""
        await self.async_translations()
        recommended = set(self.recommended_sensor_ids())
        options = [
            SelectOptionDict(
                value=station.temperature_sensor.id,
                label=self.station_label(
                    station, recommended=station.temperature_sensor.id in recommended
                ),
            )
            for station in self._temperature_stations(selected, CANDIDATE_STATIONS)
        ]
        return probatio.Schema(
            {
                probatio.Required(
                    CONF_TEMPERATURE_SENSORS, default=selected
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=options, multiple=True, mode=SelectSelectorMode.LIST
                    )
                ),
                probatio.Required(CONF_WIND_SENSOR, default=wind): SelectSelector(
                    SelectSelectorConfig(
                        options=self.wind_options(wind),
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                **(extra or {}),
            }
        )

    async def async_placeholders(
        self, selected: list[str], wind: str, interval: int | None = None
    ) -> dict[str, str]:
        """Return description placeholders for menu, list and options steps."""
        await self.async_translations()
        used_interval = interval or self.fitting_interval(len(selected), wind)
        shown_interval = used_interval or SCAN_INTERVAL_CHOICES_MIN[-1]
        return {
            "recommendation": self.recommendation_text(),
            "recommended_list": self.recommendation_list(),
            "max_stations": str(self.max_stations(wind, interval)),
            "interval": str(shown_interval),
            "planned": str(self.planned_requests(len(selected), wind, shown_interval)),
            "budget": str(PLANNED_BUDGET_PER_HOUR),
            "api_limit": str(MEASUREMENT_BUDGET_PER_HOUR),
        }

    async def async_map_payload(self, selected: list[str], wind: str) -> dict[str, Any]:
        """Return everything the interactive map page needs."""
        translations = await self.async_translations()
        prefix = f"component.{DOMAIN}.selector.map_page.options."
        recommended = set(self.recommended_sensor_ids())
        stations = [
            {
                "id": station.temperature_sensor.id,
                "number": number,
                "label": station.label,
                "lat": station.latitude,
                "lon": station.longitude,
                "distance": self.distance_text(station),
                "environment": self.translate("environment_short", station.environment)
                if station.environment
                else None,
                "elevated": station.is_elevated,
                "recommended": station.temperature_sensor.id in recommended,
            }
            for number, station in enumerate(
                self._temperature_stations(selected, MAP_CANDIDATE_STATIONS), start=1
            )
        ]
        return {
            "home": [self.latitude, self.longitude],
            "radius": self.radius,
            "stations": stations,
            "selected": selected,
            "wind": wind,
            "wind_options": self.wind_options(wind),
            "budget": {
                "per_hour": PLANNED_BUDGET_PER_HOUR,
                "others": self.others,
                "intervals": list(SCAN_INTERVAL_CHOICES_MIN),
                "min_interval": self.min_interval,
                "max_stations": MAX_SELECTED_STATIONS,
                "no_wind": NO_WIND_SENSOR,
            },
            "tiles": {"url": TILE_URL, "attribution": TILE_ATTRIBUTION},
            "recommendation": self.recommendation_text().replace("**", ""),
            "text": {
                key.removeprefix(prefix): value
                for key, value in translations.items()
                if key.startswith(prefix)
            },
        }
