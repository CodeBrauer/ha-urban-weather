"""
Take the screenshots of the documentation from the dev instance, in German and English.

    scripts/develop                                            # in another terminal
    uv run --no-project --with playwright python scripts/screenshots.py

Uses the installed Google Chrome (no browser download) and logs in with
config/dev-credentials.txt. Writes docs/screenshots/de/ and docs/screenshots/en/.

For the run the script disables the existing locations (budget free, nothing else
polls), switches the system and user language, and creates a temporary location at a
public place (no home location in the images) plus a temporary dashboard. All of it is
restored at the end, also after an error. The temporary location fetches its stations
once (about 5 API requests); the second language uses the measurement cache.
"""

from __future__ import annotations

import json
import re
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "screenshots"
CREDENTIALS = ROOT / "config" / "dev-credentials.txt"
TRANSLATIONS = ROOT / "custom_components" / "urban_weather" / "translations"
FAILURE = ROOT / ".cache" / "screenshot-failure.png"
BASE_URL = "http://localhost:8123"
DOMAIN = "urban_weather"
INTEGRATION_PAGE = "ha-config-integration-page"
FLOW_DIALOG = "dialog-data-entry-flow"
CONFIGURE = "ui.panel.config.integrations.config_entry.configure"
LANGUAGES = ("de", "en")
# Wasserturm Mannheim: a public place, so no home location shows up in the images.
LOCATION = {"latitude": 49.48396, "longitude": 8.47585, "radius": 3000}
# The temporary location is the park around it: a combination of stations shows more
# of the integration (spread, outliers, weather condition) than the single station
# recommended for the dense surroundings in the setup images.
TEMPORARY_ENVIRONMENT = "green"
DASHBOARD = "klimamessnetz-screenshots"
VIEWPORT = {"width": 1280, "height": 1000}
SCALE = 2
UI_TIMEOUT_MS = 30_000
DATA_TIMEOUT_MS = 300_000
POLL_MS = 5_000
SETTLE_MS = 1500
JPEG_QUALITY = 85

HASS = "document.querySelector('home-assistant').hass"


def credentials() -> tuple[str, str]:
    """Return username and password of the dev instance (never printed)."""
    values = {
        match[1].lower(): match[2].strip()
        for line in CREDENTIALS.read_text(encoding="utf-8").splitlines()
        if (match := re.match(r"\s*(\w+)\s*[:=]\s*(.*)", line))
    }
    return values["username"], values["password"]


