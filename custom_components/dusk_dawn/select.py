"""Selects: preset, sleep timer."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DuskDawnConfigEntry
from .const import TIMER_OPTIONS
from .entity import SpotEntity

TIMER_OFF = "off"


def timer_option(minutes: int | None) -> str:
    return str(minutes) if minutes else TIMER_OFF


async def async_setup_entry(
    hass: HomeAssistant, entry: DuskDawnConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    rt = entry.runtime_data
    async_add_entities([PresetSelect(rt, "preset"), TimerSelect(rt, "timer")])


class PresetSelect(SpotEntity, SelectEntity):
    _attr_translation_key = "preset"

    @property
    def options(self) -> list[str]:
        return [p["name"] for p in self.rt.presets]

    @property
    def current_option(self) -> str | None:
        return self.rt.preset_name()

    async def async_select_option(self, option: str) -> None:
        await self.rt.async_apply_preset(option)


class TimerSelect(SpotEntity, SelectEntity):
    _attr_translation_key = "timer"
    _attr_options = [timer_option(m) for m in TIMER_OPTIONS]

    @property
    def current_option(self) -> str:
        option = timer_option(self.rt.state["timer"]["minutes"])
        return option if option in self._attr_options else TIMER_OFF

    async def async_select_option(self, option: str) -> None:
        await self.rt.async_set_timer(None if option == TIMER_OFF else int(option))
