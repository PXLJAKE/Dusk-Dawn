"""Time: the time of the first alarm."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DuskDawnConfigEntry
from .entity import SpotEntity
from .state import parse_hhmm


async def async_setup_entry(
    hass: HomeAssistant, entry: DuskDawnConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([NextAlarmTime(entry.runtime_data, "next_alarm_time")])


class NextAlarmTime(SpotEntity, TimeEntity):
    """Wake-up time of the first alarm; setting it creates one if needed."""

    _attr_translation_key = "next_alarm_time"

    @property
    def native_value(self) -> time | None:
        alarms = self.rt.state["alarms"]
        return parse_hhmm(alarms[0]["time"]) if alarms else None

    async def async_set_value(self, value: time) -> None:
        alarms = self.rt.state["alarms"]
        data = {"time": value.strftime("%H:%M")}
        if alarms:
            data["id"] = alarms[0]["id"]
        await self.rt.async_set_alarm(data)
