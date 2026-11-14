"""Service actions (domain dusk_dawn), targeted at spot devices or entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr, entity_registry as er

from .const import (
    ALARM_TONES,
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DURATION,
    ATTR_PRESET,
    ATTR_TIMER,
    ATTR_TONE,
    ATTR_VOLUME,
    DOMAIN,
    SERVICE_GOOD_NIGHT,
    SERVICE_PLAY,
    SERVICE_RING,
    SERVICE_STOP,
    SERVICE_STOP_ALARM,
)
from .runtime import SpotError

if TYPE_CHECKING:
    from .runtime import SpotRuntime

TARGET = {
    vol.Optional(ATTR_CONFIG_ENTRY_ID): vol.Any(cv.string, [cv.string]),
    vol.Optional(ATTR_DEVICE_ID): vol.Any(cv.string, [cv.string]),
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional("area_id"): vol.Any(cv.string, [cv.string]),
    vol.Optional("floor_id"): vol.Any(cv.string, [cv.string]),
    vol.Optional("label_id"): vol.Any(cv.string, [cv.string]),
}

SCHEMAS = {
    SERVICE_PLAY: vol.Schema({
        **TARGET,
        vol.Optional(ATTR_PRESET): cv.string,
        vol.Optional(ATTR_VOLUME): vol.All(vol.Coerce(float), vol.Range(0, 1)),
        vol.Optional(ATTR_TIMER): vol.All(vol.Coerce(int), vol.Range(0, 600)),
    }),
    SERVICE_STOP: vol.Schema(TARGET),
    SERVICE_GOOD_NIGHT: vol.Schema(TARGET),
    SERVICE_RING: vol.Schema({
        **TARGET,
        vol.Optional(ATTR_TONE): vol.In(ALARM_TONES),
        vol.Optional(ATTR_DURATION): vol.All(vol.Coerce(float), vol.Range(0.1, 120)),
    }),
    SERVICE_STOP_ALARM: vol.Schema(TARGET),
}


def _as_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def resolve_spots(hass: HomeAssistant, call: ServiceCall) -> list[SpotRuntime]:
    """Spots referenced by config entry, device or entity; all spots if none given."""
    loaded = {
        e.entry_id: e for e in hass.config_entries.async_entries(DOMAIN) if e.state is ConfigEntryState.LOADED
    }
    ids: set[str] = set(_as_list(call.data.get(ATTR_CONFIG_ENTRY_ID)))
    dev_reg, ent_reg = dr.async_get(hass), er.async_get(hass)
    for device_id in _as_list(call.data.get(ATTR_DEVICE_ID)):
        if device := dev_reg.async_get(device_id):
            ids.update(device.config_entries)
    for entity_id in _as_list(call.data.get(ATTR_ENTITY_ID)):
        if (ent := ent_reg.async_get(entity_id)) and ent.config_entry_id:
            ids.add(ent.config_entry_id)
    targeted = any(call.data.get(k) for k in (ATTR_CONFIG_ENTRY_ID, ATTR_DEVICE_ID, ATTR_ENTITY_ID))
    if not targeted:
        return [e.runtime_data for e in loaded.values()]
    spots = [loaded[i].runtime_data for i in ids if i in loaded]
    if not spots:
        raise ServiceValidationError("No Dusk & Dawn spot found for this target")
    return spots


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    async def handle(call: ServiceCall) -> None:
        for rt in resolve_spots(hass, call):
            try:
                if call.service == SERVICE_PLAY:
                    timer = call.data.get(ATTR_TIMER, -1)
                    await rt.async_play(call.data.get(ATTR_PRESET), call.data.get(ATTR_VOLUME), timer)
                elif call.service == SERVICE_STOP:
                    await rt.async_stop()
                elif call.service == SERVICE_GOOD_NIGHT:
                    await rt.async_good_night()
                elif call.service == SERVICE_RING:
                    await rt.async_ring(call.data.get(ATTR_TONE), call.data.get(ATTR_DURATION))
                elif call.service == SERVICE_STOP_ALARM:
                    await rt.async_stop_alarm()
            except SpotError as err:
                raise ServiceValidationError(str(err)) from err

    for service, schema in SCHEMAS.items():
        hass.services.async_register(DOMAIN, service, handle, schema=schema)
