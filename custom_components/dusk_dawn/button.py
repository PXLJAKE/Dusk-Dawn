"""Buttons: good night, stop alarm."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DuskDawnConfigEntry
from .entity import SpotEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: DuskDawnConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    rt = entry.runtime_data
    async_add_entities([GoodNightButton(rt, "good_night"), StopAlarmButton(rt, "stop_alarm")])


class GoodNightButton(SpotEntity, ButtonEntity):
    _attr_translation_key = "good_night"

    async def async_press(self) -> None:
        await self.rt.async_good_night()


class StopAlarmButton(SpotEntity, ButtonEntity):
    _attr_translation_key = "stop_alarm"

    async def async_press(self) -> None:
        await self.rt.async_stop_alarm()
