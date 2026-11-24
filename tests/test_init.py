"""Setup, unload, entities, services."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.dusk_dawn.const import DOMAIN, SOUNDS


async def test_setup_and_unload(hass: HomeAssistant, setup_spot: MockConfigEntry) -> None:
    entry = setup_spot
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.stream is not None
    assert "dusk-dawn" in hass.data["frontend_panels"]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert "dusk-dawn" not in hass.data["frontend_panels"]


async def test_entities_created(hass: HomeAssistant, setup_spot: MockConfigEntry) -> None:
    ent_reg = er.async_get(hass)
    entries = er.async_entries_for_config_entry(ent_reg, setup_spot.entry_id)
    by_key = {e.unique_id.removeprefix(f"{setup_spot.entry_id}_"): e for e in entries}
    expected = {
        "sound", "alarms_enabled", "preset", "timer", "volume", "next_alarm_time", "next_alarm",
        "good_night", "stop_alarm", "alarm_ringing", *(f"level_{s}" for s in SOUNDS),
    }
    assert set(by_key) == expected
    assert by_key["sound"].entity_id == "switch.bedroom_sounds"
    assert by_key["level_rain"].disabled_by is None
    assert by_key["level_thunder"].disabled_by is er.RegistryEntryDisabler.INTEGRATION

    device = dr.async_get(hass).async_get_device({(DOMAIN, setup_spot.entry_id)})
    assert device is not None and device.name == "Bedroom"

    assert hass.states.get("switch.bedroom_sounds").state == "off"
    assert hass.states.get("select.bedroom_sleep_timer").state == "off"
    assert hass.states.get("select.bedroom_sound").attributes["options"][0] == "Gute Nacht"
    assert hass.states.get("number.bedroom_volume").state == "50"
    assert hass.states.get("binary_sensor.bedroom_alarm_ringing").state == "off"


async def test_entities_control(
    hass: HomeAssistant, setup_spot: MockConfigEntry, play_media_calls: list[ServiceCall]
) -> None:
    rt = setup_spot.runtime_data
    await hass.services.async_call("select", "select_option",
                                   {"entity_id": "select.bedroom_sound", "option": "Meer"}, blocking=True)
    assert rt.state["preset"] == "meer"
    assert rt.state["levels"]["waves"] == 0.85
    await hass.services.async_call("select", "select_option",
                                   {"entity_id": "select.bedroom_sleep_timer", "option": "30"}, blocking=True)
    assert rt.state["timer"]["minutes"] == 30
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.bedroom_sounds"}, blocking=True)
    assert hass.states.get("switch.bedroom_sounds").state == "on"
    assert rt.state["timer"]["ends_at"] is not None
    assert len(play_media_calls) == 1
    await hass.services.async_call("number", "set_value",
                                   {"entity_id": "number.bedroom_volume", "value": 30}, blocking=True)
    assert rt.state["volume"] == 0.3
    await hass.services.async_call("time", "set_value",
                                   {"entity_id": "time.bedroom_alarm_time", "time": "06:45:00"}, blocking=True)
    assert rt.state["alarms"][0]["time"] == "06:45"
    assert hass.states.get("sensor.bedroom_next_alarm").state not in ("unknown", "unavailable")
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.bedroom_sounds"}, blocking=True)
    assert rt.state["playing"] is False


async def test_services(
    hass: HomeAssistant, setup_spot: MockConfigEntry, play_media_calls: list[ServiceCall]
) -> None:
    rt = setup_spot.runtime_data
    device = dr.async_get(hass).async_get_device({(DOMAIN, setup_spot.entry_id)})
    await hass.services.async_call(DOMAIN, "play", {"device_id": device.id, "preset": "Meer",
                                                    "volume": 0.4, "timer": 15}, blocking=True)
    assert rt.state["playing"] and rt.state["preset"] == "meer"
    assert rt.state["volume"] == 0.4 and rt.state["timer"]["minutes"] == 15
    call = play_media_calls[-1]
    assert call.data["media_content_type"] == "music"
    assert call.data["media_content_id"].startswith(
        f"http://ha.local:8123/api/dusk_dawn/stream/{setup_spot.entry_id}.mp3?token="
    )
    assert call.data["extra"]["title"] == "Dusk & Dawn – Meer"

    await hass.services.async_call(DOMAIN, "ring", {"config_entry_id": setup_spot.entry_id, "tone": "classic"},
                                   blocking=True)
    assert rt.state["alarm_ringing"] is True
    assert hass.states.get("binary_sensor.bedroom_alarm_ringing").state == "on"
    await hass.services.async_call(DOMAIN, "stop_alarm", {}, blocking=True)
    assert rt.state["alarm_ringing"] is False
    await hass.services.async_call(DOMAIN, "stop", {"entity_id": "switch.bedroom_sounds"}, blocking=True)
    assert rt.state["playing"] is False


async def test_state_persisted(hass: HomeAssistant, setup_spot: MockConfigEntry) -> None:
    rt = setup_spot.runtime_data
    await rt.async_set_level("rain", 0.42)
    await rt.async_save_preset("Mine", "mdi:star")
    await hass.config_entries.async_reload(setup_spot.entry_id)
    await hass.async_block_till_done()
    rt = setup_spot.runtime_data
    assert rt.state["levels"]["rain"] == 0.42
    assert rt.state["presets"][0]["name"] == "Mine"
    assert rt.state["playing"] is False
