"""Sensor: next alarm (timestamp)."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import DuskDawnConfigEntry
from .entity import SpotEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: DuskDawnConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([NextAlarmSensor(entry.runtime_data, "next_alarm")])


class NextAlarmSensor(SpotEntity, SensorEntity):
    _attr_translation_key = "next_alarm"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        value = self.rt.state["next_alarm"]
        return dt_util.parse_datetime(value) if value else None
