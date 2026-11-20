"""Websocket API for the panel (contract section 4)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_FRIENDLY_NAME, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import CONF_LIGHTS, CONF_PRESENCE, CONF_SPEAKERS, DOMAIN, SIGNAL_STATE
from .runtime import SpotError
from .uploads import get_library, refresh_engines

if TYPE_CHECKING:
    from .runtime import SpotRuntime

DEBOUNCE_S = 0.1
PRESENCE_CLASSES = ("occupancy", "motion", "presence")

ACTIONS = (
    "play", "stop", "toggle", "set_level", "set_volume", "apply_preset", "save_preset", "delete_preset",
    "set_timer", "good_night", "light", "set_alarm", "delete_alarm", "ring", "stop_alarm", "preview_tone",
    "set_auto", "set_source",
)


@callback
def async_setup_websocket(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_spots)
    websocket_api.async_register_command(hass, ws_subscribe)
    websocket_api.async_register_command(hass, ws_command)
    websocket_api.async_register_command(hass, ws_config)
    websocket_api.async_register_command(hass, ws_entities)
    websocket_api.async_register_command(hass, ws_sounds)
    websocket_api.async_register_command(hass, ws_sound_delete)


def _spots(hass: HomeAssistant) -> list[SpotRuntime]:
    return [
        e.runtime_data for e in hass.config_entries.async_entries(DOMAIN) if e.state is ConfigEntryState.LOADED
    ]


def _spot(hass: HomeAssistant, entry_id: str) -> SpotRuntime | None:
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        return None
    return entry.runtime_data


@websocket_api.websocket_command({vol.Required("type"): "dusk_dawn/spots"})
@callback
def ws_spots(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    connection.send_result(msg["id"], {"spots": [rt.spot_info() for rt in _spots(hass)]})


@websocket_api.websocket_command({vol.Required("type"): "dusk_dawn/subscribe"})
@callback
def ws_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Send ``{entry_id, state}`` whenever a spot changes (debounced per spot)."""
    msg_id = msg["id"]
    pending: dict[str, Any] = {}  # entry_id -> TimerHandle

    @callback
    def _send(entry_id: str) -> None:
        pending.pop(entry_id, None)
        if (rt := _spot(hass, entry_id)) is not None:
            connection.send_message(websocket_api.event_message(msg_id, {"entry_id": entry_id,
                                                                         "state": rt.snapshot()}))

    @callback
    def _changed(entry_id: str) -> None:
        if entry_id not in pending:
            pending[entry_id] = hass.loop.call_later(DEBOUNCE_S, _send, entry_id)

    unsub = async_dispatcher_connect(hass, SIGNAL_STATE, _changed)

    @callback
    def _unsubscribe() -> None:
        unsub()
        for handle in pending.values():
            handle.cancel()
        pending.clear()

    connection.subscriptions[msg_id] = _unsubscribe
    connection.send_result(msg_id)
    for rt in _spots(hass):  # initial state, so the panel never misses a change
        connection.send_message(websocket_api.event_message(msg_id, {"entry_id": rt.entry_id,
                                                                     "state": rt.snapshot()}))


def _opt_int(value: Any) -> int | None:
    return None if value is None else int(value)


