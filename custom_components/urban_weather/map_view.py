"""Interactive station map, opened as external step of the config flow."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aiohttp import web
from homeassistant.components.http import (
    KEY_HASS,
    HomeAssistantView,
    StaticPathConfig,
    current_request,
)
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.helpers.network import get_url
from homeassistant.helpers.singleton import singleton
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import (
    CONF_TEMPERATURE_SENSORS,
    CONF_WIND_SENSOR,
    DOMAIN,
    LOGGER,
    MAP_SESSION_TTL,
    MAP_URL,
    STATIC_URL,
)

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant

    from .selection import StationSelection

WWW_DIR = Path(__file__).parent / "www"
DATA_MAP: HassKey[MapSessions] = HassKey(f"{DOMAIN}_map")
MAP_SELECTION = "map_selection"
TOKEN_BYTES = 24
NO_STORE = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}


@dataclass(slots=True)
class MapSession:
    """One open map page, bound to a config flow."""

    flow_id: str
    selection: StationSelection
    payload: dict[str, Any]
    expires: datetime


class MapSessions:
    """Short-lived, unguessable map links (the page has no Home Assistant login)."""

    def __init__(self, template: str) -> None:
        """Keep the page template."""
        self.template = template
        self._sessions: dict[str, MapSession] = {}

    def create(
        self, flow_id: str, selection: StationSelection, payload: dict[str, Any]
    ) -> str:
        """Open a session for a flow and return its token."""
        self.remove_flow(flow_id)
        now = dt_util.utcnow()
        self._sessions = {t: s for t, s in self._sessions.items() if s.expires > now}
        token = secrets.token_urlsafe(TOKEN_BYTES)
        self._sessions[token] = MapSession(
            flow_id, selection, payload, now + MAP_SESSION_TTL
        )
        return token

    def get(self, token: str) -> MapSession | None:
        """Return a valid session."""
        session = self._sessions.get(token)
        if session and session.expires > dt_util.utcnow():
            return session
        self._sessions.pop(token, None)
        return None

    def remove_flow(self, flow_id: str) -> None:
        """Forget the sessions of a finished or aborted flow."""
        self._sessions = {
            t: s for t, s in self._sessions.items() if s.flow_id != flow_id
        }


def map_url(hass: HomeAssistant, token: str) -> str:
    """Return the absolute page URL, using the address the user opened HA with."""
    request = current_request.get()
    base = f"{request.scheme}://{request.host}" if request else get_url(hass)
    return base + MAP_URL.format(token=token)


def _load_template() -> str:
    # Content hash as cache buster: assets change without a version bump
    # when installed from a branch.
    digest = hashlib.sha256()
    for name in ("map.js", "map.css"):
        digest.update((WWW_DIR / name).read_bytes())
    template = (WWW_DIR / "map.html").read_text("utf-8")
    return template.replace("__STATIC__", STATIC_URL).replace(
        "__VERSION__", digest.hexdigest()[:12]
    )


@singleton(DATA_MAP, async_=True)
async def async_get_map_sessions(hass: HomeAssistant) -> MapSessions:
    """Register the static files and the map view on first use."""
    template = await hass.async_add_executor_job(_load_template)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(WWW_DIR), cache_headers=True)]
    )
    sessions = MapSessions(template)
    hass.http.register_view(MapView(sessions))
    return sessions


class MapView(HomeAssistantView):
    """Serves the map page and receives the chosen stations."""

    url = MAP_URL
    name = f"api:{DOMAIN}:map"
    requires_auth = False

    def __init__(self, sessions: MapSessions) -> None:
        """Use the shared session store."""
        self._sessions = sessions

    async def get(self, request: web.Request, token: str) -> web.Response:  # noqa: ARG002
        """Return the page with its data embedded."""
        session = self._sessions.get(token)
        if session is None:
            return web.Response(status=HTTPStatus.NOT_FOUND, text="Link expired")
        config = json.dumps(session.payload).replace("</", "<\\/")
        return web.Response(
            text=self._sessions.template.replace("__CONFIG__", config),
            content_type="text/html",
            headers=NO_STORE,
        )

    async def post(self, request: web.Request, token: str) -> web.Response:
        """Validate the selection and continue the config flow."""
        session = self._sessions.get(token)
        if session is None:
            return self.json({"error": "expired"}, HTTPStatus.NOT_FOUND)
        try:
            data = await request.json()
            selected = [str(item) for item in data[CONF_TEMPERATURE_SENSORS]]
            wind = str(data[CONF_WIND_SENSOR])
        except ValueError, KeyError, TypeError:
            return self.json({"error": "invalid"}, HTTPStatus.BAD_REQUEST)
        if errors := session.selection.validate(selected, wind):
            return self.json(
                {"error": next(iter(errors.values()))}, HTTPStatus.BAD_REQUEST
            )
        try:
            await request.app[KEY_HASS].config_entries.flow.async_configure(
                session.flow_id,
                {
                    MAP_SELECTION: {
                        CONF_TEMPERATURE_SENSORS: selected,
                        CONF_WIND_SENSOR: wind,
                    }
                },
            )
        except UnknownFlow:
            return self.json({"error": "expired"}, HTTPStatus.NOT_FOUND)
        LOGGER.debug("Map selection received for flow %s", session.flow_id)
        self._sessions.remove_flow(session.flow_id)
        return self.json({"ok": True})
