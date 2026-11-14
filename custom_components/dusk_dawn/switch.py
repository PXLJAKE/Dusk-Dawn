"""Switches: sound on/off, alarms enabled."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DuskDawnConfigEntry
from .entity import SpotEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: DuskDawnConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    rt = entry.runtime_data
    async_add_entities([SoundSwitch(rt, "sound"), AlarmsEnabledSwitch(rt, "alarms_enabled")])


class SoundSwitch(SpotEntity, SwitchEntity):
    _attr_translation_key = "sound"

    @property
    def is_on(self) -> bool:
        return self.rt.state["playing"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.rt.async_play()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.rt.async_stop()


class AlarmsEnabledSwitch(SpotEntity, SwitchEntity):
    _attr_translation_key = "alarms_enabled"

    @property
    def is_on(self) -> bool:
        return self.rt.state["alarms_enabled"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.rt.async_set_alarms_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.rt.async_set_alarms_enabled(False)
