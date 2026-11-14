"""Binary sensor: alarm ringing."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DuskDawnConfigEntry
from .entity import SpotEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: DuskDawnConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([AlarmRingingSensor(entry.runtime_data, "alarm_ringing")])


class AlarmRingingSensor(SpotEntity, BinarySensorEntity):
    _attr_translation_key = "alarm_ringing"
    _attr_device_class = BinarySensorDeviceClass.SOUND

    @property
    def is_on(self) -> bool:
        return self.rt.state["alarm_ringing"]
