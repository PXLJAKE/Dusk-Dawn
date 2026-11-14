"""Base entity: one device per spot, pushed updates from the runtime."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, NAME
from .runtime import SpotRuntime


class SpotEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, runtime: SpotRuntime, key: str) -> None:
        self.rt = runtime
        self._attr_unique_id = f"{runtime.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.entry_id)},
            name=runtime.name,
            manufacturer=NAME,
            model="DIY Soundlampe" if runtime.diy else "Sleep spot",
            entry_type=None if runtime.diy else DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.rt.async_add_listener(self.async_write_ha_state))
