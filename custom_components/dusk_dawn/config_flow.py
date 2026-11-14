"""Config and options flow: one entry per spot."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
)

from .const import CONF_DIY_DEVICE, CONF_LIGHTS, CONF_PRESENCE, CONF_SPEAKERS, DOMAIN


def spot_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME): TextSelector(),
            vol.Optional(CONF_SPEAKERS, default=[]): EntitySelector(
                EntitySelectorConfig(domain="media_player", multiple=True)
            ),
            vol.Optional(CONF_LIGHTS, default=[]): EntitySelector(EntitySelectorConfig(domain="light", multiple=True)),
            vol.Optional(CONF_PRESENCE): EntitySelector(
                EntitySelectorConfig(domain="binary_sensor", device_class=["occupancy", "motion", "presence"])
            ),
            vol.Optional(CONF_DIY_DEVICE): TextSelector(),
        }
    )


def clean(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalise form input to the entry data format of the contract."""
    return {
        CONF_NAME: str(user_input[CONF_NAME]).strip(),
        CONF_SPEAKERS: list(user_input.get(CONF_SPEAKERS) or []),
        CONF_LIGHTS: list(user_input.get(CONF_LIGHTS) or []),
        CONF_PRESENCE: user_input.get(CONF_PRESENCE) or None,
        CONF_DIY_DEVICE: (user_input.get(CONF_DIY_DEVICE) or "").strip() or None,
    }


class DuskDawnConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = clean(user_input)
            if not data[CONF_NAME]:
                errors[CONF_NAME] = "name_required"
            else:
                self._async_abort_entries_match({CONF_NAME: data[CONF_NAME]})
                return self.async_create_entry(title=data[CONF_NAME], data=data)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(spot_schema(), user_input or {CONF_NAME: "Schlafzimmer"}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return DuskDawnOptionsFlow()


class DuskDawnOptionsFlow(OptionsFlow):
    """Same fields as the user step; the entry reloads afterwards."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            data = clean(user_input)
            if not data[CONF_NAME]:
                errors[CONF_NAME] = "name_required"
            else:
                # the entry title follows the name on the next setup (see __init__.py)
                return self.async_create_entry(data=data)
        suggested = user_input or {k: v for k, v in current.items() if v is not None}
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(spot_schema(), suggested),
            errors=errors,
        )
