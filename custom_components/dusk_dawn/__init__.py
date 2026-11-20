"""Dusk & Dawn: sleep sounds, sunrise alarm and night light for Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import (
    CONF_DIY_DEVICE,
    DOMAIN,
    NAME,
    PANEL_COMPONENT,
    PANEL_FILE,
    PANEL_ICON,
    PANEL_URL_PATH,
    SAMPLE_RATE,
    STATIC_URL,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .runtime import SpotRuntime, spot_config
from .services import async_setup_services
from .samples import SampleEngine, SoundLibrary
from .stream import StreamView
from .uploads import DATA_LIBRARY, UploadView
from .websocket import async_setup_websocket

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
DATA_PANEL = f"{DOMAIN}_panel"

type DuskDawnConfigEntry = ConfigEntry[SpotRuntime]


def load_engine_class() -> tuple[type, str]:
    """Prefer the Rust core (installed or bundled in native/), else pure Python."""
    from .native import load_core  # noqa: PLC0415

    core, origin = load_core()
    if core is not None:
        _LOGGER.info("Dusk & Dawn uses the Rust sound engine (%s: %s)", origin, core.__file__)
        return core.Engine, "rust"
    from .engine import Engine  # noqa: PLC0415

    _LOGGER.info("Dusk & Dawn uses the Python sound engine (%s)", origin)
    return Engine, "python"


def ffmpeg_binary(hass: HomeAssistant) -> str:
    try:
        from homeassistant.components.ffmpeg import get_ffmpeg_manager  # noqa: PLC0415

        return get_ffmpeg_manager(hass).binary
    except (ImportError, KeyError):  # ffmpeg integration not loaded
        return "ffmpeg"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the things shared by all spots: HTTP view, services, websocket API."""
    hass.http.register_view(StreamView())
    hass.http.register_view(UploadView())
    library = SoundLibrary(Path(hass.config.path("dusk_dawn_sounds")), SAMPLE_RATE)
    await hass.async_add_executor_job(library.load)
    hass.data[DATA_LIBRARY] = library
    async_setup_services(hass)
    async_setup_websocket(hass)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "frontend"), True)]
    )
    return True


async def _async_register_panel(hass: HomeAssistant) -> None:
    if hass.data.get(DATA_PANEL):
        return
    integration = await async_get_integration(hass, DOMAIN)
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_COMPONENT,
        frontend_url_path=PANEL_URL_PATH,
        sidebar_title=NAME,
        sidebar_icon=PANEL_ICON,
        module_url=f"{STATIC_URL}/{PANEL_FILE}?v={integration.version}",
        embed_iframe=False,
        require_admin=False,
    )
    hass.data[DATA_PANEL] = True


async def async_setup_entry(hass: HomeAssistant, entry: DuskDawnConfigEntry) -> bool:
    """Set up one spot."""
    name = spot_config(entry)["name"]
    if name and name != entry.title:  # renamed in the options flow
        hass.config_entries.async_update_entry(entry, title=name)
    engine: Any | None = None
    if not spot_config(entry)[CONF_DIY_DEVICE]:
        engine_cls, kind = await hass.async_add_executor_job(load_engine_class)
        engine = await hass.async_add_executor_job(engine_cls, SAMPLE_RATE)
        engine = SampleEngine(engine, hass.data[DATA_LIBRARY])
        _LOGGER.debug("Spot %s uses the %s sound engine", entry.title, kind)

    runtime = SpotRuntime(hass, entry, engine, ffmpeg_binary(hass))
    await runtime.async_setup()
    entry.runtime_data = runtime

    async def _on_stop(_event: Event) -> None:
        await runtime.async_shutdown()  # stop encoders and threads, write state

    entry.async_on_unload(hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, _on_stop))
    await _async_register_panel(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: DuskDawnConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: DuskDawnConfigEntry) -> bool:
    """Unload a spot; remove the panel with the last one."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
        others = [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != entry.entry_id and e.state is ConfigEntryState.LOADED
        ]
        if not others and hass.data.pop(DATA_PANEL, False):
            frontend.async_remove_panel(hass, PANEL_URL_PATH)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: DuskDawnConfigEntry) -> None:
    """Delete the stored state of a removed spot."""
    await Store(hass, STORAGE_VERSION, STORAGE_KEY.format(entry_id=entry.entry_id)).async_remove()
