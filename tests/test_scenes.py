"""Scenes: own scenes with light, editable suggestions, order, start scene."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.dusk_dawn.const import BUILTIN_PRESETS
from custom_components.dusk_dawn.lights import gradient_point, hex_to_rgb
from custom_components.dusk_dawn.state import merge_presets, merge_stored, normalize_scene


def test_normalize_scene():
    s = normalize_scene({"name": "  Abend ", "levels": {"rain": 0.5, "fire": 0.4, "own_ab12": 0.3, "wind": 0},
                         "volume": 0.3, "timer": "keep",
                         "light": {"mode": "gradient", "color": "#FF0000", "to_color": "bad", "to_brightness": 0}})
    assert s["name"] == "Abend"
    assert s["levels"] == {"rain": 0.5, "own_ab12": 0.3}
    assert s["timer"] == "keep" and s["volume"] == 0.3
    assert s["light"]["color"] == "#ff0000" and s["light"]["to_color"] == "#3b1f6e" and s["light"]["minutes"] == 30
    assert normalize_scene({"light": {"mode": "keep"}})["light"] is None
    assert normalize_scene({"timer": None})["timer"] is None


def test_merge_presets_order_edit_hide():
    stored = [
        {"id": "meer"},
        {"id": "user_1", "name": "Mine", "levels": {"rain": 0.4}},
        {"id": "regen", "edited": True, "name": "Mein Regen", "levels": {"rain": 0.2}},
        {"id": "user_bad"},  # no name: dropped
    ]
    out = merge_presets(stored, hidden=["gute_nacht"])
    ids = [p["id"] for p in out]
    assert ids[0] == "user_1"  # own scenes first
    assert ids[1:3] == ["meer", "regen"]  # stored order of the suggestions kept
    assert "gute_nacht" not in ids and "ventilator" in ids  # hidden one gone, missing ones appended
    regen = next(p for p in out if p["id"] == "regen")
    assert regen["name"] == "Mein Regen" and regen["builtin"] and regen["levels"] == {"rain": 0.2}
    assert len(out) == len(BUILTIN_PRESETS)  # 7 suggestions + 1 own


def test_gradient_point():
    assert gradient_point(0, (255, 0, 0), 200, (0, 0, 255), 0) == ((255, 0, 0), 200)
    assert gradient_point(0.5, (255, 0, 0), 200, (0, 0, 255), 0) == ((128, 0, 128), 100)
    assert hex_to_rgb("#3b1f6e") == (59, 31, 110)


async def test_scene_flow(hass: HomeAssistant, setup_spot, light_calls) -> None:
    rt = setup_spot.runtime_data
    lights = light_calls

    await rt.async_set_level("rain", 0.6)
    pid = await rt.async_save_preset("Rot", "mdi:star", volume=0.2, timer=30,
                                     light={"mode": "color", "color": "#ff0000", "brightness": 50})
    assert rt.presets[0]["id"] == pid
    await rt.async_stop()
    await rt.async_activate_scene(pid)
    await hass.async_block_till_done()
    assert rt.state["playing"] and rt.state["volume"] == 0.2 and rt.state["timer"]["minutes"] == 30
    assert lights[-1].data["rgb_color"] == [255, 0, 0] and lights[-1].data["brightness"] == 128

    # edit a suggestion, move it, start scene
    await rt.async_update_preset("meer", {"timer": None, "light": {"mode": "white", "kelvin": 3000,
                                                                     "brightness": 10}})
    meer = next(p for p in rt.presets if p["id"] == "meer")
    assert meer["edited"] and meer["timer"] is None and meer["light"]["mode"] == "white"
    await rt.async_reorder_presets(["meer", "regen", pid])
    assert [p["id"] for p in rt.presets][:3] == [pid, "meer", "regen"]  # own stays on top
    stored = merge_stored(rt._stored())
    assert [p["id"] for p in stored["presets"]][:3] == [pid, "meer", "regen"]
    assert stored["presets"][1]["light"]["kelvin"] == 3000

    await rt.async_set_auto({"start_scene": "meer"})
    await rt.async_good_night()
    await hass.async_block_till_done()
    assert rt.state["preset"] == "meer" and rt.state["timer"]["minutes"] is None
    assert lights[-1].data["color_temp_kelvin"] == 3000

    await rt.async_restore_presets()
    meer = next(p for p in rt.presets if p["id"] == "meer")
    assert not meer.get("edited") and "light" not in meer
    assert rt.presets[0]["id"] == pid