async def _dispatch(rt: SpotRuntime, action: str, msg: dict[str, Any]) -> None:
    if action == "play":
        await rt.async_play(preset=msg.get("preset"), volume=msg.get("volume"),
                            timer=_opt_int(msg["timer"]) if "timer" in msg else -1)
    elif action == "stop":
        await rt.async_stop()
    elif action == "toggle":
        await rt.async_toggle()
    elif action == "set_level":
        await rt.async_set_level(msg["sound"], float(msg["level"]))
    elif action == "set_volume":
        await rt.async_set_volume(float(msg["volume"]))
    elif action == "apply_preset":
        await rt.async_apply_preset(msg["preset_id"])
    elif action == "save_preset":
        await rt.async_save_preset(msg["name"], msg.get("icon"))
    elif action == "delete_preset":
        await rt.async_delete_preset(msg["preset_id"])
    elif action == "set_timer":
        await rt.async_set_timer(_opt_int(msg.get("minutes")))
    elif action == "good_night":
        await rt.async_good_night()
    elif action == "light":
        await rt.async_light(on=msg.get("on"), brightness=_opt_int(msg.get("brightness")),
                             kelvin=_opt_int(msg.get("kelvin")), effect=msg.get("effect"),
                             minutes=msg.get("minutes"))
    elif action == "set_alarm":
        await rt.async_set_alarm(dict(msg["alarm"]))
    elif action == "delete_alarm":
        # "id" is taken by the websocket message id, so the alarm id comes as alarm_id
        alarm_id = msg.get("alarm_id") or (msg.get("alarm") or {}).get("id")
        if not alarm_id:
            raise KeyError("alarm_id")
        await rt.async_delete_alarm(str(alarm_id))
    elif action == "ring":
        await rt.async_ring(msg.get("tone"), msg.get("duration"))
    elif action == "stop_alarm":
        await rt.async_stop_alarm()
    elif action == "preview_tone":
        await rt.async_preview_tone(msg["tone"])
    elif action == "set_source":
        await rt.async_set_source(msg["sound"], msg["mode"])
    elif action == "set_auto":
        await rt.async_set_auto(dict(msg["auto"]))


@websocket_api.websocket_command(
    vol.All(
        # the action's own arguments are extra keys, checked in _dispatch
        vol.Schema(
            {
                vol.Required("type"): "dusk_dawn/command",
                vol.Required("entry_id"): str,
                vol.Required("action"): vol.In(ACTIONS),
            },
            extra=vol.ALLOW_EXTRA,
        )
    )
)
@websocket_api.async_response
async def ws_command(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    rt = _spot(hass, msg["entry_id"])
    if rt is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Unknown spot")
        return
    try:
        await _dispatch(rt, msg["action"], msg)
    except KeyError as err:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, f"Missing field {err}")
        return
    except (SpotError, ValueError, TypeError) as err:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, str(err))
        return
    connection.send_result(msg["id"], {"state": rt.snapshot()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "dusk_dawn/config",
        vol.Required("entry_id"): str,
        vol.Optional("name"): str,
        vol.Optional("speakers"): [str],
        vol.Optional("lights"): [str],
        vol.Optional("presence"): vol.Any(None, str),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_config(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Unknown spot")
        return
    options = {**entry.data, **entry.options}
    for key, conf in (("name", CONF_NAME), ("speakers", CONF_SPEAKERS), ("lights", CONF_LIGHTS),
                      ("presence", CONF_PRESENCE)):
        if key in msg:
            options[conf] = msg[key] or None if key == "presence" else msg[key]
    title = options.get(CONF_NAME) or entry.title
    # the update listener reloads the entry with the new options
    hass.config_entries.async_update_entry(entry, options=options, title=title)
    connection.send_result(msg["id"], {"entry_id": entry.entry_id, "options": options})


@websocket_api.websocket_command({vol.Required("type"): "dusk_dawn/entities"})
@callback
def ws_entities(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    out = []
    for state in hass.states.async_all(("media_player", "light", "binary_sensor")):
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        if state.domain == "binary_sensor" and device_class not in PRESENCE_CLASSES:
            continue
        out.append({
            "entity_id": state.entity_id,
            "name": state.attributes.get(ATTR_FRIENDLY_NAME) or state.entity_id,
            "domain": state.domain,
            "device_class": device_class,
        })
    out.sort(key=lambda e: (e["domain"], e["name"].casefold()))
    connection.send_result(msg["id"], {"entities": out})


@websocket_api.websocket_command({vol.Required("type"): "dusk_dawn/sounds"})
@callback
def ws_sounds(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """The library of own recordings: ``{sound: [{id, name, duration, added}]}``."""
    connection.send_result(msg["id"], {"files": get_library(hass).listing()})


@websocket_api.websocket_command({vol.Required("type"): "dusk_dawn/sound_delete", vol.Required("file_id"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_sound_delete(hass: HomeAssistant, connection: websocket_api.ActiveConnection,
                          msg: dict[str, Any]) -> None:
    library = get_library(hass)
    entry = await hass.async_add_executor_job(library.delete, msg["file_id"])
    if entry is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Unknown file")
        return
    refresh_engines(hass, entry.sound)
    connection.send_result(msg["id"], {"files": library.listing()})