def strings(language: str) -> dict[str, Any]:
    """Return the integration's UI strings of a language."""
    return json.loads((TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8"))


def call_ws(page: Page, message: dict[str, Any]) -> Any:
    """Send a websocket command as the logged-in user."""
    return page.evaluate(f"(message) => {HASS}.callWS(message)", message)


def call_api(page: Page, method: str, path: str, data: Any = None) -> Any:
    """Call the REST API as the logged-in user."""
    return page.evaluate(
        f"([method, path, data]) => {HASS}.callApi(method, path, data)",
        [method, path, data],
    )


def login(page: Page) -> None:
    """Log into the dev instance."""
    username, password = credentials()
    page.goto(BASE_URL)
    page.locator("input[name=username]").fill(username)
    page.locator("input[name=password]").fill(password)
    page.keyboard.press("Enter")
    page.wait_for_function(
        "() => document.querySelector('home-assistant')?.hass?.states",
        timeout=UI_TIMEOUT_MS,
    )


def set_language(page: Page, language: str) -> None:
    """Switch the system language (backend texts) and the user's UI language."""
    call_ws(page, {"type": "config/core/update", "language": language})
    page.evaluate(
        """(language) => document.querySelector('home-assistant').dispatchEvent(
            new CustomEvent('hass-language-select', {detail: language}))""",
        language,
    )
    page.wait_for_function(f"(language) => {HASS}.language === language", arg=language)


def localize(page: Page, key: str) -> str:
    """Return a frontend text in the current UI language."""
    return page.evaluate(f"(key) => {HASS}.localize(key)", key)


def open_page(page: Page, path: str) -> None:
    """Load a frontend page and wait until it has rendered."""
    page.goto(BASE_URL + path)
    page.wait_for_function(
        "() => document.querySelector('home-assistant')?.hass?.states",
        timeout=UI_TIMEOUT_MS,
    )
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(SETTLE_MS)


def navigate(page: Page, path: str) -> None:
    """Navigate inside the frontend without reloading it."""
    page.evaluate(
        """(path) => { history.pushState(null, '', path);
            window.dispatchEvent(
                new CustomEvent('location-changed', {detail: {replace: false}})); }""",
        path,
    )


def shoot(target: Any, language: str, name: str) -> None:
    """Save a screenshot of a page or element, JPEG for maps, PNG otherwise."""
    path = OUT_DIR / language / name
    path.parent.mkdir(parents=True, exist_ok=True)
    options: dict[str, Any] = {"path": path}
    if path.suffix == ".jpg":
        options |= {"type": "jpeg", "quality": JPEG_QUALITY}
    target.screenshot(**options)
    print(f"  {path.relative_to(ROOT)}")


def flow_dialog(page: Page) -> Any:
    """Return the visible panel of the config or options flow dialog."""
    return page.locator(f"{FLOW_DIALOG} dialog").first


def flow_text(page: Page, text: str) -> Any:
    """
    Return a visible text of the flow dialog.

    The content is slotted into the panel, so it is not inside the panel element.
    """
    return page.locator(FLOW_DIALOG).get_by_text(text, exact=False).first


def wait_for_step(page: Page, text: str) -> None:
    """Wait until the flow dialog shows a text of the expected step."""
    flow_text(page, text).wait_for(timeout=UI_TIMEOUT_MS)
    page.wait_for_timeout(SETTLE_MS)


def submit_step(page: Page) -> None:
    """Press the submit button of the current flow step."""
    page.locator(f"{FLOW_DIALOG} ha-dialog-footer ha-button:visible").last.click()


def start_flow(page: Page) -> None:
    """Open the config flow dialog with the add button of the integration page."""
    open_page(page, f"/config/integrations/integration/{DOMAIN}")
    page.locator(f"{INTEGRATION_PAGE} .header .actions ha-button").first.click()
    page.locator(f"{FLOW_DIALOG} step-flow-form").wait_for(timeout=UI_TIMEOUT_MS)
    page.wait_for_timeout(SETTLE_MS)


def set_location(page: Page) -> None:
    """Put the public location into the location form of the first step."""
    page.locator(f"{FLOW_DIALOG} step-flow-form ha-form").first.evaluate(
        """(form, location) => form.dispatchEvent(new CustomEvent('value-changed',
            {detail: {value: {...form.data, location}}}))""",
        LOCATION,
    )
    page.wait_for_timeout(SETTLE_MS * 2)


def close_flow(page: Page) -> None:
    """Close the flow dialog with its close button; an unfinished flow is aborted."""
    page.locator(f"{FLOW_DIALOG} ha-dialog > ha-icon-button").first.click()
    page.locator(f"{FLOW_DIALOG} step-flow-form").wait_for(
        state="detached", timeout=UI_TIMEOUT_MS
    )


def shoot_config_flow(page: Page, language: str, flow_ids: list[str]) -> None:
    """Location, surroundings, stations menu, list and map page."""
    texts = strings(language)["config"]["step"]
    menu = texts["stations"]["menu_options"]

    start_flow(page)
    set_location(page)
    shoot(flow_dialog(page), language, "01-location.jpg")
    submit_step(page)
    wait_for_step(page, texts["environment"]["title"])
    shoot(flow_dialog(page), language, "02-environment.png")
    submit_step(page)
    wait_for_step(page, menu["list"])
    shoot(flow_dialog(page), language, "03-menu.png")
    flow_text(page, menu["list"]).click()
    wait_for_step(page, texts["list"]["data"]["wind_sensor"])
    shoot(flow_dialog(page), language, "05-list.png")
    close_flow(page)

    start_flow(page)
    set_location(page)
    submit_step(page)
    wait_for_step(page, texts["environment"]["title"])
    submit_step(page)
    wait_for_step(page, menu["map"])
    with page.context.expect_page(timeout=UI_TIMEOUT_MS) as popup_info:
        flow_text(page, menu["map"]).click()
    popup = popup_info.value
    popup.set_viewport_size({"width": 1280, "height": 800})
    popup.wait_for_load_state("networkidle")
    popup.wait_for_timeout(SETTLE_MS * 2)
    shoot(popup, language, "04-map.jpg")
    popup.close()
    close_flow(page)
    # The frontend keeps a flow in its external step when the dialog is closed.
    abort_flows(page, flow_ids)


def track_flows(page: Page) -> list[str]:
    """Collect the ids of all config flows started from now on (UI and API)."""
    flow_ids: list[str] = []

    def collect(response: Any) -> None:
        if response.request.method == "POST" and response.url.endswith(
            "/api/config/config_entries/flow"
        ):
            with suppress(Exception):
                flow_ids.append(response.json()["flow_id"])

    page.on("response", collect)
    return flow_ids


def abort_flows(page: Page, flow_ids: list[str]) -> None:
    """Abort flows that are still open, e.g. after an error."""
    for flow_id in flow_ids:
        with suppress(Exception):
            call_api(page, "DELETE", f"config/config_entries/flow/{flow_id}")
    flow_ids.clear()


def create_location(page: Page) -> str:
    """Create the temporary location with the recommendation; return its entry id."""
    flow = call_api(page, "POST", "config/config_entries/flow", {"handler": DOMAIN})
    flow_id = flow["flow_id"]
    call_api(
        page, "POST", f"config/config_entries/flow/{flow_id}", {"location": LOCATION}
    )
    step = call_api(
        page,
        "POST",
        f"config/config_entries/flow/{flow_id}",
        {"environment": TEMPORARY_ENVIRONMENT},
    )
    result = call_api(
        page,
        "POST",
        f"config/config_entries/flow/{flow_id}",
        {"next_step_id": "accept"},
    )
    if result.get("type") != "create_entry":
        msg = f"Could not create the temporary location: {result or step}"
        raise RuntimeError(msg)
    return result["result"]["entry_id"]


def wait_until_loaded(page: Page, entry_id: str) -> None:
    """Wait until a config entry is set up; it retries while the budget is used up."""
    for _ in range(DATA_TIMEOUT_MS // POLL_MS):
        entries = call_api(page, "GET", f"config/config_entries/entry?domain={DOMAIN}")
        if any(e["entry_id"] == entry_id and e["state"] == "loaded" for e in entries):
            return
        page.wait_for_timeout(POLL_MS)
    msg = "The temporary location was not set up in time"
    raise TimeoutError(msg)


def entities_of(page: Page, entry_id: str) -> list[str]:
    """Return the entity ids of a config entry."""
    return [
        entity["entity_id"]
        for entity in call_ws(page, {"type": "config/entity_registry/list"})
        if entity["config_entry_id"] == entry_id and not entity["disabled_by"]
    ]


def device_of(page: Page, entry_id: str) -> str:
    """Return the device id of a config entry."""
    devices = call_ws(page, {"type": "config/device_registry/list"})
    return next(d["id"] for d in devices if entry_id in d["config_entries"])


def wait_for_values(page: Page, entity_ids: list[str]) -> None:
    """
    Wait until all sensors have values.

    Skipped stations follow once the budget allows it. If values are still missing, the
    API is probably rate limited: stop instead of replacing good images with gaps.
    """
    sensors = [e for e in entity_ids if e.startswith("sensor.")]
    missing = f"""(ids) => ids.filter((id) => ['unavailable', 'unknown', undefined]
        .includes({HASS}.states[id]?.state))"""
    for _ in range(DATA_TIMEOUT_MS // POLL_MS):
        if not page.evaluate(missing, sensors):
            return
        page.wait_for_timeout(POLL_MS)
    msg = (
        f"No value for {', '.join(page.evaluate(missing, sensors))}; the API is "
        "probably rate limited (see the Home Assistant log), try again later"
    )
    raise TimeoutError(msg)


def create_dashboard(page: Page, entity_ids: list[str]) -> str:
    """Create a dashboard with the weather entity and all sensors; return its id."""
    dashboard = call_ws(
        page,
        {
            "type": "lovelace/dashboards/create",
            "url_path": DASHBOARD,
            "title": "Klimamessnetz",
            "mode": "storage",
            "show_in_sidebar": False,
            "require_admin": False,
        },
    )
    weather = next(e for e in entity_ids if e.startswith("weather."))
    sensors = [e for e in entity_ids if e.startswith("sensor.")]
    cards = [
        {"type": "weather-forecast", "entity": weather, "show_forecast": False},
        {"type": "entities", "entities": sensors},
    ]
    call_ws(
        page,
        {
            "type": "lovelace/config/save",
            "url_path": DASHBOARD,
            "config": {"views": [{"title": "Klimamessnetz", "cards": cards}]},
        },
    )
    return dashboard["id"]


def shoot_location(page: Page, language: str, entry_id: str) -> None:
    """Device page, dashboard, weather details and options of the location."""
    navigate(page, f"/config/devices/device/{device_of(page, entry_id)}")
    page.wait_for_timeout(SETTLE_MS * 2)
    shoot(page, language, "06-device.png")

    navigate(page, f"/{DASHBOARD}/0")
    page.wait_for_timeout(SETTLE_MS * 2)
    shoot(page, language, "07-dashboard.png")
    page.locator("hui-weather-forecast-card").first.click()
    dialog = page.locator("ha-more-info-dialog dialog").first
    dialog.wait_for(timeout=UI_TIMEOUT_MS)
    page.wait_for_timeout(SETTLE_MS)
    shoot(dialog, language, "09-weather.png")
    page.keyboard.press("Escape")

    navigate(page, f"/config/integrations/integration/{DOMAIN}")
    page.wait_for_timeout(SETTLE_MS)
    page.get_by_role("button", name=localize(page, CONFIGURE)).first.click()
    texts = strings(language)["options"]["step"]["init"]
    wait_for_step(page, texts["data"]["scan_interval"])
    shoot(flow_dialog(page), language, "08-options.png")
    close_flow(page)


def run(page: Page) -> None:
    """Take all screenshots; restore the instance afterwards."""
    original_language = call_ws(page, {"type": "get_config"})["language"]
    user_language = call_ws(page, {"type": "frontend/get_user_data", "key": "language"})
    others = [
        entry["entry_id"]
        for entry in call_api(
            page, "GET", f"config/config_entries/entry?domain={DOMAIN}"
        )
        if not entry["disabled_by"]
    ]
    entry_id = dashboard_id = None
    flow_ids = track_flows(page)
    try:
        for entry in others:
            call_ws(
                page,
                {
                    "type": "config_entries/disable",
                    "entry_id": entry,
                    "disabled_by": "user",
                },
            )
        for language in LANGUAGES:
            print(f"{language}: setup")
            set_language(page, language)
            shoot_config_flow(page, language, flow_ids)

        entry_id = create_location(page)
        print("waiting for the first values of the temporary location")
        wait_until_loaded(page, entry_id)
        entity_ids = entities_of(page, entry_id)
        wait_for_values(page, entity_ids)
        dashboard_id = create_dashboard(page, entity_ids)
        for language in reversed(LANGUAGES):
            print(f"{language}: location")
            set_language(page, language)
            call_api(page, "POST", f"config/config_entries/entry/{entry_id}/reload")
            wait_until_loaded(page, entry_id)
            wait_for_values(page, entity_ids)
            shoot_location(page, language, entry_id)
    except Exception:
        FAILURE.parent.mkdir(exist_ok=True)
        page.screenshot(path=FAILURE)
        print(f"failed, page saved as {FAILURE.relative_to(ROOT)}")
        raise
    finally:
        print("restoring the dev instance")
        with suppress(Exception):
            page.keyboard.press("Escape")
        abort_flows(page, flow_ids)
        if dashboard_id:
            call_ws(
                page,
                {"type": "lovelace/dashboards/delete", "dashboard_id": dashboard_id},
            )
        if entry_id:
            call_api(page, "DELETE", f"config/config_entries/entry/{entry_id}")
        for entry in others:
            call_ws(
                page,
                {
                    "type": "config_entries/disable",
                    "entry_id": entry,
                    "disabled_by": None,
                },
            )
        set_language(page, original_language)
        call_ws(
            page,
            {
                "type": "frontend/set_user_data",
                "key": "language",
                "value": user_language.get("value"),
            },
        )


def main() -> int:
    """Log in and take the screenshots."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        # The frontend's service worker reloads a fresh profile shortly after the
        # first load, which closes open dialogs.
        context = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=SCALE,
            color_scheme="light",
            service_workers="block",
        )
        page = context.new_page()
        login(page)
        run(page)
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
