"""Alarms with time travel, presence automation, pause on music."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.util import dt as dt_util

from custom_components.dusk_dawn.state import next_ring


def _local(day_offset: int, hh: int, mm: int):
    now = dt_util.now()
    return (now + timedelta(days=day_offset)).replace(hour=hh, minute=mm, second=0, microsecond=0)


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory, when) -> None:
    freezer.move_to(when)
    async_fire_time_changed(hass, when)
    await hass.async_block_till_done()


def test_next_ring_weekdays() -> None:
    tz = dt_util.get_default_time_zone()
    from datetime import datetime  # noqa: PLC0415

    friday_evening = datetime(2026, 11, 13, 22, 0, tzinfo=tz)  # a Friday
    alarm = {"time": "07:00", "days": [0, 1, 2, 3, 4]}
    assert next_ring(alarm, friday_evening) == datetime(2026, 11, 16, 7, 0, tzinfo=tz)  # Monday
    assert next_ring({"time": "07:00", "days": []}, friday_evening) == datetime(2026, 11, 14, 7, 0, tzinfo=tz)


async def test_alarm_with_sunrise_fires(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_spot: MockConfigEntry,
    play_media_calls: list[ServiceCall],
    light_calls: list[ServiceCall],
) -> None:
    rt = setup_spot.runtime_data
    await _tick(hass, freezer, _local(1, 5, 0))
    await rt.async_set_alarm({"time": "07:00", "days": [], "sunrise": True, "sunrise_min": 30,
                              "tone": "bells", "duration_min": 5, "volume": 0.5})
    ring_at = _local(0, 7, 0)
    assert rt.state["next_alarm"] == ring_at.isoformat()
    assert hass.states.get("sensor.bedroom_next_alarm").state == dt_util.as_utc(ring_at).isoformat()

    # nothing before the sunrise window
    await _tick(hass, freezer, _local(0, 6, 29))
    assert light_calls == []

    # sunrise starts 30 minutes before the alarm, very dim and warm
    await _tick(hass, freezer, _local(0, 6, 30))
    assert light_calls, "sunrise did not start"
    first = light_calls[0].data
    assert first["entity_id"] == ["light.bedside"]
    assert first["brightness"] == 1 and first["color_temp_kelvin"] == 2000
    assert rt.state["light"]["effect"] == "sunrise"
    assert rt.state["alarm_ringing"] is False

    # the alarm rings on time and streams to the speakers
    await _tick(hass, freezer, ring_at)
    assert rt.state["alarm_ringing"] is True
    assert hass.states.get("binary_sensor.bedroom_alarm_ringing").state == "on"
    assert play_media_calls and play_media_calls[-1].data["entity_id"] == ["media_player.bedroom"]
    assert rt.engine.alarm_ringing
    # a one-off alarm (no weekdays) disables itself after ringing
    assert rt.state["alarms"][0]["enabled"] is False
    assert rt.state["next_alarm"] is None

    # stops by itself after duration_min
    await _tick(hass, freezer, ring_at + timedelta(minutes=5, seconds=1))
    assert rt.state["alarm_ringing"] is False
    rt.lights_ctl.cancel_effect()


async def test_alarms_disabled(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_spot: MockConfigEntry
) -> None:
    rt = setup_spot.runtime_data
    await _tick(hass, freezer, _local(1, 5, 0))
    await rt.async_set_alarm({"time": "07:00", "days": [], "sunrise": False})
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.bedroom_alarms"}, blocking=True)
    assert rt.state["next_alarm"] is None
    await _tick(hass, freezer, _local(0, 7, 0))
    assert rt.state["alarm_ringing"] is False


async def test_presence_start_and_stop(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_spot: MockConfigEntry,
    play_media_calls: list[ServiceCall],
) -> None:
    rt = setup_spot.runtime_data
    hass.states.async_set("binary_sensor.bedroom_presence", "off")
    await hass.async_block_till_done()
    await rt.async_set_auto({"presence_start": True, "presence_from": "21:00", "presence_to": "02:00",
                             "presence_stop_min": 15, "presence_min": 10})

    # outside the window: nothing happens, even after 10 minutes
    await _tick(hass, freezer, _local(1, 18, 0))
    hass.states.async_set("binary_sensor.bedroom_presence", "on")
    await hass.async_block_till_done()
    await _tick(hass, freezer, _local(0, 18, 15))
    assert rt.state["playing"] is False
    hass.states.async_set("binary_sensor.bedroom_presence", "off")
    await hass.async_block_till_done()

    # inside the window (after midnight, the window wraps): nothing at first ...
    await _tick(hass, freezer, _local(0, 0, 30))
    hass.states.async_set("binary_sensor.bedroom_presence", "on")
    await hass.async_block_till_done()
    assert rt.state["playing"] is False
    await _tick(hass, freezer, _local(0, 0, 38))
    assert rt.state["playing"] is False
    # ... and good night after 10 minutes of presence in a row
    await _tick(hass, freezer, _local(0, 0, 41))
    assert rt.state["playing"] is True
    assert play_media_calls

    # gone for 15 minutes: stop
    hass.states.async_set("binary_sensor.bedroom_presence", "off")
    await hass.async_block_till_done()
    await _tick(hass, freezer, _local(0, 0, 50))
    assert rt.state["playing"] is True
    await _tick(hass, freezer, _local(0, 0, 57))
    assert rt.state["playing"] is False


async def test_presence_flicker_does_not_start(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_spot: MockConfigEntry
) -> None:
    rt = setup_spot.runtime_data
    hass.states.async_set("binary_sensor.bedroom_presence", "off")
    await hass.async_block_till_done()
    await rt.async_set_auto({"presence_start": True, "presence_from": "21:00", "presence_to": "02:00"})
    await _tick(hass, freezer, _local(1, 23, 0))
    hass.states.async_set("binary_sensor.bedroom_presence", "on")
    await hass.async_block_till_done()
    await _tick(hass, freezer, _local(0, 23, 6))
    hass.states.async_set("binary_sensor.bedroom_presence", "unavailable")  # sensor dropout
    await hass.async_block_till_done()
    await _tick(hass, freezer, _local(0, 23, 7))
    hass.states.async_set("binary_sensor.bedroom_presence", "on")  # does not count as arriving for 10 min
    await hass.async_block_till_done()
    await _tick(hass, freezer, _local(0, 23, 14))
    assert rt.state["playing"] is False
    await _tick(hass, freezer, _local(0, 23, 18))
    assert rt.state["playing"] is True


async def test_presence_waits_for_the_window_and_starts_once(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_spot: MockConfigEntry
) -> None:
    rt = setup_spot.runtime_data
    hass.states.async_set("binary_sensor.bedroom_presence", "off")
    await hass.async_block_till_done()
    await rt.async_set_auto({"presence_start": True, "presence_from": "21:00", "presence_to": "02:00"})
    await _tick(hass, freezer, _local(1, 20, 0))
    hass.states.async_set("binary_sensor.bedroom_presence", "on")
    await hass.async_block_till_done()
    await _tick(hass, freezer, _local(0, 20, 30))
    assert rt.state["playing"] is False  # window not open yet
    await _tick(hass, freezer, _local(0, 21, 0))  # window opens: somebody has been there for a while
    assert rt.state["playing"] is True
    await rt.async_stop()
    await _tick(hass, freezer, _local(0, 22, 0))
    assert rt.state["playing"] is False  # stopped by hand: not restarted during the same stay


async def test_window_mode_starts_and_stops_by_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_spot: MockConfigEntry
) -> None:
    rt = setup_spot.runtime_data
    await _tick(hass, freezer, _local(1, 20, 0))
    await rt.async_set_auto({"presence_start": True, "presence_mode": "window",
                             "presence_from": "21:00", "presence_to": "23:30"})
    await _tick(hass, freezer, _local(0, 20, 59))
    assert rt.state["playing"] is False
    await _tick(hass, freezer, _local(0, 21, 0))  # nobody needs to be there
    assert rt.state["playing"] is True
    await _tick(hass, freezer, _local(0, 23, 30))
    assert rt.state["playing"] is False


async def test_good_night_keeps_a_switched_off_timer_off(hass: HomeAssistant, setup_spot: MockConfigEntry) -> None:
    rt = setup_spot.runtime_data
    await rt.async_set_timer(None)
    await rt.async_good_night()
    assert rt.state["playing"] is True and rt.state["timer"]["minutes"] is None
    assert rt.state["timer"]["ends_at"] is None


async def test_pause_on_music(hass: HomeAssistant, setup_spot: MockConfigEntry) -> None:
    rt = setup_spot.runtime_data
    await rt.async_play()
    hass.states.async_set("media_player.kitchen", "playing")
    await hass.async_block_till_done()
    assert rt.state["playing"] is True  # default off

    hass.states.async_set("media_player.kitchen", "idle")
    await rt.async_set_auto({"pause_on_music": True})
    # our own speakers starting to play do not count
    hass.states.async_set("media_player.bedroom", "playing")
    await hass.async_block_till_done()
    assert rt.state["playing"] is True
    hass.states.async_set("media_player.kitchen", "playing")
    await hass.async_block_till_done()
    assert rt.state["playing"] is False


async def test_diy_lamp_keeps_and_rings_the_alarms_itself(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    play_media_calls: list[ServiceCall],
    light_calls: list[ServiceCall],
) -> None:
    """With a DIY lamp the alarm list goes to the lamp (retained MQTT) and Home Assistant stays quiet."""
    from unittest.mock import AsyncMock, patch  # noqa: PLC0415

    from homeassistant.core_config import async_process_ha_core_config  # noqa: PLC0415

    from custom_components.dusk_dawn.const import DOMAIN  # noqa: PLC0415
    from custom_components.dusk_dawn.diy import DiyLamp  # noqa: PLC0415

    entry = MockConfigEntry(
        domain=DOMAIN, title="Lamp",
        data={"name": "Lamp", "speakers": [], "lights": [], "presence": None, "diy_device": "sleepgen"},
    )
    await async_process_ha_core_config(hass, {"internal_url": "http://ha.local:8123"})
    entry.add_to_hass(hass)
    with (
        patch.object(DiyLamp, "async_start", AsyncMock()),
        patch.object(DiyLamp, "set_alarms", AsyncMock()) as set_alarms,
        patch.object(DiyLamp, "ring", AsyncMock()) as ring,
        patch.object(DiyLamp, "effect", AsyncMock()) as effect,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        rt = entry.runtime_data
        await _tick(hass, freezer, _local(1, 5, 0))
        await rt.async_set_alarm({"time": "07:00", "days": [], "sunrise": True, "sunrise_min": 30})
        assert set_alarms.await_args.args[0][0]["time"] == "07:00"
        assert set_alarms.await_args.args[1] is True
        assert rt.state["next_alarm"] == _local(0, 7, 0).isoformat()  # still shown in Home Assistant

        await _tick(hass, freezer, _local(0, 6, 30))
        await _tick(hass, freezer, _local(0, 7, 0))
        assert not ring.await_count and not effect.await_count  # the lamp does this, not Home Assistant

        # the lamp reports that its one-off alarm rang and switched itself off
        alarm_id = rt.state["alarms"][0]["id"]
        rt._diy_alarms({"enabled": True, "alarms": [{"id": alarm_id, "enabled": False}]})
        assert rt.state["alarms"][0]["enabled"] is False
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
