"""Bridge to a DIY Soundlampe (device/sleepgen) over its existing MQTT topics.

The lamp renders sound and light effects itself, so nothing is streamed.
Topics (see device/sleepgen/mqtt_ha.py), base ``sleepgen/<device_id>``:

    sound/set ON|OFF          master/set 0..100        layer/<sound>/set 0..100
    timer/set "Aus"|"N min"   lamp/set <HA JSON light command>
    alarm/set ON|OFF          alarm_tone/set <German name>
    alarm_minutes/set N       alarm_volume/set 0..100
    state  (JSON, retained)   playing / alarm_ringing / ...
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant, callback

from .const import DIY_BASE_TOPIC, DIY_EFFECTS, DIY_TIMER_OPTIONS, DIY_TONES, SOUNDS

_LOGGER = logging.getLogger(__name__)


def diy_timer_option(minutes: int | None) -> str:
    """Closest timer option the lamp knows (it has a fixed list)."""
    if not minutes:
        return "Aus"
    best = min(DIY_TIMER_OPTIONS, key=lambda m: abs(m - minutes))
    return f"{best} min"


class DiyLamp:
    """Sends commands to and mirrors state from one DIY Soundlampe."""

    def __init__(self, hass: HomeAssistant, device_id: str, on_state: Callable[[dict[str, Any]], None]) -> None:
        self.hass = hass
        self.base = DIY_BASE_TOPIC.format(device=device_id)
        self._on_state = on_state
        self._unsub: Callable[[], None] | None = None

    async def async_start(self) -> None:
        """Subscribe to the lamp's state topic (if MQTT is set up)."""
        if "mqtt" not in self.hass.config.components:
            _LOGGER.warning("MQTT is not set up; the DIY lamp %s cannot be controlled", self.base)
            return
        from homeassistant.components import mqtt  # noqa: PLC0415 - optional dependency

        @callback
        def _message(msg: Any) -> None:
            try:
                data = json.loads(msg.payload)
            except (ValueError, TypeError):
                return
            if isinstance(data, dict):
                self._on_state(data)

        self._unsub = await mqtt.async_subscribe(self.hass, f"{self.base}/state", _message)

    @callback
    def async_stop(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    async def _publish(self, sub: str, payload: Any) -> None:
        if "mqtt" not in self.hass.config.components:
            return
        from homeassistant.components import mqtt  # noqa: PLC0415

        if not isinstance(payload, str):
            payload = json.dumps(payload) if isinstance(payload, dict) else str(payload)
        await mqtt.async_publish(self.hass, f"{self.base}/{sub}", payload)

    # ------------------------------------------------------------ sound
    async def play(self, levels: dict[str, float], volume: float, timer_min: int | None) -> None:
        await self.set_levels(levels)
        await self.set_volume(volume)
        await self.set_timer(timer_min)
        await self._publish("sound/set", "ON")

    async def stop(self) -> None:
        await self._publish("sound/set", "OFF")

    async def set_levels(self, levels: dict[str, float]) -> None:
        for sound in SOUNDS:
            await self.set_level(sound, levels.get(sound, 0.0))

    async def set_level(self, sound: str, level: float) -> None:
        await self._publish(f"layer/{sound}/set", round(level * 100))

    async def set_volume(self, volume: float) -> None:
        await self._publish("master/set", round(volume * 100))

    async def set_timer(self, minutes: int | None) -> None:
        await self._publish("timer/set", diy_timer_option(minutes))

    # ------------------------------------------------------------ alarm
    async def ring(self, tone: str, minutes: float, volume: float) -> None:
        await self._publish("alarm_tone/set", DIY_TONES.get(tone, "Glocken"))
        await self._publish("alarm_minutes/set", max(1, round(minutes)))
        await self._publish("alarm_volume/set", round(volume * 100))
        await self._publish("alarm/set", "ON")

    async def stop_alarm(self) -> None:
        await self._publish("alarm/set", "OFF")

    # ------------------------------------------------------------ light
    async def light(self, on: bool, brightness: int | None = None, kelvin: int | None = None) -> None:
        cmd: dict[str, Any] = {"state": "ON" if on else "OFF"}
        if on and brightness is not None:
            cmd["brightness"] = brightness
        if on and kelvin is not None:
            cmd["color_temp_kelvin"] = kelvin
        await self._publish("lamp/set", cmd)

    async def effect(self, effect: str, minutes: float | None = None) -> None:
        cmd: dict[str, Any] = {"state": "ON", "effect": DIY_EFFECTS[effect]}
        if minutes:
            cmd["transition"] = round(minutes * 60)
        await self._publish("lamp/set", cmd)
