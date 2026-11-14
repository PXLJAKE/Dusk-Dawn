"""Numbers: master volume and one level per sound."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DuskDawnConfigEntry
from .const import DEFAULT_ENABLED_LEVELS, SOUNDS
from .entity import SpotEntity
from .runtime import SpotRuntime


async def async_setup_entry(
    hass: HomeAssistant, entry: DuskDawnConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    rt = entry.runtime_data
    entities: list[NumberEntity] = [VolumeNumber(rt, "volume")]
    entities += [LevelNumber(rt, sound) for sound in SOUNDS]
    async_add_entities(entities)


class _PercentNumber(SpotEntity, NumberEntity):
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER


class VolumeNumber(_PercentNumber):
    _attr_translation_key = "volume"

    @property
    def native_value(self) -> float:
        return round(self.rt.state["volume"] * 100)

    async def async_set_native_value(self, value: float) -> None:
        await self.rt.async_set_volume(value / 100)


class LevelNumber(_PercentNumber):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, runtime: SpotRuntime, sound: str) -> None:
        super().__init__(runtime, f"level_{sound}")
        self.sound = sound
        self._attr_translation_key = f"level_{sound}"
        self._attr_entity_registry_enabled_default = sound in DEFAULT_ENABLED_LEVELS

    @property
    def native_value(self) -> float:
        return round(self.rt.state["levels"][self.sound] * 100)

    async def async_set_native_value(self, value: float) -> None:
        await self.rt.async_set_level(self.sound, value / 100)
