"""Websocket API (contract section 4)."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from homeassistant.core import HomeAssistant, ServiceCall


async def test_spots(hass: HomeAssistant, setup_spot: MockConfigEntry, hass_ws_client: WebSocketGenerator) -> None:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "dusk_dawn/spots"})
    msg = await client.receive_json()
    assert msg["success"]
    (spot,) = msg["result"]["spots"]
    assert spot["entry_id"] == setup_spot.entry_id
    assert spot["name"] == "Bedroom"
    assert spot["speakers"] == ["media_player.bedroom"]
    assert spot["lights"] == ["light.bedside"]
    assert spot["presence"] == "binary_sensor.bedroom_presence"
    assert spot["diy_device"] is None
    state = spot["state"]
    for key in ("playing", "preset", "levels", "volume", "timer", "light", "alarms", "auto", "presets",
                "alarm_ringing", "next_alarm"):
        assert key in state
    assert len(state["presets"]) == 7
    assert all(p["builtin"] and p["icon"].startswith("mdi:") for p in state["presets"])


async def test_commands(
    hass: HomeAssistant,
    setup_spot: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    play_media_calls: list[ServiceCall],
    light_calls: list[ServiceCall],
) -> None:
    client = await hass_ws_client(hass)
    entry_id = setup_spot.entry_id

    async def cmd(action: str, **kwargs):
        await client.send_json_auto_id({"type": "dusk_dawn/command", "entry_id": entry_id, "action": action,
                                        **kwargs})
        return await client.receive_json()

    msg = await cmd("play", preset="meer")
    assert msg["success"], msg
    assert msg["result"]["state"]["playing"] is True
    assert msg["result"]["state"]["preset"] == "meer"
    assert len(play_media_calls) == 1

    msg = await cmd("set_level", sound="rain", level=0.5)
    assert msg["result"]["state"]["levels"]["rain"] == 0.5
    assert msg["result"]["state"]["preset"] is None

    msg = await cmd("save_preset", name="Mix", icon="mdi:star")
    preset_id = msg["result"]["state"]["preset"]
    assert preset_id.startswith("user_")
    assert msg["result"]["state"]["presets"][-1]["builtin"] is False
    msg = await cmd("apply_preset", preset_id="regen")
    assert msg["result"]["state"]["levels"]["waves"] == 0.0
    msg = await cmd("delete_preset", preset_id=preset_id)
    assert all(p["id"] != preset_id for p in msg["result"]["state"]["presets"])
    msg = await cmd("delete_preset", preset_id="regen")
    assert not msg["success"]

    msg = await cmd("set_volume", volume=0.7)
    assert msg["result"]["state"]["volume"] == 0.7
    msg = await cmd("set_timer", minutes=30)
    assert msg["result"]["state"]["timer"]["minutes"] == 30
    assert msg["result"]["state"]["timer"]["ends_at"]
    msg = await cmd("set_timer", minutes=None)
    assert msg["result"]["state"]["timer"] == {"minutes": None, "ends_at": None}

    msg = await cmd("light", on=True, brightness=100, kelvin=2400)
    assert msg["result"]["state"]["light"]["on"] is True
    assert light_calls[-1].data["brightness"] == 100
    assert light_calls[-1].data["color_temp_kelvin"] == 2400
    msg = await cmd("light", effect="candle")
    assert msg["result"]["state"]["light"]["effect"] == "candle"
    msg = await cmd("light", on=False)
    assert msg["result"]["state"]["light"]["effect"] is None

    msg = await cmd("set_alarm", alarm={"time": "06:30", "days": [0, 1, 2, 3, 4], "tone": "birds"})
    (alarm,) = msg["result"]["state"]["alarms"]
    assert alarm["time"] == "06:30" and alarm["tone"] == "birds" and alarm["sunrise"] is True
    assert msg["result"]["state"]["next_alarm"]
    msg = await cmd("set_alarm", alarm={"id": alarm["id"], "enabled": False})
    assert msg["result"]["state"]["alarms"][0]["enabled"] is False
    assert msg["result"]["state"]["next_alarm"] is None
    msg = await cmd("set_alarm", alarm={"id": "client-made", "time": "08:00"})
    assert [a["id"] for a in msg["result"]["state"]["alarms"]] == [alarm["id"], "client-made"]
    msg = await cmd("delete_alarm", alarm_id="client-made")
    msg = await cmd("set_alarm", alarm={"time": "25:00"})
    assert not msg["success"]
    msg = await cmd("delete_alarm", alarm_id=alarm["id"])
    assert msg["result"]["state"]["alarms"] == []

    msg = await cmd("ring", tone="classic")
    assert msg["result"]["state"]["alarm_ringing"] is True
    msg = await cmd("stop_alarm")
    assert msg["result"]["state"]["alarm_ringing"] is False
    msg = await cmd("preview_tone", tone="bells")
    assert msg["success"]

    msg = await cmd("set_auto", auto={"presence_start": True, "presence_from": "21:00"})
    assert msg["result"]["state"]["auto"]["presence_start"] is True
    assert msg["result"]["state"]["auto"]["presence_from"] == "21:00"
    msg = await cmd("set_auto", auto={"bogus": 1})
    assert not msg["success"]

    msg = await cmd("toggle")
    assert msg["result"]["state"]["playing"] is False
    msg = await cmd("good_night")
    assert msg["result"]["state"]["playing"] is True
    assert msg["result"]["state"]["timer"]["minutes"] is None  # a switched-off sleep timer stays off

    await client.send_json_auto_id({"type": "dusk_dawn/command", "entry_id": "nope", "action": "stop"})
    msg = await client.receive_json()
    assert not msg["success"] and msg["error"]["code"] == "not_found"


async def test_subscribe(hass: HomeAssistant, setup_spot: MockConfigEntry, hass_ws_client: WebSocketGenerator) -> None:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "dusk_dawn/subscribe"})
    msg = await client.receive_json()
    assert msg["success"]
    initial = await client.receive_json()
    assert initial["event"]["entry_id"] == setup_spot.entry_id

    rt = setup_spot.runtime_data
    # several quick changes are debounced into one event
    await rt.async_set_level("wind", 0.2)
    await rt.async_set_level("wind", 0.3)
    event = await client.receive_json()
    assert event["type"] == "event"
    assert event["event"]["entry_id"] == setup_spot.entry_id
    assert event["event"]["state"]["levels"]["wind"] == 0.3


async def test_entities_and_config(
    hass: HomeAssistant, setup_spot: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    hass.states.async_set("media_player.kitchen", "idle", {"friendly_name": "Kitchen"})
    hass.states.async_set("binary_sensor.hall_motion", "off", {"device_class": "motion"})
    hass.states.async_set("binary_sensor.door", "off", {"device_class": "door"})
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "dusk_dawn/entities"})
    msg = await client.receive_json()
    ids = {e["entity_id"]: e for e in msg["result"]["entities"]}
    assert ids["media_player.kitchen"] == {"entity_id": "media_player.kitchen", "name": "Kitchen",
                                           "domain": "media_player", "device_class": None}
    assert "binary_sensor.hall_motion" in ids
    assert "binary_sensor.door" not in ids

    await client.send_json_auto_id({"type": "dusk_dawn/config", "entry_id": setup_spot.entry_id,
                                    "name": "Kids", "speakers": ["media_player.kitchen"]})
    msg = await client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()
    assert setup_spot.title == "Kids"
    assert setup_spot.runtime_data.speakers == ["media_player.kitchen"]
