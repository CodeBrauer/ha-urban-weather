"""Polls the selected stations and combines their values."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .aggregation import Estimate, StationReading, estimate, latest_valid
from .api import ApiError, SensorNotFoundError
from .config_flow import Location
from .const import (
    CATCH_UP_MARGIN_S,
    CONF_DEW_POINT_OFFSET,
    CONF_SCAN_INTERVAL,
    CONF_TEMPERATURE_SENSORS,
    CONF_WIND_SENSOR,
    DEFAULT_DEW_POINT_OFFSET_K,
    DEFAULT_SCAN_INTERVAL_MIN,
    DOMAIN,
    ISSUE_ENTRY_ID,
    ISSUE_SENSOR_ID,
    KEEP_VALUES_INTERVALS,
    KEEP_VALUES_MIN_AGE,
    LOGGER,
    MAX_MEASUREMENT_AGE,
    STATION_OFFLINE_AFTER,
    Field,
)
from .hub import RequestDeferredError, StationListUnavailableError
from .selection import StationSelection

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import CALLBACK_TYPE, HomeAssistant

    from .api import ApiSensor, Measurement
    from .hub import ClimateHub
    from .stations import Station

type MannheimClimateConfigEntry = ConfigEntry[ClimateCoordinator]


def issue_id(entry_id: str, kind: str, sensor_id: str) -> str:
    """Return the repair issue id for a sensor of a config entry."""
    return f"{kind}_{entry_id}_{sensor_id}"


class ClimateCoordinator(DataUpdateCoordinator[Estimate]):
    """Fetch the latest values of all selected stations of one config entry."""

    config_entry: MannheimClimateConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MannheimClimateConfigEntry,
        hub: ClimateHub,
        stations: list[Station],
        wind_station: Station | None,
    ) -> None:
        """Remember the stations; offline detection starts counting now."""
        interval = timedelta(
            minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN)
        )
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.title}",
            update_interval=interval,
        )
        self._keep_values_for = max(
            KEEP_VALUES_MIN_AGE, KEEP_VALUES_INTERVALS * interval
        )
        self.hub = hub
        self.stations = stations
        self.wind_station = wind_station
        self._latitude = entry.data[CONF_LATITUDE]
        self._longitude = entry.data[CONF_LONGITUDE]
        self._dew_point_offset = entry.options.get(
            CONF_DEW_POINT_OFFSET, DEFAULT_DEW_POINT_OFFSET_K
        )
        started = dt_util.utcnow()
        self._last_seen: dict[str, datetime] = {
            sensor.id: started for sensor in self.sensors
        }
        self._deferred_wait = 0.0
        self._catch_up_unsub: CALLBACK_TYPE | None = None

    @property
    def sensors(self) -> list[ApiSensor]:
        """All API sensors this entry polls."""
        sensors = [s.temperature_sensor for s in self.stations if s.temperature_sensor]
        if self.wind_station and self.wind_station.wind_sensor:
            sensors.append(self.wind_station.wind_sensor)
        return sensors

    def provides(self, field: Field) -> bool:
        """Return True if any selected sensor measures this field."""
        return any(field in sensor.parameters for sensor in self.sensors)

    def distance_to(self, station: Station) -> float:
        """Distance from the configured location to a station in metres."""
        return station.distance_to(self._latitude, self._longitude)

    async def _async_setup(self) -> None:
        """Sync the repair issues with the selection and the station list."""
        options = self.config_entry.options
        selected = [
            *options.get(CONF_TEMPERATURE_SENSORS, []),
            options.get(CONF_WIND_SENSOR),
        ]
        for issue in list(ir.async_get(self.hass).issues.values()):
            data = issue.data or {}
            if (
                issue.domain == DOMAIN
                and data.get(ISSUE_ENTRY_ID) == self.config_entry.entry_id
                and data.get(ISSUE_SENSOR_ID) not in (*selected, None)
            ):
                ir.async_delete_issue(self.hass, DOMAIN, issue.issue_id)
        for sensor_id in selected:
            if sensor_id and self.hub.station_for_sensor(sensor_id) is None:
                # The old station name is gone with the list, only the id is left.
                self._set_issue("station_removed", sensor_id, sensor_id, active=True)

    async def _async_suggest_new_stations(self) -> None:
        """Suggest the recommendation if it contains recently added stations."""
        try:
            stations = await self.hub.async_get_stations()
        except StationListUnavailableError:
            return
        entry = self.config_entry
        selection = StationSelection(
            self.hass,
            self.hub,
            stations,
            Location.from_data(entry.data).as_tuple(),
            entry.entry_id,
            entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN),
        )
        selected = {
            *entry.options.get(CONF_TEMPERATURE_SENSORS, []),
            entry.options.get(CONF_WIND_SENSOR),
        }
        recommended = [
            *selection.recommended_sensor_ids(),
            selection.recommended_wind_sensor_id(),
        ]
        new = sorted(
            sensor_id
            for sensor_id in recommended
            if sensor_id not in selected and self.hub.is_new(sensor_id)
        )
        if not selection.recommendation_fits():
            new = []
        # The id names the proposal, so ignoring the issue ignores this proposal only.
        current = issue_id(entry.entry_id, "new_stations", "-".join(new))
        prefix = issue_id(entry.entry_id, "new_stations", "")
        for domain, issue in list(ir.async_get(self.hass).issues):
            if domain == DOMAIN and issue.startswith(prefix) and issue != current:
                ir.async_delete_issue(self.hass, DOMAIN, issue)
        if not new:
            return
        labels = dict.fromkeys(self.hub.station_for_sensor(s).label for s in new)
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            current,
            is_fixable=True,
            data={ISSUE_ENTRY_ID: entry.entry_id},
            severity=ir.IssueSeverity.WARNING,
            translation_key="new_stations",
            translation_placeholders={
                "stations": ", ".join(labels),
                "entry": entry.title,
            },
        )

    async def _async_update_data(self) -> Estimate:
        await self._async_suggest_new_stations()
        now = dt_util.utcnow()
        self._deferred_wait = 0.0
        readings: list[StationReading] = []
        failed = 0
        for station in self.stations:
            sensor = station.temperature_sensor
            latest = await self._async_latest(station, sensor, now)
            if latest is None:
                failed += 1
                continue
            readings.append(
                StationReading(station.code, self.distance_to(station), latest)
            )

        wind = None
        if self.wind_station and self.wind_station.wind_sensor:
            wind = await self._async_latest(
                self.wind_station, self.wind_station.wind_sensor, now
            )

        if self._deferred_wait:
            self._schedule_catch_up(self._deferred_wait)
        if not readings and self._last_values_recent(now):
            LOGGER.debug(
                "No recent data, keeping the values of %s", self.data.last_measurement
            )
            return self.data
        if not readings and self._deferred_wait:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="waiting_for_budget",
                translation_placeholders={"seconds": f"{self._deferred_wait:.0f}"},
                retry_after=self._deferred_wait + CATCH_UP_MARGIN_S,
            )
        if not readings:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="no_recent_data"
            )
        if failed:
            LOGGER.debug(
                "%s of %s stations without recent data", failed, len(self.stations)
            )
        return estimate(readings, wind, self._dew_point_offset)

    def _last_values_recent(self, now: datetime) -> bool:
        """Return True while the last estimate may stand in for missing data."""
        last = self.data.last_measurement if self.data else None
        return last is not None and now - last <= self._keep_values_for

    async def _async_latest(
        self, station: Station, sensor: ApiSensor, now: datetime
    ) -> Measurement | None:
        label = f"{station.label} / {sensor.name}"
        try:
            measurements = await self.hub.async_get_measurements(sensor.id)
        except RequestDeferredError as err:
            # Use what we have now, fetch the rest once the budget allows it.
            self._deferred_wait = max(self._deferred_wait, err.wait)
            measurements = self.hub.cached_measurements(sensor.id)
        except SensorNotFoundError:
            self._set_issue("station_removed", sensor.id, label, active=True)
            return None
        except ApiError as err:
            LOGGER.debug("Fetching %s failed: %s", sensor.name, err)
            return None
        latest = latest_valid(measurements, now, MAX_MEASUREMENT_AGE)
        if latest:
            self._last_seen[sensor.id] = now
        offline = now - self._last_seen[sensor.id] > STATION_OFFLINE_AFTER
        self._set_issue("station_offline", sensor.id, label, active=offline)
        self._set_issue("station_removed", sensor.id, label, active=False)
        return latest

    def _schedule_catch_up(self, wait: float) -> None:
        if self._catch_up_unsub:
            return
        LOGGER.debug("Fetching skipped stations in %.0f s", wait)

        async def _catch_up(_now: datetime) -> None:
            self._catch_up_unsub = None
            await self.async_request_refresh()

        self._catch_up_unsub = async_call_later(
            self.hass, wait + CATCH_UP_MARGIN_S, _catch_up
        )

    async def async_shutdown(self) -> None:
        """Cancel a pending catch-up refresh."""
        if self._catch_up_unsub:
            self._catch_up_unsub()
            self._catch_up_unsub = None
        await super().async_shutdown()

    def _set_issue(
        self, kind: str, sensor_id: str, label: str, *, active: bool
    ) -> None:
        issue = issue_id(self.config_entry.entry_id, kind, sensor_id)
        if not active:
            ir.async_delete_issue(self.hass, DOMAIN, issue)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue,
            is_fixable=True,
            data={
                ISSUE_ENTRY_ID: self.config_entry.entry_id,
                ISSUE_SENSOR_ID: sensor_id,
            },
            severity=ir.IssueSeverity.WARNING,
            translation_key=kind,
            translation_placeholders={
                "station": label,
                "entry": self.config_entry.title,
            },
        )
