"""Light control for ordinary Home Assistant lights.

Effects are done with plain ``light.turn_on`` calls so they work with any
light (Hue, Zigbee, WLED, ...):

* sunrise  stepped brightness/colour temperature with long transitions
* fade     dim down to off over the sleep timer
* candle   gentle flicker, at most one command per second

The DIY Soundlampe renders the same effects natively (see ``diy.py``).
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_COLOR_TEMP_KELVIN, ATTR_TRANSITION
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_ON
from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from .runtime import SpotRuntime

_LOGGER = logging.getLogger(__name__)

LIGHT_DOMAIN = "light"
MIN_STEP_S = 20.0  # sunrise/fade: one command every >= 20 s
MAX_STEPS = 90
CANDLE_INTERVAL_S = 1.5


def sunrise_point(p: float) -> tuple[int, int]:
    """Brightness (1..255) and colour temperature for sunrise progress ``p``.

    Same curve as the DIY lamp (device/sleepgen/light.py): a faint warm glow
    that slowly grows into bright neutral white.
    """
    p = min(max(p, 0.0), 1.0)
    brightness = max(1, round(255 * (0.004 + 0.996 * p**2.2)))
    kelvin = round(2000 + 2000 * p**0.8)
    return brightness, kelvin


class LightController:
    """Drives the lights of one spot; one effect at a time."""

    def __init__(self, hass: HomeAssistant, runtime: SpotRuntime) -> None:
        self.hass = hass
        self.runtime = runtime
        self._task: asyncio.Task[None] | None = None

    @property
    def lights(self) -> list[str]:
        return self.runtime.lights

    # ------------------------------------------------------------ primitives
    async def _call(self, service: str, data: dict[str, Any]) -> None:
        if not self.lights:
            return
        try:
            await self.hass.services.async_call(
                LIGHT_DOMAIN, service, {ATTR_ENTITY_ID: self.lights, **data}, blocking=False
            )
        except Exception as err:  # noqa: BLE001 - a missing light must not break the spot
            _LOGGER.warning("light.%s failed for %s: %s", service, self.lights, err)

    async def _on(self, brightness: int, kelvin: int | None = None, transition: float | None = None) -> None:
        data: dict[str, Any] = {ATTR_BRIGHTNESS: int(min(max(brightness, 1), 255))}
        if kelvin:
            data[ATTR_COLOR_TEMP_KELVIN] = int(kelvin)
        if transition is not None:
            data[ATTR_TRANSITION] = round(transition, 1)
        await self._call(SERVICE_TURN_ON, data)

    async def _off(self, transition: float | None = None) -> None:
        await self._call(SERVICE_TURN_OFF, {ATTR_TRANSITION: round(transition, 1)} if transition else {})

    def current_brightness(self) -> int | None:
        """Brightness of the first light that is on, if any."""
        for entity_id in self.lights:
            state = self.hass.states.get(entity_id)
            if state and state.state == STATE_ON:
                return state.attributes.get(ATTR_BRIGHTNESS) or 255
        return None

    def any_on(self) -> bool:
        return self.current_brightness() is not None

    # ------------------------------------------------------------ effects
    def cancel_effect(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None

    def _run(self, coro: Any, name: str) -> None:
        self.cancel_effect()
        self._task = self.runtime.entry.async_create_background_task(self.hass, coro, f"dusk_dawn {name}")

    async def async_set(self, on: bool | None, brightness: int | None, kelvin: int | None) -> None:
        """Plain on/off/brightness/kelvin; ends any running effect."""
        self.cancel_effect()
        light = self.runtime.state["light"]
        if brightness is not None:
            light["brightness"] = int(min(max(brightness, 1), 255))
        if kelvin is not None:
            light["kelvin"] = int(kelvin)
        if on is None:
            on = True if (brightness is not None or kelvin is not None) else light["on"]
        light["on"], light["effect"] = on, None
        if on:
            await self._on(light["brightness"], light["kelvin"], 1)
        else:
            await self._off(1)

    def start_sunrise(self, minutes: float) -> None:
        self.runtime.state["light"].update(on=True, effect="sunrise")
        self._run(self._sunrise(minutes), "sunrise")

    def start_fade(self, minutes: float) -> None:
        start = self.current_brightness() or self.runtime.state["light"]["brightness"]
        self.runtime.state["light"].update(effect="fade")
        self._run(self._fade(minutes, start), "fade")

    def start_candle(self) -> None:
        self.runtime.state["light"].update(on=True, effect="candle")
        self._run(self._candle(), "candle")

    async def _sunrise(self, minutes: float) -> None:
        total = max(minutes * 60, 1.0)
        steps = int(min(MAX_STEPS, max(1, total // MIN_STEP_S)))
        step_s = total / steps
        bri, kelvin = sunrise_point(0)
        await self._on(bri, kelvin, 0)
        for i in range(1, steps + 1):
            bri, kelvin = sunrise_point(i / steps)
            await self._on(bri, kelvin, step_s)
            await asyncio.sleep(step_s)
        self._effect_done(on=True, brightness=bri, kelvin=kelvin)

    async def _fade(self, minutes: float, start: int) -> None:
        total = max(minutes * 60, 1.0)
        steps = int(min(MAX_STEPS, max(1, total // MIN_STEP_S)))
        step_s = total / steps
        for i in range(1, steps):
            p = i / steps
            await self._on(max(1, round(start * (1 - p) ** 2)), None, step_s)
            await asyncio.sleep(step_s)
        await self._off(step_s)
        await asyncio.sleep(step_s)
        self._effect_done(on=False)

    async def _candle(self) -> None:
        base = self.runtime.state["light"]["brightness"]
        while True:
            flicker = random.uniform(0.55, 1.0)
            await self._on(max(1, round(base * flicker)), round(1900 + 350 * flicker), 1.0)
            await asyncio.sleep(CANDLE_INTERVAL_S + random.uniform(0, 0.8))

    def _effect_done(self, **light: Any) -> None:
        self.runtime.state["light"].update(effect=None, **light)
        self._task = None
        self.runtime.async_changed()
